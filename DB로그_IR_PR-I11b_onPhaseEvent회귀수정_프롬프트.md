# DB로그 IR PR-I11b — on_phase_event 회귀 수정

## 배경

PR-I11의 action damage trace score 본체는 붙었지만, `on_phase_event` 연결 방식에 회귀가 있다.

현재 확인된 문제:

1. `run_simulation(..., on_phase_event=None)`인 기존 경로가 깨진다.
   - `ctx["on_phase_event"]` 키가 항상 들어가는데 값이 `None`이다.
   - `_broadcast_phase_event()`가 키 존재만 보고 `ctx["on_phase_event"](...)`를 호출해서 `TypeError: 'NoneType' object is not callable` 발생.

2. `on_phase_event`와 `on_turn_end`를 함께 쓰면 `TURN_END` phase callback이 중복 호출된다.
   - `_broadcast_phase_event()`가 ctx의 `on_phase_event`를 호출한다.
   - 동시에 `run_simulation()`의 `_btn` wrapper가 `_phase_cb(_pk, _ctx, _targets)`를 다시 호출한다.
   - 일반 action phase는 action block이 직접 `_broadcast_phase_event()`를 부르므로 중복이 안 보이지만, `TURN_END`는 `TurnManager.broadcast_phase_event` wrapper를 타면서 중복된다.

이 보정 PR은 I11의 기능을 유지하면서 기존 경로 회귀를 제거한다.

## 수정 대상

가능하면 아래 파일만 수정한다.

- `modules/engine.py`

## 수정 요구

### 1. `_broadcast_phase_event()`에서 callable guard 추가

현재 형태가 이런 식이면:

```python
if ctx and "on_phase_event" in ctx:
    ctx["on_phase_event"](phase_key, ctx, targets)
```

아래처럼 바꾼다.

```python
phase_cb = ctx.get("on_phase_event") if ctx else None
if phase_cb is not None:
    phase_cb(phase_key, ctx, targets)
```

또는 `callable(phase_cb)` guard를 써도 된다.

중요:

- `on_phase_event=None`이면 아무 일도 하지 않아야 한다.
- 기존 `_notify_event()` 브로드캐스트는 계속 실행되어야 한다.
- phase callback은 기존처럼 action block에서 `_broadcast_phase_event()`가 호출될 때 잡혀야 한다.

### 2. `run_simulation()`의 `_btn` wrapper에서 phase callback 중복 호출 제거

현재 형태가 이런 식이면:

```python
_btn = _broadcast_phase_event
if on_turn_end is not None or on_phase_event is not None:
    def _btn(_pk, _ctx, _targets=None, _orig=_broadcast_phase_event,
             _turn_cb=on_turn_end, _phase_cb=on_phase_event):
        _orig(_pk, _ctx, _targets)
        if _phase_cb is not None:
            _phase_cb(_pk, _ctx, _targets)
        if _turn_cb is not None and _pk == "TURN_END":
            _turn_cb(_ctx)
```

아래처럼 바꾼다.

```python
_btn = _broadcast_phase_event
if on_turn_end is not None:
    def _btn(_pk, _ctx, _targets=None, _orig=_broadcast_phase_event,
             _turn_cb=on_turn_end):
        _orig(_pk, _ctx, _targets)
        if _pk == "TURN_END":
            _turn_cb(_ctx)
```

의도:

- `on_phase_event`는 `ctx["on_phase_event"]`를 통해 `_broadcast_phase_event()` 안에서 한 번만 호출한다.
- `on_turn_end`는 기존처럼 `TURN_END`일 때만 별도로 호출한다.
- `on_phase_event`만 있는 경우에도 `TurnManager`의 `TURN_END`는 `_broadcast_phase_event()`를 그대로 타므로 phase callback이 한 번 호출된다.

### 3. `build_ctx`의 `"on_phase_event": on_phase_event`는 유지

action block들은 전역 `_broadcast_phase_event("APPLY_DAMAGE", ctx, targets=t)`를 직접 호출한다.

따라서 `ctx` 안에 callback이 들어 있어야 `APPLY_DAMAGE` 같은 action phase를 캡처할 수 있다.

단, 1번 callable guard 때문에 값이 `None`이어도 안전해야 한다.

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

### B. 기존 run_simulation 경로 회귀 방지

`on_phase_event`를 넘기지 않아도 전투가 정상 실행돼야 한다.

```powershell
@'
from modules.engine import run_simulation

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 1,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 2,
          "resources": {"HP": {"current": 100, "max": 100}}}]

winner, logs, metrics = run_simulation(
    ally, enemy, max_turns=1,
    speed_stat="SPD", sys_stats=["HP", "SPD"],
    global_damage_formula="0",
    game_config={"preserve_ids": True},
    silent=True,
)
print(winner, metrics)
assert isinstance(metrics, dict)
assert metrics["damage_count"] == 2
print("run_simulation without on_phase_event OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### C. worker 기존 경로 회귀 방지

`_expected_action_damage_trace`가 없어도 worker가 에러 문자열을 반환하면 안 된다.

```powershell
@'
from modules.engine import _worker_simulate_match

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 1,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 2,
          "resources": {"HP": {"current": 100, "max": 100}}}]

res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "0",
    1, None, None, None, None, None, None, {"preserve_ids": True}, 0
))
print(res)
assert not (isinstance(res, str) and res.startswith("ERROR:"))
assert res[1]["damage_count"] == 2
print("worker without expected action damage OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### D. state-only worker 회귀 방지

I9/I10 state score 경로가 그대로 살아 있어야 한다.

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
assert not (isinstance(res, str) and res.startswith("ERROR:"))
assert res[1]["state_score"]["accuracy"] == 1.0
print("state-only worker after I11 OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### E. phase callback과 turn_end callback 중복 방지

`on_phase_event`와 `on_turn_end`를 같이 넣어도 `TURN_END` phase callback이 actor당 한 번만 호출되어야 한다.

```powershell
@'
from modules.engine import run_simulation

events = []

def on_phase(pk, ctx, targets):
    events.append(pk)

def on_turn_end(ctx):
    events.append("TURN_END_CB")

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 1,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 2,
          "resources": {"HP": {"current": 100, "max": 100}}}]

run_simulation(
    ally, enemy, max_turns=1,
    speed_stat="SPD", sys_stats=["HP", "SPD"],
    global_damage_formula="0",
    game_config={"preserve_ids": True},
    on_phase_event=on_phase,
    on_turn_end=on_turn_end,
    silent=True,
)

print(events)
assert events.count("APPLY_DAMAGE") == 2
assert events.count("TURN_END") == 2
assert events.count("TURN_END_CB") == 2
print("phase + turn_end callback count OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### F. I11 본체 action_damage_score 유지

I11에서 통과한 worker action damage score가 계속 통과해야 한다.

```powershell
@'
from modules.engine import _worker_simulate_match

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 50, "SPD": 1,
          "resources": {"HP": {"current": 50, "max": 50}}}]
gc = {
    "preserve_ids": True,
    "_expected_action_damage_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "damage": 50.0}
    ],
    "_action_damage_score_config": {"damage_tol": 0.0},
}

res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
assert res[1]["action_damage_score"]["accuracy"] == 1.0
print("I11 action damage score still OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

## 금지/주의

- `on_phase_event`를 ctx에서 제거하지 않는다. action block의 phase capture가 깨진다.
- `on_turn_end` 콜백을 제거하지 않는다. state snapshot score가 깨진다.
- `_worker_simulate_match` args tuple 구조를 바꾸지 않는다.
- `default_stochasticity_factory`나 `NoVariance` 관련 로직은 건드리지 않는다.

