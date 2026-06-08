import os
import sys
import json
import subprocess
import tempfile
import pandas as pd
from modules.step6_dashboard import _build_db_corpus_schema_payload

def test_step6_export_schema_cli_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Define schema payload inputs
        sys_stats = ["HP", "SPD"]
        sys_gimmicks = []
        health_stat = "HP"
        target_col = "result"
        battle_size = 2
        
        log_schema = {
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
        
        session_state_like = {
            "speed_stat": "SPD",
            "global_damage_formula": "999",
            "sim_max_turns": 1,
            "game_config": {"preserve_initial_on_field": True}
        }
        
        # 2. Build schema payload
        payload = _build_db_corpus_schema_payload(
            sys_stats, sys_gimmicks, health_stat, target_col, battle_size, log_schema, session_state_like
        )
        
        # Verify initial payload conditions
        assert payload["game_config"]["preserve_ids"] is True
        assert "preserve_ids" not in session_state_like["game_config"]
        
        # 3. Save exported schema
        schema_path = os.path.join(tmpdir, "exported_schema.json")
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
            
        # Optional validation of the saved schema
        with open(schema_path, "r", encoding="utf-8") as f:
            saved_schema = json.load(f)
            assert saved_schema["schema_version"] == "db_corpus_backtest.v1"
            assert saved_schema["generated_from"] == "step6_dashboard"
            assert saved_schema["log_schema"]["entity_id_col"] == "entity_id"
            assert saved_schema["game_config"]["preserve_ids"] is True
            # Verify that DEFAULT_COMBAT_FLOW is present
            from modules.engine import DEFAULT_COMBAT_FLOW
            assert saved_schema["combat_flow"] == DEFAULT_COMBAT_FLOW

        # 4. Create CSV mock data
        csv_path = os.path.join(tmpdir, "battle_log.csv")
        df = pd.DataFrame({
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
            "hp_delta": [100, 100],
        })
        df.to_csv(csv_path, index=False)
        
        # 5. Run CLI
        out_dir = os.path.join(tmpdir, "out")
        cmd = [
            sys.executable, "-X", "utf8", "run_db_corpus_backtest.py",
            "--schema", schema_path,
            "--out-dir", out_dir,
            csv_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        assert res.returncode == 0, f"Process failed: {res.stderr}\nStdout: {res.stdout}"
        
        # 6. Read and assert summary CSV
        summary_csv = os.path.join(out_dir, "db_corpus_backtest_summary.csv")
        assert os.path.exists(summary_csv)
        summary_df = pd.read_csv(summary_csv)
        
        assert len(summary_df) == 1
        row = summary_df.iloc[0]
        
        assert row["status"] == "ran"
        assert str(row["formula"]) == "999"
        assert row["speed_stat"] == "SPD"
        assert bool(row["trace_moves_enabled"]) is True
        assert bool(row["damage_trace_enabled"]) is True
        assert row["action_damage_mismatches"] == 0
        assert row["outcome_mismatches"] == 0
        assert row["next_action"] == "passed_or_low_mismatch"

    print("All step6 export schema cli roundtrip tests passed.")

if __name__ == "__main__":
    test_step6_export_schema_cli_roundtrip()
