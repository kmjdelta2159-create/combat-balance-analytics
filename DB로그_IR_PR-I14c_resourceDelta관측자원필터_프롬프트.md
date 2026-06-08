# DB로그 IR PR-I14c — action resource delta 관측 자원 필터

## 배경

PR-I14b로 `action_resource_delta_score`는 `(turn, actor, target, resource)` key 기반 매칭이 됐다.

하지만 실제 DB 로그에서는 모든 resource delta가 항상 기록되지 않는다.

예:

- DB에는 `shield_loss`만 있음
- 엔진은 같은 공격에서 `Shield -20`, `HP -30`을 모두 만든다
- 사용자는 Step6에서 Shield 컬럼만 매핑했다

이 경우 현재 worker는 actual resource delta로 HP+Shield를 모두 캡처하고, expected에는 Shield만 있으므로 HP를 `extra`로 벌점 처리한다.

부분 관측 DB 로그에서는 이것이 너무 엄격하다. 사용자가 매핑한 resource만 score 대상으로 삼고, 매핑하지 않은 resource delta는 기본적으로 무시해야 한다.

이 PR은 `action_resource_delta_score`에 **관측 resource filter**를 추가한다.

## 목표

`resource_delta_cols`로 사용자가 매핑한 resource만 actual capture/score 대상으로 삼는다.

기본 동작:

- expected에 Shield만 있으면 actual HP delta는 score에서 무시
- expected에 HP+Shield가 있으면 둘 다 채점
- 명시적으로 strict mode를 켜면 예전처럼 expected 밖 actual resource도 extra로 볼 수 있음

## 수정 대상

가능하면 아래 3개 파일만 수정한다.

- `modules/engine.py`
- `modules/per_battle_backtest.py`
- `modules/step6_dashboard.py`

## 구현 요구

### 1. score config에 resource_names 추가

`modules/per_battle_backtest.py`의 `build_battles_from_log_schema()`에서 `_action_resource_delta_score_config`에 observed resource names를 넣는다.

현재:

```python
battle_gc["_action_resource_delta_score_config"] = {
    "delta_tol": float(log_schema.get("resource_delta_tolerance", 0.0) or 0.0),
}
```

변경:

```python
_rd_cols = log_schema.get("resource_delta_cols") or {}
battle_gc["_action_resource_delta_score_config"] = {
    "delta_tol": float(log_schema.get("resource_delta_tolerance", 0.0) or 0.0),
    "resource_names": [str(x) for x in _rd_cols.keys()],
    "strict_extra": bool(log_schema.get("resource_delta_strict_extra", False)),
}
```

의미:

- `resource_names`: DB에서 관측/매핑한 resource 목록
- `strict_extra`: `False` 기본. 관측하지 않은 resource delta는 무시

### 2. worker actual_resource_delta capture 필터

`modules/engine.py`의 `_worker_simulate_match()`에서:

```python
expected_resource_delta = ...
resource_delta_cfg = ...
actual_resource_delta = []
```

아래 값을 만든다.

```python
observed_resource_names = {
    str(x) for x in (resource_delta_cfg.get("resource_names") or [])
}
strict_resource_extra = bool(resource_delta_cfg.get("strict_extra", False))
```

`_capture_phase()`에서 `resource_deltas`를 펼칠 때:

```python
for rname, delta in (dr.get("resource_deltas") or {}).items():
    rname_s = str(rname)
    if observed_resource_names and not strict_resource_extra and rname_s not in observed_resource_names:
        continue
    ...
```

의도:

- config에 resource_names가 있고 strict_extra가 False면 관측 resource만 actual에 넣는다.
- resource_names가 없으면 기존처럼 전부 캡처한다. 직접 `_worker_simulate_match` 테스트/legacy 호환용.
- strict_extra가 True면 기존처럼 전부 캡처한다.

### 3. score helper에도 optional guard 추가

캡처 단계에서 대부분 해결되지만, helper 단독 사용/미래 호출 안전성을 위해 `_score_action_resource_delta_for_worker(...)`에도 optional 인자를 추가한다.

권장 시그니처:

```python
def _score_action_resource_delta_for_worker(
    expected, actual, delta_tol=0.0, resource_names=None, strict_extra=False
):
```

helper 내부에서 actual을 multimap에 넣기 전:

```python
observed = {str(x) for x in (resource_names or [])}
for a in actual:
    if observed and not strict_extra and str(a.get("resource") or "") not in observed:
        continue
    actual_by_key.setdefault(_norm_key(a), []).append(a)
```

worker 호출부:

```python
sim_metrics["action_resource_delta_score"] = _score_action_resource_delta_for_worker(
    expected_resource_delta,
    actual_resource_delta,
    delta_tol=float(resource_delta_cfg.get("delta_tol", 0.0) or 0.0),
    resource_names=resource_delta_cfg.get("resource_names") or [],
    strict_extra=bool(resource_delta_cfg.get("strict_extra", False)),
)
```

### 4. Step6 UI에 strict extra 옵션 추가

`modules/step6_dashboard.py`의 resource delta trace score UI에 checkbox 추가.

권장:

```python
_bb_resource_delta_strict_extra = st.checkbox(
    "관측하지 않은 resource delta도 extra로 벌점",
    value=False,
    help="꺼두면 매핑한 resource 컬럼만 score 대상으로 삼습니다."
)
```

schema update에 포함:

```python
"resource_delta_strict_extra": bool(_bb_resource_delta_strict_extra),
```

주의:

- 기본값은 `False`.
- checkbox가 꺼져 있어도 변수 스코프가 안전해야 한다.

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

### B. helper observed resource filter

Shield만 관측 대상으로 주면 actual HP extra는 무시되어야 한다.

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
score = _score_action_resource_delta_for_worker(
    expected, actual, delta_tol=0.0,
    resource_names=["Shield"], strict_extra=False,
)
print(score)
assert score["checks"] == 1
assert score["mismatches"] == 0
assert score["extra"] == 0
assert score["accuracy"] == 1.0
print("observed resource filter helper OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### C. helper strict extra preserves old behavior

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
score = _score_action_resource_delta_for_worker(
    expected, actual, delta_tol=0.0,
    resource_names=["Shield"], strict_extra=True,
)
print(score)
assert score["extra"] == 1
assert score["mismatches"] == 1
assert score["first_mismatch"]["kind"] == "extra_action_resource_delta"
assert score["first_mismatch"]["resource"] == "HP"
print("strict extra helper OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### D. worker observed resource filter

전투 실제 결과는 HP+Shield delta를 만들지만, score config가 Shield만 관측 대상으로 주면 완전 일치해야 한다.

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
    "_action_resource_delta_score_config": {
        "delta_tol": 0.0,
        "resource_names": ["Shield"],
        "strict_extra": False,
    },
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, rm, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["action_resource_delta_score"]
assert score["checks"] == 1
assert score["mismatches"] == 0
assert score["extra"] == 0
assert score["accuracy"] == 1.0
print("worker observed resource filter OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### E. worker strict extra mode

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
    "_action_resource_delta_score_config": {
        "delta_tol": 0.0,
        "resource_names": ["Shield"],
        "strict_extra": True,
    },
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, rm, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["action_resource_delta_score"]
assert score["extra"] == 1
assert score["mismatches"] == 1
assert score["first_mismatch"]["resource"] == "HP"
print("worker strict resource extra OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### F. build_battles score config includes observed resources

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_battles

df = pd.DataFrame([
    {"battle": "B1", "team": "Ally", "unit": "A1", "result": 1, "HP": 100, "SPD": 999,
     "turn": 1, "actor": "A1", "target": "E1", "shield_loss": 20, "event": "damage"},
    {"battle": "B1", "team": "Enemy", "unit": "E1", "result": 0, "HP": 30, "SPD": 1,
     "turn": 1, "actor": "A1", "target": "E1", "shield_loss": 20, "event": "damage"},
])
schema = {
    "battle_id_col": "battle",
    "team_col": "team",
    "entity_id_col": "unit",
    "result_mode": "battle_level",
    "ally_values": ["Ally"],
    "enemy_values": ["Enemy"],
    "resource_delta_trace_enabled": True,
    "resource_delta_turn_col": "turn",
    "resource_delta_actor_id_col": "actor",
    "resource_delta_target_id_col": "target",
    "resource_delta_cols": {"Shield": "shield_loss"},
    "resource_delta_action_col": "event",
    "resource_delta_action_values": ["damage"],
    "resource_delta_tolerance": 0.0,
    "resource_delta_strict_extra": False,
}
battles = build_battles(
    df, 2, "result", ["HP", "SPD"], [], "HP",
    max_battles=10,
    game_config={"preserve_ids": True},
    log_schema=schema,
)
print(battles)
gc = battles[0][3]
cfg = gc["_action_resource_delta_score_config"]
assert cfg["resource_names"] == ["Shield"]
assert cfg["strict_extra"] is False
print("build_battles observed resource config OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### G. Step6 source guard

```powershell
@'
from pathlib import Path
src = Path("modules/step6_dashboard.py").read_text(encoding="utf-8")
assert "resource_delta_strict_extra" in src
assert "관측하지 않은 resource delta" in src or "strict_extra" in src
assert "resource_delta_cols" in src
print("step6 resource delta strict source guard OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### H. I14b full matching still OK

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
print("I14b full matching still OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

## 금지/주의

- `action_resource_delta_score`의 full expected 매칭을 깨지 않는다.
- `action_damage_score`, `state_score`, `damage_result` 의미를 바꾸지 않는다.
- `ResourceModule.route_damage()` 동작은 건드리지 않는다.
- 기본값은 부분 관측 로그 친화적으로 `strict_extra=False`.

