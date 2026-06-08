# DB로그 IR PR-I1b - 빈 진영 전투 스킵 보정

## 목적

I1 적용 결과 핵심 기능은 들어갔다.

- `build_battles(..., log_schema=None)` 시그니처 추가
- `build_battles_from_log_schema(...)` 추가
- Step6 Per-Battle Backtest에 전투 구성 방식 추가
- DB 역할 컬럼 방식에서 `log_schema=` 전달
- 기존 chunk 방식 회귀 통과
- DB role-schema 기본 그룹/dedup/side_signal 단위 검증 통과

다만 DB 역할 컬럼 방식에서 한쪽 진영이 비어 있는 전투도 결과에 포함되는 경계 조건 문제가 있다.

현재 `modules/per_battle_backtest.py`는 다음처럼 양쪽 모두 비어 있을 때만 skip한다.

```python
if not ally_rows and not enemy_rows:
    continue
```

이 경우 다음처럼 Enemy가 없는 전투도 만들어진다.

```python
missing_enemy_len 1 ally_len 1 enemy_len 0
```

엔진 입력 관점에서는 Ally와 Enemy가 모두 있어야 유효한 전투다.
이번 PR은 이 경계 조건만 보정한다.

## 수정 대상

- `modules/per_battle_backtest.py`

가능하면 다른 파일은 수정하지 않는다.

## 구현 요구사항

DB role-schema 경로에서 한쪽 진영이 비어 있으면 해당 battle group을 skip한다.

권장 위치:

1. team 분리 직후
2. dedup 이후

둘 다 넣는 것이 안전하다.

예:

```python
if not ally_rows or not enemy_rows:
    continue
```

그리고 dedup 이후에도 최종 참가자가 비면 skip한다.

```python
final_ally = dedup(ally_rows)
final_enemy = dedup(enemy_rows)
if not final_ally or not final_enemy:
    continue
```

중요:

- chunk 기반 legacy 경로는 변경하지 않는다.
- `b_count`는 실제로 append된 battle에 대해서만 증가해야 한다.
- unknown team 값은 계속 제외한다.
- custom `ally_values`/`enemy_values` 동작은 유지한다.
- `promote_effect_keys(...)` 호출 경로는 유지한다.

## 검증

### 1. AST

```python
import ast
from pathlib import Path
ast.parse(Path("modules/per_battle_backtest.py").read_text(encoding="utf-8"))
```

### 2. 기존 chunk 방식 회귀

```python
import pandas as pd
from modules.per_battle_backtest import build_battles

df = pd.DataFrame([
    {"HP": 100, "win": 1},
    {"HP": 100, "win": 0},
])
battles = build_battles(df, 2, "win", ["HP"], [], "HP")
assert len(battles) == 1
assert battles[0][2] is True
```

### 3. DB role-schema 정상 케이스 유지

```python
df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1", "HP": 100, "Ability": "Poison Heal", "win": 1},
    {"battle_id": 1, "side": "Enemy", "unit_id": "E1", "HP": 100, "Ability": "Magic Guard", "win": 1},
])
gc = {"channels": {"ability": "Ability"}}
battles = build_battles(
    df, 2, "win", ["HP"], ["Ability"], "HP",
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

### 4. Enemy 없는 battle skip

```python
df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1", "HP": 100, "win": 1},
])
battles = build_battles(
    df, 2, "win", ["HP"], [], "HP",
    log_schema={
        "battle_id_col": "battle_id",
        "team_col": "side",
        "entity_id_col": "unit_id",
    },
)
assert battles == []
```

### 5. unknown team만 남은 상대도 skip

```python
df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1", "HP": 100, "win": 1},
    {"battle_id": 1, "side": "Neutral", "unit_id": "N1", "HP": 100, "win": 1},
])
battles = build_battles(
    df, 2, "win", ["HP"], [], "HP",
    log_schema={
        "battle_id_col": "battle_id",
        "team_col": "side",
        "entity_id_col": "unit_id",
    },
)
assert battles == []
```

### 6. custom values 유지

```python
df = pd.DataFrame([
    {"battle_id": 1, "side": "P1", "unit_id": "A1", "HP": 100, "win": 1},
    {"battle_id": 1, "side": "P2", "unit_id": "E1", "HP": 100, "win": 1},
])
battles = build_battles(
    df, 2, "win", ["HP"], [], "HP",
    log_schema={
        "battle_id_col": "battle_id",
        "team_col": "side",
        "entity_id_col": "unit_id",
        "ally_values": ["P1"],
        "enemy_values": ["P2"],
    },
)
assert len(battles) == 1
assert len(battles[0][0]) == 1
assert len(battles[0][1]) == 1
```

## 완료 기준

DB role-schema backtest는 Ally와 Enemy가 모두 존재하는 battle group만 반환해야 한다.
이 보정 후 I1은 “DB 역할 컬럼 기반 전투 구성”의 최소 안정 조건을 만족한다.
