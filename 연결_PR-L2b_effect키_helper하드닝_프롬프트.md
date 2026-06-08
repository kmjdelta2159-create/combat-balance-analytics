# 연결 PR-L2b - effect key helper 빈 값 판정 하드닝

## 목적

L2 적용 결과 핵심 연결은 성공했다.

- Step2 Channel Mapping에 `ability`, `item`, `status` role이 추가됨
- Step6 일반 시뮬레이션에서 `promote_effect_keys(...)` 호출됨
- Step6 optimizer 경로에서 `promote_effect_keys(...)` 호출됨
- per-battle backtest 경로에서 `game_config`가 전달되고 `_row_to_inst(...)`가 승격 수행
- AST와 기본 helper/per-battle 단위 검증 통과

다만 `modules/effect_key_roles.py`의 빈 값 처리에 작은 편차가 있다.

현재 구현은 top-level에 role 키가 존재하면 값이 `"None"` 같은 빈 값이어도 fallback 승격을 하지 않는다.
또한 `"none"`처럼 lowercase placeholder를 빈 값으로 보지 않는다.

이번 PR은 helper만 작게 보정한다.

## 수정 대상

- `modules/effect_key_roles.py`

가능하면 다른 파일은 수정하지 않는다.

## 현재 문제

현재 로직은 대략 다음 형태다.

```python
for role in EFFECT_KEY_ROLES:
    if role in inst:
        continue
```

이 방식은 다음 케이스에서 기대와 다르다.

```python
inst = {
    "name": "x",
    "ability": "None",
    "gimmicks": {"Ability": "Poison Heal"},
}
gc = {"channels": {"ability": "Ability"}}
promote_effect_keys(inst, gc)
```

L2 프롬프트의 의도는 “top-level에 유효한 값이 있으면 덮어쓰지 않는다”였다.
즉 top-level 값이 빈 placeholder라면 `gimmicks["Ability"]`에서 `"Poison Heal"`로 승격되어야 한다.

또 다음 케이스도 빈 값으로 취급되어야 한다.

```python
inst = {"name": "x", "gimmicks": {"Held Item": "none"}}
promote_effect_keys(inst, {})
assert "item" not in inst
```

## 구현 요구사항

`modules/effect_key_roles.py`에 작은 helper를 둔다.

```python
def is_empty_effect_value(value):
    ...
```

권장 동작:

1. `None`은 빈 값이다.
2. float NaN은 빈 값이다.
3. 문자열은 `strip().lower()` 후 비교한다.
4. 다음 문자열은 빈 값이다.

```python
{
    "",
    "none",
    "nan",
    "null",
    "없음",
    "비어 있음",
    "<na>",
    "n/a",
}
```

5. 그 외 값은 유효한 값이다.

## promote 로직 보정

현재:

```python
if role in inst:
    continue
```

보정:

```python
if role in inst and not is_empty_effect_value(inst.get(role)):
    continue
```

그리고 실제 승격 시에도 같은 helper를 사용한다.

```python
val = gimmicks[role_col]
if not is_empty_effect_value(val):
    inst[role] = val
```

## 유지해야 할 동작

- `EFFECT_KEY_ROLES = ("ability", "item", "status")` 유지
- `promote_effect_keys(inst, game_config=None)` 시그니처 유지
- `game_config["channels"][role] is None`이면 해당 role은 명시 비활성
- 명시 매핑이 없을 때만 컬럼명 hint fallback 사용
- 값 자체를 보고 role을 추론하지 않음
- `gimmicks` 원본 삭제 금지
- Streamlit, engine, pandas import 금지

## 검증

### 1. AST

```python
import ast
from pathlib import Path
ast.parse(Path("modules/effect_key_roles.py").read_text(encoding="utf-8"))
```

### 2. 기존 정상 케이스

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

### 3. 명시 비활성 유지

```python
inst = {"name": "x", "gimmicks": {"Ability": "Poison Heal"}}
gc = {"channels": {"ability": None}}
promote_effect_keys(inst, gc)
assert "ability" not in inst
```

### 4. 빈 top-level 값 fallback

```python
inst = {
    "name": "x",
    "ability": "None",
    "gimmicks": {"Ability": "Poison Heal"},
}
gc = {"channels": {"ability": "Ability"}}
promote_effect_keys(inst, gc)
assert inst["ability"] == "Poison Heal"
```

### 5. lowercase placeholder 차단

```python
inst = {"name": "x", "gimmicks": {"Held Item": "none"}}
promote_effect_keys(inst, {})
assert "item" not in inst
```

### 6. per-battle 기존 연결 회귀 확인

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

## 완료 기준

L2의 연결 효과는 그대로 유지하면서,
빈 placeholder가 top-level 또는 gimmicks에 있을 때 effects dispatcher로 잘못 전달되지 않아야 한다.
