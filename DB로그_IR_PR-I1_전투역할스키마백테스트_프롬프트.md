# DB로그 IR PR-I1 - 전투 역할 스키마 기반 backtest 구성

## 목적

최종 목표는 리플레이 로그가 아니라 DB 로그를 전제로 한 범용 턴제 전투 복제다.

현재 `modules/per_battle_backtest.py`의 `build_battles(...)`는 다음 가정을 사용한다.

- `battle_size`개 행이 한 전투
- 앞 절반은 Ally
- 뒤 절반은 Enemy

이 방식은 데모용으로는 유효하지만, 실제 DB 로그에는 보통 다음 역할 컬럼이 있다.

- 전투 ID
- 팀/진영
- 참가자/유닛 ID
- 턴 또는 로그 순서
- 전투 결과

이번 PR의 목표는 기존 chunk 기반 backtest를 유지하면서, DB 로그 역할 컬럼을 명시 매핑해
전투를 구성하는 첫 IR 경로를 추가하는 것이다.

이번 PR은 “행동 replay”까지 가지 않는다.  
목표는 우선 DB 행을 `battle_id -> team -> participants` 구조로 해석해서
기존 엔진 backtest 입력 `(ally_team, enemy_team, actual_ally_wins)`로 변환하는 것이다.

## 수정 대상

- `modules/per_battle_backtest.py`
- `modules/step6_dashboard.py`

필요하면 새 순수 helper 모듈을 1개 추가해도 된다.
단, 엔진 의미론은 수정하지 않는다.

## 핵심 설계

`build_battles(...)`에 optional `log_schema=None` 인자를 추가한다.

```python
def build_battles(df, battle_size, target_col, system_stats, system_gimmicks,
                  health_stat, move_library=None, resource_config=None,
                  max_battles=None, game_config=None, log_schema=None):
```

- `log_schema`가 없으면 기존 chunk 방식이 그대로 동작해야 한다.
- `log_schema`에 유효한 `battle_id_col`, `team_col`이 있으면 새 DB role-schema 경로를 사용한다.
- 기존 호출 호환성을 깨지 않는다.

권장 내부 구조:

```python
def build_battles_from_log_schema(df, target_col, system_stats, system_gimmicks,
                                  health_stat, move_library=None,
                                  resource_config=None, max_battles=None,
                                  game_config=None, log_schema=None):
    ...
```

## log_schema 포맷

권장 dict:

```python
{
    "battle_id_col": "battle_id",
    "team_col": "side",
    "entity_id_col": "unit_id",
    "sort_cols": ["turn", "order"],
    "ally_values": ["Ally", "ally", "A", "blue", "player"],
    "enemy_values": ["Enemy", "enemy", "E", "red", "opponent"],
    "result_mode": "battle_level"
}
```

필수:

- `battle_id_col`
- `team_col`

선택:

- `entity_id_col`: 같은 전투/팀 안에서 한 유닛이 여러 행으로 기록될 때 dedup 기준
- `sort_cols`: 같은 유닛이 여러 행이면 어느 행을 최종 row로 볼지 결정하는 정렬 기준
- `ally_values`
- `enemy_values`
- `result_mode`

## DB role-schema 경로 동작

### 1. 전투 그룹

`battle_id_col`로 groupby한다.

- NaN battle id는 제외한다.
- `max_battles`가 있으면 앞에서부터 제한한다.
- `sort_cols`가 있으면 group 내부를 정렬한다.

### 2. 팀 분리

`team_col` 값을 문자열 `strip().lower()`로 정규화해 판단한다.

기본 ally 값:

```python
{"ally", "a", "blue", "player", "home", "left", "1", "true"}
```

기본 enemy 값:

```python
{"enemy", "e", "red", "opponent", "away", "right", "2", "false"}
```

`log_schema["ally_values"]`, `log_schema["enemy_values"]`가 있으면 그 값도 추가한다.

알 수 없는 팀 값은 해당 전투에서 제외한다.
Ally 또는 Enemy 참가자가 하나도 없으면 해당 전투는 건너뛴다.

### 3. 참가자 dedup

DB 로그는 한 유닛이 턴마다 여러 행을 가질 수 있다.

`entity_id_col`이 있고 해당 컬럼이 존재하면:

- team별로 `entity_id_col` 기준 groupby
- 정렬 후 마지막 행을 대표 row로 사용

`entity_id_col`이 없으면:

- 해당 team rows 전체를 참가자 row로 사용

이 정책은 “최종 상태 row 기반 backtest”다.
행동 replay는 다음 PR에서 다룬다.

### 4. actual result 계산

`result_mode` 기본값은 `"battle_level"`로 둔다.

지원 모드:

#### `"battle_level"`

한 전투 그룹에서 `target_col`의 첫 non-null 값을 전투 결과로 본다.

```python
ally_wins = _is_win_signal(first_non_null_target)
```

값이 없으면 `"side_signal"` fallback을 사용한다.

#### `"side_signal"`

기존 방식과 유사하게 Ally rows와 Enemy rows에서 target signal을 비교한다.

```python
ally_signal = sum(_is_win_signal(row[target_col]) for row in ally_rows)
enemy_signal = sum(_is_win_signal(row[target_col]) for row in enemy_rows)
ally_wins = ally_signal > enemy_signal
```

이 모드는 target이 row별 winner flag인 DB에 필요하다.

### 5. 인스턴스 생성

대표 row를 기존 `_row_to_inst(...)`에 넣는다.

`game_config`를 계속 전달해야 한다.
L2/L2b에서 추가한 `promote_effect_keys(...)` 경로가 유지되어야 한다.

## Step6 UI 변경

Per-Battle Backtest 박스에 전투 구성 방식을 추가한다.

```text
전투 구성 방식
- 행 개수로 묶기 (기존)
- DB 역할 컬럼으로 묶기
```

### 기존 방식

현재 UI와 동작을 유지한다.

- `battle_size`
- `max_battles`
- 앞 절반 Ally / 뒤 절반 Enemy

### DB 역할 컬럼 방식

다음 selectbox/multiselect/input을 보여준다.

- 전투 ID 컬럼 (`battle_id_col`)
- 팀/진영 컬럼 (`team_col`)
- 참가자 ID 컬럼 (`entity_id_col`, 없음 허용)
- 정렬 컬럼 (`sort_cols`, 복수 선택 가능, 없음 허용)
- 결과 해석 방식 (`battle_level`, `side_signal`)
- Ally 값 목록 text input
- Enemy 값 목록 text input

기본 추천 컬럼은 컬럼명 hint로 잡는다.

권장 hint:

```python
battle_id: ("battle", "match", "combat", "game", "전투", "매치")
team: ("team", "side", "camp", "faction", "player", "진영", "팀")
entity_id: ("unit", "actor", "character", "hero", "pokemon", "entity", "slot", "유닛", "캐릭터")
turn/order: ("turn", "round", "order", "seq", "index", "턴", "순서")
```

UI에서 구성한 값을 `log_schema` dict로 만들어 `build_battles(...)`에 넘긴다.

```python
_battles = build_battles(
    _bb_df, int(_bb_size), _bb_target,
    sys_stats, sys_gimmicks, _bb_health,
    move_library=st.session_state.get("move_library"),
    resource_config=st.session_state.get("resource_config"),
    max_battles=int(_bb_max),
    game_config=st.session_state.get("game_config"),
    log_schema=_bb_log_schema,
)
```

DB 역할 컬럼 방식에서는 `battle_size`를 사용하지 않아도 된다.
호출 호환성을 위해 값은 넘기되, builder 내부에서 `log_schema`가 있으면 무시한다.

## 금지 사항

- 기존 chunk 기반 backtest를 제거하지 않는다.
- `modules/engine.py`를 수정하지 않는다.
- 행동 replay, trace_actions 생성, turn-level action reconstruction을 이번 PR에 넣지 않는다.
- Step2의 L1 dead UI를 되살리지 않는다.
- L2/L2b의 `promote_effect_keys(...)` 경로를 우회하지 않는다.
- result 해석이 애매한 전투를 임의로 뒤집지 않는다. 값이 없으면 건너뛰거나 side_signal fallback만 사용한다.

## 검증

### 1. AST

다음 파일이 `ast.parse`를 통과해야 한다.

- `modules/per_battle_backtest.py`
- `modules/step6_dashboard.py`
- 새 helper 모듈을 추가했다면 그 파일

### 2. 기존 chunk 방식 회귀

기존 호출이 여전히 동작해야 한다.

```python
import pandas as pd
from modules.per_battle_backtest import build_battles

df = pd.DataFrame([
    {"HP": 100, "win": 1},
    {"HP": 100, "win": 0},
])
battles = build_battles(
    df,
    battle_size=2,
    target_col="win",
    system_stats=["HP"],
    system_gimmicks=[],
    health_stat="HP",
)
assert len(battles) == 1
assert battles[0][2] is True
```

### 3. DB role-schema 기본 그룹

```python
import pandas as pd
from modules.per_battle_backtest import build_battles

df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1", "HP": 100, "Ability": "Poison Heal", "win": 1},
    {"battle_id": 1, "side": "Enemy", "unit_id": "E1", "HP": 100, "Ability": "Magic Guard", "win": 1},
])
gc = {"channels": {"ability": "Ability"}}
battles = build_battles(
    df,
    battle_size=2,
    target_col="win",
    system_stats=["HP"],
    system_gimmicks=["Ability"],
    health_stat="HP",
    game_config=gc,
    log_schema={
        "battle_id_col": "battle_id",
        "team_col": "side",
        "entity_id_col": "unit_id",
        "result_mode": "battle_level",
    },
)
ally, enemy, actual = battles[0]
assert len(ally) == 1
assert len(enemy) == 1
assert ally[0]["ability"] == "Poison Heal"
assert enemy[0]["ability"] == "Magic Guard"
assert actual is True
```

### 4. duplicate action rows dedup

```python
df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1", "turn": 1, "HP": 100, "win": 1},
    {"battle_id": 1, "side": "Ally", "unit_id": "A1", "turn": 2, "HP": 80, "win": 1},
    {"battle_id": 1, "side": "Enemy", "unit_id": "E1", "turn": 1, "HP": 100, "win": 1},
])
battles = build_battles(
    df,
    battle_size=2,
    target_col="win",
    system_stats=["HP"],
    system_gimmicks=[],
    health_stat="HP",
    log_schema={
        "battle_id_col": "battle_id",
        "team_col": "side",
        "entity_id_col": "unit_id",
        "sort_cols": ["turn"],
        "result_mode": "battle_level",
    },
)
ally, enemy, actual = battles[0]
assert len(ally) == 1
assert ally[0]["HP"] == 80
```

### 5. side_signal result mode

```python
df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1", "HP": 100, "win_flag": 0},
    {"battle_id": 1, "side": "Enemy", "unit_id": "E1", "HP": 100, "win_flag": 1},
])
battles = build_battles(
    df,
    battle_size=2,
    target_col="win_flag",
    system_stats=["HP"],
    system_gimmicks=[],
    health_stat="HP",
    log_schema={
        "battle_id_col": "battle_id",
        "team_col": "side",
        "entity_id_col": "unit_id",
        "result_mode": "side_signal",
    },
)
assert battles[0][2] is False
```

### 6. UI smoke

가능하면 `streamlit.testing.v1.AppTest` 또는 기존 smoke 방식으로 Step6 import/render가 예외 없이 되는지 확인한다.

최소 grep 확인:

- `log_schema`가 `build_battles(...)` 시그니처에 있음
- Step6 backtest 호출부에서 `log_schema=`를 넘김
- 기존 `ui_backtest_size`가 legacy 모드에서 유지됨

## 완료 기준

이 PR이 끝나면 DB 로그가 이미 `battle_id/team/unit/turn/result` 계열 컬럼을 갖고 있을 때,
사용자는 행 순서와 절반 분할에 의존하지 않고 전투 단위 backtest를 돌릴 수 있어야 한다.

이것은 최종 DB-log 기반 복제 목표의 첫 IR 연결층이며,
다음 단계의 행동 replay/action reconstruction으로 넘어가기 위한 기반이다.
