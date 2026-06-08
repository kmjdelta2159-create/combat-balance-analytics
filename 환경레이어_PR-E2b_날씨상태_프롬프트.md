# PR-E′2b — 모래칩·Rain Dish·burn (날씨/상태 공급 + 디스패처 weather/status 소스)

## 목적
환경 레이어 3번째 벽돌. 턴엔드 *날씨/상태* 발동형을 닫는다 — **sandstorm 칩·Rain Dish·burn 틱**.
PR-E′2a가 ability/item 키 회복을 했고, 이번엔 (a) 발효 날씨를 엔진에 공급하고 (b) 디스패처가
날씨 토큰·status 토큰을 키로 받게 해, 소유 ability/item이 아닌 *상태/날씨 기반* 효과를 적용한다.
맹독(tox) 누진(n/16)은 카운터 공급이 필요해 다음 PR(E′2c).

근거(env 실측): 모래칩 1/16 — Latios −19·Tentacruel −22·Zapdos −23, **Ground/Steel/Rock 면역**
(Hippowdon·Ferrothorn·Jirachi·Metagross·Garchomp은 칩 0). Rain Dish 비에서 Tentacruel +22.
burn 1/8 — Rotom-Wash −33(271/8). 날씨 타임라인은 트레이스 context.weather에서 도출(검증됨).

## 검증 제약
engine.py truncation으로 전체 실행은 앱사이드(run_b4). 디스패처/날씨도출 로직은 클린룸 검증됨.
앵커는 Read/Grep 확인(이번 세션: 디스패처 797·802, `_eff_cond_ok` of_types 776, build_ctx 1385,
ctx field_state 1411).

## 대상
`modules/engine.py`(3건: 디스패처 키·weather 조건·build_ctx 날씨공급) +
`modules/reference_gen5.py`(1건: EFFECTS 추가) + `modules/fullbattle_run.py`(3건: 날씨도출 함수·
gc 주입·resync 상태공급).

## 설계 근거 (클린룸 검증됨)
- **날씨 공급**: 트레이스 move `context.weather`(RainDance/Sandstorm)를 턴별로 도출 →
  `game_config['weather_by_turn']` → 엔진 build_ctx가 매 턴 `field_state['weather']`에 세팅.
  (상태 자체를 시뮬 안 하고 관측값 주입 — 트레이스-리플레이 원칙.)
- **모래칩(날씨 토큰 키)**: ability/item이 아니므로 *발효 날씨 토큰*('sand')을 디스패처 키에
  추가(턴엔드 self). `EFFECTS['sand']` = damage_frac 1/16 + `not_types:[Rock,Ground,Steel]` 면역.
  **클린룸**: Latios −19·Zamza −22·Riou −23, Hippowdon(Ground)·Ferrothorn(Steel) 칩 0.
- **Rain Dish(weather 조건)**: ability 'Rain Dish' 키 + `condition weather:'rain'`. 클린룸: 비
  +22, 모래 미발동.
- **burn(status 토큰 키)**: resync가 `p['status']`를 로그 스냅샷에서 공급 → 디스패처가
  `owner.get('status')`='brn' 키로 `EFFECTS['brn']`(damage_frac 1/8) 발동. 클린룸: Rotom-Wash −33.
- **이중적용 가드 유지**(E′2a): 턴엔드 owner=active_char만 → 공격자 턴엔드에 상대 모래칩/burn
  미발동(클린룸 재확인). 회귀0: weather None·status None·effects 미설정 → no-op.

---

## FIND/REPLACE — modules/engine.py

### EA1 — 디스패처 키에 발효 날씨 토큰 추가 (턴엔드 self)
**FIND**:
```python
        for nm in (owner.get("ability"), owner.get("item"), owner.get("status")):
```
**REPLACE**:
```python
        keys = [owner.get("ability"), owner.get("item"), owner.get("status")]
        if phase != "ON_HIT":   # 턴엔드 self엔 발효 날씨 토큰도 키로(sandstorm 등 날씨 소스)
            keys.append((ctx.get("field_state") or {}).get("weather"))
        for nm in keys:
```

### EA2 — `_eff_cond_ok`에 weather 조건 추가
**FIND**:
```python
    ot = cond.get("of_types")
    if ot and not (set(ot) & set(_eff_types_of(owner))):
        return False
```
**REPLACE**:
```python
    w = cond.get("weather")
    if w and str((ctx.get("field_state") or {}).get("weather") or "") != w:
        return False
    ot = cond.get("of_types")
    if ot and not (set(ot) & set(_eff_types_of(owner))):
        return False
```

### EA3 — build_ctx: 발효 날씨를 field_state에 공급
> `field_state`는 build_ctx 바깥(run_simulation)에서 정의돼 클로저로 잡힌다. `turn`·`game_config`도
> 스코프에 있다. ctx 조립 직전에 세팅.

**FIND**:
```python
        attack_range = get_effective_stat(active_char, range_stat) if range_stat else None
        move_range = get_effective_stat(active_char, move_stat) if move_stat else None
```
**REPLACE**:
```python
        attack_range = get_effective_stat(active_char, range_stat) if range_stat else None
        move_range = get_effective_stat(active_char, move_stat) if move_stat else None
        # 발효 날씨를 field_state에 공급(트레이스 관측값) — 디스패처 weather 조건·모래칩용(PR-E′2b).
        # weather_by_turn 미설정 시 None(회귀0).
        field_state["weather"] = ((game_config or {}).get("weather_by_turn") or {}).get(turn)
```

---

## FIND/REPLACE — modules/reference_gen5.py

### R1 — EFFECTS에 모래칩·Rain Dish·burn 추가
**FIND**:
```python
    'Black Sludge': {'trigger': 'ON_TURN_END', 'condition': {'of_types': ['Poison']},
                     'effect': {'type': 'heal_frac', 'frac': 1/16, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'item'},
}
```
**REPLACE**:
```python
    'Black Sludge': {'trigger': 'ON_TURN_END', 'condition': {'of_types': ['Poison']},
                     'effect': {'type': 'heal_frac', 'frac': 1/16, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'item'},
    # 날씨/상태 소스(PR-E′2b). 'sand'는 발효 날씨 토큰으로 매칭(디스패처가 field_state.weather를
    # 키로 추가). Rain Dish는 ability 키 + weather 조건. 'brn'은 status 토큰 키(resync 공급).
    'sand':         {'trigger': 'ON_TURN_END', 'condition': {'not_types': ['Rock', 'Ground', 'Steel']},
                     'effect': {'type': 'damage_frac', 'frac': 1/16, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'weather'},   # 모래폭풍 칩 1/16
    'Rain Dish':    {'trigger': 'ON_TURN_END', 'condition': {'weather': 'rain'},
                     'effect': {'type': 'heal_frac', 'frac': 1/16, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'ability'},   # 비 1/16 회복
    'brn':          {'trigger': 'ON_TURN_END',
                     'effect': {'type': 'damage_frac', 'frac': 1/8, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'status'},     # 화상 틱 1/8
}
```

> 참고: Rain Dish는 Tentacruel SET ability에 이미 있어 char에 노출됨(추가 세트 변경 불필요).
> burn은 status 공급(아래 fullbattle_run)으로 char['status']='brn'이 들어와야 발동. 맹독(tox)은
> 누진이라 이번 EFFECTS에 안 넣음(E′2c) — status='tox'가 공급돼도 매칭 효과 없어 no-op.

---

## FIND/REPLACE — modules/fullbattle_run.py

### F1 — 날씨 타임라인 도출 함수 (트레이스 → {turn: 'rain'/'sand'/None})
**FIND**:
```python
def build_onfield_timeline(trace):
```
**REPLACE**:
```python
def build_weather_by_turn(trace):
    """트레이스 → {turn: 'rain'/'sand'/None}. move context.weather·env weather 필드의 그 턴
    값을 normalize, 결측 턴은 직전값 carry(날씨는 명시 전이까지 지속)."""
    def norm(w):
        if not w:
            return None
        s = str(w).lower()
        return "rain" if "rain" in s else ("sand" if "sand" in s else s)
    seen = {}
    for e in trace["events"]:
        tn = e.get("turn")
        if tn is None:
            continue
        w = (e.get("context") or {}).get("weather") or e.get("weather")
        if w is not None:
            seen[tn] = norm(w)
    out = {}
    cur = None
    for t in range(0, (max(seen) if seen else 0) + 1):
        if seen.get(t) is not None:
            cur = seen[t]
        out[t] = cur
    return out


def build_onfield_timeline(trace):
```

### F2 — setup_for_engine: weather_by_turn 주입
**FIND**:
```python
    parts, spec, ta = prepare_run(trace, ref)
    gc = spec["game_config"]
    gc["preserve_ids"] = True
```
**REPLACE**:
```python
    parts, spec, ta = prepare_run(trace, ref)
    gc = spec["game_config"]
    gc["preserve_ids"] = True
    gc["weather_by_turn"] = build_weather_by_turn(trace)   # 발효 날씨 공급(PR-E′2b)
```

### F3 — resync 훅: 상태(status) 공급
**FIND**:
```python
        for p in participants:
            pid = p.get("id")
            st = prev.get(pid)
            if st and st.get("hp") is not None:
                res = p.setdefault("resources", {}).setdefault("HP", {"current": 0, "max": 0})
                res["current"] = st["hp"]
            if pof is not None:
                p["on_field"] = (pid in pof)
```
**REPLACE**:
```python
        for p in participants:
            pid = p.get("id")
            st = prev.get(pid)
            if st and st.get("hp") is not None:
                res = p.setdefault("resources", {}).setdefault("HP", {"current": 0, "max": 0})
                res["current"] = st["hp"]
            if st is not None:
                p["status"] = st.get("status")   # 상태 공급(burn 등 디스패처 status 키용, PR-E′2b)
            if pof is not None:
                p["on_field"] = (pid in pof)
```

---

## 검증 (적용 후)
1. **클린룸(이미 통과)** — 모래칩(Latios −19·Zamza −22·Riou −23, Ground/Steel 면역 0), Rain Dish
   비 +22·모래 미발동, burn −33, 이중적용 가드(공격자 턴엔드 상대 미발동), weather None no-op.
   날씨 타임라인 도출(턴별 rain/sand) 트레이스로 확인.
2. **앱사이드 — 풀배틀**: 루트에서 `python run_b4.py`.
   - 기대(닫힘): **T16·T17 Latios** 모래 −19, **T13·T14 Zamza** 모래 −22, **T8/T9 Rotom-Wash**
     burn −33 분이 engΔ에 반영. 그동안 "엔진 0/+"이던 모래·burn 행이 로그Δ에 수렴.
   - **T7 Hippowdon**은 여전히 ★ 남음 — 맹독(tox) 누진(−52)이 E′2c라 +26(Leftovers)만 반영.
     이건 정상(다음 PR 타깃).
   - 엔진 마지막 캡처 턴 = 27 유지. 회귀 없음(weather/status 공급 전 게임은 weather_by_turn
     미설정 → field_state.weather None → 디스패처 모래/Rain Dish 미발동).
   - 출력 붙여주면 함께 읽고 잔여(맹독 누진·Trick 아이템교환·무브효과 Explosion/Wish·세트)로 진행.
3. **회귀0**: weather_by_turn 미설정(다른 게임)·status 키 없음·effects 미설정 → 디스패처 즉시
   no-op. ON_HIT·E′2a heal 경로 불변.

## 적용 메모
- 모래칩을 '날씨 토큰 키'로 매칭하는 건 status 토큰('brn')과 같은 패턴 — 디스패처 키 =
  ability/item/status/weather. trigger 필터가 ON_HIT 오발동을 막는다(모래/burn은 ON_TURN_END).
- burn은 화상 *틱*만(1/8). gen5 burn의 *물리 공격 반감*은 이번 범위 밖(Rotom-Wash는 특수라 영향
  미미). 물리 burn 반감은 후속 데미지 정밀화에서.
- **다음(E′2c)**: 맹독(tox) 누진 — status='tox' + 턴별 stage(n/16) 공급(카운터 또는 트레이스
  도출). Hippowdon T6 −26(1/16)·T7 −52(2/16) 닫힘.
