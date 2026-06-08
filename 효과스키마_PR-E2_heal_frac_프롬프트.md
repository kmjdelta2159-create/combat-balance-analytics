# PR-E2 — 효과-스키마: heal_frac + 날씨조건 + ON_TURN_END

## 목적
효과-스키마 둘째 효과타입. 디스패처에 **heal_frac**(maxHP 분수 회복) + **weather 조건** +
**ON_TURN_END 디스패치**를 추가해 *발동형 회복*을 데이터로 표현한다. 첫 인코딩: **Rain Dish**
(비일 때 턴종료 1/16 자힐). heal 원자는 이후 Wish/Leftovers-통합에 재사용. 자기완결적(턴종료
자힐, 턴넘김 없음).

## 대상
`modules/engine.py` — **3 FIND/REPLACE**(PR-E1 디스패처 확장 2 + ON_TURN_END 호출 1). 기존
leftovers/status_tick/weather_chip 무변경.

## FIND/REPLACE 1 — 날씨 조건 추가 (`_eff_cond_ok` 확장)

### FIND
```python
def _eff_cond_ok(ctx, cond):
    """효과 조건 평가. 현재: contact(접촉 무브). 미설정이면 통과."""
    if not cond:
        return True
    if cond.get("contact") and not (ctx.get("current_move") or {}).get("contact"):
        return False
    return True
```

### REPLACE
```python
def _eff_active_weather_name(ctx):
    """현재 발효 날씨 이름(field_state.weather.name). 없으면 None."""
    return ((ctx.get("field_state") or {}).get("weather") or {}).get("name")


def _eff_cond_ok(ctx, cond):
    """효과 조건 평가. contact(접촉 무브)·weather(발효 날씨 이름). 미설정이면 통과."""
    if not cond:
        return True
    if cond.get("contact") and not (ctx.get("current_move") or {}).get("contact"):
        return False
    if "weather" in cond and _eff_active_weather_name(ctx) != cond["weather"]:
        return False
    return True
```

## FIND/REPLACE 2 — heal_frac 효과타입 추가 (`_act_effect_dispatch` 내부)

### FIND
```python
            eff = spec.get("effect") or {}
            if eff.get("type") == "damage_frac":
                amt = int(res["max"] * float(eff.get("frac", 0)))
                if amt > 0:
                    res["current"] = max(0, res["current"] - amt)
                    add_log(f"  -> [Phase: {phase}] {nm}: {tgt.get('id','?')} -{amt} "
                            f"({int(res['current'])}/{int(res['max'])})")
```

### REPLACE
```python
            eff = spec.get("effect") or {}
            et = eff.get("type")
            amt = int(res["max"] * float(eff.get("frac", 0)))
            if amt <= 0:
                continue
            if et == "damage_frac":
                res["current"] = max(0, res["current"] - amt)
            elif et == "heal_frac":
                res["current"] = min(res["max"], res["current"] + amt)
            else:
                continue
            add_log(f"  -> [Phase: {phase}] {nm}: {tgt.get('id','?')} "
                    f"{'-' if et == 'damage_frac' else '+'}{amt} "
                    f"({int(res['current'])}/{int(res['max'])})")
```

## FIND/REPLACE 3 — ON_TURN_END 디스패치 호출 (`_act_turn_end_heal` 맨 앞)

`_act_turn_end_heal`은 early return이 여러 개라 호출을 함수 *맨 앞*에 둬 항상 실행.

### FIND
```python
def _act_turn_end_heal(ctx):
    """턴 종료 회복 메커니즘 (Leftovers류) — game_config['mechanisms']['leftovers'] 기반.
    부착 캐릭터가 턴 종료 시 vital 자원의 percent만큼 회복한다. 사망(현재값 0)이면
    회복하지 않는다. max 상한으로 클램프. 미부착/미설정 시 no-op."""
    char = ctx["active_char"]
```

### REPLACE
```python
def _act_turn_end_heal(ctx):
    """턴 종료 회복 메커니즘 (Leftovers류) — game_config['mechanisms']['leftovers'] 기반.
    부착 캐릭터가 턴 종료 시 vital 자원의 percent만큼 회복한다. 사망(현재값 0)이면
    회복하지 않는다. max 상한으로 클램프. 미부착/미설정 시 no-op.
    (효과-스키마 디스패처도 ON_TURN_END에서 호출 — Rain Dish류 발동형 회복.)"""
    _act_effect_dispatch(ctx, "ON_TURN_END")
    char = ctx["active_char"]
```

## 앵커 근거
- FIND1 `_eff_cond_ok`(PR-E1)·FIND2 damage_frac 블록(PR-E1)·FIND3 `_act_turn_end_heal` 도크
  전부 Grep count==1(유일).
- heal_frac은 damage_frac과 동형(자원 델타, max 캡). 날씨 조건은 field_state.weather.name 읽기
  (엔진 F3가 채우는 그 dict).

## 검증 (프로토타입, 작성 시 수행)
효과 스키마:
```
'Rain Dish': {trigger:ON_TURN_END, condition:{weather:rain}, effect:{heal_frac,1/16}, scope:self}
```
- 비(rain) ON_TURN_END, Tentacruel 200/384, ability=Rain Dish → **+24(=⌊384/16⌋) → 224** ✓
  (gen5 로그 Rain Dish 관측 2/2 = 1/16 정합.)
- 모래일 때: 미발동(200 유지) ✓
- 풀피 근접(380/384): max 캡 → 384 ✓
- effects 미설정: no-op ✓

적용자 검증: 앵커 3개 Grep count==1 → 적용 → `ast.parse` → 위 케이스 재현. 기존 leftovers
회복·접촉 데미지(PR-E1) 무변동.

## 회귀 0
heal_frac은 신규 분기(damage_frac 경로 무변). 날씨 조건은 `"weather" in cond`일 때만 — 기존
효과(Rough Skin 등 contact)는 cond에 weather 없어 무관. ON_TURN_END 디스패치는 effects 미설정/
ability 없음 시 즉시 return. 기존 Leftovers(leftovers spec) 경로 그대로 — Rain Dish는 *추가*지
대체 아님.

## 다음
- flinch(block_action) — action-gate 통합(피격→대상 이번 턴 행동차단). 셋째 효과타입.
- Life Orb 반동(ON_MOVE_USE, damage_frac self) — 트리거 페이즈만 추가하면 기존 원자 재사용.
- 나머지 발동형(Protect·Substitute·Wish·Trick)은 새 효과타입 필요 — 카탈로그 빈도순 점증.
  *효과타입·트리거가 갖춰질수록 새 특성/도구는 스키마 한 줄*(코드 무변)로 떨어진다.
