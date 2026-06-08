find_1 = """# 세트(특성/도구) — gen5는 RE/사용자수정으로 채울 자리. 시드 비움(잔차가 요구하면 채움).
SETS = {}"""

replace_1 = """# 성격 보정 — {stat: ×}. +스탯 ×1.1, -스탯 ×0.9. 미기재 스탯은 1.0.
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
}"""

find_2 = """def make_char(nick, species, set_data=None, hp_ev=252, atk_ev=252, def_ev=0,
              spa_ev=252, spd_ev=0, nat_atk=1.1):
    \"\"\"종족값 + prior로 참가자 스탯 dict(spe 포함 — 풀배틀 턴순서용). 정적 효과 반영.
    set_data 미지정 시 SETS[species](gen5는 기본 비움).\"\"\"
    B = BASE[species]
    t1, t2 = SPECIES_TYPES.get(species, ('Normal', ''))
    char = {
        'id': nick, 'name': nick, '_species': species,
        'atk': stat(B[1], ev=atk_ev, nat=nat_atk), 'df': stat(B[2], ev=def_ev),
        'spa': stat(B[3], ev=spa_ev, nat=nat_atk), 'spd': stat(B[4], ev=spd_ev),
        'spe': stat(B[5], ev=0), 'maxhp': hp_stat(B[0], ev=hp_ev),
        'gimmicks': {'t1': t1, 't2': t2}, 'active_states': [],
    }
    return apply_effects(char, set_data if set_data is not None else SETS.get(species))"""

replace_2 = """def make_char(nick, species, set_data=None, hp_ev=252, atk_ev=252, def_ev=0,
              spa_ev=252, spd_ev=0, nat_atk=1.1):
    \"\"\"종족값 + 세트로 참가자 스탯 dict(spe 포함). 세트(evs+nature) 있으면 그걸로 전 스탯
    계산, 없으면 prior(공격 252+성격) 폴백 = 회귀 0. item/ability 정적배율은 apply_effects.\"\"\"
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
    return apply_effects(char, sd)"""

with open('modules/reference_gen5.py', 'r', encoding='utf-8') as f:
    text = f.read()

count1 = text.count(find_1)
count2 = text.count(find_2)

text = text.replace(find_1, replace_1)
text = text.replace(find_2, replace_2)

with open('modules/reference_gen5.py', 'w', encoding='utf-8') as f:
    f.write(text)

print(f"Patch applied. Replacements: {count1}, {count2}")
