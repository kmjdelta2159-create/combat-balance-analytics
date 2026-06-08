import sys
from modules.mechanism_detect import detect_mechanisms, canonical_mechanism_key
from modules.mechanism_commit import infer_conditions

# Test A - detect row sources 보존
trace_a = {
    "nick2species": {"P1": "Mon"},
    "events": [
        {"turn": 1, "action": "env", "src": "Hail", "who": "P1", "kind": "damage", "delta": -10, "max": 160},
    ],
}

class FakeRefA:
    EFFECTS = {}

res_a = detect_mechanisms(trace_a, FakeRefA)
hail_row = None
for r in res_a:
    if r['class'] == 'weather' and r['name'] == 'hail':
        hail_row = r
        break

assert hail_row is not None, "weather/hail should be detected"
assert "Hail" in hail_row.get("sources", []), "sources should contain original 'Hail'"


# Test B - infer_conditions accepts original and canonical
class FakeRefB:
    SPECIES_TYPES = {"Mon": ("Normal", "")}
    SETS = {}

trace_b = {
    "nick2species": {"P1": "Mon", "P2": "Mon2"},
    "events": [
        {"turn": 1, "action": "switch", "actor": "P1", "actor_side": "P1"},
        {"turn": 1, "action": "switch", "actor": "P2", "actor_side": "P2"},
        {"turn": 1, "action": "env", "src": "Hail", "who": "P1", "kind": "damage", "delta": -10, "max": 160},
    ],
}

cond_orig = infer_conditions(trace_b, FakeRefB, "Hail")
cond_canon = infer_conditions(trace_b, FakeRefB, "hail")

assert cond_orig['spared'] == cond_canon['spared'], "Spared should be identical"
assert cond_orig['not_ability_hint'] == cond_canon['not_ability_hint'], "not_ability_hint should be identical"
assert cond_orig['not_types_hint'] == cond_canon['not_types_hint'], "not_types_hint should be identical"
assert "Mon2" in cond_orig['spared'], "Mon2 should be spared"


# Test C - decision lookup helper (simulating what run_mechcommit does)
def _index_detected(rows):
    det = {}
    for r in rows:
        det[r['name']] = r
        det[(r["class"], r["name"])] = r
        for src in r.get("sources", []):
            det[canonical_mechanism_key(src)] = r
    return det

def _lookup_detected(det, src):
    src_key = canonical_mechanism_key(src)
    return det.get(src_key) or det.get(src)

rows_c = [{"class": "weather", "name": "hail", "sources": ["Hail"]}]
det_c = _index_detected(rows_c)

row_by_orig = _lookup_detected(det_c, "Hail")
row_by_canon = _lookup_detected(det_c, "hail")

assert row_by_orig is not None and row_by_orig['name'] == 'hail', "Should lookup by original src 'Hail'"
assert row_by_canon is not None and row_by_canon['name'] == 'hail', "Should lookup by canonical name 'hail'"


# Test D - explicit class mode
assert canonical_mechanism_key("item", "Leftovers") == ("item", "Leftovers"), "Explicit item should preserve class and name"
assert canonical_mechanism_key("ability", "Poison Heal") == ("ability", "Poison Heal"), "Explicit ability should preserve class and name"
assert canonical_mechanism_key("move", "Brave Bird") == ("move", "Brave Bird"), "Explicit move should preserve name"
assert canonical_mechanism_key("move", "recoil") == ("move", "Recoil"), "recoil should be normalized to Recoil for explicit move"
assert canonical_mechanism_key("hazard", "spikes") == ("hazard", "Spikes"), "hazard aliases should apply in explicit mode"
assert canonical_mechanism_key("weather", "Hail") == ("weather", "hail"), "weather aliases should apply in explicit mode"
assert canonical_mechanism_key("status", "badly poisoned") == ("status", "tox"), "status aliases should apply in explicit mode"
assert canonical_mechanism_key("item: Leftovers") == ("item", "Leftovers"), "Raw src prefix item: should work"
assert canonical_mechanism_key("ability: Poison Heal") == ("ability", "Poison Heal"), "Raw src prefix ability: should work"

print("All mechanism commit canonical tests passed.")
