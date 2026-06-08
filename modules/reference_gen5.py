"""
gen5 포켓몬 레퍼런스 (lazy 시드) — reference_gen6과 동일 인터페이스.

풀배틀 트레이스 리플레이(PR-B2)의 gen5 데이터 면. battle_setup(세대중립 빌더)이 이 모듈을
ref로 주입받아 participants·battle_spec을 만든다. "전체 도감"이 아니라 골든 로그 등장분만
(lazy). 종족값은 관측 max HP로 자가검증됨(12종족 전부 합법 HP EV).

gen6과의 차이는 *데이터*뿐: 종족/무브/타입표/CRIT_MULT(2.0). 식·인터페이스는 동일.
gen5 고유 메커니즘(Psyshock 방어타격·SR 타입스케일·Wish·Trick·날씨 무한)은 여기 데이터가
아니라 엔진/효과-스키마 몫 — EFFECTS는 빈 슬롯(B4/후속에서 채움).
"""
import math

L = 100              # 표준 대전 레벨
CRIT_MULT = 2.0      # gen5 크리 배율 (gen6은 1.5)
# 엔진 formula 언어(gen6과 동일 base). ELEMENT_MULT가 STAB×타입, CRIT가 ×CRIT_MULT.
DAMAGE_FORMULA = "math.floor(math.floor(42 * move_power * offense / defense) / 50) + 2"

# 종족값 (HP,Atk,Def,SpA,SpD,Spe) — 골든 로그 12종. 관측 max HP로 검증됨.
BASE = {
    'Politoed': (90, 75, 75, 90, 100, 70), 'Jirachi': (100, 100, 100, 100, 100, 100),
    'Breloom': (60, 130, 80, 60, 60, 70), 'Garchomp': (108, 130, 95, 80, 85, 102),
    'Zapdos': (90, 90, 85, 125, 90, 100), 'Tentacruel': (80, 70, 65, 80, 120, 100),
    'Stoutland': (85, 110, 90, 45, 90, 80), 'Hippowdon': (108, 112, 118, 68, 72, 47),
    'Rotom-Wash': (50, 65, 107, 105, 107, 86), 'Ferrothorn': (74, 94, 131, 54, 116, 20),
    'Latios': (80, 90, 80, 130, 110, 110), 'Metagross': (80, 135, 130, 95, 90, 70),
    'Abomasnow': (90, 92, 75, 92, 85, 60),  'Clefable': (95, 70, 73, 95, 90, 60),
    'Gliscor':   (75, 95, 125, 45, 75, 95), 'Latias':   (80, 80, 90, 110, 130, 110),
    'Magnezone': (70, 70, 115, 130, 90, 60),'Reuniclus':(110, 65, 75, 125, 85, 30),
    'Scrafty':   (65, 90, 115, 45, 115, 58),'Skarmory': (65, 80, 140, 40, 70, 70),
}
SPECIES_TYPES = {
    'Politoed': ('Water', ''), 'Jirachi': ('Steel', 'Psychic'),
    'Breloom': ('Grass', 'Fighting'), 'Garchomp': ('Dragon', 'Ground'),
    'Zapdos': ('Electric', 'Flying'), 'Tentacruel': ('Water', 'Poison'),
    'Stoutland': ('Normal', ''), 'Hippowdon': ('Ground', ''),
    'Rotom-Wash': ('Electric', 'Water'), 'Ferrothorn': ('Grass', 'Steel'),
    'Latios': ('Dragon', 'Psychic'), 'Metagross': ('Steel', 'Psychic'),
    'Abomasnow': ('Grass', 'Ice'),   'Clefable': ('Normal', ''),
    'Gliscor':   ('Ground', 'Flying'),'Latias':  ('Dragon', 'Psychic'),
    'Magnezone': ('Electric', 'Steel'),'Reuniclus':('Psychic', ''),
    'Scrafty':   ('Dark', 'Fighting'),'Skarmory': ('Steel', 'Flying'),
}
# 무브 (power, category, type). type=None: Hidden Power(숨김타입 — B3/B4에서 역산/공급).
# status: 데미지 0(효과는 효과-스키마/엔진 — B4).
MOVES = {
    'Body Slam': (85, 'phys', 'Normal'), 'Draco Meteor': (130, 'spec', 'Dragon'),
    'Earthquake': (100, 'phys', 'Ground'), 'Explosion': (250, 'phys', 'Normal'),
    'Hidden Power': (70, 'spec', None), 'Hydro Pump': (120, 'spec', 'Water'),
    'Ice Fang': (65, 'phys', 'Ice'), 'Iron Head': (80, 'phys', 'Steel'),
    'Psyshock': (80, 'spec', 'Psychic'), 'Scald': (80, 'spec', 'Water'),
    'Superpower': (120, 'phys', 'Fighting'), 'Thunderbolt': (95, 'spec', 'Electric'),
    'Volt Switch': (70, 'spec', 'Electric'), 'Rapid Spin': (20, 'phys', 'Normal'),
    'Protect': (0, 'status', None), 'Toxic': (0, 'status', None),
    'Trick': (0, 'status', None), 'Wish': (0, 'status', None),
    'Stealth Rock': (0, 'status', None), 'Spore': (0, 'status', None),
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
    'Seismic Toss': (0, 'phys', 'Fighting'),   # 고정데미지(FIXED_DAMAGE_MOVES). 타입은 면역 판정용
}
# 타입표(공격타입 × 방어타입) — gen5, 등장 공격타입만(lazy). 미기재=1.0. gen5엔 Fairy 없음.
TYPE = {
    'Normal': {'Ghost': 0.0, 'Steel': 0.5, 'Rock': 0.5},
    'Dragon': {'Dragon': 2.0, 'Steel': 0.5},
    'Ground': {'Flying': 0.0, 'Steel': 2.0, 'Electric': 2.0, 'Fire': 2.0,
               'Grass': 0.5, 'Bug': 0.5, 'Poison': 2.0, 'Rock': 2.0},
    'Water': {'Fire': 2.0, 'Ground': 2.0, 'Rock': 2.0, 'Water': 0.5,
              'Grass': 0.5, 'Dragon': 0.5},
    'Ice': {'Dragon': 2.0, 'Flying': 2.0, 'Ground': 2.0, 'Grass': 2.0,
            'Steel': 0.5, 'Fire': 0.5, 'Water': 0.5, 'Ice': 0.5},
    'Steel': {'Ice': 2.0, 'Rock': 2.0, 'Steel': 0.5, 'Fire': 0.5,
              'Water': 0.5, 'Electric': 0.5},
    'Psychic': {'Fighting': 2.0, 'Poison': 2.0, 'Steel': 0.5, 'Psychic': 0.5, 'Dark': 0.0},
    'Rock': {'Flying': 2.0, 'Bug': 2.0, 'Fire': 2.0, 'Ice': 2.0,
             'Fighting': 0.5, 'Ground': 0.5, 'Steel': 0.5},
    'Fighting': {'Normal': 2.0, 'Steel': 2.0, 'Rock': 2.0, 'Ice': 2.0, 'Dark': 2.0,
                 'Psychic': 0.5, 'Flying': 0.5, 'Poison': 0.5, 'Bug': 0.5, 'Ghost': 0.0},
    'Electric': {'Water': 2.0, 'Flying': 2.0, 'Ground': 0.0, 'Grass': 0.5,
                 'Electric': 0.5, 'Dragon': 0.5},
    # Hidden Power Fire(Rotom-Wash·Latios)가 도입 — lazy 표에 없던 공격타입. gen5 표준 Fire 행.
    'Fire': {'Grass': 2.0, 'Ice': 2.0, 'Bug': 2.0, 'Steel': 2.0,
             'Fire': 0.5, 'Water': 0.5, 'Rock': 0.5, 'Dragon': 0.5},
    'Flying': {'Grass': 2.0, 'Fighting': 2.0, 'Bug': 2.0,
               'Electric': 0.5, 'Rock': 0.5, 'Steel': 0.5},
    'Dark':   {'Psychic': 2.0, 'Ghost': 2.0, 'Fighting': 0.5, 'Dark': 0.5, 'Steel': 0.5},
    'Bug':    {'Grass': 2.0, 'Psychic': 2.0, 'Dark': 2.0, 'Fire': 0.5, 'Fighting': 0.5,
               'Poison': 0.5, 'Flying': 0.5, 'Ghost': 0.5, 'Steel': 0.5},
}
# 특성 기반 타입면역(순수 ×0만) — {특성: 무효화할 공격타입}. build_game_config가 type_table에
# 의사-타입 항목으로 주입하고, make_char가 보유 종족 gimmicks에 t3=특성명을 박는다. 데이터-only.
# 주의: Water Absorb/Volt Absorb/Flash Fire 등 흡수회복·부스트형은 ×0이 틀리므로 효과-스키마 몫.
ABILITY_TYPE_IMMUNITY = {'Levitate': 'Ground'}

# 효과 레이어 시드 — 항시형 정적 스탯 배율(코퍼스 잔차가 요구하면 채움). 트리거형은 EFFECTS.
ABILITIES = {'Huge Power': {'atk': 2.0}, 'Pure Power': {'atk': 2.0}}
ITEMS = {'Choice Band': {'atk': 1.5}, 'Choice Specs': {'spa': 1.5},
         'Choice Scarf': {'spe': 1.5}, 'Life Orb': {'atk': 1.3, 'spa': 1.3},
         'Eviolite': {'df': 1.5, 'spd': 1.5}}
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
    'Hippowdon':  {'nature': 'Impish',  'evs': (252, 0, 252, 0, 4, 0),   'item': 'Leftovers',    'ability': 'Sand Stream'},   # [확정] 물리벽 / env Leftovers +26
    'Ferrothorn': {'nature': 'Relaxed', 'evs': (252, 0, 252, 0, 4, 0),   'item': 'Leftovers',    'ability': 'Iron Barbs'},    # [확정] env Leftovers +22
    'Tentacruel': {'nature': 'Bold',    'evs': (252, 0, 252, 0, 4, 0),   'item': 'Black Sludge', 'ability': 'Rain Dish'},     # [확정] 물리방어 / env Black Sludge +22
    'Politoed':   {'nature': 'Bold',    'evs': (252, 0, 252, 0, 4, 0),   'item': None,           'ability': 'Drizzle'},       # [확정] 물리방어
    'Latios':     {'nature': 'Timid',   'evs': (0, 0, 0, 252, 4, 252),   'item': 'Choice Specs', 'ability': 'Levitate', 'hp_type': 'Fire'},  # [확정] Trick=Choice / HP Fire[prior,잔차×2]
    'Jirachi':    {'nature': 'Careful', 'evs': (252, 0, 0, 0, 224, 32),  'item': 'Leftovers',    'ability': 'Serene Grace'},  # [확정] env Leftovers +25 / SpD Wish
    'Zapdos':     {'nature': 'Timid',   'evs': (0, 0, 0, 252, 4, 252),   'item': 'Leftovers',    'ability': 'Pressure'},      # [확정] env Leftovers +23
    'Rotom-Wash': {'nature': 'Modest',  'evs': (252, 0, 0, 252, 0, 4),   'item': None,           'ability': 'Levitate', 'hp_type': 'Fire'},  # [prior] HP Fire[표준,잔차×2 T1 0.93]
    'Garchomp':   {'nature': 'Jolly',   'evs': (0, 252, 0, 0, 4, 252),   'item': 'Rocky Helmet', 'ability': 'Rough Skin'},    # [확정] env: RoughSkin −52(420/8)·RockyHelmet −70(420/6)
    'Breloom':    {'nature': 'Jolly',   'evs': (0, 252, 0, 0, 4, 252),   'item': 'Toxic Orb',    'ability': 'Poison Heal'},   # [확정] env: Spore+자기맹독(Toxic Orb)·맹독데미지無(Poison Heal)
    'Stoutland':  {'nature': 'Adamant', 'evs': (0, 252, 4, 0, 0, 252),   'item': 'Choice Band',  'ability': 'Sand Rush'},     # [prior]
    'Metagross':  {'nature': 'Adamant', 'evs': (0, 252, 0, 0, 4, 252),   'item': 'Life Orb',     'ability': 'Clear Body'},    # [prior]
    'Abomasnow': {'nature': 'Naive',  'evs': (0, 0, 0, 252, 4, 252), 'item': 'Life Orb',    'ability': 'Snow Warning'},  # [확정]특성 [prior]도구/EV
    'Clefable':  {'nature': 'Calm',   'evs': (252, 0, 4, 0, 252, 0), 'item': 'Leftovers',   'ability': 'Magic Guard'},   # [확정]도구 [역설계]MagicGuard(우박無)
    'Gliscor':   {'nature': 'Impish', 'evs': (252, 0, 184, 0, 0, 72),'item': 'Toxic Orb',   'ability': 'Poison Heal'},   # [확정]도구·특성
    'Latias':    {'nature': 'Timid',  'evs': (0, 0, 0, 252, 4, 252), 'item': 'Life Orb',    'ability': 'Levitate'},      # [prior] 미행동(즉사)
    'Magnezone': {'nature': 'Modest', 'evs': (252, 0, 0, 252, 4, 0), 'item': 'Air Balloon', 'ability': 'Magnet Pull'},   # [확정]도구
    'Reuniclus': {'nature': 'Bold',   'evs': (252, 0, 252, 4, 0, 0), 'item': 'Leftovers',   'ability': 'Magic Guard'},   # [확정]도구 [역설계]MagicGuard(우박無)
    'Scrafty':   {'nature': 'Careful','evs': (252, 0, 0, 0, 252, 4), 'item': 'Leftovers',   'ability': 'Shed Skin'},     # [확정]도구·특성
    'Skarmory':  {'nature': 'Impish', 'evs': (252, 0, 252, 0, 4, 0), 'item': 'Rocky Helmet','ability': 'Sturdy'},        # [확정]도구
}
# 발동형 효과(트리거×조건×효과×스코프) — 효과-스키마 디스패처(PR-E′)가 ability/item 이름으로
# 매칭해 적용. dict[이름] = spec. ON_TURN_END(Leftovers·모래·상태틱)·해저드는 PR-E′2/E′3.
# Rough Skin/Iron Barbs(특성)·Rocky Helmet(도구): 접촉 피격 시 공격자(scope=attacker)에 반동.
EFFECTS = {
    'Rough Skin':   {'trigger': 'ON_HIT', 'condition': {'contact': True},
                     'effect': {'type': 'damage_frac', 'frac': 1/8, 'of': 'maxhp'},
                     'scope': 'attacker', 'source': 'ability'},
    'Iron Barbs':   {'trigger': 'ON_HIT', 'condition': {'contact': True},
                     'effect': {'type': 'damage_frac', 'frac': 1/8, 'of': 'maxhp'},
                     'scope': 'attacker', 'source': 'ability'},
    'Rocky Helmet': {'trigger': 'ON_HIT', 'condition': {'contact': True},
                     'effect': {'type': 'damage_frac', 'frac': 1/6, 'of': 'maxhp'},
                     'scope': 'attacker', 'source': 'item'},
    # 턴엔드 회복(PR-E′2a). owner=active_char, scope=self. Leftovers는 전원, Black Sludge는
    # Poison만 회복(비-Poison damage는 후속). Rain Dish(비 한정)·모래칩·상태틱은 PR-E′2b.
    'Leftovers':    {'trigger': 'ON_TURN_END',
                     'effect': {'type': 'heal_frac', 'frac': 1/16, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'item'},
    'Black Sludge': {'trigger': 'ON_TURN_END', 'condition': {'of_types': ['Poison']},
                     'effect': {'type': 'heal_frac', 'frac': 1/16, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'item'},
    # 날씨/상태 소스(PR-E′2b). 'sand'는 발효 날씨 토큰으로 매칭(디스패처가 field_state.weather를
    # 키로 추가). Rain Dish는 ability 키 + weather 조건. 'brn'은 status 토큰 키(resync 공급).
    'sand':         {'trigger': 'ON_TURN_END', 'condition': {'not_types': ['Rock', 'Ground', 'Steel']},
                     'effect': {'type': 'damage_frac', 'frac': 1/16, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'weather'},   # 모래폭풍 칩 1/16
    'hail':         {'trigger': 'ON_TURN_END',
                     'condition': {'not_types': ['Ice'], 'not_ability': ['Magic Guard']},
                     'effect': {'type': 'damage_frac', 'frac': 1/16, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'weather'},   # 우박 칩 1/16 (Ice·Magic Guard 면제)
    'Rain Dish':    {'trigger': 'ON_TURN_END', 'condition': {'weather': 'rain'},
                     'effect': {'type': 'heal_frac', 'frac': 1/16, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'ability'},   # 비 1/16 회복
    'brn':          {'trigger': 'ON_TURN_END',
                     'effect': {'type': 'damage_frac', 'frac': 1/8, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'status'},     # 화상 틱 1/8
    'tox':          {'trigger': 'ON_TURN_END', 'condition': {'not_ability': ['Poison Heal']},
                     'effect': {'type': 'damage_frac', 'frac': 1/16, 'of': 'maxhp', 'progressive': True},
                     'scope': 'self', 'source': 'status'},     # 맹독 누진 n/16 (Poison Heal 보유자 제외)
    'Poison Heal':  {'trigger': 'ON_TURN_END', 'condition': {'of_status': ['tox', 'psn']},
                     'effect': {'type': 'heal_frac', 'frac': 1/8, 'of': 'maxhp'},
                     'scope': 'self', 'source': 'ability'},   # 독일 때 1/8 회복(데미지 대신)
    # 무브-소스(ON_HIT). Explosion/Self-Destruct: 사용자(scope=self) 자폭. 대상 데미지는 엔진 본체가
    # 이미 적용(검증: T15 Bonaparte −108/−108) — 빠진 건 사용자 HP→0뿐.
    'Explosion':     {'trigger': 'ON_HIT', 'source': 'move',
                      'effect': {'type': 'self_faint'}, 'scope': 'self'},
    'Self-Destruct': {'trigger': 'ON_HIT', 'source': 'move',
                      'effect': {'type': 'self_faint'}, 'scope': 'self'},
    'Trick':         {'trigger': 'ON_HIT', 'source': 'move',
                      'effect': {'type': 'swap_item'}, 'scope': 'both'},   # 도구 교환(+스탯배율 조정)
    'Roost':       {'trigger': 'ON_MOVE_USE', 'source': 'move',
                    'effect': {'type': 'heal_frac', 'frac': 1/2, 'of': 'maxhp'}, 'scope': 'self'},
    'Soft-Boiled': {'trigger': 'ON_MOVE_USE', 'source': 'move',
                    'effect': {'type': 'heal_frac', 'frac': 1/2, 'of': 'maxhp'}, 'scope': 'self'},
    'Rest':        {'trigger': 'ON_MOVE_USE', 'source': 'move',
                    'effect': {'type': 'heal_frac', 'frac': 1.0, 'of': 'maxhp'}, 'scope': 'self'},  # 풀회복(+slp는 주입 status)
}

# 접촉 무브 — ON_HIT 접촉 조건용. gen5 로그 등장분(lazy). 미기재=비접촉.
# 물리라도 Earthquake·Explosion·Volt Switch는 비접촉. 특수·status 전부 비접촉.
CONTACT_MOVES = {'Body Slam', 'Ice Fang', 'Iron Head', 'Superpower', 'Rapid Spin', 'U-turn'}

# 고정 데미지 무브 — {무브명: 고정 HP 데미지}. 산식/스탯/상성 배율 무관, 단 타입 면역(×0)은 존중.
# Seismic Toss·Night Shade = 레벨(gen5 OU=100). 확장: Dragon Rage=40, Sonic Boom=20.
FIXED_DAMAGE_MOVES = {'Seismic Toss': 100}

# 반동무브 — 사용자가 '입힌 데미지'의 분수만큼 자기 피해(gen5).
RECOIL_MOVES = {
    'Brave Bird': 1/3, 'Double-Edge': 1/3, 'Flare Blitz': 1/3, 'Wood Hammer': 1/3,
    'Volt Tackle': 1/3, 'Head Smash': 1/2,
    'Take Down': 1/4, 'Submission': 1/4, 'Wild Charge': 1/4, 'Head Charge': 1/4,
}


def _gimmicks_with_immunity(t1, t2, set_data):
    """타입 컬럼 t1/t2 + 면역특성이면 의사-타입 t3(=특성명). 엔진 _move_type_multiplier가
    type_columns로 t3까지 순회해 type_table[공격타입][특성명]=0.0과 만나 ×0 면역을 낸다."""
    g = {'t1': t1, 't2': t2}
    abil = (set_data or {}).get('ability')
    if abil in ABILITY_TYPE_IMMUNITY:
        g['t3'] = abil
    return g


def stat(base, iv=31, ev=0, nat=1.0):
    return math.floor((math.floor((2 * base + iv + ev // 4) * L // 100) + 5) * nat)


def hp_stat(base, iv=31, ev=0):
    return (2 * base + iv + ev // 4) + L + 10


def stage_mult(s):
    return (2 + s) / 2 if s >= 0 else 2 / (2 - s)


def apply_effects(char, set_data):
    """set_data({ability,item})의 정적 스탯 배율을 char 스탯에 적용(항시형)."""
    for key, table in (('ability', ABILITIES), ('item', ITEMS)):
        name = (set_data or {}).get(key)
        mods = table.get(name) if name else None
        if mods:
            for st_key, mult in mods.items():
                char[st_key] = math.floor(char[st_key] * mult)
    return char


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
            'gimmicks': _gimmicks_with_immunity(t1, t2, sd), 'active_states': [],
        }
    else:
        char = {
            'id': nick, 'name': nick, '_species': species,
            'atk': stat(B[1], ev=atk_ev, nat=nat_atk), 'df': stat(B[2], ev=def_ev),
            'spa': stat(B[3], ev=spa_ev, nat=nat_atk), 'spd': stat(B[4], ev=spd_ev),
            'spe': stat(B[5], ev=0), 'maxhp': hp_stat(B[0], ev=hp_ev),
            'gimmicks': _gimmicks_with_immunity(t1, t2, sd), 'active_states': [],
        }
    return apply_effects(char, sd)


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
        'item_stat_mults': {k: dict(v) for k, v in ITEMS.items()},   # Trick 도구교환 스탯배율 조정용
    }
