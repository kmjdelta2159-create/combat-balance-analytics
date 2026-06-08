# DB로그 IR PR-I3 - move trace_actions 연결

## 목적

I1/I1b로 DB 로그를 전투 단위로 묶고, I2로 `entity_id_col`을 엔진 participant `id`로 보존했다.

이제 DB 로그에 이미 다음 정보가 있을 때, 이를 엔진의 기존 trace hook에 연결한다.

- 턴
- 행동자 ID
- 타겟 ID
- 무브/스킬 이름

엔진에는 이미 다음 구조가 있다.

```python
game_config["trace_actions"]["move"][(turn, actor_id)] = {
    "move": move_dict,
    "target": target_id,
}
```

`modules/engine.py`의 target select 단계는 이 값이 있으면 그 턴의 해당 actor가 지정된 move와 target을 사용하게 한다.

이번 PR은 DB action row를 위 구조로 변환하는 첫 단계다.

범위는 **move trace만**이다.
switch trace, faint incoming, resync, HP timeline, action reconstruction 추론은 이번 PR에 넣지 않는다.

## 수정 대상

- `modules/per_battle_backtest.py`
- `modules/step6_dashboard.py`

가능하면 다른 파일은 수정하지 않는다.
`modules/engine.py`는 수정하지 않는다.

## 현재 전제

I2 이후 DB role-schema backtest에서는 다음이 가능해야 한다.

- participant row에 `id`가 보존됨
- Step6 DB role-schema 경로에서 `_bb_gc["preserve_ids"] = True`
- worker task에 `_bb_gc`가 전달됨

I3는 이 `id`와 DB action row의 `actor_id_col`, `target_id_col`을 맞춰서 trace_actions를 만든다.

## log_schema 확장

`log_schema`에 다음 optional fields를 추가한다.

```python
{
    "trace_moves_enabled": True,
    "turn_col": "turn",
    "actor_id_col": "actor_id",
    "target_id_col": "target_id",
    "move_name_col": "move_name",
    "action_col": "action_type",
    "move_action_values": ["move", "attack", "skill", "cast"],
    "move_power_col": "move_power",
    "move_type_col": "move_type",
    "move_category_col": "move_category",
    "move_priority_col": "move_priority"
}
```

필수:

- `trace_moves_enabled=True`
- `turn_col`
- `actor_id_col`
- `target_id_col`
- `move_name_col`

선택:

- `action_col`
- `move_action_values`
- `move_power_col`
- `move_type_col`
- `move_category_col`
- `move_priority_col`

`action_col`이 없으면 `move_name_col`이 비어 있지 않은 row를 move row로 본다.
`action_col`이 있으면 `move_action_values`에 해당하는 row만 move row로 본다.

## per_battle_backtest 변경

### 1. 빈 값 판정 재사용

이미 I2에서 만든 `_is_empty_id(...)`가 있으면 재사용하거나, 이름을 더 일반화해도 된다.
단, 기존 동작을 깨지 않는다.

### 2. turn 변환 helper

추가:

```python
def _coerce_turn(v):
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None
```

### 3. move dict 생성 helper

추가:

```python
def _move_from_row(row, log_schema, move_library=None):
    ...
```

동작:

1. `move_name_col`에서 move name을 읽는다.
2. move name이 빈 값이면 `None`.
3. `move_library`에 같은 이름의 move가 있으면 그 dict를 복사해서 시작한다.
4. 없으면 최소 dict로 시작한다.

최소 dict:

```python
{"name": move_name, "power": 0.0, "category": None, "type": None, "priority": 0}
```

5. row에 `move_power_col`, `move_type_col`, `move_category_col`, `move_priority_col`이 있고 값이 비어 있지 않으면 move dict에 overlay한다.
6. power는 float, priority는 int 변환을 시도하고 실패하면 기존값 유지 또는 기본값 사용.

주의:

- `move_library` 원본 dict를 직접 mutate하지 않는다.
- `contact`, `fixed_damage`, `recoil` 같은 추가 키가 move_library에 있으면 보존한다.

### 4. trace builder 추가

추가:

```python
def build_move_trace_actions_from_group(group, log_schema, move_library=None):
    ...
```

반환:

```python
{"move": {(turn, actor_id): {"move": move_dict, "target": target_id}}, "switch": {}}
```

동작:

1. `trace_moves_enabled`가 참이 아니면 `None` 또는 빈 dict 반환.
2. 필수 컬럼이 없으면 빈 dict 반환.
3. group row를 기존 정렬 순서대로 순회한다.
4. action filter를 통과하지 못하면 skip.
5. turn, actor_id, target_id, move를 만들 수 없으면 skip.
6. actor_id/target_id는 `str(...).strip()`으로 보존한다.
7. 같은 `(turn, actor_id)`가 여러 번 나오면 마지막 row가 이긴다.

기본 `move_action_values`:

```python
{"move", "attack", "skill", "cast", "use", "use_move", "act", "공격", "스킬", "무브", "행동"}
```

### 5. battle tuple 확장

기존 `build_battles(...)`는 다음 tuple을 반환한다.

```python
(ally_team, enemy_team, ally_wins)
```

I3에서는 trace move가 활성화된 DB role-schema 경로에 한해 다음 4-tuple을 반환한다.

```python
(ally_team, enemy_team, ally_wins, battle_game_config)
```

`battle_game_config` 예:

```python
{
    "trace_actions": {"move": {...}, "switch": {}},
    "preserve_ids": True
}
```

중요:

- `trace_moves_enabled`가 없거나 false면 기존 3-tuple 유지.
- trace가 활성화됐지만 move action이 하나도 없으면 4-tuple을 반환하지 말고 기존 3-tuple로 둬도 된다.
- 기존 chunk 경로는 항상 3-tuple 유지.
- 기존 I1/I1b/I2 검증이 깨지면 안 된다.

## Step6 변경

### 1. DB role-schema UI에 move trace expander 추가

DB 역할 컬럼 방식일 때만 다음 expander를 보여준다.

```text
행동 trace 연결 (선택)
```

컨트롤:

- checkbox: move trace 사용
- turn 컬럼
- actor ID 컬럼
- target ID 컬럼
- move name 컬럼
- action type 컬럼 `(없음)` 허용
- move action 값 목록 text input
- move power 컬럼 `(없음)` 허용
- move type 컬럼 `(없음)` 허용
- move category 컬럼 `(없음)` 허용
- move priority 컬럼 `(없음)` 허용

기본 컬럼 hint:

```python
turn: ("turn", "round", "턴", "라운드")
actor: ("actor", "attacker", "source", "caster", "user", "unit", "entity", "행동자", "공격자", "시전자")
target: ("target", "defender", "victim", "target_id", "대상", "타겟", "피격자")
move_name: ("move", "skill", "action_name", "ability_name", "무브", "스킬", "행동명")
action_col: ("action", "event", "type", "kind", "행동", "이벤트", "종류")
```

무브 속성 컬럼은 기존 move extraction hint와 맞춰도 된다.

### 2. log_schema에 trace fields 추가

checkbox가 켜져 있고 필수 컬럼이 선택되면 `_bb_log_schema`에 fields를 추가한다.

예:

```python
_bb_log_schema.update({
    "trace_moves_enabled": True,
    "turn_col": _bb_turn_col,
    "actor_id_col": _bb_actor_col,
    "target_id_col": _bb_target_col,
    "move_name_col": _bb_move_name_col,
    "action_col": None if _bb_action_col == "(없음)" else _bb_action_col,
    "move_action_values": [...],
    "move_power_col": ...,
    "move_type_col": ...,
    "move_category_col": ...,
    "move_priority_col": ...,
})
```

trace checkbox가 켜졌지만 필수 컬럼이 빠졌으면 warning을 표시하고 trace fields는 넣지 않는다.

### 3. per-battle game_config merge

현재 Step6는 worker task를 만들 때 같은 `_bb_gc`를 모든 battle에 넘긴다.
I3부터는 battle별 `trace_actions`가 달라질 수 있다.

loop를 다음처럼 바꾼다.

```python
for _bb_i, _battle in enumerate(_battles):
    if len(_battle) == 4:
        _a_team, _e_team, _ally_wins, _battle_gc = _battle
    else:
        _a_team, _e_team, _ally_wins = _battle
        _battle_gc = None

    _task_gc = copy.deepcopy(_bb_gc)
    if _battle_gc:
        _task_gc.update(_battle_gc)

    _bb_tasks.append((
        _a_team, _e_team, _bb_cf, _bb_spd, sys_stats, _bb_gf,
        _bb_mt, default_stochasticity_factory, _bb_rm,
        None, None, None, None, _task_gc, _bb_i,
    ))
```

주의:

- `_bb_gc` 자체를 루프 안에서 mutate하지 않는다.
- `_battle_gc`는 `trace_actions`, `preserve_ids` 정도만 담는다.
- 기존 3-tuple도 계속 처리한다.

## 금지 사항

- `modules/engine.py` 수정 금지
- switch trace 생성 금지
- faint incoming 생성 금지
- HP resync/timeline 생성 금지
- DB에 없는 행동을 추론해서 만들지 않는다.
- target이 없는 move row를 억지로 자동 타겟팅하지 않는다.
- 기존 chunk backtest는 변경하지 않는다.
- `trace_moves_enabled`가 꺼져 있으면 기존 DB role-schema backtest 결과 tuple 형식을 유지한다.

## 검증

### 1. AST

```python
import ast
from pathlib import Path
for p in ["modules/per_battle_backtest.py", "modules/step6_dashboard.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
```

### 2. trace builder 단위 검증

```python
import pandas as pd
from modules.per_battle_backtest import build_move_trace_actions_from_group

df = pd.DataFrame([
    {
        "turn": 1,
        "actor_id": "A1-log",
        "target_id": "E1-log",
        "move_name": "Tackle",
        "move_power": 40,
        "move_type": "Normal",
        "move_category": "Physical",
        "action_type": "move",
    }
])
ta = build_move_trace_actions_from_group(
    df,
    {
        "trace_moves_enabled": True,
        "turn_col": "turn",
        "actor_id_col": "actor_id",
        "target_id_col": "target_id",
        "move_name_col": "move_name",
        "action_col": "action_type",
        "move_power_col": "move_power",
        "move_type_col": "move_type",
        "move_category_col": "move_category",
    },
)
entry = ta["move"][(1, "A1-log")]
assert entry["target"] == "E1-log"
assert entry["move"]["name"] == "Tackle"
assert entry["move"]["power"] == 40
assert entry["move"]["type"] == "Normal"
```

### 3. move_library merge 검증

```python
df = pd.DataFrame([
    {"turn": 1, "actor_id": "A1", "target_id": "E1", "move_name": "Punch"}
])
ta = build_move_trace_actions_from_group(
    df,
    {
        "trace_moves_enabled": True,
        "turn_col": "turn",
        "actor_id_col": "actor_id",
        "target_id_col": "target_id",
        "move_name_col": "move_name",
    },
    move_library=[{"name": "Punch", "power": 50, "category": "Physical", "type": "Fighting", "contact": True}],
)
mv = ta["move"][(1, "A1")]["move"]
assert mv["power"] == 50
assert mv["contact"] is True
```

### 4. build_battles 4-tuple 검증

```python
import pandas as pd
from modules.per_battle_backtest import build_battles

df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1-log", "HP": 100, "win": 1,
     "turn": 1, "actor_id": "A1-log", "target_id": "E1-log", "move_name": "Tackle"},
    {"battle_id": 1, "side": "Enemy", "unit_id": "E1-log", "HP": 100, "win": 1,
     "turn": 1, "actor_id": "E1-log", "target_id": "A1-log", "move_name": "Growl"},
])
battles = build_battles(
    df, 2, "win", ["HP"], [], "HP",
    log_schema={
        "battle_id_col": "battle_id",
        "team_col": "side",
        "entity_id_col": "unit_id",
        "trace_moves_enabled": True,
        "turn_col": "turn",
        "actor_id_col": "actor_id",
        "target_id_col": "target_id",
        "move_name_col": "move_name",
    },
)
assert len(battles) == 1
assert len(battles[0]) == 4
ally, enemy, actual, battle_gc = battles[0]
assert ally[0]["id"] == "A1-log"
assert enemy[0]["id"] == "E1-log"
assert battle_gc["preserve_ids"] is True
assert battle_gc["trace_actions"]["move"][(1, "A1-log")]["target"] == "E1-log"
```

### 5. trace disabled 회귀

같은 df에서 `trace_moves_enabled`를 빼면 기존 3-tuple이어야 한다.

```python
battles = build_battles(
    df, 2, "win", ["HP"], [], "HP",
    log_schema={
        "battle_id_col": "battle_id",
        "team_col": "side",
        "entity_id_col": "unit_id",
    },
)
assert len(battles[0]) == 3
```

### 6. engine smoke

trace action을 넣었을 때 로그에 trace move가 등장해야 한다.

```python
from modules.engine import run_simulation

ally = [{"id": "A1-log", "name": "ally", "HP": 100, "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1-log", "name": "enemy", "HP": 100, "resources": {"HP": {"current": 100, "max": 100}}}]
gc = {
    "preserve_ids": True,
    "trace_actions": {
        "move": {
            (1, "A1-log"): {"move": {"name": "Tackle", "power": 0, "category": None, "type": None}, "target": "E1-log"},
            (1, "E1-log"): {"move": {"name": "Growl", "power": 0, "category": None, "type": None}, "target": "A1-log"},
        },
        "switch": {},
    },
}
winner, logs, metrics = run_simulation(
    ally, enemy,
    max_turns=1,
    sys_stats=["HP"],
    global_damage_formula="0",
    game_config=gc,
    silent=False,
)
joined = "\n".join(logs)
assert "Tackle" in joined
assert "Growl" in joined
```

### 7. Step6 grep 확인

- UI에 `trace_moves_enabled` 또는 동등한 checkbox가 있다.
- `turn_col`, `actor_id_col`, `target_id_col`, `move_name_col`이 `_bb_log_schema`에 들어간다.
- worker loop가 3-tuple/4-tuple을 모두 처리한다.
- per-battle `_task_gc`를 만들어 `_battle_gc`를 merge한다.

## 완료 기준

DB role-schema backtest에서 move trace를 켜면,
각 battle group의 action rows가 해당 battle만의 `game_config["trace_actions"]["move"]`로 변환되어
엔진 worker task에 전달되어야 한다.

이 PR이 끝나면 DB 로그가 이미 명시적 행동 기록을 갖고 있는 경우,
시뮬레이터는 더 이상 무브 선택을 전부 자체 정책에 맡기지 않고 DB의 실제 행동 순서를 부분적으로 따라갈 수 있다.
