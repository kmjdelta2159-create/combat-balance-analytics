# PR-C1 — gen5 세트/EV 메커니즘 + 표준세트 시드 (reference_gen5 확장)

## 목적
B4 풀배틀 run·per-event 잔차가 **지배적 잔차 = 세트/EV prior 오차**임을 데이터로 확정했다
(엔진이 거의 모든 무브에서 과다 데미지 → 유닛 조기 사망 → faint desync → 100턴 표류). 근원은
make_char가 "공격 252+성격 / 방어 0 EV" prior라 방어형 유닛을 전부 프레일로 계산하는 것.
이 PR은 reference_gen5에 **세트(EV/nature/item/ability) 메커니즘**을 넣고 **표준 gen5 OU 세트를
시드**한다. 잔차가 역설계해준 확정분(Tentacruel 물리방어·Latios Choice Specs·Politoed 물리방어)
반영. 남은 어긋남은 전문가가 잔차표 보고 교정(역설계→사용자수정 루프).

## 대상
`modules/reference_gen5.py` — FIND/REPLACE 2건(SETS 시드 + set-aware make_char). 다른 파일
무변경. + 루프 도구 `run_resid.py`(이미 생성됨; 적용 후 돌려 잔차 확인).

## 설계 근거 (per-event 잔차로 검증됨 — 연쇄 없음)
표준세트 시드만으로 과다데미지의 대부분이 [0.85,1.0]로 닫힘(샌드박스 검증):
- Hydro Pump→Jirachi 0.68→0.93 · Earthquake→Garchomp 0.63→0.86 · Earthquake→Politoed
  0.72→0.98 · Scald→Hippowdon 0.65→0.95 · Body Slam→Latios 0.62→0.86.
- **잔차가 세트를 역설계**: Draco Meteor→Tentacruel(Choice Specs Latios 적용 시 R≈321 ≈ 관측
  327) → Tentacruel은 **SpD형이 아니라 물리방어형**. Latios Trick 사용 → **Choice 도구**.
  Metagross Explosion→Politoed 108(소량) → Politoed **물리방어형**.
- 남은 잔차(전문가 교정/후속): Rotom-Wash 세트(혼합 신호), Garchomp Ice Fang(Yache?),
  **Draco Meteor 2연타 -2 SpA**(무브효과 — 별도), **Hidden Power 숨김타입**(별도).

## FIND/REPLACE 1 — NATURES + 표준세트 시드 (SETS = {} 교체)

**FIND**:
```python
# 세트(특성/도구) — gen5는 RE/사용자수정으로 채울 자리. 시드 비움(잔차가 요구하면 채움).
SETS = {}
```

**REPLACE**:
```python
# 성격 보정 — {stat: ×}. +스탯 ×1.1, -스탯 ×0.9. 미기재 스탯은 1.0.
NATURES = {
    'Impish': {'df': 1.1, 'spa': 0.9}, 'Bold': {'df': 1.1, 'atk': 0.9},
    'Calm': {'spd': 1.1, 'atk': 0.9}, 'Careful': {'spd': 1.1, 'spa': 0.9},
    'Adamant': {'atk': 1.1, 'spa': 0.9}, 'Jolly': {'spe': 1.1, 'spa': 0.9},
    'Timid': {'spe': 1.1, 'atk': 0.9}, 'Modest': {'spa': 1.1, 'atk': 0.9},
    'Relaxed': {'df': 1.1, 'spe': 0.9}, 'Naive': {'spe': 1.1, 'spd': 0.9},
    'Naughty': {'atk': 1.1, 'spd': 0.9}, 'Hasty': {'spe': 1.1, 'df': 0.9},
    'Sassy': {'spd': 1.1, 'spe': 0.9}, 'Quiet': {'spa': 1.1, 'spe': 0.9},
}
# 세트(특성·도구·성격·EV) — gen5는 RE/전문가수정으로 채우는 자리. evs=(HP,Atk,Def,SpA,SpD,Spe).
# [확정]=잔차로 역설계 검증됨, [prior]=표준세트 추정(전문가 교정 대상). item/ability는
# apply_effects가 정적 스탯배율만 반영(Choice 등); 날씨특성(Drizzle/Sand Stream)은 미반영(후속).
SETS = {
    'Hippowdon':  {'nature': 'Impish',  'evs': (252, 0, 252, 0, 4, 0),   'item': None,           'ability': 'Sand Stream'},   # [확정] 물리벽
    'Ferrothorn': {'nature': 'Relaxed', 'evs': (252, 0, 252, 0, 4, 0),   'item': None,           'ability': 'Iron Barbs'},    # [prior]
    'Tentacruel': {'nature': 'Bold',    'evs': (252, 0, 252, 0, 4, 0),   'item': None,           'ability': 'Rain Dish'},     # [확정] 물리방어
    'Politoed':   {'nature': 'Bold',    'evs': (252, 0, 252, 0, 4, 0),   'item': None,           'ability': 'Drizzle'},       # [확정] 물리방어
    'Latios':     {'nature': 'Timid',   'evs': (0, 0, 0, 252, 4, 252),   'item': 'Choice Specs', 'ability': 'Levitate'},      # [확정] Trick=Choice
    'Jirachi':    {'nature': 'Careful', 'evs': (252, 0, 0, 0, 224, 32),  'item': None,           'ability': 'Serene Grace'},  # [prior] SpD Wish
    'Zapdos':     {'nature': 'Timid',   'evs': (0, 0, 0, 252, 4, 252),   'item': None,           'ability': 'Pressure'},      # [prior] 공격형
    'Rotom-Wash': {'nature': 'Modest',  'evs': (252, 0, 0, 252, 0, 4),   'item': None,           'ability': 'Levitate'},      # [prior] 혼합신호
    'Garchomp':   {'nature': 'Jolly',   'evs': (0, 252, 0, 0, 4, 252),   'item': 'Life Orb',     'ability': 'Sand Veil'},     # [prior]
    'Breloom':    {'nature': 'Jolly',   'evs': (0, 252, 0, 0, 4, 252),   'item': 'Life Orb',     'ability': 'Technician'},    # [prior]
    'Stoutland':  {'nature': 'Adamant', 'evs': (0, 252, 4, 0, 0, 252),   'item': 'Choice Band',  'ability': 'Sand Rush'},     # [prior]
    'Metagross':  {'nature': 'Adamant', 'evs': (0, 252, 0, 0, 4, 252),   'item': 'Life Orb',     'ability': 'Clear Body'},    # [prior]
}
```

## FIND/REPLACE 2 — set-aware make_char

**FIND** (현재 make_char 전체):
```python
def make_char(nick, species, set_data=None, hp_ev=252, atk_ev=252, def_ev=0,
              spa_ev=252, spd_ev=0, nat_atk=1.1):
    """종족값 + prior로 참가자 스탯 dict(spe 포함 — 풀배틀 턴순서용). 정적 효과 반영.
    set_data 미지정 시 SETS[species](gen5는 기본 비움)."""
    B = BASE[species]
    t1, t2 = SPECIES_TYPES.get(species, ('Normal', ''))
    char = {
        'id': nick, 'name': nick, '_species': species,
        'atk': stat(B[1], ev=atk_ev, nat=nat_atk), 'df': stat(B[2], ev=def_ev),
        'spa': stat(B[3], ev=spa_ev, nat=nat_atk), 'spd': stat(B[4], ev=spd_ev),
        'spe': stat(B[5], ev=0), 'maxhp': hp_stat(B[0], ev=hp_ev),
        'gimmicks': {'t1': t1, 't2': t2}, 'active_states': [],
    }
    return apply_effects(char, set_data if set_data is not None else SETS.get(species))
```

**REPLACE**:
```python
def make_char(nick, species, set_data=None, hp_ev=252, atk_ev=252, def_ev=0,
              spa_ev=252, spd_ev=0, nat_atk=1.1):
    """종족값 + 세트로 참가자 스탯 dict(spe 포함). 세트(evs+nature) 있으면 그걸로 전 스탯
    계산, 없으면 prior(공격 252+성격) 폴백 = 회귀 0. item/ability 정적배율은 apply_effects."""
    B = BASE[species]
    t1, t2 = SPECIES_TYPES.get(species, ('Normal', ''))
    sd = set_data if set_data is not None else SETS.get(species)
    if sd and sd.get('evs'):
        evs = sd['evs']                       # (HP,Atk,Def,SpA,SpD,Spe)
        nat = NATURES.get(sd.get('nature'), {})
        char = {
            'id': nick, 'name': nick, '_species': species,
            'atk': stat(B[1], ev=evs[1], nat=nat.get('atk', 1.0)),
            'df':  stat(B[2], ev=evs[2], nat=nat.get('df', 1.0)),
            'spa': stat(B[3], ev=evs[3], nat=nat.get('spa', 1.0)),
            'spd': stat(B[4], ev=evs[4], nat=nat.get('spd', 1.0)),
            'spe': stat(B[5], ev=evs[5], nat=nat.get('spe', 1.0)),
            'maxhp': hp_stat(B[0], ev=evs[0]),
            'gimmicks': {'t1': t1, 't2': t2}, 'active_states': [],
        }
    else:
        char = {
            'id': nick, 'name': nick, '_species': species,
            'atk': stat(B[1], ev=atk_ev, nat=nat_atk), 'df': stat(B[2], ev=def_ev),
            'spa': stat(B[3], ev=spa_ev, nat=nat_atk), 'spd': stat(B[4], ev=spd_ev),
            'spe': stat(B[5], ev=0), 'maxhp': hp_stat(B[0], ev=hp_ev),
            'gimmicks': {'t1': t1, 't2': t2}, 'active_states': [],
        }
    return apply_effects(char, sd)
```

## 검증
- **샌드박스(작성 시 수행)**: set-aware make_char로 per-event 잔차 재계산 → 위 §설계 근거의
  방어 잔차들이 [0.85,1.0]로 닫힘. Tentacruel 물리방어·Latios Specs가 Draco Meteor T12를
  관측에 맞춤(R≈321 vs 327).
- **적용자 검증**:
  1. `ast.parse(reference_gen5)` OK.
  2. `python run_resid.py` → flag 없는(정합) 줄이 적용 전보다 크게 늘었는지 확인. 남은
     UNDER(Hidden Power)·OVER(특정 세트)가 다음 타깃.
  3. `build_participants`/`prepare_run` 무변경 — maxhp는 관측 보정이라 세트 무관(자가검증 유지).

## 회귀 0
세트 없는 종족은 prior 폴백(현행 동일). reference_gen6·battle_setup·engine 무변경. set_data
명시 호출도 동일 경로. build_participants는 maxhp를 관측으로 덮으므로 세트 HP EV와 무관.

## 다음 (잔차 루프 계속)
`run_resid.py` 결과로 남은 타깃을 하나씩:
- **Hidden Power 숨김타입**: T1(vs Breloom SE)·T22(vs Jirachi)에서 타입 역산 → reference_gen5에
  해당 유닛 HP 타입 공급(작은 후속).
- **Draco Meteor/Leaf Storm -2 SpA**: 자기 디버프 무브효과 → 효과-스키마(ON_MOVE_USE) 또는
  무브 prop. run_resid.py는 이미 모델링(엔진엔 별도 PR).
- **남은 OVER 세트**(Rotom-Wash·Garchomp 등): 전문가가 잔차 보고 evs/item 교정.
세트가 정합하면 풀배틀 run(run_b4.py)에서 유닛이 제 타이밍에 죽어 **faint desync·100턴 표류가
해소**되는지 재확인.
```
