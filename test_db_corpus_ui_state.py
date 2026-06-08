import os
import json
import pandas as pd
from modules.ui_db_corpus_helper import build_db_corpus_backtest_downloads, process_db_corpus_upload

def test_download_csv_helper_header():
    # mismatch 0건
    summary = {"accuracy": 100.0}
    mismatch_rows = []
    
    s_csv, m_csv = build_db_corpus_backtest_downloads(summary, mismatch_rows)
    
    # header가 있는지 확인
    lines = m_csv.strip().split("\n")
    assert len(lines) == 1, "Should have exactly 1 line (header) when no mismatch"
    assert "battle_index" in lines[0]
    assert "score_type" in lines[0]
    assert "expected" in lines[0]

def test_schema_flag_in_json():
    # schema 생성 확인
    db_path = ".codex_tmp/adapt8_multi_battle_replay/pokemon_showdown_multi.db"
    if not os.path.exists(db_path):
        print(f"Fixture {db_path} not found. Skipping.")
        return
        
    with open(db_path, "rb") as f:
        file_bytes = f.read()
        
    df, report, schema = process_db_corpus_upload(file_bytes, os.path.basename(db_path))
    
    log_schema = schema.get("log_schema", {})
    assert log_schema.get("observed_status_trace_enabled") is True
    assert log_schema.get("observed_hp_trace_enabled") is True
    assert log_schema.get("observed_switch_trace_enabled") is True
    
    schema_json = json.dumps(schema, indent=2, ensure_ascii=False)
    assert "observed_status_trace_enabled" in schema_json

if __name__ == "__main__":
    test_download_csv_helper_header()
    test_schema_flag_in_json()
    print("test_db_corpus_ui_state OK")
