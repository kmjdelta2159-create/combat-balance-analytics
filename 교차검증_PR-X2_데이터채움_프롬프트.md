# 교차검증 PR-X2 — 결측 데이터 lazy 채움 (패스2: 풀런 → divergence)

> 패스1(PR-X1)이 held-out gen5 싱글(`Gen5OU-2026-newatmons-bantyranitar.html`)의 데이터 결측을
> 못박았다: **BASE 8·SETS 8·MOVES 19·TYPE 행 3(Flying/Dark/Bug)**. 이 PR은 그 *중립 데이터만*
> lazy 추가해(로드맵 §C) 엔진 풀런이 돌게 한다. 그 다음 run_xval 풀런의 divergence가 과적합
> 평결의 원천이다.
>
> **불변(절대 금지) — 이게 평결의 공정성을 지킨다**: `reference_gen5.EFFECTS`(효과-스키마)·
> 디스패처(`engine._act_effect_dispatch`/`_eff_*`)·`CONTACT_MOVES`·기존 `BASE`/`SPECIES_TYPES`/
> `MOVES`/`TYPE`/`SETS` 12종 **한 글자도 수정 금지**. Hail·Knock Off·Seismic Toss·frz 같은
> *메커니즘*은 여기서 채우지 않는다 — divergence가 ★로 드러내게 두고, 그게 (ㄴ)스키마-갭인지
> (한 줄로 표현 가능한지) 별도 판정한다. **이 PR은 순수 데이터 추가(additive)만.**

## 왜 중립 데이터만

held-out 전투의 divergence를 (ㄱ)데이터결측 / (ㄴ)스키마 표현불가 / (ㄷ)롤 노이즈로 가르려면,
*먼저 데이터(종족값·타입·무브위력·세트)를 채워 (ㄱ)을 제거*해야 (ㄴ)이 남는다. 메커니즘(EFFECTS)을
지금 손대면 (ㄴ)을 미리 가려 평결이 오염된다. 그래서 이 PR은 종족값·타입표·무브위력·세트만.

## 변경 1 — `reference_gen5.BASE`에 8종 추가 (additive, 웹검증된 gen5 종족값)

```python
    'Abomasnow': (90, 92, 75, 92, 85, 60),  'Clefable': (95, 70, 73, 95, 90, 60),
    'Gliscor':   (75, 95, 125, 45, 75, 95), 'Latias':   (80, 80, 90, 110, 130, 110),
    'Magnezone': (70, 70, 115, 130, 90, 60),'Reuniclus':(110, 65, 75, 125, 85, 30),
    'Scrafty':   (65, 90, 115, 45, 115, 58),'Skarmory': (65, 80, 140, 40, 70, 70),
```

## 변경 2 — `reference_gen5.SPECIES_TYPES`에 8종 추가

```python
    'Abomasnow': ('Grass', 'Ice'),   'Clefable': ('Normal', ''),
    'Gliscor':   ('Ground', 'Flying'),'Latias':  ('Dragon', 'Psychic'),
    'Magnezone': ('Electric', 'Steel'),'Reuniclus':('Psychic', ''),
    'Scrafty':   ('Dark', 'Fighting'),'Skarmory': ('Steel', 'Flying'),
```

## 변경 3 — `reference_gen5.MOVES`에 19무브 추가 (gen5 위력/분류/타입)

```python
    # 데미지 무브
    'Brave Bird': (120, 'phys', 'Flying'), 'Crunch': (80, 'phys', 'Dark'),
    'Ice Beam': (95, 'spec', 'Ice'), 'Ice Shard': (40, 'phys', 'Ice'),
    'Knock Off': (20, 'phys', 'Dark'), 'Outrage': (120, 'phys', 'Dragon'),
    'U-turn': (70, 'phys', 'Bug'),
    # status(데미지0 — 효과는 엔진/스키마; 여기선 위력0으로 충돌만 방지)
    'Amnesia': (0, 'status', None), 'Bulk Up': (0, 'status', None),
    'Calm Mind': (0, 'status', None), 'Magic Coat': (0, 'status', None),
    'Rest': (0, 'status', None), 'Roost': (0, 'status', None),
    'Soft-Boiled': (0, 'status', None), 'Spikes': (0, 'status', None),
    'Sunny Day': (0, 'status', None), 'Swords Dance': (0, 'status', None),
    'Whirlwind': (0, 'status', None),
    # ★(ㄴ) 후보 — Seismic Toss는 레벨고정 데미지(100). (power,cat,type) 스키마로 표현 불가.
    # 위력0 status로 두면 divergence가 Skarmory/Scrafty에 ★(엔진 0 vs 로그 고정)로 정확히 드러난다.
    'Seismic Toss': (0, 'status', None),
```

## 변경 4 — `reference_gen5.TYPE`에 공격타입 3행 추가 (Flying/Dark/Bug, gen5 표준)

```python
    'Flying': {'Grass': 2.0, 'Fighting': 2.0, 'Bug': 2.0,
               'Electric': 0.5, 'Rock': 0.5, 'Steel': 0.5},
    'Dark':   {'Psychic': 2.0, 'Ghost': 2.0, 'Fighting': 0.5, 'Dark': 0.5, 'Steel': 0.5},
    'Bug':    {'Grass': 2.0, 'Psychic': 2.0, 'Dark': 2.0, 'Fire': 0.5, 'Fighting': 0.5,
               'Poison': 0.5, 'Flying': 0.5, 'Ghost': 0.5, 'Steel': 0.5},
```

## 변경 5 — `reference_gen5.SETS`에 8종 추가 ([확정]=로그 관측, [prior]=표준세트)

로그가 특성/도구를 직접 보여준 건 [확정]: Abomasnow Snow Warning, Gliscor Poison Heal+Toxic Orb,
Magnezone Air Balloon, Scrafty Shed Skin+Leftovers, Skarmory Rocky Helmet, Clefable/Reuniclus
Leftovers. Magic Guard는 *Hail·SR 무피해 관측*에서 역설계(Clefable·Reuniclus 둘 다 우박 데미지無).

```python
    'Abomasnow': {'nature': 'Naive',  'evs': (0, 0, 0, 252, 4, 252), 'item': 'Life Orb',    'ability': 'Snow Warning'},  # [확정]특성 [prior]도구/EV
    'Clefable':  {'nature': 'Calm',   'evs': (252, 0, 4, 0, 252, 0), 'item': 'Leftovers',   'ability': 'Magic Guard'},   # [확정]도구 [역설계]MagicGuard(우박無)
    'Gliscor':   {'nature': 'Impish', 'evs': (252, 0, 184, 0, 0, 72),'item': 'Toxic Orb',   'ability': 'Poison Heal'},   # [확정]도구·특성
    'Latias':    {'nature': 'Timid',  'evs': (0, 0, 0, 252, 4, 252), 'item': 'Life Orb',    'ability': 'Levitate'},      # [prior] 미행동(즉사)
    'Magnezone': {'nature': 'Modest', 'evs': (252, 0, 0, 252, 4, 0), 'item': 'Air Balloon', 'ability': 'Magnet Pull'},   # [확정]도구
    'Reuniclus': {'nature': 'Bold',   'evs': (252, 0, 252, 4, 0, 0), 'item': 'Leftovers',   'ability': 'Magic Guard'},   # [확정]도구 [역설계]MagicGuard(우박無)
    'Scrafty':   {'nature': 'Careful','evs': (252, 0, 0, 0, 252, 4), 'item': 'Leftovers',   'ability': 'Shed Skin'},     # [확정]도구·특성
    'Skarmory':  {'nature': 'Impish', 'evs': (252, 0, 252, 0, 4, 0), 'item': 'Rocky Helmet','ability': 'Sturdy'},        # [확정]도구
```

## 변경 6 — Garchomp 세트 충돌: per-corpus 오버라이드 (★구조적 발견)

`SETS`는 *종으로 키잉*돼 한 종이 전투마다 다른 세트를 못 가진다. **골든 Garchomp = Rocky Helmet**
인데 **이 전투 Garchomp = Yache Berry**(로그 turn3 `-enditem Yache Berry` 확정). 전역 SETS를
바꾸면 골든이 깨진다(회귀0 위반). → `run_xval`에 **per-corpus SET 오버라이드** 인자를 더해 이
전투에서만 Garchomp 도구를 덮는다(전역 불변):

```python
# run_xval.py main() 안, run_and_diff 호출부에 코퍼스별 세트 패치 주입
XVAL_SET_OVERRIDE = {  # 이 전투 한정. 전역 SETS는 골든 소유로 불변.
    'Garchomp': {'nature': 'Jolly', 'evs': (0, 252, 0, 0, 4, 252), 'item': None, 'ability': 'Rough Skin'},
    # item=None: Yache는 turn3 Knock Off로 이미 소실 → 이후 Ice Shard(turn10)에 Rocky Helmet
    # 팬텀 반동이 안 생기게. Jirachi는 골든 세트(Leftovers·Serene Grace)가 이 전투와도 합치 → 무override.
}
```
`run_and_diff`/`setup_for_engine`/`prepare_run`이 `set_override` dict를 받아 `make_char(set_data=...)`
로 전달하도록 *얇은 패스스루*만 추가(기본 `None`이면 현행과 바이트 동일 → 골든 회귀0). 메커니즘
무관·전역 SETS 무변경.

> 이 스코핑(per-battle 세트)은 메커니즘 스키마 결함이 아니라 *데이터층 결함*이다. 평결 리포트에
> "데이터층은 전역-by-species가 아니라 per-corpus여야 한다"로 기록(로드맵 §C 보강 후보).

## 검증 (적용 후, 순서대로)

1. **회귀0(골든 불변)**: `python run_b4.py` 출력이 PR-X2 적용 전과 **완전 동일**(마지막 캡처 27,
   첫 divergence T1 Gengen 동일). 8종/19무브/3행/8세트 추가가 골든 12종 경로를 안 건드림.
2. **클린룸 타입곱 산수**(엔진 무관): 추가 TYPE 행으로 이 전투 핵심 매치업이 맞는지 —
   Garchomp Outrage(Dragon)→Latias(Dragon/Psy)=×2(SE✓), →Jirachi(Steel/Psy)=×0.5(resist✓);
   Abomasnow Ice Shard(Ice)→Garchomp(Dragon/Ground)=×4(SE✓); Scrafty Crunch(Dark)→Reuniclus(Psy)
   =×2(SE✓); Gliscor EQ(Ground)→Skarmory(Steel/Flying)=×0(immune✓); Gliscor U-turn(Bug)→
   Skarmory=×0.25(resist✓). 로그 플래그(`-supereffective`/`-resisted`/`-immune`)와 전부 일치.
3. **run_xval 풀런**: `python run_xval.py` → 이제 종족값 충분 → 퍼센트HP 풀런 → divergence 리포트
   출력. 마지막 캡처 턴이 로그(=29~30)에 닿는지, 크래시 없는지.
4. **출력을 붙여달라** — 그 divergence를 함께 (ㄱ)데이터/(ㄴ)스키마갭/(ㄷ)롤로 3분해한다.

## 평결 가이드 (출력 받은 뒤 함께 읽을 틀)

- **(ㄱ) 데이터/세트 노이즈**: 세트가 prior라서 나는 작은 hp차(EV/도구 미세). 무시·후속 정밀화.
- **(ㄴ) 스키마-갭 후보(미리 알려진 것)**: Hail 날씨칩(우리 EFFECTS는 sand만)·Knock Off 도구제거·
  Seismic Toss 레벨고정데미지·frz 동결게이트·Magic Guard 해저드면역·Spikes 다층·Sunny Day.
  각각이 *EFFECTS 한 줄(또는 조건 1개)*로 표현되면 **스키마 견고(합격)**, *언어 확장*을 요구하면
  **과적합 신호**. 예측: Hail=sand 복제(한 줄, 합격쪽)·Magic Guard=not_ability 조건(합격쪽)·
  Seismic Toss=새 효과타입(fixed_damage, 언어확장 — 표현력 보강 1건)·Knock Off=swap_item 친척
  (remove_item, 한 줄쪽).
- **(ㄷ) 롤**: ±15% 이내 hp차. 무시.

**평결 = (ㄴ) 중 "언어 확장 필요" 개수.** 0~1이면 스키마는 임의 gen5에 일반화된 것(2-가드 통과),
다수면 gen5-leftiez 모양으로 굳은 것. 이게 1차목표 천장의 직접 측정이다.
