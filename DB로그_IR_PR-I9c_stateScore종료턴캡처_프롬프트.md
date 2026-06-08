# DB로그 IR PR-I9c — state_score 종료 턴 snapshot 캡처 보정

## 배경

PR-I9/I9b로 DB observed state snapshot과 worker `state_score` 계산은 연결됐다.

통과 확인:

- DB snapshot builder OK
- state-only battle 4튜플 OK
- worker `state_score` perfect/mismatch 감지 OK
- Step6 `_bb_state_scores` 수집 보정 OK

새로 발견된 문제:

전투가 어떤 행동 직후 바로 끝나면, `SequentialTurnManager.run(...)`이 win condition에서 즉시 return한다.

현재 흐름:

```python
turn_executor.execute(...)
_resolve_faint(...)
is_over, winner = win_condition.check(...)
if is_over:
    return winner, sim_metrics

if self.broadcast_phase_event:
    self.broadcast_phase_event("TURN_END", ctx)
```

즉 종료 턴에는 `broadcast_phase_event("TURN_END", ctx)`가 호출되지 않는다.

PR-I9의 worker state capture는 `on_turn_end`를 통해 턴 snapshot을 저장하므로, 종료 턴 snapshot이 누락된다. 그 결과 실제로는 상태가 맞아도 expected가 전부 `missing`으로 점수화된다.

재현:

- A1이 turn 1에 E1을 쓰러뜨림
- expected snapshot turn 1: E1 hp=0/fainted=True
- worker actual snapshot: turn 1 없음
- `state_score.missing == 2`, `accuracy == 0.0`

## 목적

종료 턴에도 “그 행동 이후의 최종 상태 snapshot”을 캡처할 수 있게 한다.

이 보정은 상태 검증용 hook의 누락을 메우는 것이지, 전투 규칙을 바꾸는 작업이 아니다.

## 수정 대상

- `modules/turn_manager.py`
- 가능하면 `modules/engine.py`는 수정하지 않는다.
- `modules/per_battle_backtest.py`, `modules/step6_dashboard.py` 수정 금지

## 변경 요구

### 1. TurnManager에서 TURN_END broadcast를 return 전에도 호출

`SequentialTurnManager.run(...)` 안에서 `broadcast_phase_event("TURN_END", ctx)` 호출을 helper로 빼고, action 처리 후 return 경로에서도 호출한다.

권장 형태:

```python
def _emit_turn_end(self, ctx):
    if self.broadcast_phase_event:
        self.broadcast_phase_event("TURN_END", ctx)
```

또는 run 내부 local helper도 가능하다.

적용 위치:

1. `self.turn_executor.execute(ctx, self.registry)` 직후 `ctx["battle_over"]`가 True라 return하는 경로

```python
if ctx["battle_over"]:
    self._emit_turn_end(ctx)
    return "None", sim_metrics
```

2. `win_condition.check(...)`가 `is_over=True`인 경로

```python
if is_over:
    self._emit_turn_end(ctx)
    add_log(...)
    return winner, sim_metrics
```

3. 기존 정상 경로

```python
self._emit_turn_end(ctx)
```

주의:

- 정상 경로에서 TURN_END가 중복 호출되면 안 된다.
- 종료 경로에서만 새로 한 번 호출되어야 한다.
- `turn_executor.execute(...)` 내부의 `ON_TURN_END` phase 실행과 혼동하지 말 것. 여기서는 외부 observer/capture hook인 `broadcast_phase_event("TURN_END", ctx)`만 보정한다.

### 2. 기존 동작 보존

- `broadcast_phase_event`가 None이면 아무 일도 없어야 한다.
- `on_turn_end`가 없는 일반 시뮬레이션 결과는 변하면 안 된다.
- `_worker_simulate_match` 반환 구조는 그대로다.
- state_score 계산 로직은 건드리지 않는다.

## 금지

- `run_simulation(...)` 반환값에 participants 추가 금지
- `_worker_simulate_match` 반환 tuple 구조 변경 금지
- state score 스키마 변경 금지
- Step6 UI 변경 금지
- 전투 종료 판정 순서 자체를 바꾸지 말 것. 단지 return 전에 observer snapshot을 방출한다.

## 수동 검증 코드

### 1. AST

```powershell
@'
import ast
from pathlib import Path
for p in ["modules/turn_manager.py", "modules/engine.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 2. 종료 턴 state_score가 missing 없이 잡힌다

```powershell
@'
from modules.engine import _worker_simulate_match

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 1,
          "resources": {"HP": {"current": 100, "max": 100}}}]
gc = {
    "preserve_ids": True,
    "_expected_state_snapshots": {
        1: {
            "A1": {"hp": 100.0, "fainted": False},
            "E1": {"hp": 0.0, "fainted": True},
        }
    },
    "_state_score_config": {"hp_mode": "absolute", "hp_tol": 0.0},
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "999",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["state_score"]
assert score["missing"] == 0
assert score["mismatches"] == 0
assert score["accuracy"] == 1.0
print("terminal-turn state capture OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 3. 기존 non-terminal state_score 회귀 확인

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
assert score["mismatches"] == 0
assert score["accuracy"] == 1.0
print("non-terminal state capture regression OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 4. on_turn_end 호출 횟수 sanity check

정상 비종료 1턴 1v1에서는 기존처럼 각 active 행동 후 capture가 일어나되, 같은 turn key overwrite 때문에 final snapshot만 남아야 한다.

```powershell
$env:PYTHONIOENCODING='utf-8'; @'
from modules.engine import run_simulation

captures = []
def cb(ctx):
    captures.append((ctx.get("turn"), ctx["active_char"]["id"]))

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 1,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 2,
          "resources": {"HP": {"current": 100, "max": 100}}}]
run_simulation(
    ally, enemy, max_turns=1,
    speed_stat="SPD",
    sys_stats=["HP", "SPD"],
    global_damage_formula="0",
    game_config={"preserve_ids": True},
    on_turn_end=cb,
    silent=True,
)
print(captures)
assert captures == [(1, "E1"), (1, "A1")]
print("turn_end callback count OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

## 완료 기준

- 종료 턴 state snapshot이 누락되지 않는다.
- 기존 non-terminal state_score는 회귀하지 않는다.
- 정상 경로의 TURN_END callback이 중복 호출되지 않는다.
- 전투 결과와 `_worker_simulate_match` 반환 구조는 그대로다.
