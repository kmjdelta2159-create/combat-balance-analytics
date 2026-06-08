# DB로그 IR PR-I5 — action order 컬럼을 trace priority로 변환

## 목적

PR-I4에서 엔진/TurnManager가 `trace_actions["move"][(turn, actor_id)]["move"]["priority"]`를 현재 턴 기준으로 읽어 행동 순서를 정렬할 수 있게 됐다.

이제 DB 로그에 흔히 있는 `action_order`, `seq`, `order`, `timeline_order` 같은 실행 순서 컬럼을 move trace의 priority로 변환한다.

중요한 점:

- 엔진/TurnManager는 건드리지 않는다.
- `per_battle_backtest.py`의 DB 로그 IR 빌더와 `step6_dashboard.py`의 Step6 UI만 수정한다.
- 이 작업은 포켓몬 전용 기능이 아니라 DB 로그 기반 턴제 복제의 연결층이다.

## 현재 상태

이미 존재하는 기능:

- `build_move_trace_actions_from_group(...)`
  - DB 로그 행에서 `(turn, actor_id) -> {"move": ..., "target": ...}`를 만든다.
- `_move_from_row(...)`
  - `move_name_col`, `move_power_col`, `move_type_col`, `move_category_col`, `move_priority_col`를 읽는다.
- Step6 trace UI
  - turn / actor / target / move name / action type / move priority 컬럼을 고를 수 있다.

부족한 점:

- DB 로그의 실제 실행 순서 컬럼을 아직 trace priority로 변환하지 않는다.
- 따라서 로그에 move priority가 없고 실행 순서만 있는 데이터에서는 I4의 턴별 priority 정렬을 충분히 활용하지 못한다.

## 변경 요구

### 1. log_schema 확장

`log_schema`에 다음 optional 키를 추가한다.

```python
"move_order_col": None | str,
"move_order_direction": "ascending_first" | "descending_first",
```

기본값:

```python
move_order_col = None
move_order_direction = "ascending_first"
```

의미:

- `ascending_first`: order 값이 작은 행이 먼저 실행됨. 예: 1, 2, 3 순서.
- `descending_first`: order 값이 큰 행이 먼저 실행됨. 예: 99, 80, 10 순서.

### 2. per_battle_backtest.py 수정

대상 함수:

- `build_move_trace_actions_from_group(...)`

요구 동작:

1. 기존처럼 move trace 후보 행을 읽되, 바로 `trace_move[(turn, actor_id)] = ...`로 넣지 말고 후보 리스트를 먼저 만든다.

2. 후보에는 최소 다음 값을 담는다.

```python
{
    "turn": turn,
    "actor_id": actor_id,
    "target": target_id,
    "move": move_dict,
    "_row_seq": row_sequence_in_group,
    "_order": raw_order_value_or_none,
}
```

3. `move_order_col`이 설정되어 있고 해당 턴 후보 중 유효한 order 값이 하나라도 있으면, 턴 단위로 후보를 정렬한 뒤 synthetic priority를 덮어쓴다.

정렬 규칙:

- 숫자로 파싱 가능한 값은 숫자 기준으로 정렬한다.
- 숫자로 파싱 불가능한 값은 문자열 기준으로 정렬한다.
- `ascending_first`면 작은 값이 먼저 온다.
- `descending_first`면 큰 값이 먼저 온다.
- order 값이 비어 있는 후보는 같은 턴의 order 후보 뒤에 `_row_seq` 순으로 둔다.
- 동일 order 값은 `_row_seq` 순서를 유지한다.

priority 부여 규칙:

- I4 엔진은 priority가 큰 행동을 먼저 실행한다.
- 따라서 정렬된 첫 후보에 가장 큰 synthetic priority를 부여한다.
- 간단하고 결정적으로:

```python
move["priority"] = len(ordered_turn_candidates) - idx
```

- `move_order_col`이 유효하게 작동하는 턴에서는 DB의 관측 실행 순서가 우선이므로 기존 move priority 값은 덮어써도 된다.
- `move_order_col`이 없거나 해당 턴에 유효 order 값이 하나도 없으면 기존 `_move_from_row(...)`의 `move_priority_col`/move library priority 동작을 그대로 유지한다.

4. 반환 구조는 절대 바꾸지 않는다.

```python
return {"move": trace_move, "switch": {}}
```

5. 기존 guard를 유지한다.

- turn/actor/target/move name이 없으면 해당 행 skip
- action_col이 설정되어 있으면 move action value에 맞는 행만 포함
- participant ID 정합성 필터는 기존 `_filter_trace_actions_for_participants(...)` 쪽 동작을 깨지 않는다.

권장 helper:

```python
def _order_sort_key(v):
    ...
```

단, 새 helper는 `per_battle_backtest.py` 내부에만 둔다.

### 3. step6_dashboard.py UI 수정

Step6의 `행동 trace 연결` expander 안에 optional action order UI를 추가한다.

추가 UI:

- `action order 컬럼 (선택)` selectbox
- `order 방향` selectbox 또는 radio

컬럼 guess 후보 예:

```python
["action_order", "order", "sequence", "seq", "action_seq", "turn_order",
 "timeline_order", "log_index", "행동순서", "순서"]
```

스키마 반영:

```python
"move_order_col": None if _bb_move_order == "(없음)" else _bb_move_order,
"move_order_direction": _bb_move_order_dir,
```

주의:

- move trace 사용 조건은 기존과 동일하게 `entity_id_col`이 필요하다.
- action order 컬럼은 선택 사항이다.
- 사용자가 선택하지 않으면 기존 동작이 완전히 유지되어야 한다.

## 금지

- `modules/engine.py` 수정 금지
- `modules/turn_manager.py` 수정 금지
- DB 역할 스키마의 Ally/Enemy 분리 방식 변경 금지
- 예전 N행 반반 split 방식 수정 금지
- 새 의존성 추가 금지
- trace action 반환 구조 변경 금지

## 수동 검증 코드

작업 후 아래 검증을 실행한다.

### 1. AST

```powershell
@'
import ast
from pathlib import Path
for p in ["modules/per_battle_backtest.py", "modules/step6_dashboard.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 2. ascending_first order가 synthetic priority를 만든다

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_move_trace_actions_from_group

df = pd.DataFrame([
    {"battle_id": 1, "turn": 1, "actor": "slow", "target": "fast", "move": "Quick", "ord": 1},
    {"battle_id": 1, "turn": 1, "actor": "fast", "target": "slow", "move": "SlowHit", "ord": 2},
])
schema = {
    "trace_moves_enabled": True,
    "turn_col": "turn",
    "actor_id_col": "actor",
    "target_id_col": "target",
    "move_name_col": "move",
    "move_order_col": "ord",
    "move_order_direction": "ascending_first",
}
ta = build_move_trace_actions_from_group(df, schema)
print(ta["move"][(1, "slow")]["move"]["priority"], ta["move"][(1, "fast")]["move"]["priority"])
assert ta["move"][(1, "slow")]["move"]["priority"] > ta["move"][(1, "fast")]["move"]["priority"]
print("ascending order priority OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 3. descending_first도 반대로 동작한다

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_move_trace_actions_from_group

df = pd.DataFrame([
    {"battle_id": 1, "turn": 1, "actor": "slow", "target": "fast", "move": "Quick", "ord": 1},
    {"battle_id": 1, "turn": 1, "actor": "fast", "target": "slow", "move": "SlowHit", "ord": 2},
])
schema = {
    "trace_moves_enabled": True,
    "turn_col": "turn",
    "actor_id_col": "actor",
    "target_id_col": "target",
    "move_name_col": "move",
    "move_order_col": "ord",
    "move_order_direction": "descending_first",
}
ta = build_move_trace_actions_from_group(df, schema)
print(ta["move"][(1, "slow")]["move"]["priority"], ta["move"][(1, "fast")]["move"]["priority"])
assert ta["move"][(1, "fast")]["move"]["priority"] > ta["move"][(1, "slow")]["move"]["priority"]
print("descending order priority OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 4. order 컬럼이 없으면 기존 move priority가 유지된다

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_move_trace_actions_from_group

df = pd.DataFrame([
    {"battle_id": 1, "turn": 1, "actor": "A", "target": "E", "move": "M1", "pri": 7},
])
schema = {
    "trace_moves_enabled": True,
    "turn_col": "turn",
    "actor_id_col": "actor",
    "target_id_col": "target",
    "move_name_col": "move",
    "move_priority_col": "pri",
}
ta = build_move_trace_actions_from_group(df, schema)
print(ta["move"][(1, "A")]["move"]["priority"])
assert ta["move"][(1, "A")]["move"]["priority"] == 7
print("existing move priority fallback OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 5. 엔진 연결 확인

```powershell
$env:PYTHONIOENCODING='utf-8'; @'
import pandas as pd
from modules.per_battle_backtest import build_move_trace_actions_from_group
from modules.engine import run_simulation

df = pd.DataFrame([
    {"turn": 1, "actor": "slow", "target": "fast", "move": "Quick", "ord": 1},
    {"turn": 1, "actor": "fast", "target": "slow", "move": "SlowHit", "ord": 2},
])
schema = {
    "trace_moves_enabled": True,
    "turn_col": "turn",
    "actor_id_col": "actor",
    "target_id_col": "target",
    "move_name_col": "move",
    "move_order_col": "ord",
    "move_order_direction": "ascending_first",
}
ta = build_move_trace_actions_from_group(df, schema)

ally = [{"id": "slow", "name": "Slow", "SPD": 1, "HP": 100,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "fast", "name": "Fast", "SPD": 999, "HP": 100,
          "resources": {"HP": {"current": 100, "max": 100}}}]

winner, logs, metrics = run_simulation(
    ally, enemy, max_turns=1,
    speed_stat="SPD",
    sys_stats=["HP", "SPD"],
    global_damage_formula="0",
    game_config={"preserve_ids": True, "trace_actions": ta},
    silent=False,
)
joined = "\n".join(logs)
print("Quick", joined.find("Quick"), "SlowHit", joined.find("SlowHit"))
assert joined.find("Quick") != -1 and joined.find("SlowHit") != -1
assert joined.find("Quick") < joined.find("SlowHit")
print("DB order -> engine trace priority OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

## 완료 기준

- 기존 move trace가 깨지지 않는다.
- `move_order_col` 미선택 시 기존 동작과 동일하다.
- `move_order_col` 선택 시 같은 turn 안에서 DB 관측 실행 순서가 synthetic priority로 반영된다.
- I4의 엔진 priority 정렬과 연결되어 실제 로그 행동 순서가 뒤집힌다.
- Step6에서 사용자가 DB action order 컬럼을 직접 지정할 수 있다.
