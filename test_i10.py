import ast
from pathlib import Path
for p in ["modules/step6_dashboard.py", "modules/engine.py", "modules/per_battle_backtest.py"]:
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
            "A1": {"hp": 50.0, "fainted": False},
            "E1": {"hp": 50.0, "fainted": False},
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
score = res[1]["state_score"]
assert score["missing"] == 0
assert score["mismatches"] == 0
assert score["accuracy"] == 1.0
print("deterministic state score OK")

from modules.engine import default_stochasticity_factory

res2 = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, default_stochasticity_factory, None, None, None, None, None, gc, 0
))
print(res2)
assert not isinstance(res2, str)
score2 = res2[1]["state_score"]
assert score2["hp_mismatches"] > 0
assert score2["accuracy"] < 1.0
print("stochastic variance can affect state score: confirmed")

src = Path("modules/step6_dashboard.py").read_text(encoding="utf-8")
assert "state_score_deterministic" in src
assert "default_stochasticity_factory" in src
assert "_bb_stochasticity_factory" in src or "_select_backtest_stochasticity_factory" in src
print("step6 stochasticity selection source guard OK")
