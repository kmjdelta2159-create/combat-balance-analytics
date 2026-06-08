# DB로그 IR PR-I6 — DB switch trace actions 연결

## 목적

엔진은 이미 trace 기반 교체를 실행할 수 있다.

현재 엔진 구조:

```python
trace_actions["switch"][(turn, outgoing_id)] = incoming_id
```

하지만 DB 역할 스키마 백테스트 경로(`per_battle_backtest.py`)는 아직 `switch` trace를 만들지 않고 항상 `{}`만 반환한다.

이번 PR의 목적은 DB 로그의 교체/태그/스위치 행을 `trace_actions["switch"]`로 변환해, 관측 로그의 교체 행동을 엔진 재시뮬레이션에 연결하는 것이다.

이 작업은 포켓몬 전용이 아니다. 벤치/후열/예비 유닛을 가진 스탯 기반 턴제 게임에서 “행동자가 이번 턴에 공격하지 않고 다른 참가자를 진입시켰다”는 DB 로그 정보를 복제본에 반영하는 범용 연결층이다.

## 현재 상태

이미 존재:

- `modules/engine.py`
  - `_maybe_voluntary_switch(ctx)`가 `trace_actions["switch"][(turn, char_id)]`를 읽어 교체 실행
  - `_predict_action_priority(unit, turn)`가 trace switch를 보면 `switch_priority`로 우선 정렬
- `modules/per_battle_backtest.py`
  - `build_move_trace_actions_from_group(...)`는 move trace만 만든다.
  - `_filter_trace_actions_for_participants(...)`는 현재 move만 필터링하고 switch는 비워둔다.
- `modules/step6_dashboard.py`
  - Step6 DB 역할 스키마 UI에 move trace 설정만 있다.

## 변경 요구

### 1. log_schema 확장

다음 optional 키를 추가한다.

```python
"trace_switches_enabled": bool,
"switch_turn_col": None | str,
"switch_outgoing_id_col": None | str,
"switch_incoming_id_col": None | str,
"switch_action_col": None | str,
"switch_action_values": list[str],
```

기본 동작:

- `trace_switches_enabled`가 없거나 False면 기존과 완전히 동일하다.
- `switch_turn_col`이 없으면 `turn_col`을 재사용한다.
- `switch_outgoing_id_col`이 없으면 `actor_id_col`을 재사용한다.
- `switch_action_col`이 없으면 `action_col`을 재사용한다.
- `switch_action_values` 기본값:

```python
["switch", "swap", "tag", "change", "substitute", "switch_out",
 "switch_in", "교체", "스위치", "태그", "변경"]
```

### 2. per_battle_backtest.py 수정

#### 2-1. switch trace builder 추가

새 helper를 추가한다.

```python
def build_switch_trace_actions_from_group(group, log_schema):
    ...
```

반환:

```python
{"move": {}, "switch": {(turn, outgoing_id): incoming_id}}
```

필수 조건:

- `trace_switches_enabled`가 True여야 한다.
- turn/outgoing/incoming 컬럼이 모두 있어야 한다.
- turn은 `_coerce_turn(...)`로 int 변환한다.
- outgoing/incoming이 `_is_empty_id(...)`이면 skip한다.

action filtering:

- `switch_action_col`이 설정되어 있고 컬럼이 존재하면, 해당 값이 `switch_action_values`에 포함될 때만 switch 후보로 본다.
- `switch_action_col`이 없으면 incoming id 컬럼이 비어 있지 않은 행을 switch 후보로 본다.
- 비교는 기존 move action과 동일하게 `str(...).strip().lower()` 기준이다.

중복 처리:

- 같은 `(turn, outgoing_id)`가 여러 번 나오면 뒤 행이 이긴다.
- 이는 현재 move trace의 동일 키 overwrite와 맞춘다.

#### 2-2. trace merge 추가

`build_battles_from_log_schema(...)`의 trace 생성부를 수정한다.

현재는 대략:

```python
if log_schema.get("trace_moves_enabled"):
    trace_actions = build_move_trace_actions_from_group(...)
    ...
```

요구:

```python
trace_actions = {"move": {}, "switch": {}}
if log_schema.get("trace_moves_enabled"):
    merge move trace
if log_schema.get("trace_switches_enabled"):
    merge switch trace
```

그리고 move 또는 switch 중 하나라도 남아 있으면 battle 4튜플을 반환한다.

```python
if filtered_trace.get("move") or filtered_trace.get("switch"):
    battles.append((ally_team, enemy_team, ally_wins, battle_gc))
else:
    battles.append((ally_team, enemy_team, ally_wins))
```

#### 2-3. participant ID 필터 확장

`_filter_trace_actions_for_participants(...)`를 확장한다.

현재:

```python
return {"move": filtered_move, "switch": {}}
```

변경:

```python
filtered_switch = {}
for (turn, outgoing_id), incoming_id in trace_actions["switch"].items():
    if outgoing_id in participant_ids and incoming_id in participant_ids:
        filtered_switch[(turn, outgoing_id)] = incoming_id
return {"move": filtered_move, "switch": filtered_switch}
```

기존 move 필터는 그대로 유지한다.

### 3. step6_dashboard.py UI 수정

Step6의 DB 역할 컬럼 방식 안에 있는 `행동 trace 연결 (선택)` expander를 확장한다.

현재 move trace checkbox가 있다.

추가:

```python
_ts_use = st.checkbox("switch trace 사용", value=False)
```

switch trace UI:

- `switch turn 컬럼`
- `switch outgoing ID 컬럼`
- `switch incoming ID 컬럼`
- `switch action type 컬럼 (선택)`
- `switch action 값 목록 (쉼표 구분)`

guess 후보:

```python
# incoming
["incoming", "switch_to", "next_unit", "new_unit", "replacement",
 "bench_in", "switch_in_id", "교체대상", "진입", "등장"]

# outgoing
["outgoing", "switch_from", "actor", "unit", "entity", "old_unit",
 "switch_out_id", "교체자", "이탈"]

# action
["action", "event", "type", "kind", "switch", "교체", "스위치", "태그"]
```

스키마 반영:

```python
"trace_switches_enabled": True,
"switch_turn_col": _bb_switch_turn_col,
"switch_outgoing_id_col": _bb_switch_out_col,
"switch_incoming_id_col": _bb_switch_in_col,
"switch_action_col": None if _bb_switch_action_col == "(없음)" else _bb_switch_action_col,
"switch_action_values": [x.strip() for x in _bb_switch_action_vals.split(",") if x.strip()],
```

주의:

- move trace와 switch trace는 독립적으로 켤 수 있어야 한다.
- switch trace만 켜도 `_bb_log_schema`에 trace 설정이 들어가야 한다.
- switch trace도 participant ID 보존이 필요하므로, `참가자 ID 컬럼`이 없으면 warning을 띄우고 활성화하지 않는다.
- move trace warning과 switch trace warning은 서로 독립적이어야 한다.

## 금지

- `modules/engine.py` 수정 금지
- `modules/turn_manager.py` 수정 금지
- `trace_actions` 구조 변경 금지
- move trace 동작 변경 금지
- action order priority overlay 동작 변경 금지
- 새 의존성 추가 금지

## 수동 검증 코드

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

### 2. switch trace builder 단독 검증

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_switch_trace_actions_from_group

df = pd.DataFrame([
    {"turn": 1, "actor": "A1", "incoming": "A2", "action": "switch"},
    {"turn": 1, "actor": "E1", "incoming": "E2", "action": "move"},
])
schema = {
    "trace_switches_enabled": True,
    "switch_turn_col": "turn",
    "switch_outgoing_id_col": "actor",
    "switch_incoming_id_col": "incoming",
    "switch_action_col": "action",
    "switch_action_values": ["switch"],
}
ta = build_switch_trace_actions_from_group(df, schema)
print(ta)
assert ta["switch"] == {(1, "A1"): "A2"}
assert ta["move"] == {}
print("switch trace builder OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 3. participant ID 필터가 switch도 검증한다

```powershell
@'
from modules.per_battle_backtest import _filter_trace_actions_for_participants

ta = {
    "move": {},
    "switch": {
        (1, "A1"): "A2",
        (1, "E1"): "missing",
    },
}
filtered = _filter_trace_actions_for_participants(ta, {"A1", "A2", "E1"})
print(filtered)
assert filtered["switch"] == {(1, "A1"): "A2"}
print("switch participant filter OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 4. build_battles가 switch-only trace도 4튜플로 반환한다

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_battles

df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1", "result": "win", "HP": 100, "SPD": 10,
     "turn": 1, "actor": "A1", "incoming": "A2", "action": "switch"},
    {"battle_id": 1, "side": "Ally", "unit_id": "A2", "result": "win", "HP": 100, "SPD": 20,
     "turn": "", "actor": "", "incoming": "", "action": ""},
    {"battle_id": 1, "side": "Enemy", "unit_id": "E1", "result": "lose", "HP": 100, "SPD": 30,
     "turn": "", "actor": "", "incoming": "", "action": ""},
])
schema = {
    "battle_id_col": "battle_id",
    "team_col": "side",
    "entity_id_col": "unit_id",
    "result_mode": "battle_level",
    "trace_switches_enabled": True,
    "switch_turn_col": "turn",
    "switch_outgoing_id_col": "actor",
    "switch_incoming_id_col": "incoming",
    "switch_action_col": "action",
    "switch_action_values": ["switch"],
}
battles = build_battles(df, 2, "result", ["HP", "SPD"], [], "HP",
                        max_battles=10, game_config={}, log_schema=schema)
print("battle_count", len(battles), "tuple_len", len(battles[0]) if battles else None)
assert len(battles) == 1 and len(battles[0]) == 4
assert battles[0][3]["trace_actions"]["switch"] == {(1, "A1"): "A2"}
print("build_battles switch-only trace OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 5. 엔진 연결 확인

```powershell
$env:PYTHONIOENCODING='utf-8'; @'
from modules.engine import run_simulation

ally = [
    {"id": "A1", "name": "Lead", "HP": 100, "SPD": 10,
     "resources": {"HP": {"current": 100, "max": 100}}},
    {"id": "A2", "name": "Bench", "HP": 100, "SPD": 20,
     "resources": {"HP": {"current": 100, "max": 100}}},
]
enemy = [
    {"id": "E1", "name": "Enemy", "HP": 100, "SPD": 30,
     "resources": {"HP": {"current": 100, "max": 100}}},
]
gc = {
    "preserve_ids": True,
    "active_count": 1,
    "trace_actions": {
        "move": {},
        "switch": {(1, "A1"): "A2"},
    },
    "switch_priority": 6,
}
winner, logs, metrics = run_simulation(
    ally, enemy, max_turns=1,
    speed_stat="SPD",
    sys_stats=["HP", "SPD"],
    global_damage_formula="0",
    game_config=gc,
    silent=False,
)
joined = "\n".join(logs)
for line in logs:
    if "A1" in line or "A2" in line:
        print(line.encode("unicode_escape").decode())
assert "A1" in joined and "A2" in joined
assert "교체" in joined or "trace" in joined.lower() or "트레이스" in joined
print("engine switch trace OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

## 완료 기준

- switch trace builder가 DB 행에서 `{(turn, outgoing): incoming}`을 만든다.
- move trace와 switch trace를 독립적으로 켜고 끌 수 있다.
- participant ID 불일치 switch는 4튜플 config에 들어가지 않는다.
- switch-only trace도 battle 4튜플을 만든다.
- 엔진이 DB에서 온 switch trace를 실제 교체 행동으로 실행한다.
