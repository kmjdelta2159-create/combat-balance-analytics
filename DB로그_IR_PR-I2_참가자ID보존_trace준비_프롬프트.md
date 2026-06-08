# DB로그 IR PR-I2 - 참가자 ID 보존 및 trace 준비

## 목적

I1/I1b로 DB 로그를 `battle_id -> team -> participants` 구조로 묶는 최소 IR 경로가 생겼다.

다음 목표는 DB 로그의 `turn/actor/action/move/target` 컬럼을 엔진의 기존
`game_config["trace_actions"]` hook에 연결하는 것이다.

그 전에 반드시 필요한 선행 조건이 있다.

엔진 trace hook은 `(turn, actor_id)`와 `target_id`를 기준으로 동작한다.

```python
game_config["trace_actions"]["move"][(turn, actor_id)] = {
    "move": move_dict,
    "target": target_id,
}
```

하지만 현재 DB role-schema backtest에서 `entity_id_col`은 dedup 기준으로만 쓰이고,
엔진 participant의 top-level `id`로 보존되지 않는다.

`run_simulation(...)`도 기본값에서는 참가자 id를 `A1`, `E1`처럼 다시 만든다.
기존 엔진에는 이를 막는 옵션이 이미 있다.

```python
game_config["preserve_ids"] = True
```

이번 PR의 목표는 DB role-schema 경로에서 `entity_id_col`을 엔진 participant `id`로 보존하고,
Step6 backtest 실행 시 해당 경로에서는 `preserve_ids=True`를 주입하는 것이다.

이번 PR은 action replay를 구현하지 않는다.
trace_actions 생성은 다음 PR에서 한다.

## 수정 대상

- `modules/per_battle_backtest.py`
- `modules/step6_dashboard.py`

가능하면 다른 파일은 수정하지 않는다.
`modules/engine.py`는 수정하지 않는다.

## per_battle_backtest 변경

### 1. 빈 값 helper

`per_battle_backtest.py` 안에 작은 local helper를 둔다.

```python
def _is_empty_id(v):
    ...
```

빈 값:

- `None`
- NaN
- `""`
- `"none"`
- `"nan"`
- `"null"`
- `"없음"`
- `"비어 있음"`
- `"<na>"`
- `"n/a"`

### 2. `_row_to_inst(...)` 시그니처 확장

현재:

```python
def _row_to_inst(row, system_stats, system_gimmicks, health_stat,
                 move_library=None, resource_config=None, game_config=None):
```

변경:

```python
def _row_to_inst(row, system_stats, system_gimmicks, health_stat,
                 move_library=None, resource_config=None, game_config=None,
                 instance_id_col=None):
```

동작:

```python
if instance_id_col and instance_id_col in row:
    raw_id = row.get(instance_id_col)
    if not _is_empty_id(raw_id):
        inst["id"] = str(raw_id).strip()
```

주의:

- `inst["name"]`은 기존처럼 유지한다.
- `id`만 top-level로 추가한다.
- 기존 chunk 경로에서는 `instance_id_col=None`이므로 동작 변화가 없어야 한다.
- `promote_effect_keys(...)` 호출은 유지한다.

### 3. DB role-schema 경로에서 entity_id_col 전달

`build_battles_from_log_schema(...)`에서 최종 row를 `_row_to_inst(...)`로 바꿀 때
`instance_id_col=entity_id_col`을 넘긴다.

예:

```python
ally_team = [
    _row_to_inst(
        r, system_stats, system_gimmicks, health_stat,
        move_library, resource_config, game_config,
        instance_id_col=entity_id_col,
    )
    for r in final_ally
]
```

Enemy도 동일하다.

### 4. legacy chunk 경로 유지

`build_battles(...)`의 기존 chunk 방식에서는 `instance_id_col`을 넘기지 않는다.

## Step6 변경

현재 Step6 backtest는 `build_battles(...)` 호출 시점에 `st.session_state.get("game_config")`를 직접 넘기고,
그 뒤에 `_bb_gc`를 다시 읽는다.

DB role-schema 경로에서는 `preserve_ids=True`가 필요하므로,
버튼 클릭 직후 `_bb_gc`를 먼저 만든 뒤 같은 객체를 `build_battles(...)`와 worker task에 모두 사용한다.

권장 구조:

```python
_bb_gc = copy.deepcopy(st.session_state.get("game_config") or {})
if _bb_log_schema and _bb_log_schema.get("entity_id_col"):
    _bb_gc["preserve_ids"] = True
```

그리고:

```python
_battles = build_battles(
    ...,
    game_config=_bb_gc,
    log_schema=_bb_log_schema,
)
```

뒤쪽 worker task에도 같은 `_bb_gc`를 사용한다.

주의:

- 이미 `copy`가 import되어 있으면 그대로 사용한다.
- `st.session_state["game_config"]` 원본을 직접 mutate하지 않는다.
- legacy chunk 방식에서는 `preserve_ids`를 자동으로 켜지 않는다.
- DB role-schema 방식이어도 `entity_id_col`이 없으면 `preserve_ids`를 자동으로 켜지 않는다.

## 금지 사항

- `modules/engine.py` 수정 금지
- `trace_actions` 생성 금지
- action/move/target UI 추가 금지
- 기존 chunk backtest 동작 변경 금지
- `entity_id_col` 값을 `name`에 덮어쓰기 금지
- 빈 id 값을 `"None"` 같은 문자열 id로 보존 금지

## 검증

### 1. AST

```python
import ast
from pathlib import Path
for p in ["modules/per_battle_backtest.py", "modules/step6_dashboard.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
```

### 2. `_row_to_inst` id 보존

```python
import pandas as pd
from modules.per_battle_backtest import _row_to_inst

row = pd.Series({"unit_id": "A-mon-1", "HP": 100})
inst = _row_to_inst(
    row,
    system_stats=["HP"],
    system_gimmicks=[],
    health_stat="HP",
    instance_id_col="unit_id",
)
assert inst["id"] == "A-mon-1"
assert inst["name"] == "log_row"
```

### 3. 빈 id 미보존

```python
row = pd.Series({"unit_id": "None", "HP": 100})
inst = _row_to_inst(
    row,
    system_stats=["HP"],
    system_gimmicks=[],
    health_stat="HP",
    instance_id_col="unit_id",
)
assert "id" not in inst
```

### 4. DB role-schema participant id 보존

```python
import pandas as pd
from modules.per_battle_backtest import build_battles

df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1-log", "HP": 100, "win": 1},
    {"battle_id": 1, "side": "Enemy", "unit_id": "E1-log", "HP": 100, "win": 1},
])
battles = build_battles(
    df, 2, "win", ["HP"], [], "HP",
    log_schema={
        "battle_id_col": "battle_id",
        "team_col": "side",
        "entity_id_col": "unit_id",
    },
)
ally, enemy, actual = battles[0]
assert ally[0]["id"] == "A1-log"
assert enemy[0]["id"] == "E1-log"
```

### 5. engine preserve_ids smoke

```python
from modules.engine import run_simulation

ally = [{"id": "A1-log", "name": "ally", "HP": 10, "resources": {"HP": {"current": 10, "max": 10}}}]
enemy = [{"id": "E1-log", "name": "enemy", "HP": 10, "resources": {"HP": {"current": 10, "max": 10}}}]
winner, logs, metrics = run_simulation(
    ally, enemy,
    max_turns=1,
    sys_stats=["HP"],
    global_damage_formula="0",
    game_config={"preserve_ids": True},
    silent=False,
)
joined = "\n".join(logs)
assert "A1-log" in joined or "E1-log" in joined
```

### 6. Step6 grep 확인

- 버튼 클릭 이후 `_bb_gc = copy.deepcopy(...)` 또는 동등한 복사 생성이 있다.
- `_bb_gc["preserve_ids"] = True`가 DB role-schema + entity_id_col 조건에서만 설정된다.
- `build_battles(..., game_config=_bb_gc, log_schema=_bb_log_schema)` 형태로 같은 config를 넘긴다.
- worker task에도 같은 `_bb_gc`가 들어간다.

## 완료 기준

DB role-schema backtest에서 `entity_id_col`이 지정되면,
엔진 participant id가 DB의 actor/unit id와 동일하게 유지되어야 한다.

이 상태가 되어야 다음 PR에서 DB 로그의 `turn/actor/move/target`을
`game_config["trace_actions"]`로 안전하게 변환할 수 있다.
