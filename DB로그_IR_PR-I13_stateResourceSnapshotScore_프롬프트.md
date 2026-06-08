# DB로그 IR PR-I13 — state snapshot arbitrary resource score

## 목표

현재 `state snapshot score`는 HP/status/fainted 중심이다. 하지만 최종 목표는 포켓몬 하나가 아니라 JRPG, 가챠, SRPG, 덱빌더까지 포함하는 **스탯 기반 턴제 게임 복제**다.

이 범위에서는 HP 외에도 다음과 같은 자원이 전투 상태의 핵심이다.

- Shield / Barrier
- MP / SP / Energy
- Action gauge / Cost
- Armor / Block
- 기타 `resource_config`에 정의된 임의 자원

이 PR은 state snapshot trace에 **임의 resource current 값**을 추가해, DB 로그의 비-HP 자원 상태도 엔진 상태와 비교할 수 있게 한다.

## 수정 대상

가능하면 아래 3개 파일만 수정한다.

- `modules/engine.py`
- `modules/per_battle_backtest.py`
- `modules/step6_dashboard.py`

## 설계 요약

기존 expected state snapshot:

```python
{
    1: {
        "A1": {"hp": 90.0, "status": "poison", "fainted": False}
    }
}
```

확장 후:

```python
{
    1: {
        "A1": {
            "hp": 90.0,
            "status": "poison",
            "fainted": False,
            "resources": {
                "MP": 8.0,
                "Shield": 12.0
            }
        }
    }
}
```

기존 `hp`는 그대로 유지한다. arbitrary resources는 `resources` nested dict로만 추가한다.

## 구현 요구

### 1. engine snapshot에 resource_names 지원

`modules/engine.py`의 `_snapshot_for_worker(...)`를 확장한다.

권장 시그니처:

```python
def _snapshot_for_worker(participants, hp_mode="absolute",
                         resource_names=None, resource_mode="absolute"):
```

동작:

- 기존 `hp`, `status`, `fainted` 동작은 유지한다.
- `resource_names`가 있으면 각 참가자 snapshot에 `"resources"` dict를 추가한다.
- 각 resource current 값을 읽는다.
- `resource_mode == "percent"`면 `current / max * 100`으로 저장한다.
- `max <= 0`이면 1.0으로 간주한다.
- 값은 기존 HP처럼 `round(value, 4)` 정도로 정리한다.

예시:

```python
extra_resources = {}
for rname in resource_names or []:
    res = (p.get("resources") or {}).get(rname)
    if not res:
        continue
    cur = float(res.get("current", 0.0) or 0.0)
    if resource_mode == "percent":
        mx = float(res.get("max", 1.0) or 1.0)
        if mx <= 0:
            mx = 1.0
        val = round((cur / mx) * 100.0, 4)
    else:
        val = round(cur, 4)
    extra_resources[str(rname)] = val
if extra_resources:
    snap[pid]["resources"] = extra_resources
```

`_worker_simulate_match()`의 `_capture_state()`에서 `_state_score_config`를 읽어 전달한다.

```python
resource_names=state_cfg.get("resource_names") or [],
resource_mode=state_cfg.get("resource_mode", "absolute"),
```

### 2. state score에 resource 비교 추가

`_score_state_snapshots_for_worker(...)`를 확장한다.

권장 시그니처:

```python
def _score_state_snapshots_for_worker(expected, actual, hp_tol=0.0, resource_tol=0.0):
```

기존 metrics는 유지하고 아래 metrics를 추가한다.

- `resource_checks`
- `resource_mismatches`

동작:

- `exp_state`에 `"resources"` dict가 있으면 각 resource name을 비교한다.
- actual에 해당 resource가 없으면 mismatch로 본다.
- `abs(expected - actual) > resource_tol`이면 mismatch.
- `checks`와 `mismatches`에도 반영한다.
- `first_mismatch`에는 `kind: "resource"`와 `resource` 이름을 포함한다.

예시 first mismatch:

```python
{
    "turn": 1,
    "id": "A1",
    "kind": "resource",
    "resource": "MP",
    "expected": 8.0,
    "actual": 7.0
}
```

worker 호출부:

```python
sim_metrics["state_score"] = _score_state_snapshots_for_worker(
    expected_state,
    actual_state,
    hp_tol=float(state_cfg.get("hp_tol", 0.0) or 0.0),
    resource_tol=float(state_cfg.get("resource_tol", 0.0) or 0.0),
)
```

주의:

- 기존 I9/I10 state score 테스트가 그대로 통과해야 한다.
- expected에 resources가 없으면 기존 metrics와 거의 동일해야 한다. 단 return dict에 `resource_checks: 0`, `resource_mismatches: 0`이 추가되는 것은 허용한다.

### 3. per_battle_backtest state snapshot builder 확장

`modules/per_battle_backtest.py`의 `build_state_snapshots_from_group()`에 resource columns를 추가한다.

schema 키:

```python
"state_resource_cols": {
    "MP": "mp_after",
    "Shield": "shield_after"
}
```

동작:

- `state_resource_cols`는 dict로 처리한다.
- 해당 컬럼이 있고 값이 비어 있지 않으면 float 변환해 `state_entry["resources"][resource_name]`에 저장한다.
- HP/status/fainted 컬럼이 없어도 resource column이 하나라도 있으면 snapshot을 생성해야 한다.

현재 guard가 이런 형태라면:

```python
if not hp_col and not status_col and not fainted_col:
    return {}
```

아래처럼 확장한다.

```python
resource_cols = log_schema.get("state_resource_cols") or {}
if not hp_col and not status_col and not fainted_col and not resource_cols:
    return {}
```

`build_battles_from_log_schema()`에서 `_state_score_config`에 추가한다.

```python
"resource_names": list((log_schema.get("state_resource_cols") or {}).keys()),
"resource_mode": log_schema.get("state_resource_mode", "absolute"),
"resource_tol": float(log_schema.get("state_resource_tolerance", 0.0) or 0.0),
```

주의:

- 기존 `state_hp_mode`, `state_hp_tolerance`는 그대로 유지한다.
- resource snapshot만 있는 경우에도 `filtered_state`가 생성되어 battle_gc에 들어가야 한다.

### 4. Step6 UI에 resource state mapping 추가

`modules/step6_dashboard.py`의 `관측 상태 trace (선택)` expander 안에 추가한다.

권장 UI:

```python
_bb_state_resource_cols = {}
_resource_config_for_state = st.session_state.get("resource_config") or {}
_resource_names_for_state = [
    r for r in _resource_config_for_state.keys()
    if str(r) != "HP"
]
_bb_state_resource_names = st.multiselect(
    "state resource 컬럼 추가",
    _resource_names_for_state,
    default=[],
    help="HP 외 MP/Shield/Cost 등 임의 자원의 관측 current 값을 비교합니다."
)
for _rname in _bb_state_resource_names:
    _guess = _guess_col([str(_rname).lower(), str(_rname), f"{_rname}_after", f"{_rname}_current"])
    _col = st.selectbox(
        f"state {_rname} 컬럼",
        _all_cols,
        index=_all_cols.index(_guess) if _guess in _all_cols else 0,
        key=f"bb_state_resource_col_{_rname}",
    )
    if _col != "(없음)":
        _bb_state_resource_cols[str(_rname)] = _col
```

추가 옵션:

```python
_bb_state_resource_mode = st.selectbox(
    "state resource mode",
    ["absolute", "percent"],
    index=0,
    key="bb_state_resource_mode",
)
_bb_state_resource_tol = st.number_input(
    "resource 허용 오차",
    min_value=0.0,
    value=0.0,
    step=1.0,
    key="bb_state_resource_tol",
)
```

주의:

- `_bb_state_resource_cols`는 `_st_use`가 꺼진 경우에도 참조 오류가 나지 않게 기본값을 미리 둔다.
- resource_config가 없거나 HP밖에 없으면 UI는 조용히 비어 있거나 안내 caption 정도만 둔다.
- 이 작업은 HP 기존 selectbox를 제거하지 않는다.

schema update:

```python
"state_resource_cols": dict(_bb_state_resource_cols),
"state_resource_mode": _bb_state_resource_mode,
"state_resource_tolerance": float(_bb_state_resource_tol),
```

state trace 유효성:

기존에는 HP/status/fainted 중 하나 이상이 필요했다. 이제는 resource column만 있어도 유효해야 한다.

```python
elif (
    _bb_state_hp_col == "(없음)"
    and _bb_state_status_col == "(없음)"
    and _bb_state_fainted_col == "(없음)"
    and not _bb_state_resource_cols
):
    st.warning(...)
```

### 5. Step6 결과 집계에 resource mismatch 추가

state score 집계 UI에 resource mismatch를 포함한다.

기존:

```python
_s_hp_miss = ...
_s_st_miss = ...
_s_ft_miss = ...
```

추가:

```python
_s_res_miss = sum(int(s.get("resource_mismatches", 0) or 0) for s in _bb_state_scores)
```

표시:

- 기존 3개 metric을 유지해도 되고, 4개 columns로 늘려도 된다.
- 최소한 caption이나 metric으로 `resource 불일치`가 보여야 한다.

## 수용 조건

### A. AST

```powershell
@'
import ast
from pathlib import Path
for p in ["modules/engine.py", "modules/per_battle_backtest.py", "modules/step6_dashboard.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### B. worker resource state score perfect match

```powershell
@'
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
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### C. worker resource mismatch detection

```powershell
@'
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
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### D. worker resource percent mode

```powershell
@'
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
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### E. build_state_snapshots_from_group resource-only

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_state_snapshots_from_group

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
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### F. build_battles DB path includes resource state config

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_battles

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
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### G. 기존 HP state score 회귀

```powershell
@'
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
print(res)
assert not isinstance(res, str)
score = res[1]["state_score"]
assert score["missing"] == 0
assert score["accuracy"] == 1.0
print("legacy HP state score regression OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### H. Step6 source guard

```powershell
@'
from pathlib import Path
src = Path("modules/step6_dashboard.py").read_text(encoding="utf-8")
assert "state_resource_cols" in src
assert "state_resource_mode" in src
assert "state_resource_tolerance" in src
assert "resource_mismatches" in src
print("step6 state resource source guard OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

## 금지/주의

- 기존 HP/status/fainted state score를 깨지 않는다.
- `resources` nested dict는 expected에 있을 때만 채점한다.
- engine의 resource 시스템 구조를 갈아엎지 않는다.
- resource current snapshot만 다룬다. resource 소비 원인, 회복 원인, 비용 지불 trace까지 확장하지 않는다.
- `action_damage_score`와 `hp_delta` 비교 모드는 건드리지 않는다.

