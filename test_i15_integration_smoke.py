import ast
import pandas as pd
from pathlib import Path
from modules.engine import _worker_simulate_match
from modules.resource import ResourceModule
from modules.per_battle_backtest import build_battles

def test_syntax():
    for p in ["modules/engine.py", "modules/per_battle_backtest.py", "modules/step6_dashboard.py", "test_i15_integration_smoke.py"]:
        ast.parse(Path(p).read_text(encoding="utf-8"))
    print("Syntax OK")

def test_scenario_a_and_b():
    ally = [
        {"id": "A1", "name": "A1", "HP": 100, "SPD": 999, "resources": {"HP": {"current": 100, "max": 100}}},
        {"id": "A2", "name": "A2", "HP": 100, "SPD": 1, "resources": {"HP": {"current": 100, "max": 100}}}
    ]
    enemy = [
        {"id": "E1", "name": "E1", "HP": 100, "SPD": 50, "resources": {"HP": {"current": 100, "max": 100}, "Shield": {"current": 20, "max": 20}}},
        {"id": "E2", "name": "E2", "HP": 100, "SPD": 10, "resources": {"HP": {"current": 100, "max": 100}}}
    ]
    
    rm = ResourceModule({
        "HP": {"role": "vital", "stat": "HP", "regen": 0.0},
        "Shield": {"role": "shield", "stat": "Shield", "regen": 0.0},
    })
    
    gc_base = {
        "preserve_ids": True,
        "preserve_initial_on_field": True,
        "trace_actions": {
            "move": {(1, "A1"): {"move": {"name": "Attack", "priority": 1}, "target": "E1"}},
            "switch": {}
        },
        "_expected_action_damage_trace": [
            {"turn": 1, "actor": "A1", "target": "E1", "hp_delta": 30.0}
        ],
        "_action_damage_score_config": {
            "damage_tol": 0.0,
            "compare_field": "hp_delta"
        },
        "_expected_action_resource_delta_trace": [
            {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0}
        ],
        "_expected_state_snapshots": {
            1: {"E1": {"hp": 70.0, "resources": {"Shield": 0.0}}}
        },
        "_state_score_config": {
            "hp_mode": "absolute", "hp_tol": 0.0,
            "resource_names": ["Shield"], "resource_mode": "absolute", "resource_tol": 0.0
        }
    }
    
    # Scenario A: strict_extra = False
    gc_a = dict(gc_base)
    gc_a["_action_resource_delta_score_config"] = {
        "delta_tol": 0.0,
        "resource_names": ["Shield"],
        "strict_extra": False
    }
    
    res_a = _worker_simulate_match((ally, enemy, None, "SPD", ["HP", "SPD"], "50", 1, None, rm, None, None, None, None, gc_a, 0))
    assert not isinstance(res_a, str), f"Worker error: {res_a}"
    metrics_a = res_a[1]
    
    ad_score = metrics_a["action_damage_score"]
    assert ad_score["accuracy"] == 1.0, f"Expected damage accuracy 1.0, got {ad_score['accuracy']}"
    
    ard_score = metrics_a["action_resource_delta_score"]
    assert ard_score["accuracy"] == 1.0, f"Expected resource delta accuracy 1.0, got {ard_score['accuracy']}"
    assert ard_score["extra"] == 0, f"Expected 0 extra, got {ard_score['extra']}"
    
    st_score = metrics_a["state_score"]
    assert st_score["accuracy"] == 1.0, f"Expected state score accuracy 1.0, got {st_score['accuracy']}"
    
    print("Scenario A (strict_extra=False) OK")
    
    # Scenario B: strict_extra = True
    gc_b = dict(gc_base)
    gc_b["_action_resource_delta_score_config"] = {
        "delta_tol": 0.0,
        "resource_names": ["Shield"],
        "strict_extra": True
    }
    
    res_b = _worker_simulate_match((ally, enemy, None, "SPD", ["HP", "SPD"], "50", 1, None, rm, None, None, None, None, gc_b, 0))
    metrics_b = res_b[1]
    
    ard_score_b = metrics_b["action_resource_delta_score"]
    assert ard_score_b["extra"] >= 1, "Expected >= 1 extra resource delta"
    assert ard_score_b["mismatches"] >= 1, "Expected >= 1 mismatch"
    assert ard_score_b["first_mismatch"]["kind"] == "extra_action_resource_delta", f"Unexpected mismatch kind: {ard_score_b['first_mismatch']}"
    
    print("Scenario B (strict_extra=True) OK")

def test_scenario_c():
    df = pd.DataFrame([
        {
            "battle": "B1", "team": "Ally", "unit": "A1", "result": 1, 
            "HP": 100, "SPD": 999, "turn": 1, "actor": "A1", "target": "E1", 
            "hp_loss": 30, "shield_loss": 20, "event": "damage", "on_field": 1,
            "move_name": "Attack"
        },
        {
            "battle": "B1", "team": "Enemy", "unit": "E1", "result": 0, 
            "HP": 100, "SPD": 50, "turn": 1, "actor": "A1", "target": "E1", 
            "hp_loss": 30, "shield_loss": 20, "event": "damage", "on_field": 1,
            "move_name": "Attack"
        },
    ])
    
    schema = {
        "battle_id_col": "battle",
        "team_col": "team",
        "entity_id_col": "unit",
        "result_mode": "battle_level",
        "ally_values": ["Ally"],
        "enemy_values": ["Enemy"],
        
        "initial_on_field_enabled": True,
        "initial_on_field_col": "on_field",
        "initial_on_field_values": ["1"],
        
        "trace_moves_enabled": True,
        "turn_col": "turn",
        "actor_id_col": "actor",
        "target_id_col": "target",
        "move_name_col": "move_name",
        
        "damage_trace_enabled": True,
        "damage_turn_col": "turn",
        "damage_actor_id_col": "actor",
        "damage_target_id_col": "target",
        "damage_value_col": "hp_loss",
        "damage_action_col": "event",
        "damage_action_values": ["damage"],
        "damage_value_kind": "hp_delta",
        
        "resource_delta_trace_enabled": True,
        "resource_delta_turn_col": "turn",
        "resource_delta_actor_id_col": "actor",
        "resource_delta_target_id_col": "target",
        "resource_delta_cols": {"Shield": "shield_loss"},
        "resource_delta_action_col": "event",
        "resource_delta_action_values": ["damage"],
        "resource_delta_strict_extra": False,
        
        "state_trace_enabled": True,
        "state_turn_col": "turn",
        "state_entity_id_col": "unit",
        "state_hp_col": "HP",
        "state_resource_cols": {"Shield": "shield_loss"},
    }
    
    battles = build_battles(df, 2, "result", ["HP", "SPD"], [], "HP", max_battles=10, game_config={"preserve_ids": True}, log_schema=schema)
    assert len(battles) == 1
    
    gc = battles[0][3]
    assert gc.get("preserve_ids") is True
    assert gc.get("preserve_initial_on_field") is True
    
    assert "_expected_action_damage_trace" in gc
    assert "_expected_action_resource_delta_trace" in gc
    assert "_expected_state_snapshots" in gc
    
    rd_cfg = gc.get("_action_resource_delta_score_config", {})
    assert rd_cfg.get("resource_names") == ["Shield"]
    assert rd_cfg.get("strict_extra") is False
    
    trace_actions = gc.get("trace_actions", {})
    assert "move" in trace_actions
    
    print("Scenario C (build_battles integration) OK")

from modules.engine import run_simulation

def test_scenario_d_and_e():
    ally_d = [
        {"id": "A1", "name": "A1", "HP": 100, "SPD": 999, "resources": {"HP": {"current": 100, "max": 100}}},
        {"id": "A2", "name": "A2", "HP": 100, "SPD": 1, "resources": {"HP": {"current": 100, "max": 100}}}
    ]
    enemy_d = [
        {"id": "E1", "name": "E1", "HP": 100, "SPD": 50, "resources": {"HP": {"current": 100, "max": 100}}}
    ]
    gc_d = {
        "preserve_ids": True,
        "preserve_initial_on_field": True,
        "trace_actions": {
            "move": {},
            "switch": {(1, "A1"): "A2"},
        },
    }
    
    winner_d, logs_d, metrics_d = run_simulation(ally_d, enemy_d, max_turns=1, speed_stat="SPD", sys_stats=["HP", "SPD"], global_damage_formula="50", silent=False, game_config=gc_d)
    
    switch_log_found = any("교체" in msg or "switch" in msg.lower() for msg in logs_d)
    a1_in_log = any("A1" in msg for msg in logs_d)
    a2_in_log = any("A2" in msg for msg in logs_d)
    
    assert switch_log_found and a1_in_log and a2_in_log, "Scenario D: Switch logs not found"
    
    ally_e = [
        {"id": "A1", "name": "A1", "HP": 100, "SPD": 999, "resources": {"HP": {"current": 100, "max": 100}}}
    ]
    enemy_e = [
        {"id": "E1", "name": "E1", "HP": 10, "SPD": 50, "resources": {"HP": {"current": 10, "max": 10}}, "on_field": True},
        {"id": "E2", "name": "E2", "HP": 100, "SPD": 10, "resources": {"HP": {"current": 100, "max": 100}}, "on_field": False}
    ]
    gc_e = {
        "preserve_ids": True,
        "preserve_initial_on_field": True,
        "trace_actions": {
            "move": {(1, "A1"): {"move": {"name": "KO", "priority": 0}, "target": "E1"}},
            "switch": {},
        },
        "trace_faint_incoming": [
            {"turn": 1, "side": "Enemy", "outgoing": "E1", "incoming": "E2"},
        ],
        "on_active_faint": "replace_from_reserve",
    }
    
    final_e_parts = []
    def _turn_cb_e(ctx):
        final_e_parts.extend(ctx.get("participants", []))
        
    winner_e, logs_e, metrics_e = run_simulation(ally_e, enemy_e, max_turns=1, speed_stat="SPD", sys_stats=["HP", "SPD"], global_damage_formula="999", silent=False, game_config=gc_e, on_turn_end=_turn_cb_e)
    
    e1_p = next((p for p in final_e_parts if p["id"] == "E1"), None)
    e1_hp_current = e1_p.get("resources", {}).get("HP", {}).get("current", e1_p.get("HP", 0)) if e1_p else 100
    e1_faint_or_zero = e1_p and (e1_hp_current <= 0 or e1_p.get("fainted", False))
    assert e1_faint_or_zero, "Scenario E: E1 should be fainted or 0 HP"
    
    e2_in_log = any("E2" in msg for msg in logs_e)
    switch_in_log = any("교체" in msg or "진입" in msg or "switch" in msg.lower() or "replace" in msg.lower() for msg in logs_e)
    assert e2_in_log and switch_in_log, "Scenario E: Faint incoming logs not found"
    
    print("Scenario D (switch trace) OK")
    print("Scenario E (faint incoming) OK")

def test_scenario_f():
    df = pd.DataFrame([
        {
            "battle": "B1", "team": "Ally", "unit": "A1", "result": 1, 
            "HP": 100, "SPD": 999, "turn": 1, "actor": "A1", "target": "E1", 
            "event": "damage", "on_field": 1,
            "move_name": "KO"
        },
        {
            "battle": "B1", "team": "Ally", "unit": "A2", "result": 1, 
            "HP": 100, "SPD": 1, "turn": 1, "actor": "A1", "target": "E1", 
            "event": "damage", "on_field": 0,
            "move_name": "KO"
        },
        {
            "battle": "B1", "team": "Enemy", "unit": "E1", "result": 0, 
            "HP": 10, "SPD": 50, "turn": 1, "actor": "A1", "target": "E1", 
            "event": "damage", "on_field": 1,
            "move_name": "KO"
        },
        {
            "battle": "B1", "team": "Enemy", "unit": "E2", "result": 0, 
            "HP": 100, "SPD": 10, "turn": 1, "actor": "A1", "target": "E1", 
            "event": "damage", "on_field": 0,
            "move_name": "KO"
        },
        {
            "battle": "B1", "team": "", "unit": "", "result": 1, 
            "HP": 0, "SPD": 0, "turn": 1, "actor": "A1", "target": "", 
            "event": "switch", "on_field": 0,
            "move_name": "", "outgoing": "A1", "incoming": "A2", "side": "Ally"
        },
        {
            "battle": "B1", "team": "", "unit": "", "result": 0, 
            "HP": 0, "SPD": 0, "turn": 1, "actor": "", "target": "", 
            "event": "faint_replace", "on_field": 0,
            "move_name": "", "outgoing": "E1", "incoming": "E2", "side": "Enemy"
        },
    ])
    
    schema = {
        "battle_id_col": "battle",
        "team_col": "team",
        "entity_id_col": "unit",
        "result_mode": "battle_level",
        "ally_values": ["Ally"],
        "enemy_values": ["Enemy"],
        
        "trace_switches_enabled": True,
        "switch_turn_col": "turn",
        "switch_outgoing_id_col": "outgoing",
        "switch_incoming_id_col": "incoming",
        "switch_action_col": "event",
        "switch_action_values": ["switch"],
        
        "trace_faint_incoming_enabled": True,
        "faint_turn_col": "turn",
        "faint_side_col": "side",
        "faint_outgoing_id_col": "outgoing",
        "faint_incoming_id_col": "incoming",
        "faint_action_col": "event",
        "faint_action_values": ["faint_replace"],
    }
    
    battles = build_battles(df, 4, "result", ["HP", "SPD"], [], "HP", max_battles=10, game_config={"preserve_ids": True}, log_schema=schema)
    assert len(battles) == 1
    
    gc = battles[0][3]
    
    assert gc.get("trace_actions", {}).get("switch", {}).get((1, "A1")) == "A2", "Scenario F: Switch trace not built correctly"
    
    faint_incoming = gc.get("trace_faint_incoming", [])
    found_faint = any(f.get("turn") == 1 and f.get("outgoing") == "E1" and f.get("incoming") == "E2" for f in faint_incoming)
    assert found_faint, "Scenario F: Faint incoming trace not built correctly"
    
    assert gc.get("on_active_faint") == "replace_from_reserve", "Scenario F: on_active_faint not set correctly"
    
    print("Scenario F (build_battles switch/faint) OK")

if __name__ == "__main__":
    test_syntax()
    test_scenario_a_and_b()
    test_scenario_c()
    test_scenario_d_and_e()
    test_scenario_f()
    print("All smoke tests passed!")
