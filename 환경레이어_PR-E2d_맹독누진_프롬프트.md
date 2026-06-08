# PR-E′2d — 맹독(toxic) 누진 틱 (디스패처 progressive + 엔진 tox_stage 카운터)

## 목적
환경 레이어의 마지막 조각. 맹독(tox)은 n/16 누진(1/16→2/16→…)이고 교체로 빠지면 리셋된다.
status='tox'는 E′2c로 이미 캡처되므로, **누진 stage만** 추가하면 env 레이어(회복·날씨·상태)가
완성된다. (par은 데미지 없음 — 별도.)

근거(env 실측): Hippowdon T6 −26(stage1)·T7 −52(stage2)·T13 −26(교체 후 **리셋** stage1).
Hippowdon은 T3/T13(자발교체) 진입 턴엔 틱이 있고, T15/T24(기절교체=forced) 진입 턴엔 틱이
없다 — 엔진이 forced 진입 유닛에 그 라운드 턴엔드를 안 돌리기 때문(Latios T16 모래와 동일 구조).

## 핵심 설계 — 엔진 내 카운터 (사전계산 아님)
맹독 stage는 *행동(턴엔드 발생) 유닛만* 증가해야 한다. 그래서 타임라인 사전계산이 아니라
**엔진 char에 tox_stage 카운터**를 둔다:
- 턴엔드 디스패치(행동 유닛만 발생)에서 tox면 `tox_stage += 1`, 데미지 = maxhp × tox_stage/16.
- resync(라운드 시작)가 off-field거나 비-tox인 유닛의 tox_stage를 0으로 리셋.
- forced 진입(기절교체) 유닛은 그 라운드 턴엔드가 없어 증가 안 함 → 그 턴 무틱(관측과 일치).

**클린룸 검증(통과)**: T6 stage1→26·T7 stage2→52·T8 교체아웃 리셋·T13 자발재진입→stage1→26·
T15/T24 forced→무틱. 관측 틱과 정확 일치.

## 검증 제약
engine.py truncation으로 전체 실행은 앱사이드(run_b4). 카운터/리셋 로직은 클린룸 검증됨.
앵커는 Read/Grep 확인(디스패처 damage_frac 819, resync status 102, EFFECTS 'brn' 137).

## 대상
`modules/engine.py`(1건: damage_frac에 progressive) + `modules/fullbattle_run.py`(1건: resync
stage 리셋) + `modules/reference_gen5.py`(1건: EFFECTS 'tox').

---

## FIND/REPLACE — modules/engine.py

### E1 — damage_frac에 progressive(누진) 분기
> 디스패처 damage_frac 블록만 수정(heal_frac은 무관). 누진이면 owner(=scope self=tgt)의
> tox_stage를 증가시켜 frac에 곱한다.

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
                frac = float(eff.get("frac", 0))
                if eff.get("progressive"):       # 맹독 누진 — 누적 stage × frac (n/16)
                    tgt["tox_stage"] = tgt.get("tox_stage", 0) + 1
                    frac *= tgt["tox_stage"]
                amt = int(res["max"] * frac)
                if amt > 0:
                    res["current"] = max(0, res["current"] - amt)
                    add_log(f"  -> [Phase: {phase}] {nm}: {tgt.get('id','?')} -{amt} "
                            f"({int(res['current'])}/{int(res['max'])})")
```

---

## FIND/REPLACE — modules/fullbattle_run.py

### F1 — resync 훅: tox_stage 리셋 (off-field/비-tox)
**FIND**:
```python
            if st is not None:
                p["status"] = st.get("status")   # 상태 공급(burn 등 디스패처 status 키용, PR-E′2b)
            if pof is not None:
                p["on_field"] = (pid in pof)
```
**REPLACE**:
```python
            if st is not None:
                p["status"] = st.get("status")   # 상태 공급(burn 등 디스패처 status 키용, PR-E′2b)
            # 맹독 누진 카운터 리셋(PR-E′2d) — off-field거나 비-tox면 0(다음 tox 진입 시 stage 1부터).
            # on-field+tox면 유지(턴엔드 디스패처가 증가). forced 진입은 턴엔드 없어 그 턴 무증가.
            on_f = (pof is None) or (pid in pof)
            if (not on_f) or p.get("status") != "tox":
                p["tox_stage"] = 0
            if pof is not None:
                p["on_field"] = (pid in pof)
```

---

## FIND/REPLACE — modules/reference_gen5.py

### R1 — EFFECTS에 맹독(tox) 누진 추가
**FIND**:
```python
    'brn':          {'trigger': 'ON_TURN_END',
                     'effect': {'type': 'damage_frac', 'frac': 1/8, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'status'},     # 화상 틱 1/8
}
```
**REPLACE**:
```python
    'brn':          {'trigger': 'ON_TURN_END',
                     'effect': {'type': 'damage_frac', 'frac': 1/8, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'status'},     # 화상 틱 1/8
    'tox':          {'trigger': 'ON_TURN_END',
                     'effect': {'type': 'damage_frac', 'frac': 1/16, 'of': 'maxhp', 'progressive': True},
                     'scope': 'self', 'source': 'status'},     # 맹독 누진 n/16 (stage=엔진 tox_stage 카운터)
}
```

---

## 검증 (적용 후)
1. **클린룸(이미 통과)** — 엔진 카운터 + resync 리셋: T6 26·T7 52·T8 리셋·T13 26(자발재진입)·
   T15/T24 무틱(forced). 관측 틱과 정확 일치.
2. **앱사이드 — 풀배틀**: 루트에서 `python run_b4.py`.
   - 기대(닫힘): **T7 Hippowdon**이 −52(맹독 stage2) 반영돼 닫힘에 근접 — T7 로그 −26 = 맹독
     −52 + Leftovers +26. 즉 engΔ가 +26(Leftovers만)에서 −26(맹독 −52 + Leftovers +26)으로.
   - **T13 Hippowdon** 맹독 −26(stage1, 리셋 확인). T15/T24엔 forced 진입이라 맹독 무틱(관측 일치).
   - 엔진 마지막 캡처 턴 = 27 유지. 회귀 없음.
   - **이로써 환경 레이어(Leftovers·Black Sludge·Rain Dish·모래·burn·맹독) 완성** — 남은 ★는
     환경 밖 버킷(무브효과 Explosion/Draco/Wish·Trick 아이템교환·해저드 SR·세트 정밀화).
3. **회귀0**: progressive 미설정 효과는 기존과 동일(frac 그대로). tox_stage는 tox 효과에서만
   생성·사용. effects/status 미설정 게임 → no-op.

## 적용 메모
- tox_stage는 엔진 char에 동적 생성되는 카운터(초기 키 불필요 — `tgt.get("tox_stage",0)`).
  resync가 라운드마다 off-field/비-tox 유닛을 0으로 리셋해 교체 리셋을 구현.
- forced 진입(기절교체) 유닛이 그 라운드 턴엔드를 안 받는 건 기존 엔진 동작(Latios T16과 동일).
  맹독 누진은 이 동작에 자연 정합 — 사전계산 불필요.
- **다음**: 환경 밖 버킷. 영향 큰 순서 추천 — 무브효과(Explosion 자폭 T19 −323)·Trick 아이템
  교환(T22/23)·해저드 SR 타입스케일(+스위치인 타이밍)·세트/EV 정밀화. 사용자 결정.
