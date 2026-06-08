# PR-D1 — 타입/특성 잔차: Hidden Power 숨김타입 + Levitate 타입면역 (reference_gen5 + battle_setup, 엔진 무변경)

## 목적
풀배틀 resync(C2) 후 라운드별로 격리된 잔차 중 **타입/특성 버킷**을 닫는다. 두 사건:

1. **Hidden Power 숨김타입** — 트레이스는 무브를 "Hidden Power"로만 알려주고 *타입*을 안 준다.
   reference_gen5.MOVES의 `Hidden Power` 타입은 `None`이라 엔진/진단이 상성을 ×1로 처리 →
   과소데미지. per-event 진단(run_resid):
   - T1 Rotom-Wash HP→Breloom(Grass/Fighting): obs 238 / R(타입×1)=128 → obs/R **1.86**
   - T22 Latios HP→Jirachi(Steel/Psychic): obs 118 / R(타입×1)=100 → obs/R **1.18**
2. **Levitate 타입면역** — T16 Garchomp Earthquake→Latios에서 엔진이 ≈−253을 가했으나,
   Latios는 Levitate라 Ground ×0 면역. 로그상 Latios는 0 데미지. 엔진 타입표가 특성 면역을
   모름 → 풀배틀에서 단일 최대 과다데미지(T16).

이 PR은 **엔진을 건드리지 않는다.** 엔진의 `_move_type_multiplier`는 이미
`game_config["type_columns"]`를 순회하며 `target["gimmicks"][col]`을 `type_table`에 대조하고
`dt is not None` 가드가 있다. 따라서 (a) HP 타입은 *트레이스 행동표 생성 시점*에 종족별
hp_type로 해석해 무브 dict에 박고, (b) 특성 면역은 *의사-타입 컬럼 t3* + type_table 행에 ×0을
넣어 **순수 데이터로** 처리한다. 새 인프라 0.

## 검증 제약 / 근거 (클린룸 검증 완료)
reference_gen5·battle_setup·showdown_trace는 작아서 샌드박스 정상. 아래 변경분을 인라인
재현해 골든 로그(`Gen5OU-2015-05-11-reymedy-leftiez.html`)로 확인했다:

- **T1 Rotom-Wash HP Fire ×2** → R 256, obs 238 → **obs/R 0.93 닫힘**(정상 데미지 롤).
- **T22 Latios HP Fire ×2** → 타입은 ×2로 확정. 남은 obs/R 0.59는 *Trick으로 넘긴 Choice
  Specs 미반영*(버킷#3 item-swap) — **타입 자체는 맞고**, 잔차가 "숨김타입 미상"에서
  "아이템 상태 미모델"로 정확히 재귀속된다.
- **Levitate 면역 산식 7케이스 전부 PASS**: Ground vs {Latios,Rotom-Wash}(Levitate)=×0,
  비-면역특성(Hippowdon Sand Stream)=Ground ×1, 면역無 Steel(Jirachi)=Ground ×2,
  비-Ground(Dragon) vs Levitate=영향無 ×2, Electric vs Latios=×0.5(Dragon이 전기반감,
  Levitate 무관), Fire vs Breloom(Grass)=×2.
- **회귀0**: 비-Ground 공격은 전 종족에서 신/구 type_mult 동일(t3 부재 시 None-guard로 스킵).

**중요 발견**: HP를 'Fire'로 해석해도 `TYPE`에 **Fire 공격 행이 없으면**(lazy 시드라 Fire
무브가 없었음) 상성이 ×1로 무력화된다. 따라서 **Fire 행을 함께 추가**해야 한다. 클린룸이
이를 잡았다.

엔진 전체 실행이 필요한 T16 풀배틀 닫힘 확인은 앱사이드(run_b4). 타입표 산식 자체는 위에서
엔진 함수(`_move_type_multiplier`) 재현으로 검증됨.

## 대상
`modules/reference_gen5.py`(4건) + `modules/battle_setup.py`(1건) + `run_resid.py`(1건, 진단 도구).
엔진·turn_manager 무변경.

---

## FIND/REPLACE — modules/reference_gen5.py

### R1 — TYPE 표에 Fire 공격 행 추가 (HP Fire가 도입하는 새 공격타입)
**FIND**:
```python
    'Electric': {'Water': 2.0, 'Flying': 2.0, 'Ground': 0.0, 'Grass': 0.5,
                 'Electric': 0.5, 'Dragon': 0.5},
}
```
**REPLACE**:
```python
    'Electric': {'Water': 2.0, 'Flying': 2.0, 'Ground': 0.0, 'Grass': 0.5,
                 'Electric': 0.5, 'Dragon': 0.5},
    # Hidden Power Fire(Rotom-Wash·Latios)가 도입 — lazy 표에 없던 공격타입. gen5 표준 Fire 행.
    'Fire': {'Grass': 2.0, 'Ice': 2.0, 'Bug': 2.0, 'Steel': 2.0,
             'Fire': 0.5, 'Water': 0.5, 'Rock': 0.5, 'Dragon': 0.5},
}
```

### R2 — 특성 타입면역 테이블 (의사-타입 단일 출처)
ABILITIES 정의 바로 위(또는 EFFECTS 근처)에 추가. Levitate만 시드 — 코퍼스가 요구한 분만
(성급한 추상화 금지). **순수 타입무효화 특성만** 여기 둔다. Water Absorb/Volt Absorb/Flash
Fire처럼 *흡수회복·부스트*를 동반하는 특성은 ×0만으론 틀리므로 효과-스키마 몫(여기 넣지 말 것).

**FIND**:
```python
# 효과 레이어 시드 — 항시형 정적 스탯 배율(코퍼스 잔차가 요구하면 채움). 트리거형은 EFFECTS.
ABILITIES = {'Huge Power': {'atk': 2.0}, 'Pure Power': {'atk': 2.0}}
```
**REPLACE**:
```python
# 특성 기반 타입면역(순수 ×0만) — {특성: 무효화할 공격타입}. build_game_config가 type_table에
# 의사-타입 항목으로 주입하고, make_char가 보유 종족 gimmicks에 t3=특성명을 박는다. 데이터-only.
# 주의: Water Absorb/Volt Absorb/Flash Fire 등 흡수회복·부스트형은 ×0이 틀리므로 효과-스키마 몫.
ABILITY_TYPE_IMMUNITY = {'Levitate': 'Ground'}

# 효과 레이어 시드 — 항시형 정적 스탯 배율(코퍼스 잔차가 요구하면 채움). 트리거형은 EFFECTS.
ABILITIES = {'Huge Power': {'atk': 2.0}, 'Pure Power': {'atk': 2.0}}
```

### R3 — SETS에 hp_type 부여 (Hidden Power 보유 종족)
Hidden Power 숨김타입은 *종족 빌드 속성*이라 SET에 둔다. Rotom-Wash·Latios 둘 다 HP Fire
([prior]=표준, 잔차로 ×2 일관 확인). Latios의 ability는 이미 'Levitate'.

**FIND**:
```python
    'Latios':     {'nature': 'Timid',   'evs': (0, 0, 0, 252, 4, 252),   'item': 'Choice Specs', 'ability': 'Levitate'},      # [확정] Trick=Choice
```
**REPLACE**:
```python
    'Latios':     {'nature': 'Timid',   'evs': (0, 0, 0, 252, 4, 252),   'item': 'Choice Specs', 'ability': 'Levitate', 'hp_type': 'Fire'},  # [확정] Trick=Choice / HP Fire[prior,잔차×2]
```

**FIND**:
```python
    'Rotom-Wash': {'nature': 'Modest',  'evs': (252, 0, 0, 252, 0, 4),   'item': None,           'ability': 'Levitate'},      # [prior] 혼합신호
```
**REPLACE**:
```python
    'Rotom-Wash': {'nature': 'Modest',  'evs': (252, 0, 0, 252, 0, 4),   'item': None,           'ability': 'Levitate', 'hp_type': 'Fire'},  # [prior] HP Fire[표준,잔차×2 T1 0.93]
```

### R4 — make_char: 면역특성이면 gimmicks에 의사-타입 t3 부여
make_char의 두 char dict 생성부 모두 `'gimmicks': {'t1': t1, 't2': t2}` 형태다. 둘 다 t3 주입.
sd(set_data)는 함수 안에서 이미 `sd = set_data if ... else SETS.get(species)`로 잡혀 있다.

**FIND**:
```python
            'spe': stat(B[5], ev=evs[5], nat=nat.get('spe', 1.0)),
            'maxhp': hp_stat(B[0], ev=evs[0]),
            'gimmicks': {'t1': t1, 't2': t2}, 'active_states': [],
        }
```
**REPLACE**:
```python
            'spe': stat(B[5], ev=evs[5], nat=nat.get('spe', 1.0)),
            'maxhp': hp_stat(B[0], ev=evs[0]),
            'gimmicks': _gimmicks_with_immunity(t1, t2, sd), 'active_states': [],
        }
```

**FIND**:
```python
            'spe': stat(B[5], ev=0), 'maxhp': hp_stat(B[0], ev=hp_ev),
            'gimmicks': {'t1': t1, 't2': t2}, 'active_states': [],
        }
    return apply_effects(char, sd)
```
**REPLACE**:
```python
            'spe': stat(B[5], ev=0), 'maxhp': hp_stat(B[0], ev=hp_ev),
            'gimmicks': _gimmicks_with_immunity(t1, t2, sd), 'active_states': [],
        }
    return apply_effects(char, sd)
```

그리고 make_char **위에** 헬퍼 추가(예: `def stat(...)` 위나 make_char 직전):
```python
def _gimmicks_with_immunity(t1, t2, set_data):
    """타입 컬럼 t1/t2 + 면역특성이면 의사-타입 t3(=특성명). 엔진 _move_type_multiplier가
    type_columns로 t3까지 순회해 type_table[공격타입][특성명]=0.0과 만나 ×0 면역을 낸다."""
    g = {'t1': t1, 't2': t2}
    abil = (set_data or {}).get('ability')
    if abil in ABILITY_TYPE_IMMUNITY:
        g['t3'] = abil
    return g
```

### R5 — build_game_config: type_columns에 t3 + 면역 의사-타입을 type_table에 주입
**FIND**:
```python
def build_game_config():
    """엔진이 gen5 데미지를 독립 계산하도록 — 카테고리·타입표·STAB·크리배율."""
    return {
        'categories': {'phys': {'offense': 'atk', 'defense': 'df'},
                       'spec': {'offense': 'spa', 'defense': 'spd'}},
        'type_table': {atk: dict(row) for atk, row in TYPE.items()},
        'type_columns': ['t1', 't2'], 'stab_factor': 1.5, 'crit_mult': CRIT_MULT,
    }
```
**REPLACE**:
```python
def build_game_config():
    """엔진이 gen5 데미지를 독립 계산하도록 — 카테고리·타입표·STAB·크리배율.
    type_table에 특성 타입면역을 의사-타입 항목으로 주입(예: type_table['Ground']['Levitate']=0.0),
    type_columns에 t3(면역특성 의사-타입)를 더해 엔진이 데이터-only로 ×0을 낸다."""
    type_table = {atk: dict(row) for atk, row in TYPE.items()}
    for abil, imm_type in ABILITY_TYPE_IMMUNITY.items():
        type_table.setdefault(imm_type, {})[abil] = 0.0
    return {
        'categories': {'phys': {'offense': 'atk', 'defense': 'df'},
                       'spec': {'offense': 'spa', 'defense': 'spd'}},
        'type_table': type_table,
        'type_columns': ['t1', 't2', 't3'], 'stab_factor': 1.5, 'crit_mult': CRIT_MULT,
    }
```

---

## FIND/REPLACE — modules/battle_setup.py

### B1 — build_trace_actions: Hidden Power 타입을 공격자 세트 hp_type로 해석
무브 dict 생성 시 type이 None인 Hidden Power면 행위자 종족의 set hp_type로 채운다. 회귀0:
hp_type 미정의 종족이나 비-HP 무브는 그대로 None/기존값.

**FIND**:
```python
            md = ref.MOVES.get(e["move"])
            mv = {"name": e["move"], "power": (md[0] if md else 0),
                  "category": (md[1] if md else None), "type": (md[2] if md else None)}
            move_actions[(tn, e["actor"])] = {"move": mv, "target": tgt}
```
**REPLACE**:
```python
            md = ref.MOVES.get(e["move"])
            mtype = md[2] if md else None
            if e["move"] == "Hidden Power" and mtype is None:   # 숨김타입: 공격자 세트 hp_type
                asp = trace["nick2species"].get(e["actor"])
                mtype = (ref.SETS.get(asp) or {}).get("hp_type")
            mv = {"name": e["move"], "power": (md[0] if md else 0),
                  "category": (md[1] if md else None), "type": mtype}
            move_actions[(tn, e["actor"])] = {"move": mv, "target": tgt}
```

---

## FIND/REPLACE — run_resid.py (진단 도구: HP 타입 해석해 닫힘 확인)
도구가 Hidden Power를 종족 hp_type로 해석하도록 갱신해, 재run 시 T1이 닫히고 T22가
"HiddenPower(type?)" 대신 OVER(=Specs/Trick 미모델, 버킷#3)로 재귀속됨을 본다.

**FIND**:
```python
        asp = e.get("species")
        mv = e.get("move")
        md = r5.MOVES.get(mv)
        drop = SELF_DROP.get(mv)
        if md and md[0] > 0:
            pw, cat, mtype = md
```
**REPLACE**:
```python
        asp = e.get("species")
        mv = e.get("move")
        md = r5.MOVES.get(mv)
        drop = SELF_DROP.get(mv)
        if md and md[0] > 0:
            pw, cat, mtype = md
            if mv == "Hidden Power" and mtype is None:           # 숨김타입: 공격자 세트 hp_type
                mtype = (r5.SETS.get(asp) or {}).get("hp_type")
```

---

## 검증 (적용 후)
1. **샌드박스/앱 공통 — per-event 닫힘**: 루트에서 `python run_resid.py`.
   - 기대: **T1 Rotom-Wash Hidden Power → Breloom: eff 2.0, obs/R ≈ 0.93, flag 없음**(닫힘).
   - T22 Latios Hidden Power → Jirachi: eff 2.0로 표시되며 flag가 `HiddenPower(type?)` →
     `OVER x0.59`로 바뀜(타입 확정 + 잔차가 item-swap 버킷#3로 재귀속). **이게 정상** — 타입은
     맞고, 남은 건 Trick으로 넘긴 Choice Specs 미모델이다.
   - 그 외 줄 회귀0(이전과 동일).
2. **앱사이드 — 풀배틀 T16 닫힘**: 루트에서 `python run_b4.py`(엔진 전체 필요).
   - 기대: **T16 Garchomp Earthquake → Latios**가 엔진 ≈−253(★) → **0(또는 ±10 이내)** 로
     닫힘(Levitate ×0). 출력 전체를 붙여주면 다음 잔차(첫 실질 divergence)를 함께 읽는다.
   - 엔진 마지막 캡처 턴 = 27 유지(desync 재발 없음) 확인.
3. **회귀0 확인**: 비-Ground 공격은 전 종족 type_mult 불변(클린룸 확인). Levitate 미보유
   유닛은 gimmicks에 t3 없음 → 기존 산식과 동일.

## 적용 메모
- 엔진·turn_manager 무변경 → engine.py truncation 무관. 변경은 전부 reference_gen5(데이터·
  build_game_config)·battle_setup(행동표 해석)·run_resid(도구).
- **확장 경로**: 다른 순수 타입무효화 특성(Sap Sipper/Grass, Storm Drain/Water의 면역 측면 등)은
  `ABILITY_TYPE_IMMUNITY`에 한 줄. 흡수회복·부스트 동반 특성(Water Absorb·Volt Absorb·Flash
  Fire)은 ×0이 틀리므로 여기 넣지 말고 효과-스키마(ON_HIT heal/boost)로 — 코퍼스가 요구할 때.
- **HP 타입은 [prior]**: Fire는 gen5 표준 + 잔차 ×2 일관 확인이지 데이터 단독 유일해는 아니다
  (Ice/Poison/Psychic도 Breloom엔 ×2). 전문가 교정 여지 있음(SETS hp_type 한 줄).
