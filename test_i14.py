import ast
from pathlib import Path
for p in ["modules/engine.py", "modules/per_battle_backtest.py", "modules/step6_dashboard.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")

from modules.engine import run_simulation, _worker_simulate_match
from modules.resource import ResourceModule

events = []
def on_phase(pk, ctx, targets):
    if pk != "APPLY_DAMAGE":
        return
    events.append(ctx.get("damage_result") or {})

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999, "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 1, "resources": {"HP": {"current": 100, "max": 100}, "Shield": {"current": 20, "max": 20}}}]
rm = ResourceModule({"HP": {"role": "vital", "stat": "HP", "regen": 0.0}, "Shield": {"role": "shield", "stat": "Shield", "regen": 0.0}})

run_simulation(ally, enemy, max_turns=1, speed_stat="SPD", sys_stats=["HP", "SPD"], global_damage_formula="50", game_config={"preserve_ids": True}, resource_module=rm, on_phase_event=on_phase, silent=True)
print(events)
assert len(events) >= 1
dr = events[0]
assert dr["resource_deltas"]["Shield"] == 20
assert dr["resource_deltas"]["HP"] == 30
assert dr["hp_delta"] == 30
assert dr["absorbed"] == 20
print("damage_result resource_deltas OK")

gc = {
    "preserve_ids": True,
    "_expected_action_resource_delta_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "resource": "HP", "delta": 30.0},
        {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0},
        {"turn": 1, "actor": "E1", "target": "A1", "resource": "HP", "delta": 50.0},
    ],
    "_action_resource_delta_score_config": {"delta_tol": 0.0},
}
res = _worker_simulate_match((ally, enemy, None, "SPD", ["HP", "SPD"], "50", 1, None, rm, None, None, None, None, gc, 0))
score = res[1]["action_resource_delta_score"]
assert score["checks"] == 3
assert score["mismatches"] == 0
assert score["accuracy"] == 1.0
print("worker action resource delta score OK")

gc = {
    "preserve_ids": True,
    "_expected_action_resource_delta_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "resource": "HP", "delta": 30.0},
        {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 10.0},
        {"turn": 1, "actor": "E1", "target": "A1", "resource": "HP", "delta": 50.0},
    ],
    "_action_resource_delta_score_config": {"delta_tol": 0.0},
}
res = _worker_simulate_match((ally, enemy, None, "SPD", ["HP", "SPD"], "50", 1, None, rm, None, None, None, None, gc, 0))
score = res[1]["action_resource_delta_score"]
assert score["mismatches"] > 0
assert score["delta_mismatches"] == 1
assert score["first_mismatch"]["resource"] == "Shield"
print("worker action resource delta mismatch OK")

gc = {
    "preserve_ids": True,
    "_expected_action_damage_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "hp_delta": 30.0},
        {"turn": 1, "actor": "E1", "target": "A1", "hp_delta": 50.0},
    ],
    "_action_damage_score_config": {"damage_tol": 0.0, "compare_field": "hp_delta"},
    "_expected_action_resource_delta_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "resource": "HP", "delta": 30.0},
        {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0},
        {"turn": 1, "actor": "E1", "target": "A1", "resource": "HP", "delta": 50.0},
    ],
    "_action_resource_delta_score_config": {"delta_tol": 0.0},
}
res = _worker_simulate_match((ally, enemy, None, "SPD", ["HP", "SPD"], "50", 1, None, rm, None, None, None, None, gc, 0))
assert res[1]["action_damage_score"]["accuracy"] == 1.0
assert res[1]["action_resource_delta_score"]["accuracy"] == 1.0
print("action damage + resource delta scores coexist OK")

import pandas as pd
from modules.per_battle_backtest import build_action_resource_delta_trace_from_group
df = pd.DataFrame([
    {"turn": 1, "actor": "A1", "target": "E1", "hp_loss": 30, "shield_loss": 20, "event": "damage"},
    {"turn": 1, "actor": "A1", "target": "E1", "hp_loss": 30, "shield_loss": 20, "event": "note"},
])
schema = {
    "resource_delta_trace_enabled": True,
    "resource_delta_turn_col": "turn",
    "resource_delta_actor_id_col": "actor",
    "resource_delta_target_id_col": "target",
    "resource_delta_cols": {"HP": "hp_loss", "Shield": "shield_loss"},
    "resource_delta_action_col": "event",
    "resource_delta_action_values": ["damage"],
}
trace = build_action_resource_delta_trace_from_group(df, schema)
assert {"turn": 1, "actor": "A1", "target": "E1", "resource": "HP", "delta": 30.0} in trace
assert {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0} in trace
assert len(trace) == 2
print("resource delta trace builder OK")

from modules.per_battle_backtest import build_battles
df = pd.DataFrame([
    {"battle": "B1", "team": "Ally", "unit": "A1", "result": 1, "HP": 100, "SPD": 999, "turn": 1, "actor": "A1", "target": "E1", "hp_loss": 30, "shield_loss": 20, "event": "damage"},
    {"battle": "B1", "team": "Enemy", "unit": "E1", "result": 0, "HP": 100, "SPD": 1, "turn": 1, "actor": "A1", "target": "E1", "hp_loss": 30, "shield_loss": 20, "event": "damage"},
])
schema = {
    "battle_id_col": "battle",
    "team_col": "team",
    "entity_id_col": "unit",
    "result_mode": "battle_level",
    "ally_values": ["Ally"],
    "enemy_values": ["Enemy"],
    "resource_delta_trace_enabled": True,
    "resource_delta_turn_col": "turn",
    "resource_delta_actor_id_col": "actor",
    "resource_delta_target_id_col": "target",
    "resource_delta_cols": {"HP": "hp_loss", "Shield": "shield_loss"},
    "resource_delta_action_col": "event",
    "resource_delta_action_values": ["damage"],
    "resource_delta_tolerance": 0.0,
}
battles = build_battles(df, 2, "result", ["HP", "SPD"], [], "HP", max_battles=10, game_config={"preserve_ids": True}, log_schema=schema)
assert len(battles) == 1
assert len(battles[0]) == 4
gc = battles[0][3]
assert len(gc["_expected_action_resource_delta_trace"]) == 2
assert gc["_action_resource_delta_score_config"]["delta_tol"] == 0.0
print("build_battles resource delta trace OK")

from pathlib import Path
src = Path("modules/step6_dashboard.py").read_text(encoding="utf-8")
assert "resource_delta_trace_enabled" in src
assert "resource_delta_cols" in src
assert "action_resource_delta_score" in src
assert "_bb_action_resource_delta_scores" in src
print("step6 action resource delta source guard OK")

gc = {
    "preserve_ids": True,
    "_expected_state_snapshots": {1: {"A1": {"resources": {"MP": 8.0}}}},
    "_state_score_config": {"resource_names": ["MP"], "resource_mode": "absolute", "resource_tol": 0.0},
}
ally_mp = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 1, "resources": {"HP": {"current": 100, "max": 100}, "MP": {"current": 8, "max": 10}}}]
enemy_mp = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 2, "resources": {"HP": {"current": 100, "max": 100}}}]
rm_mp = ResourceModule({"HP": {"role": "vital", "stat": "HP", "regen": 0.0}, "MP": {"role": "mana", "stat": "MP", "regen": 0.0}})
res = _worker_simulate_match((ally_mp, enemy_mp, None, "SPD", ["HP", "SPD"], "0", 1, None, rm_mp, None, None, None, None, gc, 0))
print(res[1])
assert res[1]["state_score"]["accuracy"] == 1.0
print("I13 resource state score still OK")
