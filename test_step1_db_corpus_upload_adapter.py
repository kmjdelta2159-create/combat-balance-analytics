import os
import shutil
import pandas as pd
from modules.ui_db_corpus_helper import process_db_corpus_upload

def test_process_db_corpus_upload():
    # Use the dummy multi-battle fixture created for ADAPT8
    db_path = ".codex_tmp/adapt8_multi_battle_replay/pokemon_showdown_multi.db"
    if not os.path.exists(db_path):
        print(f"Test fixture not found at {db_path}. Run ADAPT8 fixture script first.")
        return
    
    with open(db_path, "rb") as f:
        db_bytes = f.read()
        
    df, report, schema = process_db_corpus_upload(db_bytes, "test_upload.db")
    
    # Assertions
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "battle_id" in df.columns
    
    assert report is not None
    assert report.get("battle_count") >= 2
    
    assert schema is not None
    assert "log_schema" in schema
    assert schema["log_schema"].get("observed_status_trace_enabled") is True
    
    print("test_process_db_corpus_upload OK")

def test_process_db_corpus_upload_zip():
    zip_path = ".codex_tmp/adapt8_multi_battle_replay/input_zip.zip"
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"Test fixture not found at {zip_path}.")
    with open(zip_path, "rb") as f:
        zip_bytes = f.read()
    
    df, report, schema = process_db_corpus_upload(zip_bytes, "test_upload.zip")
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert report.get("battle_count") >= 2
    assert "log_schema" in schema
    print("test_process_db_corpus_upload_zip OK")

def test_process_db_corpus_sanitize():
    db_path = ".codex_tmp/adapt8_multi_battle_replay/pokemon_showdown_multi.db"
    if not os.path.exists(db_path):
        print(f"Test fixture not found at {db_path}. Skipping.")
        return
    with open(db_path, "rb") as f:
        db_bytes = f.read()
        
    df, report, schema = process_db_corpus_upload(db_bytes, "../../../malicious!!!/path_123.db")
    # Should sanitize to path_123.db (or similar safe name)
    assert isinstance(df, pd.DataFrame)
    
    # Check invalid extension
    try:
        process_db_corpus_upload(db_bytes, "invalid_ext.txt")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "지원하지 않는 확장자" in str(e)
    print("test_process_db_corpus_sanitize OK")

if __name__ == "__main__":
    test_process_db_corpus_upload()
    test_process_db_corpus_upload_zip()
    test_process_db_corpus_sanitize()
    print("All UI DB corpus adapter tests passed!")
