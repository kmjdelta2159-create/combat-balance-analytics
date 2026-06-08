import ast
from pathlib import Path
for p in ["modules/engine.py", "modules/per_battle_backtest.py", "modules/step6_dashboard.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")

from modules.engine import run_simulation

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 1,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 2,
          "resources": {"HP": {"current": 100, "max": 100}}}]

winner, logs, metrics = run_simulation(
    ally, enemy, max_turns=1,
    speed_stat="SPD", sys_stats=["HP", "SPD"],
    global_damage_formula="0",
    game_config={"preserve_ids": True},
    silent=True,
)
print(winner, metrics)
assert isinstance(metrics, dict)
assert metrics["damage_count"] == 2
print("run_simulation without on_phase_event OK")

from modules.engine import _worker_simulate_match

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 1,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 2,
          "resources": {"HP": {"current": 100, "max": 100}}}]

res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "0",
    1, None, None, None, None, None, None, {"preserve_ids": True}, 0
))
print(res)
assert not (isinstance(res, str) and res.startswith("ERROR:"))
assert res[1]["damage_count"] == 2
print("worker without expected action damage OK")

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
assert not (isinstance(res, str) and res.startswith("ERROR:"))
assert res[1]["state_score"]["accuracy"] == 1.0
print("state-only worker after I11 OK")

events = []

def on_phase(pk, ctx, targets):
    events.append(pk)

def on_turn_end(ctx):
    events.append("TURN_END_CB")

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 1,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 2,
          "resources": {"HP": {"current": 100, "max": 100}}}]

run_simulation(
    ally, enemy, max_turns=1,
    speed_stat="SPD", sys_stats=["HP", "SPD"],
    global_damage_formula="0",
    game_config={"preserve_ids": True},
    on_phase_event=on_phase,
    on_turn_end=on_turn_end,
    silent=True,
)

print(events)
assert events.count("APPLY_DAMAGE") == 2
assert events.count("TURN_END") == 2
assert events.count("TURN_END_CB") == 2
print("phase + turn_end callback count OK")

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
assert res[1]["action_damage_score"]["accuracy"] == 1.0
print("I11 action damage score still OK")
