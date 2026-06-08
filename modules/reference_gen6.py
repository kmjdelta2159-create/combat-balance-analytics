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
