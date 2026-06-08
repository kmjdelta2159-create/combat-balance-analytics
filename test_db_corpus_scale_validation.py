import os
import sys
import subprocess
import pandas as pd
import tempfile

def test_scale_validation_runner():
    db_fixture = ".codex_tmp/adapt8_multi_battle_replay/pokemon_showdown_multi.db"
    zip_fixture = ".codex_tmp/adapt8_multi_battle_replay/input_zip.zip"
    
    if not os.path.exists(db_fixture) or not os.path.exists(zip_fixture):
        print("Fixtures not found. Please ensure ADAPT8 multi battle replay fixtures exist.")
        return
        
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = os.path.join(tmpdir, "out")
        cmd = [
            sys.executable, "-X", "utf8", "run_db_corpus_scale_validation.py",
            "--input", db_fixture,
            "--input", zip_fixture,
            "--out", out_dir
        ]
        
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        assert res.returncode == 0, f"Process failed: {res.stderr}"
        
        # Checking for "Skipping"
        assert "Skipping" not in res.stdout, "Test output should not contain 'Skipping'"
        
        # Verify outputs exist
        summary_csv = os.path.join(out_dir, "scale_validation_summary.csv")
        summary_json = os.path.join(out_dir, "scale_validation_summary.json")
        mismatch_csv = os.path.join(out_dir, "scale_validation_mismatch_report.csv")
        reports_json = os.path.join(out_dir, "scale_validation_adapter_reports.json")
        flags_csv = os.path.join(out_dir, "scale_validation_schema_flags.csv")
        inputs_json = os.path.join(out_dir, "scale_validation_inputs.json")
        
        assert os.path.exists(summary_csv)
        assert os.path.exists(summary_json)
        assert os.path.exists(mismatch_csv)
        assert os.path.exists(reports_json)
        assert os.path.exists(flags_csv)
        assert os.path.exists(inputs_json)
        
        df = pd.read_csv(summary_csv)
        assert len(df) == 2
        
        # Check kind
        assert all(df["input_kind"] == "replicated_fixture"), "All inputs should be replicated_fixture"
        assert all(df["status"] == "ran"), "All inputs should have status 'ran'"
        
        # Check equivalency
        db_row = df[df["input_path"] == db_fixture].iloc[0]
        zip_row = df[df["input_path"] == zip_fixture].iloc[0]
        
        assert db_row["battle_count"] == 2
        assert db_row["move_count"] == 72
        assert db_row["accuracy_pct"] == 100.0
        assert db_row["outcome_mismatches"] == 0
        assert db_row["state_mismatches"] == 0
        
        assert db_row["battle_count"] == zip_row["battle_count"]
        assert db_row["accuracy_pct"] == zip_row["accuracy_pct"]
        assert db_row["outcome_mismatches"] == zip_row["outcome_mismatches"]
        assert db_row["state_mismatches"] == zip_row["state_mismatches"]
        
        df_mm = pd.read_csv(mismatch_csv)
        assert len(df_mm) == 0, "Mismatch report should be empty for 100% accuracy"
        assert "expected_full" in df_mm.columns, "Mismatch report missing columns"
        
        print("test_scale_validation_runner passed.")

if __name__ == "__main__":
    test_scale_validation_runner()
