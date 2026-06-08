import sys
from modules.mechanism_detect import detect_mechanisms, _is_modeled

# Test A - weather alias
class FakeRefWeather:
    EFFECTS = {"sand": {}, "hail": {}}

trace_a = {
    "nick2species": {"P1": "Mon"},
    "events": [
        {"turn": 1, "action": "env", "src": "Sandstorm", "who": "P1", "kind": "damage", "delta": -10, "max": 160},
        {"turn": 2, "action": "env", "src": "Hail", "who": "P1", "kind": "damage", "delta": -10, "max": 160},
    ],
}

res_a = detect_mechanisms(trace_a, FakeRefWeather)
sand_found = False
hail_found = False
for r in res_a:
    if r['class'] == 'weather' and r['name'] == 'sand':
        sand_found = True
        assert r['modeled'], "Sandstorm should be canonicalized to 'sand' and modeled=True"
    if r['class'] == 'weather' and r['name'] == 'hail':
        hail_found = True
        assert r['modeled'], "Hail should be modeled=True"
assert sand_found and hail_found, "Sandstorm and Hail should be detected as weather"


# Test B - status alias
class FakeRefStatus:
    EFFECTS = {"brn": {}, "psn": {}, "tox": {}}

trace_b = {
    "nick2species": {"P1": "Mon"},
    "events": [
        {"turn": 1, "action": "env", "src": "burned", "who": "P1", "kind": "damage", "delta": -10, "max": 160},
        {"turn": 2, "action": "env", "src": "poisoned", "who": "P1", "kind": "damage", "delta": -10, "max": 160},
        {"turn": 3, "action": "env", "src": "badly poisoned", "who": "P1", "kind": "damage", "delta": -10, "max": 160},
    ],
}

res_b = detect_mechanisms(trace_b, FakeRefStatus)
brn_found = False
psn_found = False
tox_found = False
for r in res_b:
    if r['class'] == 'status' and r['name'] == 'brn':
        brn_found = True
        assert r['modeled'], "burned should be canonicalized to 'brn' and modeled=True"
    if r['class'] == 'status' and r['name'] == 'psn':
        psn_found = True
        assert r['modeled'], "poisoned should be canonicalized to 'psn' and modeled=True"
    if r['class'] == 'status' and r['name'] == 'tox':
        tox_found = True
        assert r['modeled'], "badly poisoned should be canonicalized to 'tox' and modeled=True"
assert brn_found and psn_found and tox_found, "burn, poison, tox should be detected as status"


# Test C - registry modeled
class FakeRefRegistry:
    EFFECTS = {}
    RECOIL_MOVES = {"Brave Bird": 1/3}
    FIXED_DAMAGE_MOVES = {"Seismic Toss": 100}

trace_c = {
    "nick2species": {"P1": "Mon"},
    "events": [
        {"turn": 1, "action": "env", "src": "Recoil", "who": "P1", "kind": "damage", "delta": -10, "max": 160},
    ],
}

res_c = detect_mechanisms(trace_c, FakeRefRegistry)
recoil_found = False
for r in res_c:
    if r['class'] == 'move' and r['name'] == 'Recoil':
        recoil_found = True
        assert r['modeled'], "Recoil should be modeled=True when RECOIL_MOVES is not empty"
assert recoil_found, "Recoil should be detected as move"

assert _is_modeled("move", "Brave Bird", FakeRefRegistry), "Brave Bird should be modeled=True"
assert _is_modeled("move", "Seismic Toss", FakeRefRegistry), "Seismic Toss should be modeled=True"


# Test D - hazard substrate
class FakeRefHazard:
    EFFECTS = {}

assert _is_modeled("hazard", "Stealth Rock", FakeRefHazard), "Stealth Rock should be modeled=True"
assert _is_modeled("hazard", "Spikes", FakeRefHazard), "Spikes should be modeled=True"
assert not _is_modeled("hazard", "Toxic Spikes", FakeRefHazard), "Toxic Spikes should be modeled=False"


# Test E - catalog-only false positive 방지
class FakeRefCatalog:
    EFFECTS = {}
    MOVES = {"Wish": (0, "status", None)}
    ITEMS = {"Life Orb": {"atk": 1.3}}

assert not _is_modeled("move", "Wish", FakeRefCatalog), "Wish should be modeled=False if only in MOVES"
assert not _is_modeled("item", "Life Orb", FakeRefCatalog), "Life Orb should be modeled=False if only in ITEMS"


print("All tests passed.")
