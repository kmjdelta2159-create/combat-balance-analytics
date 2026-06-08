import os

from modules.ui_db_corpus_helper import process_db_corpus_upload, run_db_corpus_backtest_from_session

def setup_session_state(filepath):
    if not os.path.exists(filepath):
        print(f"Fixture {filepath} not found. Skipping.")
        return None
        
    with open(filepath, "rb") as f:
        file_bytes = f.read()
        
    df, report, schema = process_db_corpus_upload(file_bytes, os.path.basename(filepath))
    
    return {
        "df": df,
        "db_corpus_adapter_report": report,
        "db_corpus_schema": schema,
        "target_col": "result",
        "health_stat": "HP",
        "system_stats": ["HP", "ATK", "DEF", "SPA", "SPD", "SPE"],
        "system_gimmicks": [],
        "game_config": {}
    }

def test_db_corpus_oneclick_backtest_db():
    db_path = ".codex_tmp/adapt8_multi_battle_replay/pokemon_showdown_multi.db"
    session_state = setup_session_state(db_path)
    
    summary, mismatch_rows = run_db_corpus_backtest_from_session(session_state)
    
    assert summary["battle_count"] == 2
    assert summary["actual_count"] == 2
    assert summary["predicted_count"] == 2
    assert summary["accuracy_pct"] == 100.0
    assert summary["outcome_mismatches"] == 0
    assert summary["state_mismatches"] == 0
    assert summary["state_checks"] == 234
    assert len(mismatch_rows) == 0

def test_db_corpus_oneclick_backtest_zip():
    zip_path = ".codex_tmp/adapt8_multi_battle_replay/input_zip.zip"
    session_state = setup_session_state(zip_path)
    
    summary, mismatch_rows = run_db_corpus_backtest_from_session(session_state)
    
    assert summary["battle_count"] == 2
    assert summary["actual_count"] == 2
    assert summary["predicted_count"] == 2
    assert summary["accuracy_pct"] == 100.0
    assert summary["outcome_mismatches"] == 0
    assert summary["state_mismatches"] == 0
    assert summary["state_checks"] == 234
    assert len(mismatch_rows) == 0

if __name__ == "__main__":
    import sys
    db_path = ".codex_tmp/adapt8_multi_battle_replay/pokemon_showdown_multi.db"
    if not os.path.exists(db_path):
        print(f"Test fixture not found at {db_path}. Run ADAPT8 script first.")
        sys.exit(1)
        
    test_db_corpus_oneclick_backtest_db()
    test_db_corpus_oneclick_backtest_zip()
    print("test_step6_db_corpus_oneclick_backtest OK")
