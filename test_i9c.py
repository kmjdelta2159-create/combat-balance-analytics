import ast
from pathlib import Path
for p in ["modules/turn_manager.py", "modules/engine.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")

from modules.engine import _worker_simulate_match

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 1,
          "resources": {"HP": {"current": 100, "max": 100}}}]
gc = {
    "preserve_ids": True,
    "_expected_state_snapshots": {
        1: {
            "A1": {"hp": 100.0, "fainted": False},
            "E1": {"hp": 0.0, "fainted": True},
        }
    },
    "_state_score_config": {"hp_mode": "absolute", "hp_tol": 0.0},
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "999",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["state_score"]
assert score["missing"] == 0
assert score["mismatches"] == 0
assert score["accuracy"] == 1.0
print("terminal-turn state capture OK")

ally2 = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 1,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy2 = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 2,
          "resources": {"HP": {"current": 100, "max": 100}}}]
gc2 = {
    "preserve_ids": True,
    "_expected_state_snapshots": {
        1: {
            "A1": {"hp": 100.0, "fainted": False},
            "E1": {"hp": 100.0, "fainted": False},
        }
    },
    "_state_score_config": {"hp_mode": "absolute", "hp_tol": 0.0},
}
res2 = _worker_simulate_match((
    ally2, enemy2, None, "SPD", ["HP", "SPD"], "0",
    1, None, None, None, None, None, None, gc2, 0
))
print(res2)
assert not isinstance(res2, str)
score2 = res2[1]["state_score"]
assert score2["missing"] == 0
assert score2["mismatches"] == 0
assert score2["accuracy"] == 1.0
print("non-terminal state capture regression OK")

from modules.engine import run_simulation

captures = []
def cb(ctx):
    captures.append((ctx.get("turn"), ctx["active_char"]["id"]))

ally3 = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 1,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy3 = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 2,
          "resources": {"HP": {"current": 100, "max": 100}}}]
run_simulation(
    ally3, enemy3, max_turns=1,
    speed_stat="SPD",
    sys_stats=["HP", "SPD"],
    global_damage_formula="0",
    game_config={"preserve_ids": True},
    on_turn_end=cb,
    silent=True,
)
print(captures)
assert captures == [(1, "E1"), (1, "A1")]
print("turn_end callback count OK")
