# DB로그 IR PR-I9b — Step6 state_score 집계 누락 보정

## 배경

PR-I9의 핵심 기능은 대부분 통과했다.

통과 확인:

- `engine.py`, `per_battle_backtest.py`, `step6_dashboard.py` AST OK
- `build_state_snapshots_from_group(...)` OK
- state-only battle 4튜플 OK
- `_worker_simulate_match(...)`가 `metrics["state_score"]`를 생성 OK
- perfect match/mismatch 감지 OK

발견된 문제:

- `modules/step6_dashboard.py`에서 `_bb_state_scores`를 표시 블록에서 사용하지만, 백테스트 실행 루프에서 초기화/수집하지 않는다.
- 현재 검색 결과상 `_bb_state_scores`는 아래 표시부에서만 등장한다.

```python
if _bb_state_scores:
    ...
```

이 상태면 백테스트 완료 후 `NameError`가 날 수 있다.

## 수정 대상

- `modules/step6_dashboard.py`
- 가능하면 `modules/per_battle_backtest.py`도 작은 fallback 보정 가능

## 필수 수정

### 1. `_bb_state_scores` 초기화

백테스트 실행 준비부에서 `_bb_predictions`, `_bb_errors`와 같은 위치에 초기화한다.

예:

```python
_bb_predictions = []
_bb_state_scores = []
_bb_errors = 0
```

### 2. worker 결과에서 state_score 수집

현재 루프는 대략 다음 형태다.

```python
for _bb_r in _bb_pool.map(_worker_simulate_match, _bb_tasks, chunksize=4):
    if isinstance(_bb_r, str):
        _bb_errors += 1
        _bb_predictions.append(False)
    else:
        _bb_predictions.append(_bb_r[0] == 1)
```

여기에 metrics 수집을 추가한다.

```python
else:
    _bb_predictions.append(_bb_r[0] == 1)
    _metrics = _bb_r[1] if len(_bb_r) > 1 else {}
    if isinstance(_metrics, dict) and _metrics.get("state_score"):
        _bb_state_scores.append(_metrics["state_score"])
```

주의:

- `_worker_simulate_match` 반환 구조는 바꾸지 않는다.
- worker error string인 경우에는 state score를 수집하지 않는다.
- state score가 없는 기존 백테스트에서는 `_bb_state_scores == []`로 표시 블록이 조용히 skip되어야 한다.

### 3. 표시 블록 안전화

표시 블록에서 sum 대상 key가 누락되어도 죽지 않게 `.get(...)`을 사용한다.

예:

```python
_s_checks = sum(int(s.get("checks", 0) or 0) for s in _bb_state_scores)
_s_mismatch = sum(int(s.get("mismatches", 0) or 0) for s in _bb_state_scores)
...
```

`first_mismatch`도 안전하게:

```python
_first = next((s.get("first_mismatch") for s in _bb_state_scores if s.get("first_mismatch")), None)
```

## 권장 보정

### 4. per_battle_backtest.py fallback 보정

`build_state_snapshots_from_group(...)`에서 turn/id 컬럼 fallback을 프롬프트 의도대로 맞춘다.

현재처럼 직접 키만 읽지 말고:

```python
turn_col = (
    log_schema.get("state_turn_col")
    or log_schema.get("turn_col")
    or log_schema.get("switch_turn_col")
    or log_schema.get("faint_turn_col")
)
id_col = log_schema.get("state_entity_id_col") or log_schema.get("entity_id_col")
```

이건 UI 경로에는 큰 차이가 없지만, programmatic log_schema 사용에서 더 안정적이다.

## 금지

- `_worker_simulate_match` 반환 구조 변경 금지
- `engine.py` 수정 금지
- 기존 승패 백테스트 점수 제거 금지
- state_score 표시를 항상 강제로 띄우지 말 것. score가 있을 때만 표시
- move/switch/faint/initial trace 동작 변경 금지

## 수동 검증 코드

### 1. AST

```powershell
@'
import ast
from pathlib import Path
for p in ["modules/step6_dashboard.py", "modules/per_battle_backtest.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 2. `_bb_state_scores` 초기화/수집 정적 확인

```powershell
@'
from pathlib import Path
src = Path("modules/step6_dashboard.py").read_text(encoding="utf-8")
assert "_bb_state_scores = []" in src
assert "_bb_state_scores.append" in src
assert "state_score" in src
print("Step6 state_score collection source OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 3. worker state_score 회귀 확인

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
assert not isinstance(res, str)
assert res[1]["state_score"]["accuracy"] == 1.0
print("worker state_score regression OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 4. state snapshot fallback 확인

```powershell
@'
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
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

## 완료 기준

- Step6 백테스트 루프가 `_bb_state_scores`를 초기화한다.
- worker metrics에서 `state_score`를 수집한다.
- state_score가 없을 때 기존 승패 백테스트가 그대로 동작한다.
- state_score가 있을 때 표시 블록이 NameError 없이 집계된다.
- 기존 worker state_score 계산은 회귀하지 않는다.
