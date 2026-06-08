# PR4 — 효과 레이어 시드 (특성/도구 정적 스탯 수정)

## 목적
PR3 잔차 리포트가 *데이터로 요구한 첫 메커니즘*을 인코딩한다 — Diggersby의 **Huge Power**
(공격 2배). 역설계→사용자수정 루프의 한 사이클 완주: 잔차가 지목 → 보정 인코딩 → 잔차 폐쇄.
이게 효과-스키마의 *첫 벽돌*이자 (나)의 특성/도구 질량 커버리지 시작이다.

범위(최소): **항시형 정적 스탯 배율** 특성/도구만(Huge Power·Eviolite·Choice류·Life Orb).
전투 중 *발동형* 특성/효과는 효과-스키마(후속). 모호하지 않은 보정만 세트에 할당.

## 대상
`modules/reference_gen6.py` — **1 FIND/REPLACE**(make_char 확장). 엔진·trace_replay·showdown_trace
무변경.

## FIND
```python
def make_char(nick, species, atk_ev=252, def_ev=0, spa_ev=252, spd_ev=0, nat_atk=1.1):
    """종족값 + 표준세트 prior로 참가자 스탯 dict. atk/spa는 공격형(252,+nat), def/spd는 prior."""
    B = BASE[species]
    t1, t2 = SPECIES_TYPES.get(species, ('Normal', ''))
    return {
        'id': nick, 'name': nick, '_species': species,
        'atk': stat(B[1], ev=atk_ev, nat=nat_atk), 'df': stat(B[2], ev=def_ev),
        'spa': stat(B[3], ev=spa_ev, nat=nat_atk), 'spd': stat(B[4], ev=spd_ev),
        'maxhp': hp_stat(B[0], ev=252), 'gimmicks': {'t1': t1, 't2': t2},
        'active_states': [],
    }
```

## REPLACE
```python
# 효과 레이어 시드 — 정적 스탯 수정 특성/도구(코퍼스 잔차가 데이터로 요구한 것만).
# 트리거형(전투 중 발동)은 효과-스키마(후속). 여기는 항시 적용 스탯 배율만.
ABILITIES = {'Huge Power': {'atk': 2.0}, 'Pure Power': {'atk': 2.0}}
ITEMS = {'Eviolite': {'df': 1.5, 'spd': 1.5}, 'Choice Band': {'atk': 1.5},
         'Choice Specs': {'spa': 1.5}, 'Life Orb': {'atk': 1.3, 'spa': 1.3}}
# 세트 데이터(역설계/사용자수정/prior로 채움) — species -> {ability,item}. 모호하지 않은 것만.
SETS = {'Diggersby': {'ability': 'Huge Power'}}


def apply_effects(char, set_data):
    """set_data({ability,item})의 정적 스탯 배율을 char 스탯에 적용(항시형)."""
    for key, table in (('ability', ABILITIES), ('item', ITEMS)):
        name = (set_data or {}).get(key)
        mods = table.get(name) if name else None
        if mods:
            for st_key, mult in mods.items():
                char[st_key] = math.floor(char[st_key] * mult)
    return char


def make_char(nick, species, atk_ev=252, def_ev=0, spa_ev=252, spd_ev=0, nat_atk=1.1,
              set_data=None):
    """종족값 + 표준세트 prior로 참가자 스탯 dict. atk/spa는 공격형(252,+nat), def/spd는 prior.
    set_data 미지정 시 SETS[species] 사용(없으면 효과 없음). 정적 특성/도구 배율 반영."""
    B = BASE[species]
    t1, t2 = SPECIES_TYPES.get(species, ('Normal', ''))
    char = {
        'id': nick, 'name': nick, '_species': species,
        'atk': stat(B[1], ev=atk_ev, nat=nat_atk), 'df': stat(B[2], ev=def_ev),
        'spa': stat(B[3], ev=spa_ev, nat=nat_atk), 'spd': stat(B[4], ev=spd_ev),
        'maxhp': hp_stat(B[0], ev=252), 'gimmicks': {'t1': t1, 't2': t2},
        'active_states': [],
    }
    return apply_effects(char, set_data if set_data is not None else SETS.get(species))
```

## 앵커 근거
- FIND = PR3의 `make_char` 정의 전체. `def make_char(nick, species, atk_ev=252` 1회만 등장
  (Grep count==1). REPLACE는 그 앞에 ABILITIES/ITEMS/SETS/apply_effects를 삽입하고 make_char에
  `set_data` 파라미터 + 효과 적용을 추가.
- `residual_report`는 `make_char(...)`를 set_data 없이 호출 → SETS[species] 자동 적용(Diggersby만).
  기존 호출부 무변경(set_data 기본 None → SETS 폴백).

## 검증 (실엔진 경유·작성 시 수행)
`ast.parse` OK. Kecleon전 `residual_report(...def_ev_priors={'Reuniclus':252,'Chansey':252})`:
- **T8 Diggersby U-turn → Reuniclus**: 이전 식 (95,112) residual → **Huge Power(×2) 적용 후
  식 (188,222), 관측 192 → match.** 잔차 폐쇄.
- 요약: **match 4 / ko_lowerbound 2 / residual 3** (이전 3/2/4). 다른 이벤트 무변동(회귀 0 —
  SETS에 Diggersby만 할당).

적용자 검증: 앵커 Grep count==1 → 적용 → `ast.parse` → 리포트 재현(Diggersby match, 4/2/3).

## 정직한 경계 — EV vs 도구 모호성
- **Eviolite를 Chansey에 *할당하지 않았다*.** PR3에서 Chansey Focus Blast는 252 SpD prior로
  이미 match라, Eviolite를 더하면 과보정(방어↑→데미지↓→관측이 밴드 위로). 단일 전투에서
  EV와 도구는 한 식에 얽혀 분리 불가(under-determined) → *모호한 보정은 안 한다.* ITEMS에
  Eviolite를 *정의*만 해두고 할당은 보류(공동 EV 추론/사용자 확인 후).
- 남은 잔차 3(Alakazam·Reuniclus ×2)은 방어 EV/성격 prior 차이 — 메커니즘 아님. 역산 v1
  (공동 EV) 또는 사용자 수정으로 닫힘.
- **항시형만**: Huge Power·Eviolite·Choice·Life Orb은 항시 스탯 배율이라 레퍼런스 레이어에서
  처리. 발동형(위협 진입·잔비 날씨·기합의띠 생존 등)은 엔진 효과-스키마가 필요(후속).

## 다음
- 효과-스키마 본격화(발동형 특성/도구 — 트리거×조건×효과) 또는 역산 v1(공동 EV로 prior
  의존 축소 → 남은 3 잔차 폐쇄·모호성 해소). 코퍼스 확장(다른 전투/세대)도 스키마 일반성
  점검에 필요.
