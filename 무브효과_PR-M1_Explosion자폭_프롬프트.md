# PR-M1 — Explosion/Self-Destruct 자폭 (디스패처 무브-소스 + self_faint 효과타입)

## 목적
환경 밖 첫 버킷(무브 효과)의 첫 벽돌. **Explosion/Self-Destruct 사용자 자폭**을 닫는다. 키스톤
디스패처를 *무브-소스*로 확장(무브명 키 + self_faint 효과타입) — ability/item/status/weather에
이어 무브도 효과 소스가 된다.

근거(트레이스 실측): T15 Ferrothorn Explosion·T19 Metagross Explosion — move 이벤트 faints에
**사용자 자신**이 포함(자폭). 대상 데미지는 엔진 본체가 이미 정확(검증: T15 Bonaparte
−108/−108). 빠진 건 *사용자 HP→0*뿐이라 깨끗하게 고립돼 있다. 자폭 후 사용자 교체는 기존
faint 경로(_resolve_faint + trace_faint_incoming)가 처리.

## 검증 제약
engine.py truncation으로 전체 실행은 앱사이드(run_b4). 디스패처 확장 로직은 클린룸 검증됨.
앵커는 Read 확인(디스패처 keys 805·heal_frac 829, EFFECTS 'tox' 140).

## 대상
`modules/engine.py`(2건: 무브명 키 + 무브-소스 가드 / self_faint 효과타입) +
`modules/reference_gen5.py`(1건: EFFECTS Explosion·Self-Destruct).

## 설계 근거 (클린룸 검증됨)
- **무브-소스 매칭**: ON_HIT에서 owner=active_char(사용자)일 때 `current_move` 이름을 키로 추가
  → `effects.get('Explosion')` 매칭. source=='move' 가드로 ability/item 동명 오발동 차단.
- **self_faint 효과타입**: scope=self(=active_char) HP를 0으로. 대상(current_target)은 자폭효과
  안 받음(키에 무브명은 active_char만 추가).
- **클린룸**: Metagross/Ferrothorn Explosion → 사용자 HP→0, 대상 불변(본체 데미지는 엔진이 별도),
  일반 무브(Body Slam) 자폭 안 함(회귀0), Rough Skin 등 기존 효과 공존.

---

## FIND/REPLACE — modules/engine.py

### E1 — ON_HIT에서 사용자 무브명을 키로 + 무브-소스 가드
**FIND**:
```python
        keys = [owner.get("ability"), owner.get("item"), owner.get("status")]
        if phase != "ON_HIT":   # 턴엔드 self엔 발효 날씨 토큰도 키로(sandstorm 등 날씨 소스)
            keys.append((ctx.get("field_state") or {}).get("weather"))
        for nm in keys:
            spec = effects.get(nm) if nm else None
            if not spec or spec.get("trigger") != phase:
                continue
            if not _eff_cond_ok(ctx, spec.get("condition"), owner):
                continue
```
**REPLACE**:
```python
        keys = [owner.get("ability"), owner.get("item"), owner.get("status")]
        if phase != "ON_HIT":   # 턴엔드 self엔 발효 날씨 토큰도 키로(sandstorm 등 날씨 소스)
            keys.append((ctx.get("field_state") or {}).get("weather"))
        if phase == "ON_HIT" and owner is ctx.get("active_char"):   # 무브-소스: 사용자가 쓴 무브명
            keys.append((ctx.get("current_move") or {}).get("name"))
        for nm in keys:
            spec = effects.get(nm) if nm else None
            if not spec or spec.get("trigger") != phase:
                continue
            if spec.get("source") == "move" and nm != (ctx.get("current_move") or {}).get("name"):
                continue   # move-소스는 실제 사용 무브에만(ability/item 동명 오발동 차단)
            if not _eff_cond_ok(ctx, spec.get("condition"), owner):
                continue
```

### E2 — self_faint 효과타입 추가
**FIND**:
```python
            elif eff.get("type") == "heal_frac":
                amt = int(res["max"] * float(eff.get("frac", 0)))
                if amt > 0:
                    res["current"] = min(res["max"], res["current"] + amt)
                    add_log(f"  -> [Phase: {phase}] {nm}: {tgt.get('id','?')} +{amt} "
                            f"({int(res['current'])}/{int(res['max'])})")
```
**REPLACE**:
```python
            elif eff.get("type") == "heal_frac":
                amt = int(res["max"] * float(eff.get("frac", 0)))
                if amt > 0:
                    res["current"] = min(res["max"], res["current"] + amt)
                    add_log(f"  -> [Phase: {phase}] {nm}: {tgt.get('id','?')} +{amt} "
                            f"({int(res['current'])}/{int(res['max'])})")
            elif eff.get("type") == "self_faint":
                res["current"] = 0       # Explosion/Self-Destruct 사용자 자폭(HP→0)
                add_log(f"  -> [Phase: {phase}] {nm}: {tgt.get('id','?')} 자폭(HP→0)")
```

---

## FIND/REPLACE — modules/reference_gen5.py

### R1 — EFFECTS에 Explosion·Self-Destruct(무브-소스 자폭) 추가
**FIND**:
```python
    'tox':          {'trigger': 'ON_TURN_END',
                     'effect': {'type': 'damage_frac', 'frac': 1/16, 'of': 'maxhp', 'progressive': True},
                     'scope': 'self', 'source': 'status'},     # 맹독 누진 n/16 (stage=엔진 tox_stage 카운터)
}
```
**REPLACE**:
```python
    'tox':          {'trigger': 'ON_TURN_END',
                     'effect': {'type': 'damage_frac', 'frac': 1/16, 'of': 'maxhp', 'progressive': True},
                     'scope': 'self', 'source': 'status'},     # 맹독 누진 n/16 (stage=엔진 tox_stage 카운터)
    # 무브-소스(ON_HIT). Explosion/Self-Destruct: 사용자(scope=self) 자폭. 대상 데미지는 엔진 본체가
    # 이미 적용(검증: T15 Bonaparte −108/−108) — 빠진 건 사용자 HP→0뿐.
    'Explosion':     {'trigger': 'ON_HIT', 'source': 'move',
                      'effect': {'type': 'self_faint'}, 'scope': 'self'},
    'Self-Destruct': {'trigger': 'ON_HIT', 'source': 'move',
                      'effect': {'type': 'self_faint'}, 'scope': 'self'},
}
```

---

## 검증 (적용 후)
1. **클린룸(이미 통과)** — Explosion 사용자 자폭(Metagross·Ferrothorn HP→0)·대상 불변·일반 무브
   회귀·Rough Skin 공존.
2. **앱사이드 — 풀배틀**: 루트에서 `python run_b4.py`.
   - 기대(닫힘): **T19 Metagross** 자폭으로 fainted — 엔진 마지막 캡처에서 Metagross 기절 반영
     (이전 엔진 0=미사망). **T15 Ferrothorn**도 자폭 fainted.
   - 대상 데미지는 이미 맞으므로(T15 Bonaparte −108/−108) 변화 없음 — 이 PR은 *사용자 기절*을 더함.
   - 엔진 마지막 캡처 턴 = 27 유지. 회귀 없음.
   - 출력 붙여주면 함께 읽고 다음 무브효과(Psyshock 방어타격 → Wish 지연회복 → Draco 자기디버프)
     또는 Trick으로 진행.
3. **회귀0**: source=='move' 효과 미설정 게임·일반 무브 → 무브명 키가 effects에 없어 no-op.
   ability/item/status/weather 효과 경로 전부 불변(클린룸 재확인).

## 적용 메모
- self_faint는 사용자 HP를 0으로만 하고, 교체는 기존 _resolve_faint(trace_faint_incoming)가
  처리 — 새 교체 경로 불필요.
- Explosion은 비접촉이라 contact 조건과 무관. self_faint는 조건 없이 무브 사용 시 발동.
- **무브-소스 확장의 의미**: 이제 효과 소스가 ability/item/status/weather/**move** 5종. 다음
  무브효과들도 이 위에 데이터로 — Psyshock(방어스탯 오버라이드)·Wish(지연 heal)·Draco(자기 stat
  drop)·Life Orb(반동). 각기 새 효과타입 1개씩.
