# DB로그 IR PR-I4 - trace 행동 우선도 turn 전달

## 목적

I3/I3b로 DB action row를 `game_config["trace_actions"]["move"]`로 변환할 수 있게 됐다.

하지만 현재 엔진의 행동 순서 예측기는 trace action의 현재 턴을 알지 못한다.

현재 `modules/turn_manager.py`는 다음처럼 action priority를 호출한다.

```python
acting_units.sort(key=lambda x: -self._action_priority(x))
```

그리고 `modules/engine.py`의 `_predict_action_priority(unit)`는 다음 방식이다.

```python
if _will_voluntary_switch(unit, participants, game_config):
    return switch_priority
...
_pmove = _select_move_pure(...)
return int(_pmove.get("priority", 0))
```

문제:

- trace move가 지정되어도 priority 예측은 여전히 greedy move 선택을 본다.
- trace switch가 지정되어도 `_will_voluntary_switch(...)`는 현재 trace switch를 보지 못한다.
- `trace_actions[(turn, actor_id)]` 구조인데 action priority 함수가 `turn`을 받지 않는다.

이번 PR의 목표는 TurnManager가 현재 turn을 action priority 함수에 전달할 수 있게 만들고,
엔진의 `_predict_action_priority`가 trace move/switch를 현재 턴 기준으로 읽게 하는 것이다.

이번 PR은 DB action order 컬럼을 새로 만들지 않는다.
이미 trace move dict 안에 들어온 `priority`와 기존 `switch_priority`를 현재 턴에 맞춰 읽는 인프라 보정이다.

## 수정 대상

- `modules/turn_manager.py`
- `modules/engine.py`

가능하면 다른 파일은 수정하지 않는다.

## turn_manager 변경

### 요구사항

`SequentialTurnManager`는 기존 1-인자 `action_priority(unit)` 콜백과 새 2-인자
`action_priority(unit, turn)` 콜백을 모두 지원해야 한다.

기존 콜백 호환성을 깨지 않는다.

### 권장 구현

`SequentialTurnManager.__init__`에서 `inspect.signature(...)`로 콜백이 turn을 받을 수 있는지 판정한다.

예:

```python
import inspect

def _accepts_turn_arg(fn):
    if fn is None:
        return False
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return False
    if any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params):
        return True
    positional = [
        p for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                      inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    return len(positional) >= 2
```

`__init__`에서:

```python
self._action_priority_accepts_turn = _accepts_turn_arg(action_priority)
```

`run(...)`에서:

```python
if self._action_priority is not None:
    if self._action_priority_accepts_turn:
        acting_units.sort(key=lambda x: -self._action_priority(x, turn))
    else:
        acting_units.sort(key=lambda x: -self._action_priority(x))
```

주의:

- try/except TypeError fallback으로 내부 TypeError까지 삼키지 않는 편이 좋다.
- 기존 action_priority 미설정 동작은 그대로 둔다.
- sort 안정성은 유지한다. 동순위는 기존 속도순 정렬 결과가 유지되어야 한다.

## engine 변경

### `_predict_action_priority` 시그니처 확장

현재:

```python
def _predict_action_priority(unit):
```

변경:

```python
def _predict_action_priority(unit, turn=None):
```

### trace switch 우선도

현재 turn이 있고 `game_config["trace_actions"]["switch"]`에 `(turn, unit["id"])`가 있으면
`switch_priority`를 반환한다.

```python
ta = (game_config or {}).get("trace_actions") or {}
if turn is not None:
    sw = (ta.get("switch") or {}).get((turn, unit.get("id")))
    if sw:
        return int((game_config or {}).get("switch_priority", 6))
```

### trace move 우선도

현재 turn이 있고 `game_config["trace_actions"]["move"]`에 `(turn, unit["id"])`가 있으면
그 trace move dict의 priority를 반환한다.

```python
ma = (ta.get("move") or {}).get((turn, unit.get("id")))
if ma:
    try:
        return int((ma.get("move") or {}).get("priority", 0))
    except (TypeError, ValueError):
        return 0
```

### fallback 유지

trace action이 없으면 기존 로직을 그대로 사용한다.

```python
if _will_voluntary_switch(unit, participants, game_config):
    return int((game_config or {}).get("switch_priority", 6))
...
_pmove = _select_move_pure(...)
...
```

중요:

- trace action이 없을 때 기존 행동 순서는 변하지 않아야 한다.
- trace move priority가 없으면 0.
- trace switch는 공격보다 높은 기본 `switch_priority=6`.
- `turn=None`인 경우 기존 fallback만 사용한다.
- `build_ctx(unit, 0, participants)` fallback은 그대로 유지한다.

## 금지 사항

- DB action order 컬럼 UI 추가 금지
- `per_battle_backtest.py` 수정 금지
- `step6_dashboard.py` 수정 금지
- trace action이 없는 일반 시뮬레이션 행동 순서 변경 금지
- priority 동순위의 기존 속도순 안정 정렬을 깨지 않는다.
- trace move가 없는데 임의로 move를 선택해서 trace action을 만들지 않는다.

## 검증

### 1. AST

```python
import ast
from pathlib import Path
for p in ["modules/turn_manager.py", "modules/engine.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
```

### 2. TurnManager 1-인자 콜백 호환

```python
from modules.turn_manager import SequentialTurnManager
from modules.action_registry import ActionRegistry
from modules.resource import ResourceModule
from modules.win_condition import ResourceDepletion

called = []
def prio(unit):
    called.append((unit["id"], "one"))
    return 0

mgr = SequentialTurnManager(
    ActionRegistry(),
    turn_executor=type("NoopExec", (), {"execute": lambda self, ctx, registry: None})(),
    resource_module=ResourceModule(),
    win_condition=ResourceDepletion(["HP"]),
    action_priority=prio,
)
participants = [
    {"id": "A", "team": "Ally", "resources": {"HP": {"current": 1, "max": 1}}},
    {"id": "E", "team": "Enemy", "resources": {"HP": {"current": 1, "max": 1}}},
]
mgr.run(participants, 1, {}, lambda u,t,p: {"active_char": u, "battle_over": False}, lambda msg: None)
assert called
assert all(x[1] == "one" for x in called)
```

### 3. TurnManager 2-인자 콜백

```python
called = []
def prio2(unit, turn):
    called.append((unit["id"], turn))
    return 0

mgr = SequentialTurnManager(
    ActionRegistry(),
    turn_executor=type("NoopExec", (), {"execute": lambda self, ctx, registry: None})(),
    resource_module=ResourceModule(),
    win_condition=ResourceDepletion(["HP"]),
    action_priority=prio2,
)
participants = [
    {"id": "A", "team": "Ally", "resources": {"HP": {"current": 1, "max": 1}}},
    {"id": "E", "team": "Enemy", "resources": {"HP": {"current": 1, "max": 1}}},
]
mgr.run(participants, 1, {}, lambda u,t,p: {"active_char": u, "battle_over": False}, lambda msg: None)
assert called
assert all(x[1] == 1 for x in called)
```

### 4. trace move priority smoke

trace move priority가 속도보다 먼저 적용되는지 확인한다.

```python
from modules.engine import run_simulation

ally = [{
    "id": "slow",
    "name": "slow",
    "SPD": 1,
    "HP": 100,
    "resources": {"HP": {"current": 100, "max": 100}},
}]
enemy = [{
    "id": "fast",
    "name": "fast",
    "SPD": 999,
    "HP": 100,
    "resources": {"HP": {"current": 100, "max": 100}},
}]
gc = {
    "preserve_ids": True,
    "trace_actions": {
        "move": {
            (1, "slow"): {"move": {"name": "Quick", "power": 0, "priority": 5}, "target": "fast"},
            (1, "fast"): {"move": {"name": "SlowHit", "power": 0, "priority": 0}, "target": "slow"},
        },
        "switch": {},
    },
}
winner, logs, metrics = run_simulation(
    ally, enemy,
    max_turns=1,
    speed_stat="SPD",
    sys_stats=["HP", "SPD"],
    global_damage_formula="0",
    game_config=gc,
    silent=False,
)
joined = "\n".join(logs)
assert joined.find("Quick") != -1
assert joined.find("SlowHit") != -1
assert joined.find("Quick") < joined.find("SlowHit")
```

### 5. trace fallback 기존 순서

trace_actions가 없으면 기존 속도순이어야 한다.

```python
winner, logs, metrics = run_simulation(
    ally, enemy,
    max_turns=1,
    speed_stat="SPD",
    sys_stats=["HP", "SPD"],
    global_damage_formula="0",
    game_config={"preserve_ids": True},
    silent=False,
)
joined = "\n".join(logs)
assert joined.find("fast") < joined.find("slow")
```

### 6. grep 확인

- `SequentialTurnManager.run(...)`에서 2-인자 action_priority를 지원한다.
- `_predict_action_priority(unit, turn=None)` 형태다.
- `_predict_action_priority`가 trace switch를 먼저 본다.
- `_predict_action_priority`가 trace move priority를 본다.
- trace action이 없을 때 기존 `_will_voluntary_switch`/`_select_move_pure` fallback이 남아 있다.

## 완료 기준

trace mode에서 현재 턴의 DB 지정 행동 우선도가 엔진 행동 순서에 반영되어야 한다.

이 PR 후에는 I3의 move trace가 “무슨 행동을 하는가”뿐 아니라
무브 priority 수준의 “누가 먼저 행동하는가”까지 엔진에 전달할 수 있다.
