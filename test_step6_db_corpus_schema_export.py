import os
import sys
import json
import numpy as np
import pandas as pd
from modules.step6_dashboard import _json_safe, _build_db_corpus_schema_payload

def test_step6_db_corpus_schema_export():
    # 1. payload 기본 키 검증
    sys_stats = ["HP", "ATK"]
    sys_gimmicks = ["Type"]
    health_stat = "HP"
    target_col = "result"
    battle_size = 2
    log_schema = {
        "entity_id_col": "entity_id",
        "team_col": "team"
    }
    
    session_state_like = {
        "combat_flow": "sequential",
        "speed_stat": "SPD",
        "global_damage_formula": "30",
        "sim_max_turns": 50,
        "move_library": {"Hit": {"power": 40}},
        "resource_config": {"MP": {"max": 10}},
        "damage_type_map": {"Normal": 1.0},
        "game_config": {"preserve_ids": False, "test_key": "test_val"},
        "range_stat": "RNG",
        "move_stat": "MOV"
    }

    payload = _build_db_corpus_schema_payload(
        sys_stats, sys_gimmicks, health_stat, target_col, battle_size, log_schema, session_state_like
    )

    assert payload["schema_version"] == "db_corpus_backtest.v1"
    assert payload["generated_from"] == "step6_dashboard"
    assert payload["system_stats"] == sys_stats
    assert payload["system_gimmicks"] == sys_gimmicks
    assert payload["health_stat"] == health_stat
    assert payload["target_col"] == target_col
    assert payload["battle_size"] == battle_size
    assert payload["log_schema"] == log_schema
    assert payload["combat_flow"] == "sequential"
    assert payload["speed_stat"] == "SPD"
    assert payload["global_damage_formula"] == "30"
    assert payload["sim_max_turns"] == 50
    assert payload["move_library"] == {"Hit": {"power": 40}}
    assert payload["resource_config"] == {"MP": {"max": 10}}
    assert payload["damage_type_map"] == {"Normal": 1.0}
    assert payload["range_stat"] == "RNG"
    assert payload["move_stat"] == "MOV"

    # 2. preserve_ids 보정 검증
    # session_state_like["game_config"]["preserve_ids"] was False originally
    # but log_schema has "entity_id_col", so payload["game_config"]["preserve_ids"] should be True
    assert payload["game_config"]["preserve_ids"] is True
    assert payload["game_config"]["test_key"] == "test_val"
    # 원본 game_config는 변경되지 않아야 함
    assert session_state_like["game_config"]["preserve_ids"] is False

    # 3. JSON 직렬화 검증 (numpy/pandas types)
    session_state_like_with_np = dict(session_state_like)
    session_state_like_with_np["speed_stat"] = np.int64(42)
    session_state_like_with_np["global_damage_formula"] = pd.NA
    session_state_like_with_np["range_stat"] = float('nan')
    session_state_like_with_np["move_stat"] = (1, 2, 3)

    payload_np = _build_db_corpus_schema_payload(
        sys_stats, sys_gimmicks, health_stat, target_col, battle_size, log_schema, session_state_like_with_np
    )

    try:
        json_str = json.dumps(payload_np, ensure_ascii=False)
    except Exception as e:
        assert False, f"JSON serialization failed: {e}"

    loaded_payload = json.loads(json_str)
    assert loaded_payload["speed_stat"] == 42
    assert loaded_payload["global_damage_formula"] is None
    assert loaded_payload["range_stat"] is None
    assert loaded_payload["move_stat"] == [1, 2, 3]

    # 4. entity id가 없을 때 보정 없음 검증
    log_schema_no_entity = {
        "team_col": "team"
    }
    payload_no_entity = _build_db_corpus_schema_payload(
        sys_stats, sys_gimmicks, health_stat, target_col, battle_size, log_schema_no_entity, session_state_like
    )
    # preserve_ids should remain whatever it was in session_state (False)
    assert payload_no_entity["game_config"]["preserve_ids"] is False

    print("All step6 db corpus schema export tests passed.")

if __name__ == "__main__":
    test_step6_db_corpus_schema_export()
