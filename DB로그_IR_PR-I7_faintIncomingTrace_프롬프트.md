# DB로그 IR PR-I7 — faint incoming trace 연결

## 목적

엔진/TurnManager에는 이미 기절 후 예비 등장 순서를 로그로 지정하는 입력이 있다.

현재 엔진 입력:

```python
game_config["trace_faint_incoming"] = [
    {"turn": 1, "side": "Ally", "outgoing": "A1", "incoming": "A3"},
]
game_config["on_active_faint"] = "replace_from_reserve"
```

`SequentialTurnManager._resolve_faint(...)`는 active 유닛이 죽었을 때 `trace_faint_incoming`의 `outgoing -> incoming` 지정을 우선 사용한다.

하지만 DB 역할 스키마 백테스트 경로는 아직 이 값을 만들지 않는다.

이번 PR의 목적은 DB 로그의 “기절 후 등장/강제 교체/KO replacement” 행을 `trace_faint_incoming`으로 변환해, 관측 로그의 강제 예비 등장 순서를 엔진 재시뮬레이션에 연결하는 것이다.

이건 포켓몬 전용이 아니다. SRPG/가챠/JRPG/몬스터 배틀처럼 active slot과 reserve/bench가 있는 턴제 게임에서 “누가 쓰러진 뒤 누가 들어왔는가”를 복제하는 범용 연결층이다.

## 현재 상태

이미 존재:

- `modules/turn_manager.py`
  - `trace_faint_incoming`을 받아 forced replacement 대상 선택
  - `on_active_faint == "replace_from_reserve"`일 때만 작동
- `modules/engine.py`
  - `game_config["trace_faint_incoming"]`을 TurnManager에 전달
- `modules/per_battle_backtest.py`
  - move trace, switch trace는 만든다.
  - faint incoming trace는 아직 만들지 않는다.
- `modules/step6_dashboard.py`
  - move trace, switch trace UI는 있다.
  - faint incoming trace UI는 없다.

## 변경 요구

### 1. log_schema 확장

다음 optional 키를 추가한다.

```python
"trace_faint_incoming_enabled": bool,
"faint_turn_col": None | str,
"faint_side_col": None | str,
"faint_outgoing_id_col": None | str,
"faint_incoming_id_col": None | str,
"faint_action_col": None | str,
"faint_action_values": list[str],
```

기본 동작:

- `trace_faint_incoming_enabled`가 없거나 False면 기존과 완전히 동일하다.
- `faint_turn_col`이 없으면 `switch_turn_col` 또는 `turn_col`을 재사용한다.
- `faint_outgoing_id_col`이 없으면 `switch_outgoing_id_col` 또는 `actor_id_col`을 재사용한다.
- `faint_side_col`이 없으면 `team_col`을 재사용한다. 단, side는 엔진 필수값은 아니므로 없어도 skip하지 않는다.
- `faint_action_col`이 없으면 `switch_action_col` 또는 `action_col`을 재사용한다.
- `faint_action_values` 기본값:

```python
[
    "faint_replace", "replace", "replacement", "send_out", "enter_after_faint",
    "fainted_switch", "faint_incoming", "ko_replace", "forced_switch",
    "기절교체", "쓰러짐교체", "강제교체", "등장", "진입"
]
```

### 2. per_battle_backtest.py 수정

#### 2-1. faint incoming builder 추가

새 helper를 추가한다.

```python
def build_faint_incoming_trace_from_group(group, log_schema):
    ...
```

반환:

```python
[
    {"turn": turn, "side": side_optional, "outgoing": outgoing_id, "incoming": incoming_id},
    ...
]
```

필수 조건:

- `trace_faint_incoming_enabled`가 True여야 한다.
- turn/outgoing/incoming 컬럼을 찾을 수 있어야 한다.
- turn은 `_coerce_turn(...)`로 int 변환한다.
- outgoing/incoming이 `_is_empty_id(...)`이면 skip한다.
- side가 없거나 비어 있어도 skip하지 않는다. side가 있으면 entry에 넣는다.

action filtering:

- `faint_action_col`이 설정되어 있고 컬럼이 존재하면, 해당 값이 `faint_action_values`에 포함될 때만 후보로 본다.
- `faint_action_col`이 없으면 incoming id 컬럼이 비어 있지 않은 행을 후보로 본다.
- 비교는 `str(...).strip().lower()` 기준이다.

중복 처리:

- 같은 `(turn, outgoing_id)`가 여러 번 나오면 뒤 행이 이긴다.
- 반환 list에는 최종값만 남긴다.

구현 힌트:

```python
dedup = {}
dedup[(turn, outgoing_id)] = entry
return list(dedup.values())
```

#### 2-2. participant ID 필터 추가

새 helper를 추가한다.

```python
def _filter_faint_incoming_for_participants(entries, participant_ids):
    ...
```

동작:

- `outgoing`과 `incoming`이 모두 `participant_ids`에 있을 때만 남긴다.
- `turn`, `side` 등 부가 필드는 유지한다.

#### 2-3. build_battles_from_log_schema(...)에 병합

현재 trace 처리부는 move/switch trace를 만들어 `battle_gc`에 넣는다.

요구:

```python
trace_actions = {"move": {}, "switch": {}}
faint_incoming = []

if log_schema.get("trace_moves_enabled"):
    ...
if log_schema.get("trace_switches_enabled"):
    ...
if log_schema.get("trace_faint_incoming_enabled"):
    faint_incoming = build_faint_incoming_trace_from_group(...)
```

participant ID가 유니크할 때:

```python
filtered_trace = _filter_trace_actions_for_participants(...)
filtered_faint = _filter_faint_incoming_for_participants(faint_incoming, participant_ids)
```

4튜플 생성 조건:

```python
if filtered_trace.get("move") or filtered_trace.get("switch") or filtered_faint:
    battle_gc = {"preserve_ids": True}
    if filtered_trace has anything:
        battle_gc["trace_actions"] = filtered_trace
    if filtered_faint:
        battle_gc["trace_faint_incoming"] = filtered_faint
        battle_gc["on_active_faint"] = "replace_from_reserve"
    battles.append((ally_team, enemy_team, ally_wins, battle_gc))
else:
    battles.append((ally_team, enemy_team, ally_wins))
```

주의:

- `trace_actions` 구조를 바꾸지 않는다.
- faint incoming만 있는 battle도 4튜플이어야 한다.
- participant ID가 유니크하지 않으면 기존 guard처럼 trace config를 붙이지 않는다.
- `active_count`는 여기서 추측해서 설정하지 않는다. 사용자가 Step2/game_config에서 정한다.

### 3. step6_dashboard.py UI 수정

Step6 DB 역할 컬럼 방식의 `행동 trace 연결 (선택)` expander 안에 faint incoming trace UI를 추가한다.

추가 checkbox:

```python
_tf_use = st.checkbox("faint incoming trace 사용", value=False)
```

추가 UI:

- `faint turn 컬럼`
- `faint side 컬럼 (선택)`
- `faint outgoing ID 컬럼`
- `faint incoming ID 컬럼`
- `faint action type 컬럼 (선택)`
- `faint action 값 목록 (쉼표 구분)`

guess 후보:

```python
# outgoing
["fainted", "faint", "ko", "dead", "defeated", "outgoing",
 "old_unit", "unit", "actor", "쓰러짐", "기절", "이탈"]

# incoming
["incoming", "replacement", "replace", "send_out", "next_unit",
 "new_unit", "bench_in", "진입", "등장", "교체대상"]

# side
["side", "team", "camp", "faction", "player", "진영", "팀"]

# action
["action", "event", "type", "kind", "faint", "ko", "replace",
 "send_out", "기절", "쓰러짐", "등장", "진입"]
```

스키마 반영:

```python
"trace_faint_incoming_enabled": True,
"faint_turn_col": _bb_faint_turn_col,
"faint_side_col": None if _bb_faint_side_col == "(없음)" else _bb_faint_side_col,
"faint_outgoing_id_col": _bb_faint_out_col,
"faint_incoming_id_col": _bb_faint_in_col,
"faint_action_col": None if _bb_faint_action_col == "(없음)" else _bb_faint_action_col,
"faint_action_values": [x.strip() for x in _bb_faint_action_vals.split(",") if x.strip()],
```

주의:

- move trace, switch trace, faint incoming trace는 서로 독립 checkbox여야 한다.
- faint incoming trace도 participant ID 보존이 필요하므로 `참가자 ID 컬럼`이 없으면 warning을 띄우고 활성화하지 않는다.
- faint incoming trace만 켜도 4튜플 battle config가 만들어져야 한다.

## 금지

- `modules/engine.py` 수정 금지
- `modules/turn_manager.py` 수정 금지
- `trace_actions` 구조 변경 금지
- move trace/switch trace/order priority 동작 변경 금지
- `active_count`를 임의로 설정하지 말 것
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

### 2. faint incoming builder 단독 검증

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_faint_incoming_trace_from_group

df = pd.DataFrame([
    {"turn": 1, "side": "Ally", "outgoing": "A1", "incoming": "A3", "action": "replace"},
    {"turn": 1, "side": "Enemy", "outgoing": "E1", "incoming": "E2", "action": "move"},
])
schema = {
    "trace_faint_incoming_enabled": True,
    "faint_turn_col": "turn",
    "faint_side_col": "side",
    "faint_outgoing_id_col": "outgoing",
    "faint_incoming_id_col": "incoming",
    "faint_action_col": "action",
    "faint_action_values": ["replace"],
}
entries = build_faint_incoming_trace_from_group(df, schema)
print(entries)
assert entries == [{"turn": 1, "side": "Ally", "outgoing": "A1", "incoming": "A3"}]
print("faint incoming builder OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 3. participant ID 필터 검증

```powershell
@'
from modules.per_battle_backtest import _filter_faint_incoming_for_participants

entries = [
    {"turn": 1, "side": "Ally", "outgoing": "A1", "incoming": "A3"},
    {"turn": 1, "side": "Enemy", "outgoing": "E1", "incoming": "missing"},
]
filtered = _filter_faint_incoming_for_participants(entries, {"A1", "A3", "E1"})
print(filtered)
assert filtered == [{"turn": 1, "side": "Ally", "outgoing": "A1", "incoming": "A3"}]
print("faint incoming participant filter OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 4. build_battles가 faint-only trace도 4튜플로 반환한다

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_battles

df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1", "result": "win", "HP": 100, "SPD": 10,
     "turn": 1, "outgoing": "A1", "incoming": "A3", "action": "replace"},
    {"battle_id": 1, "side": "Ally", "unit_id": "A2", "result": "win", "HP": 100, "SPD": 20,
     "turn": "", "outgoing": "", "incoming": "", "action": ""},
    {"battle_id": 1, "side": "Ally", "unit_id": "A3", "result": "win", "HP": 100, "SPD": 30,
     "turn": "", "outgoing": "", "incoming": "", "action": ""},
    {"battle_id": 1, "side": "Enemy", "unit_id": "E1", "result": "lose", "HP": 100, "SPD": 40,
     "turn": "", "outgoing": "", "incoming": "", "action": ""},
])
schema = {
    "battle_id_col": "battle_id",
    "team_col": "side",
    "entity_id_col": "unit_id",
    "result_mode": "battle_level",
    "trace_faint_incoming_enabled": True,
    "faint_turn_col": "turn",
    "faint_side_col": "side",
    "faint_outgoing_id_col": "outgoing",
    "faint_incoming_id_col": "incoming",
    "faint_action_col": "action",
    "faint_action_values": ["replace"],
}
battles = build_battles(df, 2, "result", ["HP", "SPD"], [], "HP",
                        max_battles=10, game_config={}, log_schema=schema)
print("battle_count", len(battles), "tuple_len", len(battles[0]) if battles else None)
assert len(battles) == 1 and len(battles[0]) == 4
gc = battles[0][3]
assert gc["trace_faint_incoming"] == [{"turn": 1, "side": "Ally", "outgoing": "A1", "incoming": "A3"}]
assert gc["on_active_faint"] == "replace_from_reserve"
assert gc["preserve_ids"] is True
print("build_battles faint-only trace OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 5. 엔진 연결 확인

이 테스트는 A1이 쓰러졌을 때 roster 순서상 먼저인 A2가 아니라 trace가 지정한 A3가 등장하는지 확인한다.

```powershell
$env:PYTHONIOENCODING='utf-8'; @'
from modules.engine import run_simulation

ally = [
    {"id": "A1", "name": "Lead", "HP": 100, "SPD": 10,
     "resources": {"HP": {"current": 100, "max": 100}}},
    {"id": "A2", "name": "Bench2", "HP": 100, "SPD": 20,
     "resources": {"HP": {"current": 100, "max": 100}}},
    {"id": "A3", "name": "Bench3", "HP": 100, "SPD": 30,
     "resources": {"HP": {"current": 100, "max": 100}}},
]
enemy = [
    {"id": "E1", "name": "Enemy", "HP": 100, "SPD": 999,
     "resources": {"HP": {"current": 100, "max": 100}}},
]
gc = {
    "preserve_ids": True,
    "active_count": 1,
    "on_active_faint": "replace_from_reserve",
    "trace_faint_incoming": [
        {"turn": 1, "side": "Ally", "outgoing": "A1", "incoming": "A3"},
    ],
}
winner, logs, metrics = run_simulation(
    ally, enemy, max_turns=1,
    speed_stat="SPD",
    sys_stats=["HP", "SPD"],
    global_damage_formula="999",
    game_config=gc,
    silent=False,
)
joined = "\n".join(logs)
for line in logs:
    if "A1" in line or "A2" in line or "A3" in line:
        print(line.encode("unicode_escape").decode())
assert "A3" in joined
assert "A2" not in joined or joined.find("A3") < joined.find("A2")
print("engine faint incoming trace OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

## 완료 기준

- DB 행에서 faint incoming list를 만든다.
- participant ID 불일치 faint incoming은 제거된다.
- faint-only trace도 battle 4튜플을 만든다.
- battle config에 `trace_faint_incoming`과 `on_active_faint="replace_from_reserve"`가 들어간다.
- 엔진에서 roster 기본 순서가 아니라 trace가 지정한 incoming이 등장한다.
