# DB로그 IR PR-I8 — 초기 active/on-field 상태 연결

## 목적

PR-I3~I7로 DB 로그의 move, action order, voluntary switch, faint incoming trace가 엔진에 연결됐다.

남은 중요한 연결은 전투 시작 시점의 필드 상태다.

현재 엔진은 `game_config["active_count"]`와 roster 순서로 초기 active/on-field를 정한다.

```python
p["on_field"] = roster_idx < active_count
```

이 방식은 단순 전투에는 괜찮지만, DB 로그 기반 재현에서는 다음 문제가 있다.

- 실제 로그의 lead/active 유닛이 roster 첫 번째가 아닐 수 있다.
- 팀마다 active 수가 다를 수 있다.
- switch/faint trace는 “누가 필드에 있었는가”가 맞아야 의미가 있다.

이번 PR의 목적은 DB 역할 스키마가 초기 active/on-field 상태를 읽고, 엔진이 이를 보존해서 시작하도록 연결하는 것이다.

이 작업은 포켓몬 전용이 아니다. active slot/bench/reserve가 있는 모든 스탯 기반 턴제 게임의 DB 로그 복제에 필요한 초기 상태 IR이다.

## 현재 상태

이미 존재:

- `modules/engine.py`
  - `active_count` 기반으로 초기 `on_field`를 설정한다.
- `modules/per_battle_backtest.py`
  - DB role schema로 participant id를 보존한다.
  - trace 4튜플 battle config를 만들 수 있다.
- `modules/step6_dashboard.py`
  - DB 역할 컬럼 방식 UI가 있다.

부족:

- DB의 initial active/lead/on-field 컬럼을 읽지 않는다.
- participant dict에 `on_field`를 넣어도 엔진 초기화에서 덮어쓴다.

## 변경 요구

### 1. engine.py — 초기 on_field 보존 옵션 추가

`run_simulation(...)`의 초기 on_field 설정 부분을 확장한다.

새 game_config 키:

```python
"preserve_initial_on_field": bool
```

동작:

- 기본값 False면 기존 동작과 완전히 동일하다.
- True이고, 해당 팀의 participant 중 하나라도 `on_field` 키를 가지고 있으면:
  - 그 팀은 instance/participant의 `on_field` 값을 보존한다.
  - `on_field`가 없는 멤버는 False로 본다.
  - 단, 해당 팀에 True가 하나도 없으면 기존 `active_count` fallback을 사용한다.
- True여도 어떤 팀에도 `on_field` 키가 없으면 기존 동작과 동일하다.
- `roster_idx`는 기존처럼 항상 부여한다.

권장 구조:

```python
_preserve_initial_on_field = bool(_gc_field.get("preserve_initial_on_field"))
for _team_name in ("Ally", "Enemy"):
    _team_members = [...]
    ...
    _has_explicit_on_field = _preserve_initial_on_field and any("on_field" in p for p in _team_members)
    if _has_explicit_on_field and any(bool(p.get("on_field")) for p in _team_members):
        for _p in _team_members:
            _p["on_field"] = bool(_p.get("on_field", False))
    else:
        for _ri, _p in enumerate(_team_members):
            _p["on_field"] = _ri < _ac
```

주의:

- 이 변경은 `preserve_initial_on_field`가 True일 때만 작동해야 한다.
- 기존 `active_count` 사용자 설정을 깨지 않는다.

### 2. per_battle_backtest.py — DB row에서 초기 on_field 읽기

#### 2-1. log_schema 확장

다음 optional 키를 추가한다.

```python
"initial_on_field_enabled": bool,
"initial_on_field_col": None | str,
"initial_on_field_values": list[str],
"initial_order_col": None | str,
```

기본값:

```python
initial_on_field_enabled = False
initial_on_field_values = ["1", "true", "yes", "y", "active", "lead", "on", "field", "front", "starter",
                           "초기", "선발", "활성", "필드", "전열"]
initial_order_col = None
```

의미:

- `initial_on_field_col`: 각 participant가 시작 시 active/on-field인지 나타내는 컬럼
- `initial_on_field_values`: active로 해석할 값 목록
- `initial_order_col`: optional. roster order를 DB 컬럼으로 정렬할 때 사용

#### 2-2. helper 추가

```python
def _is_initial_on_field_value(v, active_values):
    ...
```

동작:

- empty id면 False
- 문자열 lower/strip 후 active_values에 있으면 True
- 숫자값이면 `float(v) > 0`도 True로 처리
- `"0"`, `"false"`, `"no"`, `"bench"`, `"reserve"` 등은 False

#### 2-3. participant instance에 on_field 설정

`build_battles_from_log_schema(...)`에서 `ally_team`, `enemy_team` 생성 후, `initial_on_field_enabled`가 True이고 컬럼이 존재하면 각 inst에 `on_field`를 설정한다.

중요:

- `final_ally`와 `ally_team`의 순서가 대응한다고 가정하고 zip으로 적용한다.
- `final_enemy`와 `enemy_team`도 동일.

예:

```python
if log_schema.get("initial_on_field_enabled"):
    _apply_initial_on_field(ally_team, final_ally, log_schema)
    _apply_initial_on_field(enemy_team, final_enemy, log_schema)
```

`initial_order_col`이 설정되어 있으면 dedup 후 final rows를 그 컬럼 기준으로 정렬한다.

정렬 규칙:

- 숫자는 숫자 기준
- 문자열은 문자열 기준
- empty는 뒤로
- 정렬은 팀 내부에서만 수행

#### 2-4. battle_gc에 preserve flag 추가

초기 on_field 정보가 하나라도 적용되면 battle 4튜플을 만들어야 한다.

```python
battle_gc["preserve_initial_on_field"] = True
```

그리고 `preserve_ids`도 True로 둔다.

기존 trace와 병합:

- move/switch/faint trace가 있으면 같은 `battle_gc`에 같이 넣는다.
- initial on_field만 있어도 4튜플을 반환한다.
- participant ID 유니크 guard는 trace ID 필터에는 계속 적용한다.
- initial on_field 자체는 participant ID가 없어도 적용 가능하지만, DB 역할 스키마에서는 기존 entity_id_col 흐름을 우선한다.

권장 구현:

```python
battle_gc = {"preserve_ids": True}
has_battle_gc = False

if initial_applied:
    battle_gc["preserve_initial_on_field"] = True
    has_battle_gc = True

if filtered trace/faint:
    ...
    has_battle_gc = True

if has_battle_gc:
    battles.append((ally_team, enemy_team, ally_wins, battle_gc))
else:
    battles.append((ally_team, enemy_team, ally_wins))
```

### 3. step6_dashboard.py UI 수정

DB 역할 컬럼 방식에 `초기 필드 상태 (선택)` expander를 추가한다.

위치는 `팀 값(문자열) 상세 매핑`과 `행동 trace 연결 (선택)` 사이가 좋다.

UI:

```python
_if_use = st.checkbox("initial active/on-field 사용", value=False)
_bb_initial_on_field_col = st.selectbox("initial on-field 컬럼", _all_cols, ...)
_bb_initial_values = st.text_input("active로 인식할 값 목록 (쉼표 구분)", ...)
_bb_initial_order_col = st.selectbox("initial roster/order 컬럼 (선택)", _all_cols, ...)
```

guess 후보:

```python
# on-field flag
["on_field", "active", "lead", "starter", "front", "slot_active",
 "initial_active", "is_active", "field", "선발", "초기", "활성", "필드", "전열"]

# order
["roster_idx", "slot", "position", "party_order", "team_order", "order", "seq",
 "배치", "순서", "슬롯"]
```

schema 반영:

```python
"initial_on_field_enabled": True,
"initial_on_field_col": _bb_initial_on_field_col,
"initial_on_field_values": [x.strip() for x in _bb_initial_values.split(",") if x.strip()],
"initial_order_col": None if _bb_initial_order_col == "(없음)" else _bb_initial_order_col,
```

주의:

- 이 설정은 move/switch/faint trace와 독립이다.
- 켜졌는데 컬럼이 선택되지 않으면 warning을 띄우고 schema에 넣지 않는다.

## 금지

- trace_actions 구조 변경 금지
- move/switch/faint incoming trace 동작 변경 금지
- active_count 기존 동작 회귀 금지
- DB 역할 스키마 외 기존 N행 반반 방식 변경 금지
- 새 의존성 추가 금지

## 수동 검증 코드

### 1. AST

```powershell
@'
import ast
from pathlib import Path
for p in ["modules/engine.py", "modules/per_battle_backtest.py", "modules/step6_dashboard.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 2. 엔진 preserve_initial_on_field 직접 검증

```powershell
$env:PYTHONIOENCODING='utf-8'; @'
from modules.engine import run_simulation

ally = [
    {"id": "A1", "name": "Bench1", "HP": 100, "SPD": 1, "on_field": False,
     "resources": {"HP": {"current": 100, "max": 100}}},
    {"id": "A2", "name": "Lead2", "HP": 100, "SPD": 2, "on_field": True,
     "resources": {"HP": {"current": 100, "max": 100}}},
]
enemy = [
    {"id": "E1", "name": "Enemy", "HP": 100, "SPD": 999, "on_field": True,
     "resources": {"HP": {"current": 100, "max": 100}}},
]
winner, logs, metrics = run_simulation(
    ally, enemy, max_turns=1,
    speed_stat="SPD",
    sys_stats=["HP", "SPD"],
    global_damage_formula="0",
    game_config={"preserve_ids": True, "active_count": 1, "preserve_initial_on_field": True},
    silent=False,
)
joined = "\n".join(logs)
for line in logs:
    if "[Turn 1]" in line:
        print(line.encode("unicode_escape").decode())
assert "[Turn 1] A2" in joined
assert "[Turn 1] A1" not in joined
print("engine preserve_initial_on_field OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 3. 기본 active_count 회귀 검증

```powershell
$env:PYTHONIOENCODING='utf-8'; @'
from modules.engine import run_simulation

ally = [
    {"id": "A1", "name": "First", "HP": 100, "SPD": 1, "on_field": False,
     "resources": {"HP": {"current": 100, "max": 100}}},
    {"id": "A2", "name": "Second", "HP": 100, "SPD": 2, "on_field": True,
     "resources": {"HP": {"current": 100, "max": 100}}},
]
enemy = [
    {"id": "E1", "name": "Enemy", "HP": 100, "SPD": 999,
     "resources": {"HP": {"current": 100, "max": 100}}},
]
winner, logs, metrics = run_simulation(
    ally, enemy, max_turns=1,
    speed_stat="SPD",
    sys_stats=["HP", "SPD"],
    global_damage_formula="0",
    game_config={"preserve_ids": True, "active_count": 1},
    silent=False,
)
joined = "\n".join(logs)
for line in logs:
    if "[Turn 1]" in line:
        print(line.encode("unicode_escape").decode())
assert "[Turn 1] A1" in joined
assert "[Turn 1] A2" not in joined
print("active_count fallback regression OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 4. build_battles initial-only 4튜플 검증

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_battles

df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1", "result": "win", "HP": 100, "SPD": 10, "lead": 0, "slot": 1},
    {"battle_id": 1, "side": "Ally", "unit_id": "A2", "result": "win", "HP": 100, "SPD": 20, "lead": 1, "slot": 2},
    {"battle_id": 1, "side": "Enemy", "unit_id": "E1", "result": "lose", "HP": 100, "SPD": 30, "lead": 1, "slot": 1},
    {"battle_id": 1, "side": "Enemy", "unit_id": "E2", "result": "lose", "HP": 100, "SPD": 40, "lead": 0, "slot": 2},
])
schema = {
    "battle_id_col": "battle_id",
    "team_col": "side",
    "entity_id_col": "unit_id",
    "result_mode": "battle_level",
    "initial_on_field_enabled": True,
    "initial_on_field_col": "lead",
    "initial_on_field_values": ["1", "true", "lead"],
    "initial_order_col": "slot",
}
battles = build_battles(df, 2, "result", ["HP", "SPD"], [], "HP",
                        max_battles=10, game_config={}, log_schema=schema)
print("battle_count", len(battles), "tuple_len", len(battles[0]) if battles else None)
assert len(battles) == 1 and len(battles[0]) == 4
ally, enemy, ally_wins, gc = battles[0]
print([(u["id"], u.get("on_field")) for u in ally], [(u["id"], u.get("on_field")) for u in enemy], gc)
assert [u["id"] for u in ally] == ["A1", "A2"]
assert ally[0]["on_field"] is False and ally[1]["on_field"] is True
assert enemy[0]["on_field"] is True and enemy[1]["on_field"] is False
assert gc["preserve_initial_on_field"] is True
print("build_battles initial on-field OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 5. DB initial on-field → engine 연결 검증

```powershell
$env:PYTHONIOENCODING='utf-8'; @'
import pandas as pd
from modules.per_battle_backtest import build_battles
from modules.engine import run_simulation

df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1", "result": "win", "HP": 100, "SPD": 10, "lead": 0},
    {"battle_id": 1, "side": "Ally", "unit_id": "A2", "result": "win", "HP": 100, "SPD": 20, "lead": 1},
    {"battle_id": 1, "side": "Enemy", "unit_id": "E1", "result": "lose", "HP": 100, "SPD": 999, "lead": 1},
])
schema = {
    "battle_id_col": "battle_id",
    "team_col": "side",
    "entity_id_col": "unit_id",
    "result_mode": "battle_level",
    "initial_on_field_enabled": True,
    "initial_on_field_col": "lead",
    "initial_on_field_values": ["1"],
}
battles = build_battles(df, 2, "result", ["HP", "SPD"], [], "HP",
                        max_battles=10, game_config={}, log_schema=schema)
ally, enemy, ally_wins, gc = battles[0]
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
    if "[Turn 1]" in line:
        print(line.encode("unicode_escape").decode())
assert "[Turn 1] A2" in joined
assert "[Turn 1] A1" not in joined
print("DB initial on-field -> engine OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

## 완료 기준

- 엔진은 `preserve_initial_on_field=True`일 때 instance `on_field`를 보존한다.
- 기본 `active_count` 동작은 회귀하지 않는다.
- DB role schema가 initial active/on-field 컬럼을 participant에 반영한다.
- initial on-field만 있어도 battle 4튜플 config가 만들어진다.
- DB initial on-field 정보가 실제 엔진 행동자 선택에 반영된다.
