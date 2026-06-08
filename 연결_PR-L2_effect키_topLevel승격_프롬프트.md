# 연결 PR-L2 - effects 키 top-level 승격

## 목적

L1에서 Step2의 미소비 설정을 제거하고 `game_config["mechanisms"]["effects"]` JSON 입력을 연결했다.
하지만 현재 DB 로그 기반 인스턴스 생성 경로에서는 `ability`, `item`, `status` 값이 대부분
`inst["gimmicks"]` 안에만 남아 있다.

엔진의 effects dispatcher와 일부 전투 규칙은 top-level 키를 본다.

- `owner.get("ability")`
- `owner.get("item")`
- `owner.get("status")`

따라서 사용자가 Step2에서 다음과 같은 effects를 입력해도,
DB 로그/Step6 일반 경로에서는 해당 키가 top-level로 승격되지 않으면 발동하지 않는다.

```json
{
  "Leftovers": {
    "trigger": "ON_TURN_END",
    "effect": {"type": "heal_frac", "frac": 0.0625, "of": "maxhp"},
    "scope": "self",
    "source": "item"
  },
  "Burn": {
    "trigger": "ON_TURN_END",
    "effect": {"type": "damage_frac", "frac": 0.125, "of": "maxhp"},
    "scope": "self",
    "source": "status"
  }
}
```

이번 PR의 목표는 DB/Step6 인스턴스 생성 시점에 `ability`, `item`, `status` 역할 컬럼을
top-level 인스턴스 키로 보수적으로 복사하는 것이다.

## 현재 확인된 연결 지점

### 엔진

`modules/engine.py`의 `_act_effect_dispatch(ctx, phase)`는 다음 키를 사용한다.

```python
keys = [owner.get("ability"), owner.get("item"), owner.get("status")]
```

또한 엔진 일부 규칙도 top-level ability를 직접 참조한다.

- `Magic Guard`
- `Levitate`
- `Trick`류 item swap

이번 PR에서는 엔진 의미론을 바꾸지 않는다. 인스턴스 생성 경로에서 엔진이 기대하는 키를 채운다.

### Step6 수동 시뮬레이션

`modules/step6_dashboard.py`의 `df_to_instances(...)`는 현재 다음 형태로 인스턴스를 만든다.

```python
inst = {"name": row["Hero"], "gimmicks": {}}
for g in sys_gimmicks:
    inst["gimmicks"][g] = row.get(g, "None")
```

### Step6 최적화 경로

같은 파일의 `_opt_build_inst(...)`도 `gimmicks`만 복사한다.

```python
inst = {"name": str(name), "gimmicks": dict(gimmick_dict)}
```

### per-battle backtest

`modules/per_battle_backtest.py`의 `_row_to_inst(...)`도 동일하게 `gimmicks`만 만든다.

```python
inst = {"name": "log_row", "gimmicks": {}}
for g in system_gimmicks:
    inst["gimmicks"][g] = row.get(g, "None")
```

## 구현 범위

수정 대상:

- `modules/step2_system_definition.py`
- `modules/step6_dashboard.py`
- `modules/per_battle_backtest.py`
- 필요하면 새 순수 helper 모듈 1개 추가 가능

권장 구조:

- 새 파일 `modules/effect_key_roles.py`를 추가한다.
- 이 모듈은 Streamlit, engine, pandas에 의존하지 않는 순수 helper여야 한다.
- `step6_dashboard.py`와 `per_battle_backtest.py`에서 이 helper를 import해서 사용한다.

엔진 파일은 수정하지 않는다.

## Step2 변경

기존 Channel Mapping expander에 roles를 추가한다.

현재 `_channel_roles`에는 대략 다음 역할이 있다.

- `passive`
- `trigger`
- `target`
- `formula`
- `element`
- `damage_type`

여기에 다음 3개를 추가한다.

- `ability` - 특성/능력/패시브 보유값
- `item` - 아이템/장비/도구 보유값
- `status` - 현재 상태/상태이상 값

중요:

- 새 expander를 만들지 않는다.
- 새 독립 설정 블록을 만들지 않는다.
- 기존 Channel Mapping 저장 루프를 그대로 활용한다.
- 사용자가 명시적으로 `(없음)`을 선택하면 해당 role은 비활성으로 저장되어야 한다.
- 사용자가 선택하지 않으면 기존처럼 자동 감지 fallback을 허용한다.

## helper 요구사항

`modules/effect_key_roles.py`에 다음 성격의 helper를 만든다.

```python
EFFECT_KEY_ROLES = ("ability", "item", "status")

def promote_effect_keys(inst, game_config=None):
    ...
    return inst
```

동작 규칙:

1. `inst`는 dict이며 `inst["gimmicks"]`를 읽는다.
2. 이미 `inst["ability"]`, `inst["item"]`, `inst["status"]` 중 유효한 값이 있으면 덮어쓰지 않는다.
3. `game_config["channels"]`에 해당 role이 명시되어 있으면 그 컬럼을 우선한다.
4. 해당 role이 channels에서 `None`이면 그 role은 승격하지 않는다.
5. 명시 매핑이 없으면 컬럼명 hint로 fallback한다.
6. 값이 비어 있으면 승격하지 않는다.
7. `gimmicks` 원본 값은 삭제하지 않는다.

비어 있는 값으로 볼 예:

- `None`
- 빈 문자열
- `"None"`
- `"nan"`
- `"null"`
- `"없음"`
- `"비어 있음"`

권장 fallback hint:

```python
{
    "ability": ("ability", "trait", "passive", "특성", "어빌리티", "능력"),
    "item": ("item", "held_item", "held item", "equipment", "equip", "아이템", "도구", "장비"),
    "status": ("status", "state", "condition", "ailment", "상태", "상태이상"),
}
```

힌트는 컬럼명에 대해서만 적용한다. 값 자체를 보고 role을 추론하지 않는다.

## Step6 변경

`modules/step6_dashboard.py` 상단 import 영역에 helper를 추가한다.

```python
from modules.effect_key_roles import promote_effect_keys
```

### `df_to_instances(...)`

`inst["gimmicks"]`를 채운 직후, stats/resources/movepool 처리 전에 호출한다.

```python
for g in sys_gimmicks:
    inst["gimmicks"][g] = row.get(g, "None")
promote_effect_keys(inst, st.session_state.get("game_config"))
```

### `_opt_build_inst(...)`

`inst` 생성 직후, stats/resources/movepool 처리 전에 호출한다.

```python
inst = {"name": str(name), "gimmicks": dict(gimmick_dict)}
promote_effect_keys(inst, _gc)
```

주의:

- `_gc = st.session_state.get("game_config")`가 이미 근처에 있으므로 그것을 사용한다.
- optimizer score 계산 로직은 바꾸지 않는다.
- 기존 `gimmicks` 기반 ML/가중치 경로는 그대로 유지한다.

## per-battle backtest 변경

`modules/per_battle_backtest.py`에 helper import를 추가한다.

```python
from modules.effect_key_roles import promote_effect_keys
```

`_row_to_inst(...)`에 선택 인자를 추가한다.

```python
def _row_to_inst(row, system_stats, system_gimmicks, health_stat,
                 move_library=None, resource_config=None, game_config=None):
```

`gimmicks`를 채운 직후 호출한다.

```python
for g in system_gimmicks:
    inst["gimmicks"][g] = row.get(g, "None")
promote_effect_keys(inst, game_config)
```

`build_battles(...)`에도 선택 인자를 추가한다.

```python
def build_battles(..., max_battles=None, game_config=None):
```

그리고 `_row_to_inst(...)` 호출에 `game_config`를 전달한다.

기존 호출 호환성을 깨지 않도록 `game_config`는 마지막 keyword-only 성격의 optional 인자로 둔다.

## Step6 backtest 호출부 변경

`modules/step6_dashboard.py`의 `build_battles(...)` 호출에서 `game_config`를 넘긴다.

현재 `_bb_gc = st.session_state.get("game_config")`는 `build_battles(...)` 이후에 잡힌다.
이번 PR에서는 `_bb_gc`를 호출 전에 잡거나, 호출부에서 직접 `st.session_state.get("game_config")`를 넘긴다.

예:

```python
_bb_gc = st.session_state.get("game_config")
_battles = build_battles(
    ...,
    max_battles=int(_bb_max),
    game_config=_bb_gc,
)
```

그 뒤 `_worker_simulate_match` task에도 기존처럼 같은 `_bb_gc`를 넘긴다.

## 금지 사항

- `modules/engine.py` 의미론을 바꾸지 않는다.
- effects 스키마 포맷을 바꾸지 않는다.
- L1에서 제거한 dead UI를 되살리지 않는다.
- weather/status_gates/move_props/set_weather/clear_weather/inflict_status 블록을 복구하지 않는다.
- `gimmicks` 값을 top-level로 옮긴 뒤 삭제하지 않는다.
- 값 기반 자동 추론을 하지 않는다. 컬럼명/명시 channel만 사용한다.
- 백테스트의 battle grouping 정책은 이번 PR에서 건드리지 않는다.

## 검증

### 1. AST 검증

다음 파일이 `ast.parse`를 통과해야 한다.

- `modules/effect_key_roles.py`
- `modules/step2_system_definition.py`
- `modules/step6_dashboard.py`
- `modules/per_battle_backtest.py`

### 2. helper 단위 검증

간단한 Python snippet으로 다음을 확인한다.

```python
from modules.effect_key_roles import promote_effect_keys

inst = {
    "name": "x",
    "gimmicks": {
        "Ability": "Poison Heal",
        "Held Item": "Leftovers",
        "Status": "Burn",
    },
}
gc = {"channels": {"ability": "Ability", "item": "Held Item", "status": "Status"}}
promote_effect_keys(inst, gc)
assert inst["ability"] == "Poison Heal"
assert inst["item"] == "Leftovers"
assert inst["status"] == "Burn"
assert inst["gimmicks"]["Held Item"] == "Leftovers"
```

그리고 비활성 매핑도 확인한다.

```python
inst = {"name": "x", "gimmicks": {"Ability": "Poison Heal"}}
gc = {"channels": {"ability": None}}
promote_effect_keys(inst, gc)
assert "ability" not in inst
```

### 3. per-battle 경로 검증

```python
import pandas as pd
from modules.per_battle_backtest import _row_to_inst

row = pd.Series({
    "HP": 100,
    "Ability": "Poison Heal",
    "Held Item": "Leftovers",
    "Status": "Burn",
})
gc = {"channels": {"ability": "Ability", "item": "Held Item", "status": "Status"}}
inst = _row_to_inst(
    row,
    system_stats=["HP"],
    system_gimmicks=["Ability", "Held Item", "Status"],
    health_stat="HP",
    game_config=gc,
)
assert inst["ability"] == "Poison Heal"
assert inst["item"] == "Leftovers"
assert inst["status"] == "Burn"
assert inst["resources"]["HP"]["max"] == 100
```

### 4. grep 검증

다음을 확인한다.

- `modules/step2_system_definition.py`의 `_channel_roles`에 `ability`, `item`, `status`가 있다.
- `modules/step6_dashboard.py`에서 `promote_effect_keys` 호출이 2곳 이상 있다.
- `modules/per_battle_backtest.py`에서 `promote_effect_keys` 호출이 1곳 이상 있다.
- L1에서 제거한 dead setting 이름은 여전히 없어야 한다.

확인할 dead setting 이름:

- `weather_defs`
- `status_gates`
- `move_props`
- `set_weather`
- `clear_weather`
- `inflict_status`

## 완료 기준

이 PR이 끝나면 사용자는 DB 로그에 다음 계열 컬럼을 넣고 Step2 Channel Mapping에서 역할을 지정할 수 있어야 한다.

- 특성/능력 컬럼 -> `ability`
- 아이템/장비/도구 컬럼 -> `item`
- 상태/상태이상 컬럼 -> `status`

그 결과 Step2의 effects JSON에 입력한 item/status/ability 기반 효과가 Step6 일반 시뮬레이션,
optimizer 시뮬레이션, per-battle backtest 인스턴스에서 실제 엔진 키와 연결되어야 한다.
