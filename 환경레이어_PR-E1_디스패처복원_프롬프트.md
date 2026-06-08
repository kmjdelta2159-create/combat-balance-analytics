# PR-E′1 — 효과 디스패처 코어 복원 + ON_HIT 접촉 (engine + reference_gen5 + battle_setup)

## 목적
환경 레이어 복원의 첫 벽돌이자 **키스톤 재건**. B3~C2 정리 과정에서 유실된 효과 디스패처를
복구해, 발동형 효과를 *코드가 아니라 데이터*(`game_config['mechanisms']['effects']`)로 적용한다.
첫 범위는 자기완결적인 **ON_HIT + damage_frac + 접촉 데미지**(Rough Skin·Iron Barbs·Rocky
Helmet). 턴엔드 env(Leftovers·모래·상태틱)와 진입 해저드는 후속 PR-E′2/E′3.

배경: 현재 엔진엔 일반 디스패처가 없고(Grep 0건), `battle_setup`은 `mechanisms['effects']`에
EFFECTS를 주입하지만(71줄) 소비자가 없어 *배선이 끊겨* 있다. 이 PR이 소비자를 복구한다.

## 검증 제약
engine.py truncation으로 전체 실행은 앱사이드(run_b4). 디스패처 로직은 클린룸 검증됨(아래).
앵커는 Read/Grep으로 고정(이번 세션 확인: `_act_on_hit` 748, `_act_death_check` 750).

## 대상
`modules/engine.py`(1건: `_act_on_hit` 끝 호출 + 디스패처 4함수) + `modules/reference_gen5.py`
(3건: EFFECTS dict·CONTACT_MOVES·Garchomp 세트 교정) + `modules/battle_setup.py`(2건: char에
ability/item 노출·무브 contact 플래그). 기존 single-slot 메커니즘·해결 파이프라인 무변경.

## 설계 근거 (클린룸 검증됨)
- 트리거=엔진 기존 페이즈(ON_HIT). 신규 페이즈 없음 — `_act_on_hit` 끝에서 디스패처 호출.
- 효과 소유자 = 관련 캐릭터의 ability/item. ON_HIT에선 피격자(current_target)·공격자
  (active_char) 둘을 owner 후보로 본다. Rough Skin/Rocky Helmet은 **피격자(소유자)가 공격자
  (scope=attacker)에게 반동**을 준다.
- 효과 = damage_frac(maxHP 분수, status_tick 패턴 재사용). 조건 = contact(접촉 무브).
- **클린룸 결과**: Hippowdon이 접촉 Ice Fang으로 Garchomp(Rough Skin+Rocky Helmet, maxhp 420)를
  치면 → Hippowdon 420→368(−52=⌊420/8⌋)→298(−70=⌊420/6⌋). env 덤프 실측과 정확 일치. 비접촉
  (Earthquake) 미발동. effects 빈/ability·item 키 없음 → no-op(회귀0). 4케이스 전부 통과.
- **세트 역설계**: env 스트림이 이 로그 Garchomp(Rikimaru)의 실제 ability/item을 **Rough Skin +
  Rocky Helmet**으로 확정(−52=420/8, −70=420/6). 현 prior(Sand Veil/Life Orb)는 오류 → 교정.

---

## FIND/REPLACE — modules/engine.py

### E1 — `_act_on_hit` 끝에 디스패처 호출 + 디스패처 4함수 삽입
**FIND**:
```python
    _broadcast_phase_event("ON_HIT", ctx, targets=t)

def _act_death_check(ctx):
```
**REPLACE**:
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
    leftovers/action_gate는 무관(별도). 첫 효과타입: damage_frac(maxHP 분수 데미지)."""
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

**앵커 근거**: FIND = `_act_on_hit`의 마지막 줄(ON_HIT 브로드캐스트) + 직후 `def
_act_death_check`. 둘 다 Grep count==1(유일, 이번 세션 확인). REPLACE는 브로드캐스트 뒤에
디스패처 호출을 더하고 두 함수 사이에 4함수를 삽입.

---

## FIND/REPLACE — modules/reference_gen5.py

### R1 — EFFECTS를 dict로 (접촉 데미지 발동형)
**FIND**:
```python
# 발동형 효과(트리거×조건×효과) — 효과-스키마(PR-E). gen5분은 B4 잔차가 드러내면 채움.
EFFECTS = []
```
**REPLACE**:
```python
# 발동형 효과(트리거×조건×효과×스코프) — 효과-스키마 디스패처(PR-E′)가 ability/item 이름으로
# 매칭해 적용. dict[이름] = spec. ON_TURN_END(Leftovers·모래·상태틱)·해저드는 PR-E′2/E′3.
# Rough Skin/Iron Barbs(특성)·Rocky Helmet(도구): 접촉 피격 시 공격자(scope=attacker)에 반동.
EFFECTS = {
    'Rough Skin':   {'trigger': 'ON_HIT', 'condition': {'contact': True},
                     'effect': {'type': 'damage_frac', 'frac': 1/8, 'of': 'maxhp'},
                     'scope': 'attacker', 'source': 'ability'},
    'Iron Barbs':   {'trigger': 'ON_HIT', 'condition': {'contact': True},
                     'effect': {'type': 'damage_frac', 'frac': 1/8, 'of': 'maxhp'},
                     'scope': 'attacker', 'source': 'ability'},
    'Rocky Helmet': {'trigger': 'ON_HIT', 'condition': {'contact': True},
                     'effect': {'type': 'damage_frac', 'frac': 1/6, 'of': 'maxhp'},
                     'scope': 'attacker', 'source': 'item'},
}

# 접촉 무브 — ON_HIT 접촉 조건용. gen5 로그 등장분(lazy). 미기재=비접촉.
# 물리라도 Earthquake·Explosion·Volt Switch는 비접촉. 특수·status 전부 비접촉.
CONTACT_MOVES = {'Body Slam', 'Ice Fang', 'Iron Head', 'Superpower', 'Rapid Spin'}
```

### R2 — Garchomp 세트 교정 (env 역설계: Rough Skin + Rocky Helmet)
**FIND**:
```python
    'Garchomp':   {'nature': 'Jolly',   'evs': (0, 252, 0, 0, 4, 252),   'item': 'Life Orb',     'ability': 'Sand Veil'},     # [prior]
```
**REPLACE**:
```python
    'Garchomp':   {'nature': 'Jolly',   'evs': (0, 252, 0, 0, 4, 252),   'item': 'Rocky Helmet', 'ability': 'Rough Skin'},    # [확정] env: RoughSkin −52(420/8)·RockyHelmet −70(420/6)
```

---

## FIND/REPLACE — modules/battle_setup.py

### B1 — build_participants: char에 ability/item 노출 (디스패처 owner 매칭용)
디스패처는 `owner.get('ability')`/`owner.get('item')`로 매칭한다. 현재 char엔 이 키가 없어
(`ch['set']`에만 있음) 그대로면 디스패처가 영원히 no-op. 세트에서 노출한다.

**FIND**:
```python
        ch["hp"] = ch["maxhp"]
        ch["side"] = side.get(nick)
        ch["set"] = set_data or {}
        parts.append(ch)
```
**REPLACE**:
```python
        ch["hp"] = ch["maxhp"]
        ch["side"] = side.get(nick)
        ch["set"] = set_data or {}
        ch["ability"] = (set_data or {}).get("ability")   # 효과 디스패처 owner 매칭(PR-E′)
        ch["item"] = (set_data or {}).get("item")
        parts.append(ch)
```

### B2 — build_trace_actions: 무브 dict에 contact 플래그
디스패처 조건 `contact`는 `ctx['current_move']['contact']`를 읽는다. 트레이스 무브 dict에 추가.
회귀0: CONTACT_MOVES 미정의 ref거나 비접촉 무브면 False.

**FIND**:
```python
            mv = {"name": e["move"], "power": (md[0] if md else 0),
                  "category": (md[1] if md else None), "type": mtype}
            move_actions[(tn, e["actor"])] = {"move": mv, "target": tgt}
```
**REPLACE**:
```python
            mv = {"name": e["move"], "power": (md[0] if md else 0),
                  "category": (md[1] if md else None), "type": mtype,
                  "contact": e["move"] in getattr(ref, "CONTACT_MOVES", set())}
            move_actions[(tn, e["actor"])] = {"move": mv, "target": tgt}
```

> 주의: B2의 FIND는 PR-D1(타입/특성)에서 이미 `"type": mtype`로 바뀐 상태를 가정한다. PR-D1이
> 적용돼 있어야 이 앵커가 맞는다(이미 적용 완료).

---

## 검증 (적용 후)
1. **클린룸(이미 통과)** — 디스패처 산식: Hippowdon 접촉 Ice Fang → Garchomp(Rough Skin+Rocky
   Helmet) 피격 → Hippowdon 420→368→298. 비접촉 미발동. effects빈/키없음 no-op.
2. **앱사이드 — 풀배틀**: 루트에서 `python run_b4.py`.
   - 기대: **T5 Hippowdon**에 접촉 반동이 출현. 이번 PR만으론 engΔ ≈ −122(−52−70)까지 가고,
     로그 −96과는 +26(Leftovers, 턴엔드) 차이가 남음 → **E′2에서 Leftovers 얹으면 완전 닫힘**.
     이번 PR의 성공 기준은 "T5에 Rough Skin/Rocky Helmet 반동 로그가 찍히고 engΔ가 0→−122 쪽으로
     이동"이다(완전 닫힘 아님, 부분 진척).
   - Ferrothorn 접촉 피격 시 Iron Barbs(−1/8) 출현(해당 턴 있으면).
   - 엔진 마지막 캡처 턴 = 27 유지(desync 재발 없음).
   - 출력 전체를 붙여주면 함께 읽고 E′2(턴엔드 env)로 진행.
3. **회귀0**: effects 미설정 게임·ability/item 키 없는 char·비접촉 무브 → 디스패처 즉시 no-op.
   기존 single-slot leftovers/status/hazard·해결 파이프라인 비트 동일.

## 적용 메모
- char에 ability/item 노출은 디스패처 owner 매칭의 전제(B1). 이게 없으면 EFFECTS가 있어도
  영원히 no-op. 적용 시 B1 필수.
- EFFECTS가 list→dict로 바뀌므로, `build_battle_spec`의 `mechanisms['effects']=EFFECTS`(71줄)는
  그대로 dict를 싣는다(무변경). 디스패처는 dict.get(name)으로 읽는다.
- 다음(PR-E′2): 디스패처를 ON_TURN_END에 등록 + heal_frac. Leftovers/Black Sludge/Rain Dish/
  sandstorm/psn/brn/tox를 EFFECTS로. 날씨/상태를 field_state·char에 공급(resync 훅). 다수
  ★행 일괄 닫힘.
