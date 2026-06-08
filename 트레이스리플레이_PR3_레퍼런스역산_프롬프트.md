# PR3 — gen6 레퍼런스 + battle_spec + 잔차 리포트 (표준 v0)

## 목적
A 하니스의 3조각, 그리고 **"복제가 숫자가 되는" 첫 지점.** 쇼다운 트레이스를 *엔진이 독립
계산*할 수 있는 battle_spec(gen6 종족값→스탯·무브·데미지식·타입표)으로 바꾸고, trace_replay
(PR2)로 깨끗한 직격 이벤트를 엔진 경유 계산해 관측과 diff한다. 식이 못 맞히는 잔차 =
*수정 타깃*(미모델 특성/도구/세트)으로 리포트 → 역설계→사용자수정 루프의 작업 큐.

표준 v0 범위(사용자 결정): gen6 식 + 종족값 레퍼런스 + **트레이스 부스트 추적** + **KO 인지
(하한)** + 공격자 스탯은 종족값·표준세트 prior로 계산, **방어자 EV는 표준세트 prior**, 잔차
리포트. 공동 EV 추론은 후속.

## 대상
**신규 파일** `modules/reference_gen6.py`. 엔진·trace_replay·showdown_trace **무변경**(import만).

## 핵심 설계 (de-risk로 확정된 교란 처리)
- **KO 상한 절단**: KO 이벤트의 관측 데미지는 잔여 HP에 잘림(과잉살상) → *하한*으로 판정
  (관측 ≤ 식 max면 정합). 실측: T2 Sucker Punch 식 ~450, 관측 213(Delphox 잔여) → ko_lowerbound.
- **랭크 부스트 추적**: 트레이스 boost 이벤트를 누적해 공격자 유효 스탯에 stage_mult 적용.
  실측: Power-Up Punch +1 → T11/T12가 ×1.5. (없으면 T6 104 vs T12 153 불일치.)
- **종족값 자가검증**: 관측 max HP가 종족값+EV를 확인(Reuniclus 424·Chansey 704 = 252 HP EV).
- **gen6 식은 엔진 formula 언어로**: base=`floor(floor(42*power*offense/defense)/50)+2`,
  ELEMENT_MULT가 STAB×타입, CRIT가 ×1.5. 엔진 독립계산이 standalone과 일치 확인됨.

## 생성할 파일 내용 (전체 — 바이트 그대로)

```python
"""
gen6 포켓몬 레퍼런스 (lazy 시드) + battle_spec 빌더 + 잔차 리포트.

트레이스-리플레이 PR3. 쇼다운 트레이스를 *엔진이 독립 계산*할 수 있는 battle_spec(참가자
스탯·무브·gen6 데미지식·타입표)으로 바꾸고, trace_replay(PR2)로 깨끗한 직격 이벤트를
엔진 경유 계산해 관측과 diff한다. KO는 하한, 랭크 부스트는 트레이스에서 추적, 방어자
EV는 표준세트 prior. 식이 못 맞히는 잔차 = *수정 타깃*(미모델 특성/도구/세트)으로 리포트.

"전체 도감"이 아니라 코퍼스 등장분만(lazy). 종족값은 관측 max HP로 자가검증됨.
"""
import math
from modules.trace_replay import TraceStochasticity, make_event_ctx, compute_event_damage

L = 100  # 표준 대전 레벨

# 종족값 (HP,Atk,Def,SpA,SpD,Spe) — 등장분만. 관측 max HP로 검증(Reuniclus424·Chansey704=252EV).
BASE = {
    'Kecleon': (60, 90, 70, 60, 120, 40), 'Delphox': (75, 69, 72, 114, 100, 104),
    'Alakazam': (55, 50, 45, 135, 95, 120), 'Reuniclus': (110, 65, 75, 125, 85, 30),
    'Chansey': (250, 5, 5, 35, 105, 50), 'Diggersby': (85, 56, 77, 50, 77, 78),
}
# 무브 (power, category, type)
MOVES = {
    'Fake Out': (40, 'phys', 'Normal'), 'Sucker Punch': (80, 'phys', 'Dark'),
    'Shadow Sneak': (40, 'phys', 'Ghost'), 'Power-Up Punch': (40, 'phys', 'Fighting'),
    'U-turn': (70, 'phys', 'Bug'), 'Focus Blast': (120, 'spec', 'Fighting'),
}
SPECIES_TYPES = {
    'Kecleon': ('Normal', ''), 'Delphox': ('Fire', 'Psychic'), 'Alakazam': ('Psychic', ''),
    'Reuniclus': ('Psychic', ''), 'Chansey': ('Normal', ''), 'Diggersby': ('Normal', 'Ground'),
}
# 타입표(등장 공격타입 × 방어타입) — gen6. 미기재=1.0.
TYPE6 = {
    'Normal': {'Ghost': 0.0}, 'Dark': {'Psychic': 2.0}, 'Ghost': {'Psychic': 2.0, 'Normal': 0.0},
    'Fighting': {'Psychic': 0.5, 'Normal': 2.0, 'Steel': 2.0, 'Dark': 2.0},
    'Bug': {'Psychic': 2.0, 'Dark': 2.0},
}
# 엔진 formula 언어로 표현한 gen6 데미지 base (L=100). ELEMENT_MULT가 STAB×타입, CRIT가 ×1.5.
DAMAGE_FORMULA = "math.floor(math.floor(42 * move_power * offense / defense) / 50) + 2"
CRIT_MULT = 1.5  # gen6


def stat(base, iv=31, ev=0, nat=1.0):
    return math.floor((math.floor((2 * base + iv + ev // 4) * L / 100) + 5) * nat)

def hp_stat(base, iv=31, ev=0):
    return (2 * base + iv + ev // 4) + L + 10

def stage_mult(s):
    return (2 + s) / 2 if s >= 0 else 2 / (2 - s)


def build_game_config():
    """엔진이 gen6 데미지를 독립 계산하도록 — 카테고리·타입표·STAB."""
    type_cols = ['t1', 't2']
    table = {atk: dict(row) for atk, row in TYPE6.items()}
    return {
        'categories': {'phys': {'offense': 'atk', 'defense': 'df'},
                       'spec': {'offense': 'spa', 'defense': 'spd'}},
        'type_table': table, 'type_columns': type_cols, 'stab_factor': 1.5,
    }


def _protean_users(trace):
    out = set()
    for e in trace['events']:
        if e.get('action') == 'start' and 'Protean' in (e.get('what') or ''):
            out.add(e['actor'])
    return out


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


def enriched_clean_events(trace):
    """깨끗한 직격(비날씨·비자해) + 공격자 atk 랭크 + KO 플래그. 부스트는 누적 추적."""
    atk_stage = {}
    out = []
    for e in trace['events']:
        if e.get('action') != 'move':
            continue
        a = e['actor']
        if not (e.get('context') or {}).get('weather'):
            for h in e['hits']:
                if h['who'] == a or h.get('delta') is None:
                    continue
                eff = (2.0 if 'supereffective' in e['flags'] else
                       0.5 if 'resisted' in e['flags'] else
                       0.0 if 'immune' in e['flags'] else 1.0)
                out.append({'turn': e['turn'], 'attacker': a, 'attacker_species': e['species'],
                            'move': e['move'], 'defender': h['who'],
                            'defender_species': trace['nick2species'].get(h['who']),
                            'observed': -h['delta'], 'crit': 'crit' in e['flags'], 'eff': eff,
                            'atk_stage': atk_stage.get(a, 0), 'ko': h['who'] in e['faints']})
        for b in e['boosts']:
            if b['stat'] == 'atk':
                atk_stage[b['who']] = atk_stage.get(b['who'], 0) + b['stages']
    return out


def residual_report(registry, trace, def_ev_priors=None, tol_low=0.85):
    """이벤트별 엔진 경유 계산 vs 관측. 분류: match / ko_lowerbound / residual(수정 타깃)."""
    def_ev_priors = def_ev_priors or {}
    protean = _protean_users(trace)
    gc = build_game_config()
    rows = []
    for ce in enriched_clean_events(trace):
        asp, dsp = ce['attacker_species'], ce['defender_species']
        if asp not in BASE or dsp not in BASE or ce['move'] not in MOVES or ce['eff'] == 0.0:
            continue
        pw, cat, mtype = MOVES[ce['move']]
        atk = make_char(ce['attacker'], asp, def_ev=def_ev_priors.get(asp, 0))
        dfd = make_char(ce['defender'], dsp, def_ev=def_ev_priors.get(dsp, 0),
                        spd_ev=def_ev_priors.get(dsp, 0))
        if ce['attacker'] in protean:
            atk['current_type'] = mtype
        okey = 'atk' if cat == 'phys' else 'spa'
        atk[okey] = math.floor(atk[okey] * stage_mult(ce['atk_stage']))
        stoch = TraceStochasticity(crit_mult=CRIT_MULT)
        ctx = make_event_ctx(atk, dfd, {'name': ce['move'], 'power': pw, 'type': mtype,
                                        'category': cat},
                             ['atk', 'df', 'spa', 'spd'], gc, DAMAGE_FORMULA, stoch)
        R = compute_event_damage(registry, ctx, crit=ce['crit'])
        lo = int(tol_low * R)
        obs = ce['observed']
        if ce['ko']:
            verdict = 'ko_lowerbound' if obs <= R else 'residual'
        else:
            verdict = 'match' if lo <= obs <= R else 'residual'
        rows.append({'turn': ce['turn'], 'attacker': asp, 'stage': ce['atk_stage'],
                     'move': ce['move'], 'defender': dsp, 'observed': obs,
                     'band': (lo, R), 'ko': ce['ko'], 'verdict': verdict})
    return rows
```

## 검증 (실엔진 경유·작성 시 수행 — 적용자 재현용)
`ast.parse` OK. Kecleon전(`OUMonotype-2014-...`) `residual_report(DEFAULT_ACTION_REGISTRY, t,
def_ev_priors={'Reuniclus':252,'Chansey':252})`:

```
T1  Kecleon    Fake Out      ->Delphox   관측 79  식(74,88)      -> match
T2  Kecleon    Sucker Punch  ->Delphox   관측 213 식(443,522) KO -> ko_lowerbound
T3  Kecleon    Shadow Sneak  ->Alakazam  관측 168 식(211,249)    -> residual
T6  Kecleon    Shadow Sneak  ->Reuniclus 관측 104 식(109,129)    -> residual
T8  Diggersby  U-turn        ->Reuniclus 관측 192 식(95,112)     -> residual
T8  Reuniclus  Focus Blast   ->Chansey   관측 238 식(214,252)    -> match
T10 Kecleon    Power-Up Punch->Reuniclus 관측 27  식(27,32)      -> match
T11 Kecleon +1 Sucker Punch  ->Reuniclus 관측 296 식(318,375)    -> residual
T12 Kecleon +1 Shadow Sneak  ->Reuniclus 관측 153 식(160,189) KO -> ko_lowerbound
```
요약: **match 3 / ko_lowerbound 2 / residual 4.** 종족값·식·부스트·KO 처리가 작동.

적용자 검증: 파일 생성 → `ast.parse` → 위 리포트 재현(엔진 import + 9이벤트). 기존 무변경.

## 잔차 = 수정 타깃 (역설계→수정 루프의 산출)
잔차 4건은 노이즈가 아니라 *구체적 수정 신호*다 — 이게 PR3의 진짜 가치다:
- **T8 U-turn(Diggersby) 관측 192 ≫ 식 (95,112)** → **Huge Power**(공격 2배) 미모델. 잔차가
  미모델 *특성*을 정확히 지목.
- **T3 Alakazam·T6/T11 Reuniclus 소폭 초과** → 방어자 Def EV/성격 prior 차이(세트 추정).
- (참고) Chansey Focus Blast는 252 SpD prior로 match — prior가 Eviolite 효과를 흡수.

이 잔차들이 다음 단계의 *작업 큐*다: 특성/도구를 효과-스키마에 인코딩하거나(시스템 RE/
엔지니어), 세트를 사용자가 수정. 슬라이더가 설계대로 — RE가 5/9를 닫고, 4건의 *정확한* 수정
지점을 남긴다.

## 회귀 0 / 정직한 경계
- 신규 파일 1개, 기존 무변경.
- **단일 전투·표준세트 prior라 under-determined**: 공격/방어 EV를 한 식에서 분리 못 함 →
  prior 의존. 공동 EV 추론(여러 이벤트 연립)은 후속.
- **gen6 전용**: gen5 등은 crit_mult·타입표·식 상수가 달라 별도 레퍼런스(세대 고정).
- 종족값/무브는 등장분만(lazy). 코퍼스 확장 시 BASE/MOVES/TYPE6에 등장분 추가.

## 다음
잔차 큐가 효과-스키마(특성/도구) 방향을 데이터로 가리킨다 — Huge Power·Eviolite류가 첫
인코딩 후보. 또는 공동 EV 추론으로 prior 의존 축소(역산 v1).
