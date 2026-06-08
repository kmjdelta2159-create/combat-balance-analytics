import os
import sys
import json
import subprocess
import pandas as pd
import tempfile

def test_db_corpus_backtest_report():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Create a valid schema (Basic)
        schema_path = os.path.join(tmpdir, "schema.json")
        schema_data = {
            "target_col": "result",
            "battle_size": 2,
            "system_stats": ["HP"],
            "health_stat": "HP",
            "game_config": {"preserve_ids": True},
            "log_schema": {
                "battle_id_col": "battle_id",
                "team_col": "team",
                "entity_id_col": "entity_id",
                "result_mode": "battle_level",
                "ally_values": ["Ally"],
                "enemy_values": ["Enemy"]
            }
        }
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(schema_data, f)

        # 2. Create a valid CSV DB log
        valid_csv_path = os.path.join(tmpdir, "valid.csv")
        valid_df = pd.DataFrame({
            "battle_id": [1, 1],
            "team": ["Ally", "Enemy"],
            "entity_id": ["A1", "E1"],
            "result": [1, 0],
            "HP": [100, 100]
        })
        valid_df.to_csv(valid_csv_path, index=False)

        # 3. Create an invalid CSV DB log (missing columns)
        invalid_csv_path = os.path.join(tmpdir, "invalid.csv")
        invalid_df = pd.DataFrame({
            "wrong_col": [1, 2]
        })
        invalid_df.to_csv(invalid_csv_path, index=False)

        # 4. Create an HTML file
        html_path = os.path.join(tmpdir, "replay.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write("<html>replay</html>")

        # 5. Create a schema for global_damage_formula test
        dmg_schema_path = os.path.join(tmpdir, "dmg_schema.json")
        dmg_schema_data = {
            "target_col": "result",
            "battle_size": 2,
            "system_stats": ["HP", "SPD"],
            "health_stat": "HP",
            "speed_stat": "SPD",
            "global_damage_formula": "30",
            "sim_max_turns": 1,
            "game_config": {"preserve_ids": True, "preserve_initial_on_field": True},
            "log_schema": {
                "battle_id_col": "battle_id",
                "team_col": "team",
                "entity_id_col": "entity_id",
                "result_mode": "battle_level",
                "ally_values": ["Ally"],
                "enemy_values": ["Enemy"],
                "initial_on_field_enabled": True,
                "initial_on_field_col": "team",
                "initial_on_field_values": ["Ally", "Enemy"],
                "trace_moves_enabled": True,
                "turn_col": "turn",
                "actor_id_col": "actor",
                "target_id_col": "target",
                "move_name_col": "move",
                "damage_trace_enabled": True,
                "damage_turn_col": "turn",
                "damage_actor_id_col": "actor",
                "damage_target_id_col": "target",
                "damage_value_col": "hp_delta",
                "damage_value_kind": "hp_delta"
            }
        }
        with open(dmg_schema_path, "w", encoding="utf-8") as f:
            json.dump(dmg_schema_data, f)

        # 6. Create a CSV for damage trace test
        dmg_csv_path = os.path.join(tmpdir, "damage_trace.csv")
        dmg_df = pd.DataFrame({
            "battle_id": [1, 1],
            "team": ["Ally", "Enemy"],
            "entity_id": ["A1", "E1"],
            "result": [1, 0],
            "HP": [100, 100],
            "SPD": [10, 1],
            "turn": [1, 1],
            "actor": ["A1", "A1"],
            "target": ["E1", "E1"],
            "move": ["Hit", "Hit"],
            "hp_delta": [30, 30]
        })
        dmg_df.to_csv(dmg_csv_path, index=False)


        # Run harness for basic cases
        out_dir = os.path.join(tmpdir, "out")
        cmd = [
            sys.executable, "-X", "utf8", "run_db_corpus_backtest.py",
            "--schema", schema_path,
            "--out-dir", out_dir,
            valid_csv_path, invalid_csv_path, html_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        assert res.returncode == 0, f"Process failed: {res.stderr}"

        out_csv = os.path.join(out_dir, "db_corpus_backtest_summary.csv")
        df_out = pd.read_csv(out_csv)
        assert len(df_out) == 3

        valid_row = df_out[df_out["file"] == "valid.csv"].iloc[0]
        assert valid_row["status"] == "ran"
        
        invalid_row = df_out[df_out["file"] == "invalid.csv"].iloc[0]
        assert invalid_row["status"] == "schema_invalid"
        assert invalid_row["next_action"] == "fix_schema"

        html_row = df_out[df_out["file"] == "replay.html"].iloc[0]
        assert html_row["status"] == "error"
        assert "HTML replay is not a DB-log corpus input" in html_row["next_action"]

        # Run harness for damage trace test
        dmg_out_dir = os.path.join(tmpdir, "dmg_out")
        cmd2 = [
            sys.executable, "-X", "utf8", "run_db_corpus_backtest.py",
            "--schema", dmg_schema_path,
            "--out-dir", dmg_out_dir,
            dmg_csv_path
        ]
        res2 = subprocess.run(cmd2, capture_output=True, text=True, encoding='utf-8')
        assert res2.returncode == 0, f"Process failed: {res2.stderr}"

        dmg_out_csv = os.path.join(dmg_out_dir, "db_corpus_backtest_summary.csv")
        df_dmg_out = pd.read_csv(dmg_out_csv)
        assert len(df_dmg_out) == 1
        
        dmg_row = df_dmg_out.iloc[0]
        assert dmg_row["status"] == "ran"
        assert dmg_row["action_damage_mismatches"] == 0
        assert dmg_row["outcome_mismatches"] > 0
        assert dmg_row["next_action"] == "inspect_outcome_mismatch"

        # 7. Create a schema and CSV for passed case (formula "999")
        passed_schema_path = os.path.join(tmpdir, "passed_schema.json")
        passed_schema_data = dict(dmg_schema_data)
        passed_schema_data["global_damage_formula"] = "999"
        with open(passed_schema_path, "w", encoding="utf-8") as f:
            json.dump(passed_schema_data, f)
            
        passed_csv_path = os.path.join(tmpdir, "passed.csv")
        passed_df = pd.DataFrame({
            "battle_id": [1, 1],
            "team": ["Ally", "Enemy"],
            "entity_id": ["A1", "E1"],
            "result": [1, 0],
            "HP": [100, 100],
            "SPD": [10, 1],
            "turn": [1, 1],
            "actor": ["A1", "A1"],
            "target": ["E1", "E1"],
            "move": ["Hit", "Hit"],
            "hp_delta": [100, 100]
        })
        passed_df.to_csv(passed_csv_path, index=False)

        # Run harness for passed case
        passed_out_dir = os.path.join(tmpdir, "passed_out")
        cmd3 = [
            sys.executable, "-X", "utf8", "run_db_corpus_backtest.py",
            "--schema", passed_schema_path,
            "--out-dir", passed_out_dir,
            passed_csv_path
        ]
        res3 = subprocess.run(cmd3, capture_output=True, text=True, encoding='utf-8')
        assert res3.returncode == 0, f"Process failed: {res3.stderr}"

        passed_out_csv = os.path.join(passed_out_dir, "db_corpus_backtest_summary.csv")
        df_passed_out = pd.read_csv(passed_out_csv)
        assert len(df_passed_out) == 1
        
        passed_row = df_passed_out.iloc[0]
        assert passed_row["status"] == "ran"
        assert passed_row["action_damage_mismatches"] == 0
        assert passed_row["outcome_mismatches"] == 0
        assert passed_row["next_action"] == "passed_or_low_mismatch"

    print("All tests passed.")

if __name__ == "__main__":
    test_db_corpus_backtest_report()
