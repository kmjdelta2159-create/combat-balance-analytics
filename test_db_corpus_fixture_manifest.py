import os
import sys
import subprocess
import tempfile

def test_manifest():
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            sys.executable, "-X", "utf8", "run_db_corpus_fixture_manifest.py",
            "db_corpus_fixtures/manifest.json",
            "--out-dir", tmpdir
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        assert res.returncode == 0, f"Process failed: {res.stderr}\nStdout: {res.stdout}"
        print(res.stdout)

        # verify summary output existence
        assert os.path.exists(os.path.join(tmpdir, "basic_damage_pass", "db_corpus_backtest_summary.csv"))
        assert os.path.exists(os.path.join(tmpdir, "outcome_mismatch_triage", "db_corpus_backtest_summary.csv"))
        assert os.path.exists(os.path.join(tmpdir, "resource_delta_trace_pass", "db_corpus_backtest_summary.csv"))

        # verify schema standard format
        import json
        with open("db_corpus_fixtures/resource_delta_trace_pass/schema.json", "r", encoding="utf-8") as f:
            schema = json.load(f)
        rc = schema.get("resource_config", {})
        assert rc["HP"]["role"] == "vital"
        assert rc["HP"]["stat"] == "HP"
        assert rc["Shield"]["role"] == "shield"
        assert rc["Shield"]["stat"] == "Shield"
        assert "vital" not in rc["HP"]
        assert "shield" not in rc["Shield"]

if __name__ == "__main__":
    test_manifest()
