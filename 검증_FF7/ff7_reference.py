# -*- coding: utf-8 -*-
"""ff7_reference.py — FF7 1v1 트레이스-리플레이 레퍼런스(하니스 호환).
통합 데미지식 + categories(phys/spec) + 9속성 의사-타입 type_table(약점 2x·흡수 -1)."""
import math  # noqa (DAMAGE_FORMULA eval 환경에서 사용)

ELEMENTS = ["Fire", "Ice", "Lightning", "Earth", "Water", "Wind", "Holy", "Poison", "Gravity"]
L = 50

# 통제 known-answer 캐릭터(원시 FF7 스탯). C1: Fire 약점·Ice 흡수.
CHARS = {
    'C0': {'HP': 5000, 'Strength': 50, 'Magic': 60, 'Vitality': 40, 'Spirit': 35,
           'Dexterity': 60, 'Luck': 10, 'WeaponAttack': 40, 'WeaponMagic': 30,
           'ArmorDefense': 30, 'ArmorSpirit': 20, 'ResistElement': 'Lightning', 'AbsorbElement': None},
    'C1': {'HP': 6000, 'Strength': 45, 'Magic': 40, 'Vitality': 50, 'Spirit': 45,
           'Dexterity': 40, 'Luck': 8, 'WeaponAttack': 35, 'WeaponMagic': 20,
           'ArmorDefense': 40, 'ArmorSpirit': 25, 'ResistElement': 'Fire', 'AbsorbElement': 'Ice'},
}

# 무브: name -> (power, category, element). category는 엔진 categories 키('phys'/'spec')와 일치.
MOVES = {
    'Slash': (16, 'phys', None), 'Heavy_Strike': (24, 'phys', None), 'Cross_Slash': (32, 'phys', None),
    'Pierce': (20, 'phys', None), 'Limit_Break': (32, 'phys', None),
    'Fire': (14, 'spec', 'Fire'), 'Fire2': (30, 'spec', 'Fire'), 'Fire3': (60, 'spec', 'Fire'),
    'Ice': (14, 'spec', 'Ice'), 'Ice2': (30, 'spec', 'Ice'), 'Ice3': (60, 'spec', 'Ice'),
    'Bolt': (14, 'spec', 'Lightning'), 'Bolt2': (30, 'spec', 'Lightning'), 'Bolt3': (60, 'spec', 'Lightning'),
    'Quake': (24, 'spec', 'Earth'), 'Quake2': (48, 'spec', 'Earth'),
    'Water': (24, 'spec', 'Water'), 'Aqualung': (50, 'spec', 'Water'),
    'Wind_Slash': (28, 'spec', 'Wind'), 'Aero': (54, 'spec', 'Wind'), 'Holy': (66, 'spec', 'Holy'),
    'Bio': (26, 'spec', 'Poison'), 'Bio2': (46, 'spec', 'Poison'),
    'Demi': (28, 'spec', 'Gravity'), 'Demi2': (42, 'spec', 'Gravity'),
}
CONTACT_MOVES = set()
SETS = {}
EFFECTS = {}
# build_participants의 'species in BASE' 체크 + HP-EV 역산 B[0]용. 첫 값=HP(관측 max로 덮임).
BASE = {cid: (c['HP'], 0, 0, 0, 0, c['Dexterity']) for cid, c in CHARS.items()}
SPECIES_TYPES = {cid: ('', '') for cid in CHARS}

# 통합 데미지식(phys·magic 공통). element는 ELEMENT_MULT 단계 type_table. FF7 정수 // 재현.
DAMAGE_FORMULA = ("math.floor(math.floor(math.floor(offense*(offense+50)/64)"
                  "*(512-min(512,max(0,defense)))/512)*move_power/16)")


def make_char(nick, species, set_data=None):
    c = CHARS[species]
    g = {}
    if c.get('ResistElement'):
        g['t1'] = 'weak:' + c['ResistElement']     # 약점(2x) 의사-타입
    if c.get('AbsorbElement'):
        g['t2'] = 'absorb:' + c['AbsorbElement']    # 흡수(-1) 의사-타입
    return {'id': nick, 'name': nick, '_species': species,
            'atk': c['Strength'] + c['WeaponAttack'], 'df': c['Vitality'] + c['ArmorDefense'],
            'spa': c['Magic'] + c['WeaponMagic'], 'spd': c['Spirit'] + c['ArmorSpirit'],
            'spe': c['Dexterity'], 'maxhp': c['HP'], 'gimmicks': g, 'active_states': []}


def build_game_config():
    # 9속성 × 의사-타입: type_table[E]['weak:E']=2.0, ['absorb:E']=-1.0. 그 외 1.0(미기재).
    type_table = {e: {'weak:' + e: 2.0, 'absorb:' + e: -1.0} for e in ELEMENTS}
    return {'categories': {'phys': {'offense': 'atk', 'defense': 'df'},
                           'spec': {'offense': 'spa', 'defense': 'spd'}},
            'type_table': type_table, 'type_columns': ['t1', 't2'],
            'stab_factor': 1.0, 'crit_mult': 1.0}
