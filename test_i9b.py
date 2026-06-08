import ast
from pathlib import Path

for p in ["modules/step6_dashboard.py", "modules/per_battle_backtest.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")

src = Path("modules/step6_dashboard.py").read_text(encoding="utf-8")
assert "_bb_state_scores = []" in src
assert "_bb_state_scores.append" in src
assert "state_score" in src
print("Step6 state_score collection source OK")

from modules.engine import _worker_simulate_match

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
assert not isinstance(res, str)
assert res[1]["state_score"]["accuracy"] == 1.0
print("worker state_score regression OK")

import pandas as pd
from modules.per_battle_backtest import build_state_snapshots_from_group

df = pd.DataFrame([
    {"turn": 1, "unit_id": "A1", "hp_after": 90},
])
schema = {
    "state_trace_enabled": True,
    "turn_col": "turn",
    "entity_id_col": "unit_id",
    "state_hp_col": "hp_after",
}
snaps = build_state_snapshots_from_group(df, schema)
print(snaps)
assert snaps[1]["A1"]["hp"] == 90.0
print("state snapshot fallback OK")
