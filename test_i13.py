import ast
from pathlib import Path
for p in ["modules/engine.py", "modules/per_battle_backtest.py", "modules/step6_dashboard.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")

from modules.engine import _worker_simulate_match

ally = [{
    "id": "A1", "name": "A1", "HP": 100, "SPD": 1,
    "resources": {
        "HP": {"current": 100, "max": 100},
        "MP": {"current": 8, "max": 10},
    },
}]
enemy = [{
    "id": "E1", "name": "E1", "HP": 100, "SPD": 2,
    "resources": {
        "HP": {"current": 100, "max": 100},
        "Shield": {"current": 12, "max": 20},
    },
}]
gc = {
    "preserve_ids": True,
    "_expected_state_snapshots": {
        1: {
            "A1": {"resources": {"MP": 8.0}},
            "E1": {"resources": {"Shield": 12.0}},
        }
    },
    "_state_score_config": {
        "hp_mode": "absolute",
        "hp_tol": 0.0,
        "resource_names": ["MP", "Shield"],
        "resource_mode": "absolute",
        "resource_tol": 0.0,
    },
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "0",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["state_score"]
assert score["resource_checks"] == 2
assert score["resource_mismatches"] == 0
assert score["accuracy"] == 1.0
print("resource state score perfect match OK")

ally = [{
    "id": "A1", "name": "A1", "HP": 100, "SPD": 1,
    "resources": {
        "HP": {"current": 100, "max": 100},
        "MP": {"current": 8, "max": 10},
    },
}]
enemy = [{
    "id": "E1", "name": "E1", "HP": 100, "SPD": 2,
    "resources": {"HP": {"current": 100, "max": 100}},
}]
gc = {
    "preserve_ids": True,
    "_expected_state_snapshots": {
        1: {
            "A1": {"resources": {"MP": 7.0}},
        }
    },
    "_state_score_config": {
        "resource_names": ["MP"],
        "resource_mode": "absolute",
        "resource_tol": 0.0,
    },
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "0",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["state_score"]
assert score["resource_checks"] == 1
assert score["resource_mismatches"] == 1
assert score["first_mismatch"]["kind"] == "resource"
assert score["first_mismatch"]["resource"] == "MP"
print("resource state mismatch detection OK")

ally = [{
    "id": "A1", "name": "A1", "HP": 100, "SPD": 1,
    "resources": {
        "HP": {"current": 100, "max": 100},
        "MP": {"current": 8, "max": 10},
    },
}]
enemy = [{
    "id": "E1", "name": "E1", "HP": 100, "SPD": 2,
    "resources": {"HP": {"current": 100, "max": 100}},
}]
gc = {
    "preserve_ids": True,
    "_expected_state_snapshots": {
        1: {"A1": {"resources": {"MP": 80.0}}}
    },
    "_state_score_config": {
        "resource_names": ["MP"],
        "resource_mode": "percent",
        "resource_tol": 0.0,
    },
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "0",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
assert res[1]["state_score"]["accuracy"] == 1.0
print("resource percent mode OK")

import pandas as pd
from modules.per_battle_backtest import build_state_snapshots_from_group, build_battles

df = pd.DataFrame([
    {"turn": 1, "unit": "A1", "mp_after": 8, "shield_after": 0},
    {"turn": 1, "unit": "E1", "mp_after": 0, "shield_after": 12},
])
schema = {
    "state_trace_enabled": True,
    "state_turn_col": "turn",
    "state_entity_id_col": "unit",
    "state_resource_cols": {"MP": "mp_after", "Shield": "shield_after"},
}
snap = build_state_snapshots_from_group(df, schema)
print(snap)
assert snap[1]["A1"]["resources"]["MP"] == 8.0
assert snap[1]["E1"]["resources"]["Shield"] == 12.0
print("state resource snapshot builder OK")

df = pd.DataFrame([
    {"battle": "B1", "team": "Ally", "unit": "A1", "result": 1,
     "HP": 100, "SPD": 1, "MP": 10, "turn": 1, "mp_after": 8},
    {"battle": "B1", "team": "Enemy", "unit": "E1", "result": 0,
     "HP": 100, "SPD": 2, "MP": 0, "turn": 1, "mp_after": 0},
])
schema = {
    "battle_id_col": "battle",
    "team_col": "team",
    "entity_id_col": "unit",
    "result_mode": "battle_level",
    "ally_values": ["Ally"],
    "enemy_values": ["Enemy"],
    "state_trace_enabled": True,
    "state_turn_col": "turn",
    "state_entity_id_col": "unit",
    "state_resource_cols": {"MP": "mp_after"},
    "state_resource_mode": "absolute",
    "state_resource_tolerance": 0.0,
}
battles = build_battles(
    df, 2, "result", ["HP", "SPD", "MP"], [], "HP",
    resource_config={
        "HP": {"role": "vital", "stat": "HP", "regen": 0.0},
        "MP": {"role": "pool", "stat": "MP", "regen": 0.0},
    },
    max_battles=10,
    game_config={"preserve_ids": True},
    log_schema=schema,
)
print(battles)
assert len(battles) == 1
assert len(battles[0]) == 4
gc = battles[0][3]
assert gc["_expected_state_snapshots"][1]["A1"]["resources"]["MP"] == 8.0
assert gc["_state_score_config"]["resource_names"] == ["MP"]
assert gc["_state_score_config"]["resource_tol"] == 0.0
print("build_battles resource state config OK")

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 1,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 2,
          "resources": {"HP": {"current": 100, "max": 100}}}]
gc = {
    "preserve_ids": True,
    "_expected_state_snapshots": {
        1: {
            "A1": {"hp": 100.0, "fainted": False},
            "E1": {"hp": 100.0, "fainted": False},
        }
    },
    "_state_score_config": {"hp_mode": "absolute", "hp_tol": 0.0},
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "0",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["state_score"]
assert score["missing"] == 0
assert score["accuracy"] == 1.0
print("legacy HP state score regression OK")

from pathlib import Path
src = Path("modules/step6_dashboard.py").read_text(encoding="utf-8")
assert "state_resource_cols" in src
assert "state_resource_mode" in src
assert "state_resource_tolerance" in src
assert "resource_mismatches" in src
print("step6 state resource source guard OK")
