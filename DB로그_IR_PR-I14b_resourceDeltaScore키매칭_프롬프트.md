# DB로그 IR PR-I14b — action resource delta score key matching 보정

## 배경

PR-I14의 `action_resource_delta_score` 본체는 붙었다.

확인된 정상 동작:

- `APPLY_DAMAGE`에서 `damage_result["resource_deltas"]`가 생성된다.
- Shield가 먼저 흡수하고 HP가 남은 피해를 받는 케이스를 캡처한다.
- worker가 `_expected_action_resource_delta_trace`를 받아 score를 만든다.
- `per_battle_backtest` builder와 Step6 UI/source 연결도 들어갔다.

하지만 score helper에 실제 채점 결함이 있다.

현재 `_score_action_resource_delta_for_worker(expected, actual, ...)`는 expected/actual을 key로 정렬한 뒤 같은 index끼리 비교한다. 이 방식은 expected가 actual의 부분집합일 때 오탐한다.

예:

```python
expected = [
    {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0}
]
actual = [
    {"turn": 1, "actor": "A1", "target": "E1", "resource": "HP", "delta": 30.0},
    {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0},
]
```

올바른 결과:

- Shield는 Shield와 매칭되어 delta mismatch 없음
- HP는 extra event 1건

현재 결과:

- expected Shield가 actual HP와 비교되어 identity/delta mismatch가 발생
- HP는 extra로도 잡힘

이 PR은 score helper를 **identity key 기반 매칭**으로 고친다.

## 수정 대상

가능하면 아래 파일만 수정한다.

- `modules/engine.py`

Step6/per_battle builder는 건드리지 않아도 된다.

## 수정 요구

### 1. `_score_action_resource_delta_for_worker`를 key 기반으로 변경

identity key:

```python
(turn, actor, target, resource)
```

권장 구현:

```python
def _norm_key(e):
    return (
        int(e.get("turn") or 0),
        str(e.get("actor") or ""),
        str(e.get("target") or ""),
        str(e.get("resource") or ""),
    )
```

actual을 multimap으로 만든다.

```python
actual_by_key = {}
for a in actual:
    actual_by_key.setdefault(_norm_key(a), []).append(a)
```

expected를 순회하며 같은 key의 actual event를 하나 소비한다.

```python
for exp in expected:
    checks += 1
    key = _norm_key(exp)
    bucket = actual_by_key.get(key) or []
    if not bucket:
        missing += 1
        mismatches += 1
        ...
        continue
    act = bucket.pop(0)
    ...
```

남은 actual event는 extra로 센다.

```python
leftover = [a for bucket in actual_by_key.values() for a in bucket]
extra = len(leftover)
checks += extra
mismatches += extra
```

### 2. delta mismatch와 identity mismatch 의미 정리

권장 의미:

- `delta_mismatches`: 같은 key는 찾았지만 delta 값이 다른 경우
- `missing`: expected key가 actual에 없는 경우
- `extra`: expected에 없는 actual key/event가 남은 경우
- `identity_mismatches`: index 비교식 identity mismatch는 더 이상 쓰지 않는다. key matching에서는 0으로 유지하거나, missing+extra를 identity_mismatches로 더해도 된다.

추천은 다음이다.

- key mismatch는 `missing`/`extra`로 충분히 표현한다.
- `identity_mismatches`는 0 또는 legacy 호환 필드로 유지한다.

중요한 것은 Shield expected가 actual HP와 비교되어 `delta_mismatches`를 만들면 안 된다는 점이다.

### 3. first_mismatch 보강

현재 helper는 extra만 있는 경우 `first_mismatch`가 `None`일 수 있다.

남은 extra actual이 있고 아직 `first_mismatch`가 없다면 다음 형태로 채운다.

```python
first_mismatch = {
    "turn": extra_event.get("turn"),
    "id": extra_event.get("actor"),
    "kind": "extra_action_resource_delta",
    "resource": extra_event.get("resource"),
    "expected": None,
    "actual": extra_event.get("delta"),
    "actual_full": extra_event,
}
```

missing의 first mismatch:

```python
{
    "turn": exp.get("turn"),
    "id": exp.get("actor"),
    "kind": "missing_action_resource_delta",
    "resource": exp.get("resource"),
    "expected": exp.get("delta"),
    "actual": None,
    "expected_full": exp,
}
```

delta mismatch:

```python
{
    "turn": exp.get("turn"),
    "id": exp.get("actor"),
    "kind": "action_resource_delta",
    "resource": exp.get("resource"),
    "expected": exp_val,
    "actual": act_val,
    "expected_full": exp,
    "actual_full": act,
}
```

### 4. 기존 완전 매칭 동작 유지

expected에 HP+Shield가 모두 있고 actual에도 HP+Shield가 있으면 기존처럼 `accuracy == 1.0`이어야 한다.

I14의 builder, UI, capture 로직은 건드리지 않는다.

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

### B. helper partial expected matching

expected가 Shield만 요구하고 actual이 HP+Shield를 갖는 경우, Shield는 정상 매칭되고 HP만 extra여야 한다.

```powershell
@'
from modules.engine import _score_action_resource_delta_for_worker

expected = [
    {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0}
]
actual = [
    {"turn": 1, "actor": "A1", "target": "E1", "resource": "HP", "delta": 30.0},
    {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0},
]
score = _score_action_resource_delta_for_worker(expected, actual, delta_tol=0.0)
print(score)
assert score["delta_mismatches"] == 0
assert score["missing"] == 0
assert score["extra"] == 1
assert score["mismatches"] == 1
assert score["first_mismatch"]["kind"] == "extra_action_resource_delta"
assert score["first_mismatch"]["resource"] == "HP"
print("partial expected resource delta matching OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### C. helper order-insensitive perfect match

```powershell
@'
from modules.engine import _score_action_resource_delta_for_worker

expected = [
    {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0},
    {"turn": 1, "actor": "A1", "target": "E1", "resource": "HP", "delta": 30.0},
]
actual = [
    {"turn": 1, "actor": "A1", "target": "E1", "resource": "HP", "delta": 30.0},
    {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0},
]
score = _score_action_resource_delta_for_worker(expected, actual, delta_tol=0.0)
print(score)
assert score["checks"] == 2
assert score["mismatches"] == 0
assert score["accuracy"] == 1.0
print("order-insensitive resource delta matching OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### D. helper same-key delta mismatch

```powershell
@'
from modules.engine import _score_action_resource_delta_for_worker

expected = [
    {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 10.0}
]
actual = [
    {"turn": 1, "actor": "A1", "target": "E1", "resource": "HP", "delta": 30.0},
    {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0},
]
score = _score_action_resource_delta_for_worker(expected, actual, delta_tol=0.0)
print(score)
assert score["delta_mismatches"] == 1
assert score["extra"] == 1
assert score["first_mismatch"]["kind"] == "action_resource_delta"
assert score["first_mismatch"]["resource"] == "Shield"
assert score["first_mismatch"]["expected"] == 10.0
assert score["first_mismatch"]["actual"] == 20.0
print("same-key resource delta mismatch OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### E. worker partial expected matching

전투 실제 결과가 HP+Shield delta를 모두 만들지만 expected는 Shield만 제공하는 경우, Shield는 맞고 HP만 extra여야 한다.

```powershell
@'
from modules.engine import _worker_simulate_match
from modules.resource import ResourceModule

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 30, "SPD": 1,
          "resources": {
              "HP": {"current": 30, "max": 30},
              "Shield": {"current": 20, "max": 20},
          }}]
rm = ResourceModule({
    "HP": {"role": "vital", "stat": "HP", "regen": 0.0},
    "Shield": {"role": "shield", "stat": "Shield", "regen": 0.0},
})
gc = {
    "preserve_ids": True,
    "_expected_action_resource_delta_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0},
    ],
    "_action_resource_delta_score_config": {"delta_tol": 0.0},
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, rm, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["action_resource_delta_score"]
assert score["delta_mismatches"] == 0
assert score["missing"] == 0
assert score["extra"] == 1
assert score["first_mismatch"]["kind"] == "extra_action_resource_delta"
assert score["first_mismatch"]["resource"] == "HP"
print("worker partial resource delta matching OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### F. I14 full perfect match 유지

```powershell
@'
from modules.engine import _worker_simulate_match
from modules.resource import ResourceModule

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 30, "SPD": 1,
          "resources": {
              "HP": {"current": 30, "max": 30},
              "Shield": {"current": 20, "max": 20},
          }}]
rm = ResourceModule({
    "HP": {"role": "vital", "stat": "HP", "regen": 0.0},
    "Shield": {"role": "shield", "stat": "Shield", "regen": 0.0},
})
gc = {
    "preserve_ids": True,
    "_expected_action_resource_delta_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "resource": "HP", "delta": 30.0},
        {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0},
    ],
    "_action_resource_delta_score_config": {"delta_tol": 0.0},
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, rm, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["action_resource_delta_score"]
assert score["checks"] == 2
assert score["mismatches"] == 0
assert score["accuracy"] == 1.0
print("I14 full resource delta score still OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### G. 기존 I13 resource state score 회귀

```powershell
@'
from modules.engine import _worker_simulate_match

ally = [{
    "id": "A1", "name": "A1", "HP": 100, "SPD": 1,
    "resources": {"HP": {"current": 100, "max": 100}, "MP": {"current": 8, "max": 10}},
}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 2,
          "resources": {"HP": {"current": 100, "max": 100}}}]
gc = {
    "preserve_ids": True,
    "_expected_state_snapshots": {1: {"A1": {"resources": {"MP": 8.0}}}},
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
assert res[1]["state_score"]["accuracy"] == 1.0
print("I13 resource state score still OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

## 금지/주의

- I14의 capture, builder, Step6 UI를 갈아엎지 않는다.
- `_worker_simulate_match` args tuple 구조를 바꾸지 않는다.
- `action_damage_score`, `state_score`, `damage_result` 의미를 바꾸지 않는다.
- resource delta가 expected의 부분집합일 수 있다는 전제를 지킨다.

