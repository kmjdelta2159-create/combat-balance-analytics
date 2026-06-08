import ast
from pathlib import Path
for p in ["modules/engine.py", "modules/per_battle_backtest.py", "modules/step6_dashboard.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")

from modules.engine import run_simulation

events = []

def on_phase(pk, ctx, targets):
    if pk != "APPLY_DAMAGE":
        return
    dr = ctx.get("damage_result") or {}
    target_list = targets if isinstance(targets, list) else [targets]
    for t in target_list:
        events.append({
            "turn": ctx.get("turn"),
            "actor": ctx["active_char"]["id"],
            "target": t["id"],
            "damage": dr.get("damage"),
            "hp_before": dr.get("hp_before"),
            "hp_after": dr.get("hp_after"),
            "hp_delta": dr.get("hp_delta"),
        })

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 30, "SPD": 1,
          "resources": {"HP": {"current": 30, "max": 30}}}]

run_simulation(
    ally, enemy, max_turns=1,
    speed_stat="SPD", sys_stats=["HP", "SPD"],
    global_damage_formula="50",
    game_config={"preserve_ids": True},
    on_phase_event=on_phase,
    silent=True,
)

print(events)
assert len(events) == 1
e = events[0]
assert e["damage"] == 50
assert e["hp_before"] == 30
assert e["hp_after"] == 0
assert e["hp_delta"] == 30
print("damage_result overkill split OK")

from modules.engine import _worker_simulate_match

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 30, "SPD": 1,
          "resources": {"HP": {"current": 30, "max": 30}}}]
gc = {
    "preserve_ids": True,
    "_expected_action_damage_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "damage": 50.0}
    ],
    "_action_damage_score_config": {"damage_tol": 0.0},
}

res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["action_damage_score"]
assert score["accuracy"] == 1.0
assert score["damage_mismatches"] == 0
print("default damage compare mode OK")

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 30, "SPD": 1,
          "resources": {"HP": {"current": 30, "max": 30}}}]
gc = {
    "preserve_ids": True,
    "_expected_action_damage_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "hp_delta": 30.0}
    ],
    "_action_damage_score_config": {"damage_tol": 0.0, "compare_field": "hp_delta"},
}

res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["action_damage_score"]
assert score["accuracy"] == 1.0
assert score["damage_mismatches"] == 0
print("hp_delta compare mode OK")

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 30, "SPD": 1,
          "resources": {"HP": {"current": 30, "max": 30}}}]
gc = {
    "preserve_ids": True,
    "_expected_action_damage_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "hp_delta": 50.0}
    ],
    "_action_damage_score_config": {"damage_tol": 0.0, "compare_field": "hp_delta"},
}

res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["action_damage_score"]
assert score["accuracy"] < 1.0
assert score["damage_mismatches"] == 1
assert score["first_mismatch"]["field"] == "hp_delta"
print("hp_delta mismatch detection OK")

import pandas as pd
from modules.per_battle_backtest import build_battles, build_action_damage_trace_from_group

df = pd.DataFrame([
    {"battle": "B1", "team": "Ally", "unit": "A1", "result": 1, "HP": 100, "SPD": 999,
     "turn": 1, "actor": "A1", "target": "E1", "hp_loss": 30, "event": "damage"},
    {"battle": "B1", "team": "Enemy", "unit": "E1", "result": 0, "HP": 30, "SPD": 1,
     "turn": 1, "actor": "A1", "target": "E1", "hp_loss": 30, "event": "damage"},
])
schema = {
    "battle_id_col": "battle",
    "team_col": "team",
    "entity_id_col": "unit",
    "result_mode": "battle_level",
    "ally_values": ["Ally"],
    "enemy_values": ["Enemy"],
    "damage_trace_enabled": True,
    "damage_turn_col": "turn",
    "damage_actor_id_col": "actor",
    "damage_target_id_col": "target",
    "damage_value_col": "hp_loss",
    "damage_value_kind": "hp_delta",
    "damage_action_col": "event",
    "damage_action_values": ["damage"],
    "damage_tolerance": 0.0,
}

trace = build_action_damage_trace_from_group(df, schema)
print(trace)
assert trace[0]["hp_delta"] == 30.0

battles = build_battles(
    df, 2, "result", ["HP", "SPD"], [], "HP",
    max_battles=10,
    game_config={"preserve_ids": True},
    log_schema=schema,
)
print(battles)
gc = battles[0][3]
assert gc["_expected_action_damage_trace"][0]["hp_delta"] == 30.0
assert gc["_action_damage_score_config"]["compare_field"] == "hp_delta"
print("per_battle hp_delta mode OK")

from pathlib import Path
src = Path("modules/step6_dashboard.py").read_text(encoding="utf-8")
assert "damage_value_kind" in src
assert "hp_delta" in src
assert "damage_tolerance" in src
assert "action_damage_score" in src
print("step6 damage value kind source guard OK")
