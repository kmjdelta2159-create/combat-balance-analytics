import ast
from pathlib import Path
for p in ["modules/engine.py", "modules/per_battle_backtest.py", "modules/step6_dashboard.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")

from modules.engine import run_simulation

events = []
def on_phase(pk, ctx, targets):
    if pk == "APPLY_DAMAGE":
        target_list = targets if isinstance(targets, list) else [targets]
        for t in target_list:
            events.append((ctx.get("turn"), ctx["active_char"]["id"], t["id"], ctx.get("dmg")))

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 50, "SPD": 1,
          "resources": {"HP": {"current": 50, "max": 50}}}]

run_simulation(
    ally, enemy, max_turns=1,
    speed_stat="SPD", sys_stats=["HP", "SPD"],
    global_damage_formula="50",
    game_config={"preserve_ids": True},
    on_phase_event=on_phase,
    silent=True,
)
print(events)
assert events == [(1, "A1", "E1", 50)]
print("phase callback damage capture OK")

from modules.engine import _worker_simulate_match

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 50, "SPD": 1,
          "resources": {"HP": {"current": 50, "max": 50}}}]
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
assert score["checks"] == 1
assert score["mismatches"] == 0
assert score["missing"] == 0
assert score["extra"] == 0
assert score["accuracy"] == 1.0
print("worker action damage score OK")

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 50, "SPD": 1,
          "resources": {"HP": {"current": 50, "max": 50}}}]
gc = {
    "preserve_ids": True,
    "_expected_action_damage_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "damage": 50.0}
    ],
    "_action_damage_score_config": {"damage_tol": 0.0},
    "_expected_state_snapshots": {
        1: {
            "A1": {"hp": 100.0, "fainted": False},
            "E1": {"hp": 0.0, "fainted": True},
        }
    },
    "_state_score_config": {"hp_mode": "absolute", "hp_tol": 0.0},
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
assert res[1]["action_damage_score"]["accuracy"] == 1.0
assert res[1]["state_score"]["accuracy"] == 1.0
print("state + action damage scores coexist OK")

import pandas as pd
from modules.per_battle_backtest import build_action_damage_trace_from_group

df = pd.DataFrame([
    {"battle": "B1", "turn": 1, "actor": "A1", "target": "E1", "dmg": 50, "event": "damage", "ord": 2},
    {"battle": "B1", "turn": 1, "actor": "E1", "target": "A1", "dmg": 10, "event": "note", "ord": 1},
])
schema = {
    "damage_trace_enabled": True,
    "damage_turn_col": "turn",
    "damage_actor_id_col": "actor",
    "damage_target_id_col": "target",
    "damage_value_col": "dmg",
    "damage_action_col": "event",
    "damage_action_values": ["damage"],
    "damage_order_col": "ord",
}
trace = build_action_damage_trace_from_group(df, schema)
print(trace)
assert trace == [{"turn": 1, "actor": "A1", "target": "E1", "damage": 50.0}]
print("damage trace builder OK")

from modules.per_battle_backtest import build_battles

df = pd.DataFrame([
    {"battle": "B1", "team": "Ally", "unit": "A1", "result": 1, "HP": 100, "SPD": 999,
     "turn": 1, "actor": "A1", "target": "E1", "dmg": 50, "event": "damage"},
    {"battle": "B1", "team": "Enemy", "unit": "E1", "result": 0, "HP": 50, "SPD": 1,
     "turn": 1, "actor": "A1", "target": "E1", "dmg": 50, "event": "damage"},
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
    "damage_value_col": "dmg",
    "damage_action_col": "event",
    "damage_action_values": ["damage"],
    "damage_tolerance": 0.0,
}
battles = build_battles(
    df, 2, "result", ["HP", "SPD"], [], "HP",
    max_battles=10,
    game_config={"preserve_ids": True},
    log_schema=schema,
)
print(battles)
assert len(battles) == 1
assert len(battles[0]) == 4
gc = battles[0][3]
assert gc["_expected_action_damage_trace"] == [
    {"turn": 1, "actor": "A1", "target": "E1", "damage": 50.0}
]
assert gc["_action_damage_score_config"]["damage_tol"] == 0.0
print("build_battles action damage trace OK")

src = Path("modules/step6_dashboard.py").read_text(encoding="utf-8")
assert "damage_trace_enabled" in src
assert "action_damage_score" in src
assert "_bb_action_damage_scores" in src
assert "damage_tolerance" in src
print("step6 action damage score source guard OK")
