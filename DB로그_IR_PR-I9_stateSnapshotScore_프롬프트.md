# DB로그 IR PR-I9 — 관측 상태 스냅샷 점수 연결

## 목적

PR-I3~I8로 DB 로그의 행동 재현 쪽 핵심 연결이 붙었다.

현재 연결된 것:

- 초기 active/on-field
- move trace
- action order → priority
- voluntary switch trace
- faint incoming trace

하지만 Step6 백테스트 점수는 아직 거의 승패 정확도 중심이다.

최종 목표는 전투 로그 기반 복제/역설계이므로, 승패뿐 아니라 “턴별 상태가 맞는가”를 봐야 한다.

이번 PR은 첫 상태 검증층으로, DB 로그의 관측 HP/status/faint 값을 턴별 expected snapshot으로 만들고, 엔진의 턴 종료 snapshot과 비교해 `state_score`를 산출한다.

범위는 작게 잡는다.

- 우선 턴 종료 단위 snapshot만 다룬다.
- HP/status/fainted만 다룬다.
- UI는 DB 역할 컬럼 방식의 optional 설정으로만 추가한다.
- 기존 승패 백테스트는 그대로 유지한다.

## 현재 상태

이미 존재:

- `modules/engine.py`
  - `run_simulation(..., on_turn_end=...)` 콜백을 받을 수 있다.
  - `_worker_simulate_match(...)`가 Step6 백테스트 병렬 worker로 쓰인다.
- `modules/per_battle_backtest.py`
  - DB role schema battle config를 만들 수 있다.
- `modules/step6_dashboard.py`
  - `_worker_simulate_match` 결과에서 winner만 점수화한다.
- `modules/fullbattle_diff.py`
  - replay 전용 snapshot/divergence 유틸이 있으나 DB role schema와는 직접 연결되어 있지 않다.

## 변경 요구

### 1. per_battle_backtest.py — DB observed snapshot IR 추가

#### 1-1. log_schema 확장

다음 optional 키를 추가한다.

```python
"state_trace_enabled": bool,
"state_turn_col": None | str,
"state_entity_id_col": None | str,
"state_hp_col": None | str,
"state_status_col": None | str,
"state_fainted_col": None | str,
"state_hp_mode": "absolute" | "percent",
"state_hp_tolerance": float,
```

기본값:

```python
state_trace_enabled = False
state_turn_col = turn_col 또는 switch_turn_col 또는 faint_turn_col
state_entity_id_col = entity_id_col
state_hp_mode = "absolute"
state_hp_tolerance = 0.0
```

#### 1-2. helper 추가

```python
def build_state_snapshots_from_group(group, log_schema):
    ...
```

반환:

```python
{
    1: {
        "A1": {"hp": 80.0, "status": "poison", "fainted": False},
        "E1": {"hp": 0.0, "fainted": True},
    },
    2: {...},
}
```

동작:

- `state_trace_enabled`가 False면 `{}` 반환
- turn/id 컬럼이 없으면 `{}`
- `state_hp_col`, `state_status_col`, `state_fainted_col` 중 하나도 없으면 `{}`
- turn은 `_coerce_turn(...)`
- id는 `str(...).strip()`
- 같은 `(turn, id)`가 여러 번 나오면 뒤 행이 이긴다.
- hp:
  - 비어 있으면 생략
  - 숫자로 파싱되면 float로 저장
- status:
  - 비어 있으면 생략
  - 문자열로 저장
- fainted:
  - truthy: `1`, `true`, `yes`, `y`, `fainted`, `dead`, `ko`, `down`, `기절`, `쓰러짐`, `사망`
  - falsy: `0`, `false`, `no`, `n`, `alive`, `normal`, `생존`
  - hp가 0이면 fainted가 명시되지 않아도 `fainted=True`를 넣어도 된다.

#### 1-3. participant ID 필터

새 helper:

```python
def _filter_state_snapshots_for_participants(snapshots, participant_ids):
    ...
```

동작:

- snapshot 안의 id가 participant_ids에 있는 것만 남긴다.
- 빈 turn은 제거한다.

#### 1-4. build_battles_from_log_schema(...) 병합

`build_battles_from_log_schema(...)`에서 battle_gc 생성 시 state snapshot도 포함한다.

```python
state_snapshots = {}
if log_schema.get("state_trace_enabled"):
    state_snapshots = build_state_snapshots_from_group(group, log_schema)
```

participant ID가 유니크한 경우:

```python
filtered_state = _filter_state_snapshots_for_participants(state_snapshots, participant_ids)
```

filtered_state가 있으면:

```python
battle_gc["_expected_state_snapshots"] = filtered_state
battle_gc["_state_score_config"] = {
    "hp_mode": log_schema.get("state_hp_mode", "absolute"),
    "hp_tol": float(log_schema.get("state_hp_tolerance", 0.0) or 0.0),
}
```

그리고 `has_battle_gc = True`.

주의:

- `preserve_ids`는 True.
- initial/trace/faint config와 같은 battle_gc에 공존해야 한다.
- state snapshot만 있어도 4튜플 battle을 반환한다.
- `_expected_state_snapshots`와 `_state_score_config`는 엔진 내부 채점용 metadata다. 기존 run_simulation에는 영향 없어야 한다.

### 2. engine.py — worker에서 state_score 계산

`_worker_simulate_match(...)`를 확장한다.

기존 반환 형태는 유지한다.

```python
return (1 if winner == "Ally" else 0, sim_metrics)
```

단, `game_config`에 `_expected_state_snapshots`가 있으면:

1. `on_turn_end` 콜백으로 엔진 snapshot을 캡처한다.
2. 시뮬레이션 후 expected vs actual을 비교한다.
3. 결과를 `sim_metrics["state_score"]`에 넣는다.

#### 2-1. engine snapshot helper

engine.py 안에 worker 근처 helper를 추가한다.

```python
def _status_of_for_worker(p):
    ...

def _snapshot_for_worker(participants, hp_mode="absolute"):
    ...
```

snapshot 형식은 expected와 맞춘다.

```python
{
    "A1": {"hp": 80.0, "status": "poison", "fainted": False}
}
```

HP:

- `resources["HP"]["current"]`
- percent 모드면 `current / max * 100`
- 소수점은 너무 민감하지 않게 `round(..., 4)` 정도로 맞춘다.

status:

- 우선 `p.get("status")`
- 없으면 `active_states`에서 `gate_status` 또는 `status`를 가진 첫 값을 사용

fainted:

- HP current <= 0

#### 2-2. scoring helper

engine.py 안에 추가:

```python
def _score_state_snapshots_for_worker(expected, actual, hp_tol=0.0):
    ...
```

반환 예:

```python
{
    "turns": 3,
    "checks": 12,
    "mismatches": 2,
    "accuracy": 0.8333,
    "hp_checks": 6,
    "hp_mismatches": 1,
    "status_checks": 3,
    "status_mismatches": 0,
    "faint_checks": 3,
    "faint_mismatches": 1,
    "missing": 0,
    "first_mismatch": {"turn": 2, "id": "A1", "kind": "hp", "expected": 40.0, "actual": 55.0},
}
```

규칙:

- expected에 있는 것만 검사한다.
- actual에 id가 없으면 `missing += 1`, mismatch로 센다.
- expected에 hp가 있으면 hp check
- expected에 status가 있으면 status check
- expected에 fainted가 있으면 faint check
- HP는 `abs(expected - actual) > hp_tol`이면 mismatch
- `checks == 0`이면 accuracy는 0.0

#### 2-3. _worker_simulate_match(...) 연결

```python
expected_state = (game_config or {}).get("_expected_state_snapshots")
state_cfg = (game_config or {}).get("_state_score_config") or {}
actual_state = {}

def _capture_state(ctx):
    actual_state[ctx.get("turn")] = _snapshot_for_worker(
        ctx["participants"],
        hp_mode=state_cfg.get("hp_mode", "absolute"),
    )
```

`expected_state`가 있으면 `run_simulation(..., on_turn_end=_capture_state)`로 호출한다.

시뮬레이션 후:

```python
if expected_state:
    sim_metrics["state_score"] = _score_state_snapshots_for_worker(
        expected_state, actual_state, hp_tol=float(state_cfg.get("hp_tol", 0.0) or 0.0)
    )
```

주의:

- `_worker_simulate_match` 반환 arity는 바꾸지 않는다.
- Monte Carlo 경로가 깨지면 안 된다.
- game_config에 metadata key가 있어도 run_simulation 본체는 무시하므로 괜찮다.

### 3. step6_dashboard.py — UI와 결과 표시

#### 3-1. DB role schema UI 추가

DB 역할 컬럼 방식에 `관측 상태 trace (선택)` expander를 추가한다.

위치는 `초기 필드 상태 (선택)`과 `행동 trace 연결 (선택)` 사이가 좋다.

UI:

```python
_st_use = st.checkbox("state snapshot trace 사용", value=False)
_bb_state_turn_col = st.selectbox("state turn 컬럼", _all_cols, ...)
_bb_state_id_col = st.selectbox("state entity ID 컬럼", _all_cols, ...)
_bb_state_hp_col = st.selectbox("state HP 컬럼 (선택)", _all_cols, ...)
_bb_state_status_col = st.selectbox("state status 컬럼 (선택)", _all_cols, ...)
_bb_state_fainted_col = st.selectbox("state fainted 컬럼 (선택)", _all_cols, ...)
_bb_state_hp_mode = st.selectbox("state HP mode", ["absolute", "percent"])
_bb_state_hp_tol = st.number_input("HP 허용 오차", min_value=0.0, value=0.0, step=1.0)
```

guess 후보:

```python
turn: ["turn", "round", "턴", "라운드"]
id: ["unit", "entity", "actor", "character", "hero", "pokemon", "참가자", "유닛"]
hp: ["hp", "health", "current_hp", "remain_hp", "hp_after", "체력", "잔여"]
status: ["status", "condition", "state", "상태", "상태이상"]
fainted: ["fainted", "dead", "ko", "down", "is_dead", "is_fainted", "기절", "쓰러짐"]
```

schema 반영:

```python
"state_trace_enabled": True,
"state_turn_col": _bb_state_turn_col,
"state_entity_id_col": _bb_state_id_col,
"state_hp_col": None if _bb_state_hp_col == "(없음)" else _bb_state_hp_col,
"state_status_col": None if _bb_state_status_col == "(없음)" else _bb_state_status_col,
"state_fainted_col": None if _bb_state_fainted_col == "(없음)" else _bb_state_fainted_col,
"state_hp_mode": _bb_state_hp_mode,
"state_hp_tolerance": float(_bb_state_hp_tol),
```

validation:

- turn/id가 없으면 warning
- hp/status/fainted 중 하나도 선택하지 않으면 warning

#### 3-2. 결과 집계 표시

Step6 backtest worker 결과 처리에서 `metrics.get("state_score")`를 모은다.

예:

```python
_bb_state_scores = []
...
if isinstance(_bb_r, tuple) and len(_bb_r) >= 2:
    _metrics = _bb_r[1] or {}
    if _metrics.get("state_score"):
        _bb_state_scores.append(_metrics["state_score"])
```

백테스트 결과 아래에 state score metric을 표시한다.

집계:

- checks 합
- mismatches 합
- accuracy = 1 - mismatches/checks
- hp/status/faint mismatch 합
- missing 합
- first mismatch 예시 하나

표시:

- `상태 일치율`
- `HP 불일치`
- `상태/기절 불일치`
- 첫 mismatch는 `st.caption` 또는 `st.json`

state score가 없으면 표시하지 않는다.

## 금지

- `_worker_simulate_match` 반환 tuple 구조 변경 금지
- 기존 승패 백테스트 점수 제거 금지
- move/switch/faint/initial trace 동작 변경 금지
- replay 전용 `fullbattle_*` 모듈을 억지로 재사용하지 말 것. 필요하면 나중에 통합한다.
- 새 의존성 추가 금지

## 수동 검증 코드

### 1. AST

```powershell
@'
import ast
from pathlib import Path
for p in ["modules/engine.py", "modules/per_battle_backtest.py", "modules/step6_dashboard.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 2. DB snapshot builder 검증

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_state_snapshots_from_group

df = pd.DataFrame([
    {"turn": 1, "unit": "A1", "hp_after": 80, "status": "poison", "dead": 0},
    {"turn": 1, "unit": "E1", "hp_after": 0, "status": "", "dead": 1},
    {"turn": 2, "unit": "A1", "hp_after": 60, "status": "poison", "dead": 0},
])
schema = {
    "state_trace_enabled": True,
    "state_turn_col": "turn",
    "state_entity_id_col": "unit",
    "state_hp_col": "hp_after",
    "state_status_col": "status",
    "state_fainted_col": "dead",
}
snaps = build_state_snapshots_from_group(df, schema)
print(snaps)
assert snaps[1]["A1"]["hp"] == 80.0
assert snaps[1]["A1"]["status"] == "poison"
assert snaps[1]["A1"]["fainted"] is False
assert snaps[1]["E1"]["fainted"] is True
assert snaps[2]["A1"]["hp"] == 60.0
print("state snapshot builder OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 3. build_battles state-only 4튜플 검증

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_battles

df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1", "result": "win", "HP": 100, "SPD": 10,
     "turn": 1, "hp_after": 100, "dead": 0},
    {"battle_id": 1, "side": "Enemy", "unit_id": "E1", "result": "lose", "HP": 100, "SPD": 20,
     "turn": 1, "hp_after": 100, "dead": 0},
])
schema = {
    "battle_id_col": "battle_id",
    "team_col": "side",
    "entity_id_col": "unit_id",
    "result_mode": "battle_level",
    "state_trace_enabled": True,
    "state_turn_col": "turn",
    "state_entity_id_col": "unit_id",
    "state_hp_col": "hp_after",
    "state_fainted_col": "dead",
    "state_hp_mode": "absolute",
    "state_hp_tolerance": 0,
}
battles = build_battles(df, 2, "result", ["HP", "SPD"], [], "HP",
                        max_battles=10, game_config={}, log_schema=schema)
print("battle_count", len(battles), "tuple_len", len(battles[0]) if battles else None)
assert len(battles) == 1 and len(battles[0]) == 4
gc = battles[0][3]
print(gc)
assert "_expected_state_snapshots" in gc
assert gc["_expected_state_snapshots"][1]["A1"]["hp"] == 100.0
assert gc["_state_score_config"]["hp_mode"] == "absolute"
print("build_battles state-only OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 4. worker state_score perfect match

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
assert score["checks"] >= 4
assert score["mismatches"] == 0
assert score["accuracy"] == 1.0
print("worker state_score perfect OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 5. worker state_score mismatch 감지

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
            "A1": {"hp": 50.0, "fainted": False},
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
assert score["hp_mismatches"] >= 1
assert score["mismatches"] >= 1
print("worker state_score mismatch OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

## 완료 기준

- DB observed state snapshot IR을 만들 수 있다.
- state-only battle도 4튜플 config를 만든다.
- `_worker_simulate_match` 반환 구조는 유지하면서 `metrics["state_score"]`를 추가한다.
- Step6 승패 백테스트는 기존처럼 동작한다.
- state_score가 있으면 상태 일치율/불일치 요약을 추가로 표시한다.
