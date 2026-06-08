# DB로그 IR PR-I10 — state snapshot score 결정론 모드 분리

## 목표

Step6 전투별 백테스트에서 `state snapshot trace`를 켠 경우, 관측 DB 상태와 엔진 상태를 비교하는 `state_score`가 기본 Monte Carlo 데미지 분산에 흔들리지 않도록 한다.

현재 흐름은 `modules/step6_dashboard.py`의 per-battle task 생성에서 항상 `default_stochasticity_factory`를 넘긴다. 이 factory는 `DamageVariance(±10%)`라서, DB 로그의 관측 HP 스냅샷을 맞히는 검증에도 난수가 섞인다.

이 PR의 의도는 다음을 분리하는 것이다.

- 일반 Monte Carlo/밸런스 분석: 기존처럼 확률·분산 사용
- DB 로그 기반 상태 복제 검증: 기본은 결정론(`NoVariance`)으로 비교

즉 이 작업은 UI 표현력 개선이 아니라, 최종 목표인 “DB 로그 기반 전투 시스템 복제”에서 복제 오차와 RNG 오차를 분리하는 연결 보강이다.

## 수정 대상

가능하면 아래 파일만 수정한다.

- `modules/step6_dashboard.py`

필요하면 아주 작게 아래 파일을 건드릴 수 있다.

- `modules/engine.py`

`modules/per_battle_backtest.py`는 가능하면 그대로 둔다. 이미 battle별 `game_config`에 `_expected_state_snapshots`를 넣는 역할은 충분하다.

## 구현 요구

### 1. per-battle 백테스트용 stochasticity 선택 helper 추가

`modules/step6_dashboard.py` 상단 또는 per-battle 블록 근처에 작은 helper를 추가한다.

예시:

```python
def _select_backtest_stochasticity_factory(log_schema):
    if log_schema and log_schema.get("state_trace_enabled"):
        if bool(log_schema.get("state_score_deterministic", True)):
            return None
    return default_stochasticity_factory
```

의미:

- `None`을 넘기면 `_worker_simulate_match -> run_simulation` 경로에서 기존 `NoVariance()` 기본값을 사용한다.
- state trace가 없으면 기존과 완전히 동일하게 `default_stochasticity_factory`를 사용한다.
- state trace가 있어도 사용자가 명시적으로 stochastic 검증을 원하면 기존 factory를 쓸 수 있게 한다.

함수명은 달라도 되지만, 선택 로직은 모듈 레벨에서 테스트 가능한 형태로 두는 것을 권장한다.

### 2. State trace UI에 결정론 옵션 추가

`modules/step6_dashboard.py`의 `관측 상태 trace (선택)` expander 안에 옵션을 추가한다.

권장 UI:

```python
_bb_state_deterministic = st.checkbox(
    "state score는 결정론으로 계산",
    value=True,
    help="DB 관측 상태와 엔진 상태를 비교할 때 데미지 분산을 끄고 복제 오차만 봅니다."
)
```

주의:

- `_st_use`가 꺼져 있어도 이후 코드에서 변수가 없어지지 않게 기본값을 미리 잡아라.
- 새 UI는 `state snapshot trace 사용`과 같은 expander 안에 둔다.
- 다른 trace(move/switch/faint) expander와 섞지 않는다.

### 3. log_schema에 옵션 저장

state trace 설정이 유효할 때 `_bb_log_schema.update({...})`에 아래 값을 포함한다.

```python
"state_score_deterministic": bool(_bb_state_deterministic),
```

### 4. per-battle task 생성에서 factory 선택 적용

현재 per-battle task 생성부에는 이런 식의 고정값이 있다.

```python
_bb_tasks.append((
    _a_team, _e_team, _bb_cf, _bb_spd, sys_stats, _bb_gf,
    _bb_mt, default_stochasticity_factory, _bb_rm,
    None, None, None, None, _task_gc, _bb_i,
))
```

이를 helper 기반으로 바꾼다.

예시:

```python
_bb_stochasticity_factory = _select_backtest_stochasticity_factory(_bb_log_schema)
...
_bb_tasks.append((
    _a_team, _e_team, _bb_cf, _bb_spd, sys_stats, _bb_gf,
    _bb_mt, _bb_stochasticity_factory, _bb_rm,
    None, None, None, None, _task_gc, _bb_i,
))
```

주의:

- Monte Carlo 버튼 경로(`run_monte_carlo`)는 건드리지 않는다.
- Optimizer 경로도 건드리지 않는다.
- state trace가 꺼져 있으면 기존 per-battle 동작과 동일해야 한다.
- state trace가 켜져 있고 기본 옵션이면 per-battle state_score는 결정론이어야 한다.

### 5. 결과 안내 문구 보강

`관측 상태 스냅샷 일치율` 결과 근처에 짧은 caption을 추가해도 좋다.

예시:

```python
if _bb_log_schema and _bb_log_schema.get("state_trace_enabled"):
    if _bb_log_schema.get("state_score_deterministic", True):
        st.caption("state score는 결정론 모드(NoVariance)로 계산되었습니다.")
    else:
        st.caption("state score는 현재 stochasticity 설정을 포함해 계산되었습니다.")
```

## 수용 조건

아래 검사를 모두 통과해야 한다.

### A. AST

```powershell
$env:PYTHONIOENCODING='utf-8'; @'
import ast
from pathlib import Path
for p in ["modules/step6_dashboard.py", "modules/engine.py", "modules/per_battle_backtest.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### B. Worker 결정론 state_score 회귀

`stochasticity_factory=None`일 때 state snapshot score가 정확히 맞아야 한다.

```powershell
$env:PYTHONIOENCODING='utf-8'; @'
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
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### C. 기본 DamageVariance가 state_score를 흔들 수 있음을 확인

이 테스트는 구현 요구의 배경을 보호한다. `default_stochasticity_factory`를 직접 넘기면 HP가 정확히 50/50이 아니어서 mismatch가 발생해야 한다.

```powershell
$env:PYTHONIOENCODING='utf-8'; @'
from modules.engine import _worker_simulate_match, default_stochasticity_factory

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
    1, default_stochasticity_factory, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["state_score"]
assert score["hp_mismatches"] > 0
assert score["accuracy"] < 1.0
print("stochastic variance can affect state score: confirmed")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### D. Step6 source 연결 확인

`modules/step6_dashboard.py`에서 다음이 확인돼야 한다.

- `state_score_deterministic`가 `_bb_log_schema`에 저장된다.
- per-battle task의 `stochasticity_factory` 자리에 더 이상 무조건 `default_stochasticity_factory`를 넣지 않는다.
- state trace가 꺼진 경우에는 기존처럼 `default_stochasticity_factory`가 선택된다.
- state trace가 켜진 경우 기본값은 `None`이다.

간단 검사 예시:

```powershell
$env:PYTHONIOENCODING='utf-8'; @'
from pathlib import Path
src = Path("modules/step6_dashboard.py").read_text(encoding="utf-8")
assert "state_score_deterministic" in src
assert "default_stochasticity_factory" in src
assert "_bb_stochasticity_factory" in src or "_select_backtest_stochasticity_factory" in src
print("step6 stochasticity selection source guard OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

## 금지/주의

- `default_stochasticity_factory` 자체를 `NoVariance`로 바꾸지 않는다. Monte Carlo와 optimizer는 여전히 확률/분산을 써야 한다.
- `_worker_simulate_match`의 인자 구조를 깨지 않는다.
- `run_simulation`의 기본 `NoVariance()` 동작을 깨지 않는다.
- state trace가 없는 기존 per-battle 백테스트 결과 흐름을 바꾸지 않는다.

