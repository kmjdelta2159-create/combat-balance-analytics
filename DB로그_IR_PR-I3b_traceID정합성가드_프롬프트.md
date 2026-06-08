# DB로그 IR PR-I3b - move trace ID 정합성 가드

## 목적

I3 적용 결과 핵심 기능은 들어갔다.

- `build_move_trace_actions_from_group(...)` 추가
- DB action row에서 `(turn, actor_id) -> {move, target}` 변환 가능
- trace 활성 시 DB role-schema battle이 4-tuple을 반환
- Step6 worker loop가 3-tuple/4-tuple을 모두 처리
- 엔진 smoke에서 `Tackle`, `Growl` trace move 로그 확인

다만 중요한 경계 조건이 있다.

move trace는 엔진 participant id와 DB action row의 `actor_id`, `target_id`가 맞아야 동작한다.
I2에서 `entity_id_col`을 보존한 이유가 바로 이것이다.

현재 구현은 `entity_id_col` 없이도 move trace를 켤 수 있다.
이 경우 DB actor id가 `"A1-log"` 같은 값인데 participant id는 엔진에서 `"A1"`, `"E1"`로 생성되어
trace action이 매칭되지 않는다.

더 위험한 점은 엔진 trace mode에서 `trace_actions`가 존재하지만 현재 actor의 action이 없으면
그 actor 행동을 skip한다는 것이다.

즉 잘못 연결된 trace는 “일부 행동 미적용”이 아니라 “전원이 행동하지 않는 전투”를 만들 수 있다.

이번 PR은 move trace의 ID 정합성 가드만 추가한다.

## 수정 대상

- `modules/per_battle_backtest.py`
- `modules/step6_dashboard.py`

가능하면 다른 파일은 수정하지 않는다.
`modules/engine.py`는 수정하지 않는다.

## per_battle_backtest 변경

### 1. participant id 수집 helper

추가:

```python
def _participant_ids(*teams):
    ...
```

동작:

- `ally_team`, `enemy_team`에서 top-level `id`를 수집한다.
- `_is_empty_id(...)`인 값은 제외한다.
- set을 반환한다.

### 2. trace action 필터 helper

추가:

```python
def _filter_trace_actions_for_participants(trace_actions, participant_ids):
    ...
```

동작:

- `trace_actions["move"]`만 대상으로 한다.
- actor id가 `participant_ids`에 없으면 제외한다.
- target id가 `participant_ids`에 없으면 제외한다.
- 남은 move dict만 `{"move": filtered, "switch": {}}`로 반환한다.

주의:

- 원본 `trace_actions`를 mutate하지 않는다.
- switch는 I3 범위 밖이므로 항상 `{}` 유지.

### 3. 4-tuple 생성 조건 강화

현재:

```python
if trace_actions and trace_actions.get("move"):
    battle_gc = {
        "trace_actions": trace_actions,
        "preserve_ids": True
    }
    battles.append((ally_team, enemy_team, ally_wins, battle_gc))
```

보정:

```python
participant_ids = _participant_ids(ally_team, enemy_team)
if len(participant_ids) < (len(ally_team) + len(enemy_team)):
    battles.append((ally_team, enemy_team, ally_wins))
else:
    filtered_trace = _filter_trace_actions_for_participants(trace_actions, participant_ids)
    if filtered_trace.get("move"):
        battle_gc = {"trace_actions": filtered_trace, "preserve_ids": True}
        battles.append((ally_team, enemy_team, ally_wins, battle_gc))
    else:
        battles.append((ally_team, enemy_team, ally_wins))
```

의도:

- 모든 participant가 보존 id를 가져야 trace를 켠다.
- actor/target id가 현재 battle participant에 없는 action row는 버린다.
- 유효 action이 하나도 없으면 기존 3-tuple로 fallback한다.
- trace mismatch 때문에 엔진이 모든 행동을 skip하는 상태를 만들지 않는다.

## Step6 변경

DB 역할 컬럼 방식에서 move trace checkbox가 켜졌을 때,
`entity_id_col`이 선택되지 않았으면 warning을 표시하고 trace fields를 `_bb_log_schema`에 넣지 않는다.

현재 필수 trace 컬럼 검사:

```python
if _bb_turn_col == "(없음)" or _bb_actor_col == "(없음)" or ...
```

여기에 entity id 검사도 추가한다.

```python
if _bb_ent_col == "(없음)":
    st.warning("move trace를 사용하려면 참가자 ID 컬럼이 필요합니다.")
```

중요:

- DB role-schema 자체는 `entity_id_col` 없이도 기존처럼 동작해야 한다.
- move trace만 `entity_id_col`을 요구한다.
- trace checkbox가 꺼져 있으면 warning을 띄우지 않는다.
- legacy chunk 방식은 변경하지 않는다.

## 금지 사항

- `modules/engine.py` 수정 금지
- actor/target id를 임의로 `A1/E1`에 매핑하지 않는다.
- target이 없는 action row를 자동 타겟팅하지 않는다.
- ID mismatch가 있는 action row를 억지로 살리지 않는다.
- trace mismatch 상태에서 4-tuple을 반환하지 않는다.
- 기존 trace disabled 3-tuple 경로를 깨지 않는다.

## 검증

### 1. AST

```python
import ast
from pathlib import Path
for p in ["modules/per_battle_backtest.py", "modules/step6_dashboard.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
```

### 2. 정상 trace 유지

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
assert len(battles[0]) == 4
assert battles[0][3]["trace_actions"]["move"][(1, "A1-log")]["target"] == "E1-log"
```

### 3. entity_id_col 없으면 trace fallback

```python
df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "HP": 100, "win": 1,
     "turn": 1, "actor_id": "A1-log", "target_id": "E1-log", "move_name": "Tackle"},
    {"battle_id": 1, "side": "Enemy", "HP": 100, "win": 1,
     "turn": 1, "actor_id": "E1-log", "target_id": "A1-log", "move_name": "Growl"},
])
battles = build_battles(
    df, 2, "win", ["HP"], [], "HP",
    log_schema={
        "battle_id_col": "battle_id",
        "team_col": "side",
        "trace_moves_enabled": True,
        "turn_col": "turn",
        "actor_id_col": "actor_id",
        "target_id_col": "target_id",
        "move_name_col": "move_name",
    },
)
assert len(battles[0]) == 3
```

### 4. actor mismatch action 제외

```python
df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1-log", "HP": 100, "win": 1,
     "turn": 1, "actor_id": "NOPE", "target_id": "E1-log", "move_name": "Tackle"},
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
assert len(battles[0]) == 4
trace_move = battles[0][3]["trace_actions"]["move"]
assert (1, "NOPE") not in trace_move
assert (1, "E1-log") in trace_move
```

### 5. 모든 action mismatch면 3-tuple fallback

```python
df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1-log", "HP": 100, "win": 1,
     "turn": 1, "actor_id": "NOPE1", "target_id": "E1-log", "move_name": "Tackle"},
    {"battle_id": 1, "side": "Enemy", "unit_id": "E1-log", "HP": 100, "win": 1,
     "turn": 1, "actor_id": "NOPE2", "target_id": "A1-log", "move_name": "Growl"},
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
assert len(battles[0]) == 3
```

### 6. Step6 grep 확인

- move trace checkbox가 켜진 경우 `entity_id_col` 선택을 검사한다.
- `entity_id_col`이 없으면 `_bb_log_schema.update({"trace_moves_enabled": True, ...})`를 실행하지 않는다.
- trace checkbox가 꺼져 있으면 기존 DB role-schema backtest는 그대로 가능하다.

## 완료 기준

move trace는 participant id와 action row id가 정합할 때만 활성화되어야 한다.
ID mismatch가 있는 DB 로그는 잘못된 trace mode로 엔진 행동을 침묵시키지 않고,
기존 DB role-schema 3-tuple backtest로 안전하게 fallback해야 한다.
