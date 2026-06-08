# PR-E′2a — 턴엔드 회복 (디스패처 ON_TURN_END + heal_frac: Leftovers·Black Sludge)

## 목적
환경 레이어 2번째 벽돌. PR-E′1의 ON_HIT 디스패처를 **ON_TURN_END**로 확장해, 턴 종료 회복을
*데이터*로 적용한다. 첫 범위: **heal_frac + Leftovers·Black Sludge**(ability/item 키 매칭, 날씨
무관). 날씨 의존(Rain Dish)·모래칩·상태틱은 상태 공급이 필요해 PR-E′2b로 분리.

근거: run_b4 ★ 행 다수가 "엔진 0" — Leftovers 회복(+22~+26)이 gen5 spec에 안 엮여서다. env
스트림이 보유자를 역설계: **Leftovers = Hippowdon·Zapdos·Jirachi·Ferrothorn**, **Black Sludge =
Tentacruel(Poison → 회복)**. (Latios는 T20 Trick으로 후반에 Leftovers를 얻지만 *초기* 세트는
Choice Specs라 유지 — 동적 아이템 교환은 별도 버킷.)

## 검증 제약
engine.py truncation으로 전체 실행은 앱사이드(run_b4). 디스패처 확장 로직은 클린룸 검증됨
(아래). 앵커는 Read 확인(PR-E′1로 삽입된 디스패처 블록 + `_act_turn_end_heal` 760).

## 대상
`modules/engine.py`(5건: 디스패처 4개 수술 + `_act_turn_end_heal` 시작 1줄) +
`modules/reference_gen5.py`(2건: EFFECTS 추가 + SETS 아이템 교정). fullbattle_run 무변경.

## 설계 근거 (클린룸 검증됨)
- **ON_TURN_END owner = active_char만**. 턴엔드엔 `current_target`이 직전 피격자로 남아 있어,
  그대로 두면 상대 Leftovers가 *공격자 턴엔드에도* 발동 = 이중회복 버그. 페이즈별 owner 스코프로
  차단(ON_HIT만 target+attacker, 그 외 active_char만). **클린룸: 공격자 턴엔드에 상대 미회복 확인.**
- **heal_frac**: maxHP 분수 회복(max 캡). **클린룸 실측 일치**: Hippowdon +26(420/16)·Nanami
  +25(403/16)·Riou +23(383/16)·Ferrothorn +22(352/16)·Tentacruel(Zamza) Black Sludge +22(363/16).
- **of_types 조건**: Black Sludge는 Poison 타입만 회복(비-Poison은 미발동/후속 damage). 클린룸:
  Poison +22, 비-Poison no-op.
- 회귀0: effects 미설정·item/ability 키 없음 → no-op. ON_HIT 경로 불변(반동 368 클린룸 재확인).

---

## FIND/REPLACE — modules/engine.py

### E1 — 디스패처: 페이즈별 owner + status 키 (이중회복 가드)
**FIND**:
```python
    add_log = ctx.get("add_log") or (lambda *a, **k: None)
    for owner in (ctx.get("current_target"), ctx.get("active_char")):
        if owner is None:
            continue
        for nm in (owner.get("ability"), owner.get("item")):
```
**REPLACE**:
```python
    add_log = ctx.get("add_log") or (lambda *a, **k: None)
    # 페이즈별 owner — ON_HIT은 피격자+공격자, 그 외(ON_TURN_END 등)는 active_char만
    # (턴엔드에 current_target가 남아 상대 효과가 이중 발동하는 것을 차단).
    owners = ((ctx.get("current_target"), ctx.get("active_char"))
              if phase == "ON_HIT" else (ctx.get("active_char"),))
    for owner in owners:
        if owner is None:
            continue
        for nm in (owner.get("ability"), owner.get("item"), owner.get("status")):
```

### E2 — `_eff_cond_ok`: of_types/not_types(소유자 타입) 추가
**FIND**:
```python
def _eff_cond_ok(ctx, cond):
    """효과 조건 평가. 현재: contact(접촉 무브). 미설정이면 통과."""
    if not cond:
        return True
    if cond.get("contact") and not (ctx.get("current_move") or {}).get("contact"):
        return False
    return True
```
**REPLACE**:
```python
def _eff_types_of(char):
    """소유자 타입 리스트(t1/t2/t3). 조건 of_types/not_types용."""
    g = (char or {}).get("gimmicks", {})
    return [g.get(k) for k in ("t1", "t2", "t3") if g.get(k)]


def _eff_cond_ok(ctx, cond, owner=None):
    """효과 조건 평가. contact(접촉 무브)·of_types/not_types(소유자 타입). 미설정이면 통과."""
    if not cond:
        return True
    if cond.get("contact") and not (ctx.get("current_move") or {}).get("contact"):
        return False
    ot = cond.get("of_types")
    if ot and not (set(ot) & set(_eff_types_of(owner))):
        return False
    nt = cond.get("not_types")
    if nt and (set(nt) & set(_eff_types_of(owner))):
        return False
    return True
```

### E3 — `_eff_cond_ok` 호출에 owner 전달
**FIND**:
```python
            if not _eff_cond_ok(ctx, spec.get("condition")):
                continue
```
**REPLACE**:
```python
            if not _eff_cond_ok(ctx, spec.get("condition"), owner):
                continue
```

### E4 — heal_frac 효과타입 추가
**FIND**:
```python
            eff = spec.get("effect") or {}
            if eff.get("type") == "damage_frac":
                amt = int(res["max"] * float(eff.get("frac", 0)))
                if amt > 0:
                    res["current"] = max(0, res["current"] - amt)
                    add_log(f"  -> [Phase: {phase}] {nm}: {tgt.get('id','?')} -{amt} "
                            f"({int(res['current'])}/{int(res['max'])})")
```
**REPLACE**:
```python
            eff = spec.get("effect") or {}
            if eff.get("type") == "damage_frac":
                amt = int(res["max"] * float(eff.get("frac", 0)))
                if amt > 0:
                    res["current"] = max(0, res["current"] - amt)
                    add_log(f"  -> [Phase: {phase}] {nm}: {tgt.get('id','?')} -{amt} "
                            f"({int(res['current'])}/{int(res['max'])})")
            elif eff.get("type") == "heal_frac":
                amt = int(res["max"] * float(eff.get("frac", 0)))
                if amt > 0:
                    res["current"] = min(res["max"], res["current"] + amt)
                    add_log(f"  -> [Phase: {phase}] {nm}: {tgt.get('id','?')} +{amt} "
                            f"({int(res['current'])}/{int(res['max'])})")
```

### E5 — `_act_turn_end_heal` 시작에 디스패처 구동
> 주의: 디스패처 호출은 함수 **맨 앞**에 둔다. 기존 단발 leftovers 미설정 시 함수가 `if not
> spec: return`으로 일찍 빠지므로, 끝에 두면 gen5(디스패처만 쓰는)에선 호출이 안 된다.

**FIND**:
```python
def _act_turn_end_heal(ctx):
    """턴 종료 회복 메커니즘 (Leftovers류) — game_config['mechanisms']['leftovers'] 기반.
    부착 캐릭터가 턴 종료 시 vital 자원의 percent만큼 회복한다. 사망(현재값 0)이면
    회복하지 않는다. max 상한으로 클램프. 미부착/미설정 시 no-op."""
    char = ctx["active_char"]
    mechs = (ctx.get("game_config") or {}).get("mechanisms") or {}
    spec = mechs.get("leftovers")
    if not spec:
        return
```
**REPLACE**:
```python
def _act_turn_end_heal(ctx):
    """턴 종료 회복 메커니즘 (Leftovers류) — game_config['mechanisms']['leftovers'] 기반.
    부착 캐릭터가 턴 종료 시 vital 자원의 percent만큼 회복한다. 사망(현재값 0)이면
    회복하지 않는다. max 상한으로 클램프. 미부착/미설정 시 no-op.
    + 효과-스키마 디스패처(ON_TURN_END)를 맨 앞에서 구동(PR-E′2) — effects 미설정 시 no-op.
    단발 leftovers와 병존(둘 다 미설정이면 완전 no-op = 회귀0)."""
    _act_effect_dispatch(ctx, "ON_TURN_END")
    char = ctx["active_char"]
    mechs = (ctx.get("game_config") or {}).get("mechanisms") or {}
    spec = mechs.get("leftovers")
    if not spec:
        return
```

---

## FIND/REPLACE — modules/reference_gen5.py

### R1 — EFFECTS에 턴엔드 회복 추가
**FIND**:
```python
    'Rocky Helmet': {'trigger': 'ON_HIT', 'condition': {'contact': True},
                     'effect': {'type': 'damage_frac', 'frac': 1/6, 'of': 'maxhp'},
                     'scope': 'attacker', 'source': 'item'},
}
```
**REPLACE**:
```python
    'Rocky Helmet': {'trigger': 'ON_HIT', 'condition': {'contact': True},
                     'effect': {'type': 'damage_frac', 'frac': 1/6, 'of': 'maxhp'},
                     'scope': 'attacker', 'source': 'item'},
    # 턴엔드 회복(PR-E′2a). owner=active_char, scope=self. Leftovers는 전원, Black Sludge는
    # Poison만 회복(비-Poison damage는 후속). Rain Dish(비 한정)·모래칩·상태틱은 PR-E′2b.
    'Leftovers':    {'trigger': 'ON_TURN_END',
                     'effect': {'type': 'heal_frac', 'frac': 1/16, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'item'},
    'Black Sludge': {'trigger': 'ON_TURN_END', 'condition': {'of_types': ['Poison']},
                     'effect': {'type': 'heal_frac', 'frac': 1/16, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'item'},
}
```

### R2 — SETS 아이템 교정 (env 역설계: Leftovers 보유자 + Tentacruel Black Sludge)
env 회복 스트림이 보유자를 확정. Hippowdon·Zapdos·Jirachi·Ferrothorn에 Leftovers, Tentacruel에
Black Sludge. (Latios는 초기 Choice Specs 유지 — Trick 후반 획득은 동적 교환 버킷.)

**FIND**:
```python
    'Ferrothorn': {'nature': 'Relaxed', 'evs': (252, 0, 252, 0, 4, 0),   'item': None,           'ability': 'Iron Barbs'},    # [prior]
    'Tentacruel': {'nature': 'Bold',    'evs': (252, 0, 252, 0, 4, 0),   'item': None,           'ability': 'Rain Dish'},     # [확정] 물리방어
```
**REPLACE**:
```python
    'Ferrothorn': {'nature': 'Relaxed', 'evs': (252, 0, 252, 0, 4, 0),   'item': 'Leftovers',    'ability': 'Iron Barbs'},    # [확정] env Leftovers +22
    'Tentacruel': {'nature': 'Bold',    'evs': (252, 0, 252, 0, 4, 0),   'item': 'Black Sludge', 'ability': 'Rain Dish'},     # [확정] 물리방어 / env Black Sludge +22
```

**FIND**:
```python
    'Jirachi':    {'nature': 'Careful', 'evs': (252, 0, 0, 0, 224, 32),  'item': None,           'ability': 'Serene Grace'},  # [prior] SpD Wish
    'Zapdos':     {'nature': 'Timid',   'evs': (0, 0, 0, 252, 4, 252),   'item': None,           'ability': 'Pressure'},      # [prior] 공격형
```
**REPLACE**:
```python
    'Jirachi':    {'nature': 'Careful', 'evs': (252, 0, 0, 0, 224, 32),  'item': 'Leftovers',    'ability': 'Serene Grace'},  # [확정] env Leftovers +25 / SpD Wish
    'Zapdos':     {'nature': 'Timid',   'evs': (0, 0, 0, 252, 4, 252),   'item': 'Leftovers',    'ability': 'Pressure'},      # [확정] env Leftovers +23
```

**FIND**:
```python
    'Hippowdon':  {'nature': 'Impish',  'evs': (252, 0, 252, 0, 4, 0),   'item': None,           'ability': 'Sand Stream'},   # [확정] 물리벽
```
**REPLACE**:
```python
    'Hippowdon':  {'nature': 'Impish',  'evs': (252, 0, 252, 0, 4, 0),   'item': 'Leftovers',    'ability': 'Sand Stream'},   # [확정] 물리벽 / env Leftovers +26
```

---

## 검증 (적용 후)
1. **클린룸(이미 통과)** — 디스패처 ON_TURN_END: Leftovers 보유자별 +26/+25/+23/+22, Black
   Sludge Poison +22·비-Poison no-op, **이중회복 가드**(공격자 턴엔드에 상대 미회복), 회귀0,
   ON_HIT 반동 368 불변.
2. **앱사이드 — 풀배틀**: 루트에서 `python run_b4.py`.
   - 기대: 그동안 "엔진 0"이던 **Leftovers 회복 행이 닫힘** — 예: T10 Riou(Zapdos) +23, T18/T24
     Nanami(Jirachi) +25, T15 Ferrothorn +22 등에서 engΔ가 로그Δ에 수렴(±roll).
   - **T5 Hippowdon 완전 닫힘 근접**: PR-E′1 반동 −122 + 이번 Leftovers +26 = −96 ≈ 로그 −96.
   - 엔진 마지막 캡처 턴 = 27 유지. 다른 행 회귀 없음.
   - 출력 전체를 붙여주면 함께 읽고 **E′2b**(Rain Dish·모래칩·상태틱 + 날씨/상태 공급)로 진행.
3. **회귀0**: effects 미설정 게임·item/ability 키 없는 char → 디스패처 즉시 no-op. 단발
   leftovers/status 슬롯·해결 파이프라인 비트 동일.

## 적용 메모
- E1~E5는 PR-E′1로 삽입된 디스패처 블록과 `_act_turn_end_heal`을 수술한다. 앵커는 그 코드의
  고유 줄(이번 세션 Read 확인).
- Leftovers/Black Sludge는 ITEMS(정적 스탯배율 테이블)에 없어 apply_effects 무영향 — 순수
  디스패처 발동용. char의 item 노출은 PR-E′1 B1으로 이미 됨.
- **다음(E′2b)**: 날씨 공급(build_ctx에 weather_by_turn) + Rain Dish(weather:rain)·sandstorm
  chip(weather:sand + not_types:[Rock,Ground,Steel], source=weather 분리 디스패치)·burn/poison
  (status 공급). 맹독 누진(n/16)은 카운터 공급이 필요해 그 다음.
