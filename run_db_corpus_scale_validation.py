import argparse
import os
import json
import pandas as pd
from modules.ui_db_corpus_helper import process_db_corpus_upload, run_db_corpus_backtest_from_session
from modules.showdown_db_adapter import extract_from_zip_or_dir, convert_to_battle_log, generate_schema

def validate_input(input_path):
    try:
        if os.path.isdir(input_path):
            battles_df, events_df, rosters_df = extract_from_zip_or_dir(input_path)
            df, report = convert_to_battle_log(battles_df, events_df, rosters_df)
            schema = generate_schema()
            return df, report, schema, None
        elif input_path.endswith(".zip") or input_path.endswith(".db"):
            with open(input_path, "rb") as f:
                b = f.read()
            df, report, schema = process_db_corpus_upload(b, os.path.basename(input_path))
            return df, report, schema, None
        else:
            return None, None, None, f"Unsupported extension: {input_path}"
    except Exception as e:
        import traceback
        return None, None, None, f"Error: {str(e)}\n{traceback.format_exc()}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", help="Input .db, .zip, folder, or manifest")
    parser.add_argument("--out", required=True, help="Output directory")
    args = parser.parse_args()

    inputs = []
    if args.input:
        for p in args.input:
            if p.endswith(".json") and os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        inputs.extend(data)
            elif p.endswith(".csv") and os.path.isfile(p):
                df = pd.read_csv(p)
                if "input_path" in df.columns:
                    inputs.extend(df["input_path"].tolist())
            else:
                inputs.append(p)
                
    if not inputs:
        print("No inputs provided.")
        return
                
    os.makedirs(args.out, exist_ok=True)
    
    summary_rows = []
    adapter_reports = {}
    schema_flags = []
    all_mismatch_rows = []
    input_records = []
    
    for i, p in enumerate(inputs):
        name = os.path.basename(p)
        if name in ["pokemon_showdown_multi.db", "input_zip.zip"]:
            input_kind = "replicated_fixture"
        else:
            input_kind = "unknown"
            
        row = {
            "input_path": p,
            "input_kind": input_kind,
            "status": "pending",
            "battle_count": 0,
            "event_count": 0,
            "participant_count": 0,
            "move_count": 0,
            "state_event_count": 0,
            "damage_event_count": 0,
            "winner_sides_count": 0,
            "roster_only_entities_count": 0,
            "unknown_damage_actor_count": 0,
            "rows": 0,
            "accuracy_pct": 0.0,
            "outcome_mismatches": 0,
            "state_checks": 0,
            "state_mismatches": 0,
            "next_action": "",
            "first_mismatch_turn": "",
            "first_mismatch_id": "",
            "first_mismatch_kind": "",
            "first_mismatch_expected": "",
            "first_mismatch_actual": "",
            "error": ""
        }
        
        print(f"[{i+1}/{len(inputs)}] Processing {p}...")
        df, report, schema, error = validate_input(p)
        if error:
            row["status"] = "error"
            row["error"] = error
            row["next_action"] = "fix_input"
        else:
            row["rows"] = len(df)
            row["battle_count"] = report.get("battle_count", 0)
            row["event_count"] = report.get("event_count", 0)
            row["participant_count"] = report.get("participant_count", 0)
            row["move_count"] = report.get("move_count", 0)
            row["state_event_count"] = report.get("state_event_count", 0)
            row["damage_event_count"] = report.get("damage_event_count", 0)
            row["winner_sides_count"] = len(report.get("winner_sides", {}))
            row["roster_only_entities_count"] = len(report.get("roster_only_entities", []))
            row["unknown_damage_actor_count"] = report.get("unknown_damage_actor_count", 0)
            
            if row["battle_count"] > 1 and input_kind != "replicated_fixture":
                row["input_kind"] = "real_corpus"
            
            session_state = {
                "df": df,
                "db_corpus_schema": schema,
                "target_col": "result",
                "health_stat": "HP",
                "system_stats": ["HP", "ATK", "DEF", "SPA", "SPD", "SPE"],
                "system_gimmicks": [],
                "game_config": {}
            }
            
            try:
                summary, mismatch_rows = run_db_corpus_backtest_from_session(session_state)
                row["status"] = "ran"
                row["accuracy_pct"] = summary.get("accuracy_pct", 0.0)
                row["outcome_mismatches"] = summary.get("outcome_mismatches", 0)
                row["state_checks"] = summary.get("state_checks", 0)
                row["state_mismatches"] = summary.get("state_mismatches", 0)
                row["next_action"] = summary.get("next_action", "needs_investigation")
                row["first_mismatch_turn"] = summary.get("first_mismatch_turn", "")
                row["first_mismatch_id"] = summary.get("first_mismatch_id", "")
                row["first_mismatch_kind"] = summary.get("first_mismatch_kind", "")
                row["first_mismatch_expected"] = summary.get("first_mismatch_expected", "")
                row["first_mismatch_actual"] = summary.get("first_mismatch_actual", "")
                
                for mm in mismatch_rows:
                    mm["input_path"] = p
                    all_mismatch_rows.append(mm)
            except Exception as e:
                import traceback
                row["status"] = "error"
                row["error"] = f"Error: {str(e)}\n{traceback.format_exc()}"
                row["next_action"] = "fix_backtest_error"
                
            adapter_reports[p] = report
            schema_flags.append({
                "input_path": p,
                **schema.get("log_schema", {})
            })
            
        summary_rows.append(row)
        input_records.append({"input_path": p, "status": row["status"], "input_kind": row["input_kind"]})
        
    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(os.path.join(args.out, "scale_validation_summary.csv"), index=False, encoding="utf-8")
    df_summary.to_json(os.path.join(args.out, "scale_validation_summary.json"), orient="records", force_ascii=False, indent=2)
    
    if all_mismatch_rows:
        df_mm = pd.DataFrame(all_mismatch_rows)
    else:
        df_mm = pd.DataFrame(columns=[
            "input_path", "battle_index", "score_type", "turn", "id", "kind", 
            "resource", "expected", "actual", "checks", "mismatches", 
            "accuracy", "expected_full", "actual_full"
        ])
    df_mm.to_csv(os.path.join(args.out, "scale_validation_mismatch_report.csv"), index=False, encoding="utf-8")
    
    with open(os.path.join(args.out, "scale_validation_adapter_reports.json"), "w", encoding="utf-8") as f:
        json.dump(adapter_reports, f, ensure_ascii=False, indent=2)
        
    if schema_flags:
        df_schema = pd.DataFrame(schema_flags)
        df_schema.to_csv(os.path.join(args.out, "scale_validation_schema_flags.csv"), index=False, encoding="utf-8")
    
    with open(os.path.join(args.out, "scale_validation_inputs.json"), "w", encoding="utf-8") as f:
        json.dump(input_records, f, ensure_ascii=False, indent=2)
        
    print(f"\nDone. Processed {len(inputs)} inputs. Results saved to {args.out}")

if __name__ == "__main__":
    main()
