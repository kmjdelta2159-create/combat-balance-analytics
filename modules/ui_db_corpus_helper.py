import os
import shutil
import tempfile
import json
import pandas as pd
from modules.showdown_db_adapter import extract_from_zip_or_dir, convert_to_battle_log, generate_schema

def process_db_corpus_upload(file_bytes, filename):
    """
    Process an uploaded .db or .zip file for the Pokemon Showdown DB Corpus.
    Saves the file temporarily, runs the adapter to extract and convert,
    and returns the resulting dataframe, adapter report, and generated schema.
    """
    import re
    safe_name = os.path.basename(filename)
    safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', safe_name)
    
    if not (safe_name.lower().endswith(".db") or safe_name.lower().endswith(".zip")):
        raise ValueError("지원하지 않는 확장자입니다. .db 또는 .zip 파일만 지원합니다.")

    temp_dir = ".codex_tmp/ui1_db_corpus_surface"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Secure a temporary path
    file_path = os.path.join(temp_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
        
    try:
        # 1. Extract raw dataframes
        battles_df, events_df, rosters_df = extract_from_zip_or_dir(file_path)
        
        # 2. Convert to battle log format
        battle_log_df, report = convert_to_battle_log(battles_df, events_df, rosters_df)
        
        # 3. Generate schema
        schema = generate_schema()
        
        raw_tables = {
            "battles": battles_df,
            "battle_events": events_df,
            "battle_roster_pokemon": rosters_df
        }
        
        return battle_log_df, report, schema, raw_tables
    finally:
        # Clean up the temporary uploaded file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

def _mismatch_row_from_score(battle_index, score_type, score):
    _fm = score.get("first_mismatch")
    if not _fm:
        return None
    checks = max(1, score.get("checks", 1) or 1)
    mismatches = score.get("mismatches", 0) or 0
    accuracy = score.get("accuracy")
    if accuracy is None:
        accuracy = (1.0 - (mismatches / checks)) * 100.0
    return {
        "battle_index": battle_index,
        "score_type": score_type,
        "turn": _fm.get("turn"),
        "id": _fm.get("id"),
        "kind": _fm.get("kind"),
        "resource": _fm.get("resource"),
        "expected": _fm.get("expected"),
        "actual": _fm.get("actual"),
        "checks": score.get("checks"),
        "mismatches": score.get("mismatches"),
        "accuracy": accuracy,
        "expected_full": repr(_fm.get("expected_full", _fm.get("expected"))),
        "actual_full": repr(_fm.get("actual_full", _fm.get("actual")))
    }

def _extend_mismatch_rows_from_metrics(rows, battle_index, metrics):
    if not metrics:
        return
    for stype in ["state_score", "action_damage_score", "action_resource_delta_score"]:
        if metrics.get(stype):
            row = _mismatch_row_from_score(battle_index, stype.replace("_score", ""), metrics[stype])
            if row:
                rows.append(row)

def run_db_corpus_backtest_from_session(session_state_like, max_battles=None):
    """
    Run one-click backtest using DB corpus schema from session state.
    """
    import copy
    import concurrent.futures
    from modules.per_battle_backtest import build_battles, score_predictions
    from modules.engine import _worker_simulate_match
    
    df = session_state_like.get("df")
    schema = session_state_like.get("db_corpus_schema", {})
    log_schema = schema.get("log_schema", {})
    
    if df is None or not log_schema:
        raise ValueError("Missing dataframe or log schema")
        
    sys_stats = session_state_like.get("system_stats", [])
    sys_gimmicks = session_state_like.get("system_gimmicks", [])
    health_stat = session_state_like.get("health_stat")
    target_col = session_state_like.get("target_col")
    
    gc = copy.deepcopy(session_state_like.get("game_config") or {})
    if log_schema.get("entity_id_col"):
        gc["preserve_ids"] = True
        
    battles = build_battles(
        df, 0, target_col, sys_stats, sys_gimmicks, health_stat,
        None, None, max_battles, gc, log_schema
    )
    
    actuals = [b[2] for b in battles]
    predicts = []
    scores = []
    
    # Engine variables needed for task tuple
    combat_flow = session_state_like.get("combat_flow")
    from modules.engine import DEFAULT_COMBAT_FLOW
    if not combat_flow:
        combat_flow = DEFAULT_COMBAT_FLOW
    speed_stat = session_state_like.get("speed_stat")
    global_formula = session_state_like.get("global_damage_formula", "0")
    max_turns = int(session_state_like.get("sim_max_turns", 100))
    from modules.step6_dashboard import _select_backtest_stochasticity_factory
    from modules.resource import ResourceModule
    stoch_factory = _select_backtest_stochasticity_factory(log_schema)
    res_mod = ResourceModule(
        session_state_like.get("resource_config") or None,
        damage_type_map=session_state_like.get("damage_type_map") or None,
    )
    
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = []
        for i, b in enumerate(battles):
            b_gc = b[3] if len(b) > 3 else {}
            b_conf = copy.deepcopy(gc)
            if b_gc:
                b_conf.update(b_gc)
                
            task_args = (
                b[0], b[1], combat_flow, speed_stat, sys_stats, global_formula,
                max_turns, stoch_factory, res_mod,
                None, None, None, None, b_conf, i
            )
            futures.append(executor.submit(_worker_simulate_match, task_args))
            
        for f in futures:
            r = f.result()
            if isinstance(r, str):
                predicts.append(False)
                scores.append({})
            else:
                predicts.append(r[0] == 1)
                scores.append(r[1] if len(r) > 1 else {})
            
    summary = score_predictions(predicts, actuals)
    total_outcome_mismatches = summary.get("total", 0) - summary.get("correct", 0)
    
    total_checks = 0
    total_mismatches = 0
    first_mismatch = None
    
    mismatch_rows = []
    for idx, sc in enumerate(scores):
        if not sc: continue
        _extend_mismatch_rows_from_metrics(mismatch_rows, idx, sc)
        for stype in ["state_score", "action_damage_score", "action_resource_delta_score"]:
            if sc.get(stype):
                st_data = sc[stype]
                total_checks += st_data.get("checks", 0)
                total_mismatches += st_data.get("mismatches", 0)
                if st_data.get("first_mismatch") and first_mismatch is None:
                    first_mismatch = st_data["first_mismatch"]
                    
    summary_extended = {
        "battle_count": summary.get("total", 0),
        "actual_count": summary.get("total", 0),
        "predicted_count": summary.get("total", 0),
        "accuracy_pct": summary.get("accuracy", 0.0) * 100.0,
        "outcome_mismatches": total_outcome_mismatches,
        "state_checks": total_checks,
        "state_mismatches": total_mismatches,
        "next_action": "passed_or_low_mismatch" if total_mismatches == 0 and total_outcome_mismatches == 0 else "needs_investigation"
    }
    
    if first_mismatch:
        summary_extended.update({
            "first_mismatch_turn": first_mismatch.get("turn"),
            "first_mismatch_id": first_mismatch.get("id"),
            "first_mismatch_kind": first_mismatch.get("kind"),
            "first_mismatch_expected": first_mismatch.get("expected"),
            "first_mismatch_actual": first_mismatch.get("actual"),
        })
        
    return summary_extended, mismatch_rows

def build_db_corpus_backtest_downloads(summary, mismatch_rows):
    """
    Generate CSV strings for backtest summary and mismatch report.
    Returns (summary_csv_str, mismatch_csv_str).
    """
    summary_df = pd.DataFrame([summary])
    summary_csv = summary_df.to_csv(index=False)
    
    if mismatch_rows:
        mismatch_df = pd.DataFrame(mismatch_rows)
    else:
        mismatch_df = pd.DataFrame(columns=[
            "battle_index", "score_type", "turn", "id", "kind", 
            "resource", "expected", "actual", "checks", "mismatches", 
            "accuracy", "expected_full", "actual_full"
        ])
        
    mismatch_csv = mismatch_df.to_csv(index=False)
    return summary_csv, mismatch_csv
