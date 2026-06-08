# PR-E1 — 효과-스키마 디스패처 (ON_HIT 접촉 데미지)

## 목적
효과-스키마 설계안의 *첫 벽돌*. 엔진에 효과 디스패처를 세워, 발동형 효과를 *코드가 아니라
데이터*(`game_config['mechanisms']['effects']`)로 적용한다. 첫 범위: **ON_HIT + damage_frac +
접촉 데미지(Rough Skin·Rocky Helmet)**. 자기완결적(피격 시 공격자 데미지, 턴 넘김 없음).
flinch(행동차단)는 action-gate 통합이 필요해 다음 PR.

## 대상
`modules/engine.py` — **1 FIND/REPLACE**(`_act_on_hit` 끝에 디스패처 호출 + 디스패처 함수
4개 삽입). 기존 status_tick/weather_chip/action_gate/해결코드 무변경.

## 설계 (설계안 §4 디스패처, 프로토타입 검증)
- 트리거 = 엔진 기존 페이즈(ON_HIT). 신규 페이즈 없음 — `_act_on_hit` 끝에서 dispatcher 호출.
- 효과 소유자 = 관련 캐릭터의 `ability`/`item`(피격자=current_target, 자신=active_char).
- 조건 = `contact`(접촉 무브). 효과 = `damage_frac`(maxHP 분수, status_tick 패턴 재사용).
- 스코프 = self/attacker(active_char) / target(current_target).

## FIND
```python
    _broadcast_phase_event("ON_HIT", ctx, targets=t)

def _act_death_check(ctx):
```

## REPLACE
```python
    _broadcast_phase_event("ON_HIT", ctx, targets=t)
    _act_effect_dispatch(ctx, "ON_HIT")


def _eff_get_res(char):
    """vital 자원 dict 반환. 없으면 None."""
    return (char.get("resources") or {}).get("HP")


def _eff_scope(ctx, scope):
    """효과 적용 대상. self/attacker=active_char, target=current_target."""
    if scope == "target":
        return ctx.get("current_target")
    return ctx.get("active_char")


def _eff_cond_ok(ctx, cond):
    """효과 조건 평가. 현재: contact(접촉 무브). 미설정이면 통과."""
    if not cond:
        return True
    if cond.get("contact") and not (ctx.get("current_move") or {}).get("contact"):
        return False
    return True


def _act_effect_dispatch(ctx, phase):
    """효과-스키마 디스패처 — game_config['mechanisms']['effects']에서 trigger==phase인
    효과 중, 관련 캐릭터(피격자/자신)의 ability/item에 해당하는 것을 조건·스코프대로 적용.
    effects 미설정 또는 캐릭터에 ability/item 없으면 no-op(회귀 0). 기존 status_tick/
    weather_chip/action_gate는 무관(별도). 첫 효과타입: damage_frac(maxHP 분수 데미지)."""
    gc = ctx.get("game_config") or {}
    effects = ((gc.get("mechanisms") or {}).get("effects")) or {}
    if not effects:
        return
    add_log = ctx.get("add_log") or (lambda *a, **k: None)
    for owner in (ctx.get("current_target"), ctx.get("active_char")):
        if owner is None:
            continue
        for nm in (owner.get("ability"), owner.get("item")):
            spec = effects.get(nm) if nm else None
            if not spec or spec.get("trigger") != phase:
                continue
            if not _eff_cond_ok(ctx, spec.get("condition")):
                continue
            tgt = _eff_scope(ctx, spec.get("scope", "self"))
            res = _eff_get_res(tgt) if tgt else None
            if not res or res.get("current", 0) <= 0:
                continue
            eff = spec.get("effect") or {}
            if eff.get("type") == "damage_frac":
                amt = int(res["max"] * float(eff.get("frac", 0)))
                if amt > 0:
                    res["current"] = max(0, res["current"] - amt)
                    add_log(f"  -> [Phase: {phase}] {nm}: {tgt.get('id','?')} -{amt} "
                            f"({int(res['current'])}/{int(res['max'])})")


def _act_death_check(ctx):
```

## 앵커 근거
- FIND = `_act_on_hit`의 마지막 줄(ON_HIT 브로드캐스트) + 직후 `def _act_death_check`. 각각
  Grep count==1(유일). REPLACE는 브로드캐스트 뒤에 dispatcher 호출을 추가하고, 두 함수 사이에
  디스패처 4함수를 삽입.
- 스키마 위치 `mechanisms['effects']`는 기존 hazard/weather_defs/status_gates/move_props와
  동형(정적·병렬 안전).

## 검증 (프로토타입·실 gen5 수치, 작성 시 수행)
효과 스키마:
```
'Rough Skin':   {trigger:ON_HIT, condition:{contact}, effect:{damage_frac,1/8}, scope:attacker}
'Rocky Helmet': {trigger:ON_HIT, condition:{contact}, effect:{damage_frac,1/6}, scope:attacker}
```
Garchomp(ability=Rough Skin, item=Rocky Helmet)가 Hippowdon의 접촉 Ice Fang 피격 시
(gen5 로그 실측: Hippowdon 420→368→298):
- Rough Skin: −52(=⌊420/8⌋) → 368 ✓
- Rocky Helmet: −70(=⌊420/6⌋) → 298 ✓  **관측과 정확 일치.**
- 비접촉 무브: 미발동(420 유지) ✓
- effects 미설정: no-op ✓

적용자 검증:
1. 앵커 Grep count==1 → 적용 → `python -c "import ast; ast.parse(...)"`.
2. 위 스키마 + Garchomp/Hippowdon 모의 ctx로 ON_HIT 디스패처 호출 → 298 재현.
3. **회귀 0**: 기존 char에 `ability`/`item` 키 사용 0건(Grep 확인) + effects 미설정이면
   디스패처 즉시 return. 기존 전투 경로 비트 동일.

## 회귀 0
신규 함수 4개 + `_act_on_hit` 끝 1줄 추가. 기존 char dict엔 ability/item 키가 없어
(`owner.get('ability')=None`) 디스패처가 아무 효과도 못 찾음 → no-op. effects 스키마도
기본 미설정 → 즉시 return. status_tick/weather_chip/action_gate/해결 파이프라인 전부 무관.

## 다음
- **하니스 배선**: 트레이스-리플레이가 reference SETS의 ability/item을 char에 실어 ON_HIT
  디스패처를 타게 → gen5 접촉 env(Rough Skin/Rocky Helmet)를 end-to-end 검증.
- **flinch**(block_action) — action-gate 통합(피격→대상 이번 턴 행동차단). 효과타입 2번째.
- heal_frac(Rain Dish·Leftovers) → on_action(Protect) → 점증. 기존 status_tick/weather_chip을
  디스패처로 흡수하는 통합 리팩터는 *의도된 후속*(지금 아님).
