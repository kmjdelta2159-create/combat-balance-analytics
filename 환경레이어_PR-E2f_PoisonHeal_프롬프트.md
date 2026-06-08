# PR-E′2f — Poison Heal (Breloom 맹독 데미지 억제)

## 목적
PR-E′2e(status log[T] 공급)가 T7 맹독을 닫으면서, **T1 Gengen이 −256→−275로 악화**됐다. 원인을
진단으로 확정: **Gengen(Breloom)이 Poison Heal + Toxic Orb**다.
- T1 트레이스: `Gengen Spore` 무브 이벤트 flags=['status:slp', 'status:tox'] — Spore로 상대를
  재우면서 **자기 자신이 맹독**(Toxic Orb 자가발동). 그런데 로그엔 Gengen 맹독 데미지 틱이
  *전혀 없음*(env psn/tox 0건) — **Poison Heal이 맹독 데미지를 회복으로 바꾸기 때문**.

즉 맹독(tox) 데미지 효과를 **Poison Heal 보유자에겐 억제**해야 한다. env가 Breloom 세트를
역설계했다(Spore + 자기맹독 + 맹독데미지無 = 전형적 Poison Heal SubSeed Breloom).

## 검증 제약
디스패처 조건 로직은 클린룸 검증됨. 앵커는 Read 확인(_eff_cond_ok 782, Breloom 104, 'tox' 140).

## 대상
`modules/engine.py`(1건: _eff_cond_ok에 not_ability) + `modules/reference_gen5.py`(2건: 'tox'
효과 조건 + Breloom 세트). 

## 설계 근거 (클린룸 검증됨)
- `not_ability` 조건: 효과 condition에 `not_ability: [...]`가 있고 소유자 ability가 그 안에 있으면
  효과 미발동. 클린룸: Gengen(Poison Heal) 맹독 억제(False), Hippowdon(Sand Stream) 정상 발동(True).
- 'tox' 효과에 `not_ability: ['Poison Heal']` → Poison Heal 보유자만 맹독 데미지 제외.
- 정직한 범위: 이 PR은 *맹독 데미지 억제*만 한다. Poison Heal의 *회복(+1/8)*과 Toxic Orb 발동
  턴 타이밍(부여 턴엔 무틱)은 모델 안 함 — Gengen은 T1에 −256(HP Fire 롤)로 복귀(로그 −238,
  롤 노이즈)하고, Poison Heal 회복은 작은 잔차로 남김(후속). 잘못된 데미지를 없애는 게 우선.

## FIND/REPLACE — modules/engine.py

### E1 — _eff_cond_ok에 not_ability 조건
**FIND**:
```python
    nt = cond.get("not_types")
    if nt and (set(nt) & set(_eff_types_of(owner))):
        return False
    return True
```
**REPLACE**:
```python
    nt = cond.get("not_types")
    if nt and (set(nt) & set(_eff_types_of(owner))):
        return False
    na = cond.get("not_ability")
    if na and (owner or {}).get("ability") in na:
        return False   # Poison Heal 등 — 해당 특성 보유자에겐 미발동(맹독/독 데미지 억제)
    return True
```

## FIND/REPLACE — modules/reference_gen5.py

### R1 — 'tox' 효과에 not_ability 조건
**FIND**:
```python
    'tox':          {'trigger': 'ON_TURN_END',
                     'effect': {'type': 'damage_frac', 'frac': 1/16, 'of': 'maxhp', 'progressive': True},
                     'scope': 'self', 'source': 'status'},     # 맹독 누진 n/16 (stage=엔진 tox_stage 카운터)
```
**REPLACE**:
```python
    'tox':          {'trigger': 'ON_TURN_END', 'condition': {'not_ability': ['Poison Heal']},
                     'effect': {'type': 'damage_frac', 'frac': 1/16, 'of': 'maxhp', 'progressive': True},
                     'scope': 'self', 'source': 'status'},     # 맹독 누진 n/16 (Poison Heal 보유자 제외)
```

### R2 — Breloom 세트 교정 (env 역설계: Poison Heal + Toxic Orb)
**FIND**:
```python
    'Breloom':    {'nature': 'Jolly',   'evs': (0, 252, 0, 0, 4, 252),   'item': 'Life Orb',     'ability': 'Technician'},    # [prior]
```
**REPLACE**:
```python
    'Breloom':    {'nature': 'Jolly',   'evs': (0, 252, 0, 0, 4, 252),   'item': 'Toxic Orb',    'ability': 'Poison Heal'},   # [확정] env: Spore+자기맹독(Toxic Orb)·맹독데미지無(Poison Heal)
```

## 검증 (적용 후)
1. **클린룸(이미 통과)** — Gengen(Poison Heal) 맹독 억제, Hippowdon 정상 발동, 조건 None 통과.
2. **앱사이드 — 풀배틀**: 루트에서 `python run_b4.py`.
   - 기대: **T1 Gengen이 −256 부근으로 복귀**(HP Fire 롤만, 맹독 데미지 제거). 로그 −238과는 롤
     차(±). **T7 Hippowdon −26/−26 유지**(Sand Stream이라 맹독 정상).
   - 엔진 마지막 캡처 턴 = 27 유지. 회귀 없음.
   - 출력 붙여주면 함께 읽고 다음(switch-in-turn 잔류 또는 Psyshock/Trick 버킷)으로.
3. **회귀0**: not_ability 미설정 효과는 기존과 동일. Poison Heal 미보유 유닛의 맹독은 정상 발동.

## 적용 메모
- Breloom 세트 교정(Technician→Poison Heal, Life Orb→Toxic Orb)은 env 확정. Breloom이 데미지
  무브를 거의 안 써(Spore 등) 데미지 행 영향 미미 — 영향 시 잔차가 드러내면 재조정.
- **남은 작은 잔차(후속)**: (a) Poison Heal *회복* +1/8(Gengen이 매 턴 소폭 회복), (b) Toxic Orb
  발동 턴(T1)엔 무틱이어야 하는 inflict-timing. 둘 다 작고, 잘못된 데미지 제거가 우선이라 분리.
- **방법론 메모**: E′2e가 한 잔차(T7)를 닫으며 다른 잔차(T1 Poison Heal)를 드러냈다 — 역설계
  루프가 세트(Breloom=Poison Heal)를 데이터로 지목한 전형. status 공급 타이밍은 무브-부여 vs
  도구-부여로 갈리는데, 정밀 해법은 엔진이 무브-부여 status를 턴 중 적용하는 것(무브효과 버킷).
