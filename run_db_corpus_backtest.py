import argparse
import json
import os
import io
import time
import pandas as pd
import concurrent.futures
import copy

from modules.per_battle_backtest import build_battles, score_predictions
from modules.engine import _worker_simulate_match, default_stochasticity_factory, DEFAULT_COMBAT_FLOW
from modules.resource import ResourceModule

def load_db_file(file_path):
    """Load log files from path to DataFrame, similar to step1_upload._parse_log_file"""
    name = file_path.lower()
    if name.endswith(".csv"):
        return pd.read_csv(file_path)

    if name.endswith(".tsv") or name.endswith(".txt"):
        for sep in ("\t", ",", r"\s+"):
            try:
                df = pd.read_csv(file_path, sep=sep, engine="python")
                if df.shape[1] > 1:
                    return df
            except Exception:
                continue
        raise ValueError("TSV/TXT 구분자를 감지할 수 없습니다.")

    if name.endswith(".xlsx") or name.endswith(".xls"):
        xf = pd.ExcelFile(file_path)
        return xf.parse(xf.sheet_names[0])

    if name.endswith(".json"):
        with open(file_path, 'rb') as f:
            raw = f.read()
        raw_str = raw.decode("utf-8", errors="replace")
        try:
            df = pd.read_json(io.BytesIO(raw))
            if isinstance(df, pd.DataFrame) and df.shape[0] > 0:
                return df
        except Exception:
            pass
        try:
            df = pd.read_json(io.BytesIO(raw), lines=True)
            if isinstance(df, pd.DataFrame) and df.shape[0] > 0:
                return df
        except Exception:
            pass
        try:
            obj = json.loads(raw_str)
            if isinstance(obj, dict):
                for key, val in obj.items():
                    if isinstance(val, list) and len(val) > 0:
                        df = pd.json_normalize(val)
                        if df.shape[0] > 0:
                            return df
        except Exception:
            pass
        raise ValueError("JSON을 테이블로 변환할 수 없습니다.")

    if name.endswith(".parquet"):
        return pd.read_parquet(file_path)

    raise ValueError(f"지원하지 않는 파일 형식입니다: {name}")

def _get_stochasticity(log_schema):
    if log_schema:
        trace_on = (log_schema.get("state_trace_enabled") or 
                    log_schema.get("damage_trace_enabled") or 
                    log_schema.get("resource_delta_trace_enabled"))
        if trace_on and bool(log_schema.get("state_score_deterministic", True)):
            return None
    return default_stochasticity_factory

def main():
    parser = argparse.ArgumentParser(description="DB-log corpus backtest harness")
    parser.add_argument("--schema", required=True, help="Path to schema JSON file")
    parser.add_argument("--out-dir", default="검증_코퍼스", help="Output directory")
    parser.add_argument("--max-battles", type=int, default=1000, help="Max battles per file")
    parser.add_argument("--battle-size", type=int, default=2, help="Fallback battle size")
    parser.add_argument("--target-col", default="result", help="Fallback target col")
    parser.add_argument("--allow-replay-html", action="store_true", help="Allow HTML replay files (legacy)")
    parser.add_argument("logs", nargs="+", help="DB log files")

    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    with open(args.schema, 'r', encoding='utf-8') as f:
        schema_data = json.load(f)

    sys_stats = schema_data.get("system_stats", [])
    sys_gimmicks = schema_data.get("system_gimmicks", [])
    health_stat = schema_data.get("health_stat", "HP")
    resource_config = schema_data.get("resource_config", None)
    game_config = schema_data.get("game_config", {})
    log_schema = schema_data.get("log_schema", {})
    target_col = schema_data.get("target_col", args.target_col)
    battle_size = schema_data.get("battle_size", args.battle_size)

    combat_flow = schema_data.get("combat_flow", DEFAULT_COMBAT_FLOW)
    speed_stat = schema_data.get("speed_stat")
    global_damage_formula = schema_data.get("global_damage_formula", "0")
    max_turns = int(schema_data.get("sim_max_turns", schema_data.get("max_turns", 100)))
    move_library = schema_data.get("move_library")
    damage_type_map = schema_data.get("damage_type_map")
    range_stat = schema_data.get("range_stat")
    move_stat = schema_data.get("move_stat")

    report_rows = []

    print("=== DB Corpus Backtest Summary ===")
    print(f"{'file':<20} {'status':<15} {'battles':<8} {'acc':<8} {'outcome_miss':<13} {'state_miss':<12} {'dmg_miss':<10} {'res_miss':<10} {'next'}")

    for log_file in args.logs:
        name = os.path.basename(log_file)
        fmt = name.split(".")[-1] if "." in name else ""

        row = {
            "file": name,
            "format": fmt,
            "rows": 0,
            "columns": 0,
            "status": "loaded",
            "target_col": target_col,
            "battle_count": 0,
            "actual_count": 0,
            "predicted_count": 0,
            "accuracy_pct": 0.0,
            "outcome_accuracy_pct": 0.0,
            "outcome_mismatches": 0,
            "correct": 0,
            "errors": 0,
            "state_checks": 0,
            "state_mismatches": 0,
            "action_damage_checks": 0,
            "action_damage_mismatches": 0,
            "action_resource_delta_checks": 0,
            "action_resource_delta_mismatches": 0,
            "first_mismatch_score_type": "",
            "first_mismatch_turn": "",
            "first_mismatch_id": "",
            "first_mismatch_kind": "",
            "first_mismatch_resource": "",
            "first_mismatch_expected": "",
            "first_mismatch_actual": "",
            "speed_stat": speed_stat,
            "max_turns": max_turns,
            "formula": global_damage_formula,
            "trace_moves_enabled": log_schema.get("trace_moves_enabled", False),
            "state_trace_enabled": log_schema.get("state_trace_enabled", False),
            "damage_trace_enabled": log_schema.get("damage_trace_enabled", False),
            "resource_delta_trace_enabled": log_schema.get("resource_delta_trace_enabled", False),
            "next_action": "",
            "error": ""
        }

        if fmt.lower() == "html" and not args.allow_replay_html:
            row["status"] = "error"
            row["next_action"] = "HTML replay is not a DB-log corpus input"
            row["error"] = row["next_action"]
            report_rows.append(row)
            print(f"{name:<20} {'error':<15} {'-':<8} {'-':<8} {'-':<13} {'-':<12} {'-':<10} {'-':<10} {row['next_action']}")
            continue

        try:
            df = load_db_file(log_file)
            row["rows"] = len(df)
            row["columns"] = len(df.columns)
        except Exception as e:
            row["status"] = "error"
            row["next_action"] = "error"
            row["error"] = str(e)
            report_rows.append(row)
            print(f"{name:<20} {'error':<15} {'-':<8} {'-':<8} {'-':<13} {'-':<12} {'-':<10} {'-':<10} {row['next_action']}")
            continue

        # Basic schema check
        missing_cols = []
        if log_schema:
            for k, v in log_schema.items():
                if k.endswith("_col") and v and v not in df.columns:
                    missing_cols.append(v)

        if missing_cols:
            row["status"] = "schema_invalid"
            row["next_action"] = "fix_schema"
            row["error"] = f"Missing columns: {', '.join(missing_cols)}"
            report_rows.append(row)
            print(f"{name:<20} {'schema_invalid':<15} {'-':<8} {'-':<8} {'-':<13} {'-':<12} {'-':<10} {'-':<10} fix_schema")
            continue

        try:
            battles = build_battles(
                df, battle_size, target_col,
                sys_stats, sys_gimmicks, health_stat,
                move_library=move_library,
                resource_config=resource_config,
                max_battles=args.max_battles,
                game_config=game_config,
                log_schema=log_schema
            )
        except Exception as e:
            row["status"] = "error"
            row["next_action"] = "error"
            row["error"] = f"build_battles error: {str(e)}"
            report_rows.append(row)
            print(f"{name:<20} {'error':<15} {'-':<8} {'-':<8} {'-':<13} {'-':<12} {'-':<10} {'-':<10} error")
            continue

        if not battles:
            row["status"] = "no_battles"
            row["next_action"] = "fix_schema"
            report_rows.append(row)
            print(f"{name:<20} {'no_battles':<15} {'-':<8} {'-':<8} {'-':<13} {'-':<12} {'-':<10} {'-':<10} fix_schema")
            continue

        row["battle_count"] = len(battles)
        
        tasks = []
        actuals = []
        rm = ResourceModule(resource_config, damage_type_map=damage_type_map)
        stoch_factory = _get_stochasticity(log_schema)
        
        for i, battle in enumerate(battles):
            if len(battle) == 4:
                a_team, e_team, ally_wins, battle_gc = battle
            else:
                a_team, e_team, ally_wins = battle
                battle_gc = None
                
            task_gc = copy.deepcopy(game_config)
            if battle_gc:
                task_gc.update(battle_gc)
                
            tasks.append((
                a_team, e_team, combat_flow, speed_stat, sys_stats, global_damage_formula,
                max_turns, stoch_factory, rm, None, range_stat, move_stat, None, task_gc, i
            ))
            actuals.append(ally_wins)

        predictions = []
        state_scores = []
        action_damage_scores = []
        action_resource_delta_scores = []
        engine_errors = 0
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
            for res in pool.map(_worker_simulate_match, tasks, chunksize=4):
                if isinstance(res, str):
                    engine_errors += 1
                    predictions.append(False)
                else:
                    predictions.append(res[0] == 1)
                    metrics = res[1] if len(res) > 1 else {}
                    if isinstance(metrics, dict):
                        if metrics.get("state_score"): state_scores.append(metrics["state_score"])
                        if metrics.get("action_damage_score"): action_damage_scores.append(metrics["action_damage_score"])
                        if metrics.get("action_resource_delta_score"): action_resource_delta_scores.append(metrics["action_resource_delta_score"])

        row["errors"] = engine_errors
        sc = score_predictions(predictions, actuals)
        row["actual_count"] = sc["ally_wins_actual"]
        row["predicted_count"] = sum(1 for p in predictions if p)
        row["accuracy_pct"] = sc["accuracy"] * 100.0
        row["outcome_accuracy_pct"] = sc["accuracy"] * 100.0
        row["correct"] = sc["correct"]
        row["outcome_mismatches"] = sc["total"] - sc["correct"]

        # Aggregate state scores
        if state_scores:
            row["state_checks"] = sum(int(s.get("checks", 0) or 0) for s in state_scores)
            row["state_mismatches"] = sum(int(s.get("mismatches", 0) or 0) for s in state_scores)
        if action_damage_scores:
            row["action_damage_checks"] = sum(int(s.get("checks", 0) or 0) for s in action_damage_scores)
            row["action_damage_mismatches"] = sum(int(s.get("mismatches", 0) or 0) for s in action_damage_scores)
        if action_resource_delta_scores:
            row["action_resource_delta_checks"] = sum(int(s.get("checks", 0) or 0) for s in action_resource_delta_scores)
            row["action_resource_delta_mismatches"] = sum(int(s.get("mismatches", 0) or 0) for s in action_resource_delta_scores)

        # Find first mismatch
        first_miss = None
        for stype, slist in [("state", state_scores), ("action_damage", action_damage_scores), ("action_resource_delta", action_resource_delta_scores)]:
            fm = next((s.get("first_mismatch") for s in slist if s.get("first_mismatch")), None)
            if fm:
                row["first_mismatch_score_type"] = stype
                row["first_mismatch_turn"] = fm.get("turn", "")
                row["first_mismatch_id"] = fm.get("id", "")
                row["first_mismatch_kind"] = fm.get("kind", "")
                row["first_mismatch_resource"] = fm.get("resource", "")
                row["first_mismatch_expected"] = repr(fm.get("expected_full", fm.get("expected", "")))
                row["first_mismatch_actual"] = repr(fm.get("actual_full", fm.get("actual", "")))
                first_miss = True
                break

        row["status"] = "ran"
        
        outcome_mismatches = row["outcome_mismatches"]
        total_mismatches = row["state_mismatches"] + row["action_damage_mismatches"] + row["action_resource_delta_mismatches"]
        
        if engine_errors > 0:
            row["next_action"] = "inspect_engine_errors"
        elif total_mismatches > 0:
            row["next_action"] = "inspect_mismatch"
        elif outcome_mismatches > 0:
            row["next_action"] = "inspect_outcome_mismatch"
        else:
            if log_schema and not (
                log_schema.get("damage_trace_enabled")
                or log_schema.get("state_trace_enabled")
                or log_schema.get("resource_delta_trace_enabled")
            ):
                row["next_action"] = "need_db_event_columns"
            else:
                row["next_action"] = "passed_or_low_mismatch"

        report_rows.append(row)
        acc_str = f"{row['accuracy_pct']:.1f}%"
        print(f"{name:<20} {'ran':<15} {row['battle_count']:<8} {acc_str:<8} {row['outcome_mismatches']:<13} {row['state_mismatches']:<12} {row['action_damage_mismatches']:<10} {row['action_resource_delta_mismatches']:<10} {row['next_action']}")

    # Save
    out_csv = os.path.join(args.out_dir, "db_corpus_backtest_summary.csv")
    out_md = os.path.join(args.out_dir, "db_corpus_backtest_summary.md")

    if report_rows:
        df_out = pd.DataFrame(report_rows)
        df_out.to_csv(out_csv, index=False, encoding="utf-8-sig")

        with open(out_md, 'w', encoding='utf-8') as f:
            f.write("# DB 로그 코퍼스 백테스트 리포트\n\n")
            f.write("- 이 리포트는 DB 로그 기반 코퍼스 검증 리포트다.\n")
            f.write("- HTML 리플레이 검증은 별도 legacy/reference harness이며 주 경로가 아니다.\n")
            f.write("- 결측 컬럼/schema 문제는 엔진 결함이 아니라 입력 매핑 문제로 분리한다.\n")
            f.write("- mismatch는 복제본과 관측 DB 로그가 갈라진 첫 지점이다.\n\n")
            md_str = "|" + "|".join(df_out.columns) + "|\n"
            md_str += "|" + "|".join(["---"] * len(df_out.columns)) + "|\n"
            for _, row in df_out.iterrows():
                md_str += "|" + "|".join([str(x) for x in row.values]) + "|\n"
            f.write(md_str)

if __name__ == "__main__":
    main()
