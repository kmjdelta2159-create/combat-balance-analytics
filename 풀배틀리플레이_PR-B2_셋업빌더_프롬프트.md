# PR-B2 — 풀배틀 셋업 빌더 (세대중립) + gen5 레퍼런스 (신규 모듈 2개)

## 목적
풀배틀 트레이스 리플레이(`풀배틀리플레이_설계안.md`)의 셋업 조각. 트레이스에서 **양팀
participants**(스탯·타입·resources·세트)와 **battle_spec**(formula·type_table·crit·effects)를
만든다. 핸드오프 원칙대로 **하니스는 세대중립**, 세대는 *레퍼런스 데이터 교체*로만 바뀐다 —
그래서 빌더(`battle_setup.py`)는 reference 모듈을 주입받는 세대중립 구조이고, gen5 골든
풀배틀 로그를 위해 **gen5 레퍼런스**(`reference_gen5.py`)를 새로 시드한다. **기존 모듈
무변경**(신규 파일 2개, reference_gen6 손대지 않음 = 회귀0).

## 대상
**신규 파일 2개**: `modules/battle_setup.py`(세대중립 빌더) + `modules/reference_gen5.py`
(gen5 데이터, reference_gen6과 동일 인터페이스). 다른 파일 변경 없음.

## 설계 근거 (gen5 골든 로그·gen6 로그로 검증됨)
- **세대중립 빌더 + ref 주입**: `build_participants(trace, ref)`·`build_battle_spec(trace, ref)`가
  `ref.BASE / SPECIES_TYPES / MOVES / TYPE / make_char / build_game_config / DAMAGE_FORMULA /
  SETS / ABILITIES / ITEMS / (EFFECTS)`만 의존. reference_gen5·reference_gen6 둘 다 만족 →
  같은 빌더가 두 세대에 그대로 돈다(검증됨).
- **maxhp = 관측 ground truth + HP EV 역산 자가검증**: 트레이스가 실 max HP를 노출하므로
  participant maxhp를 관측값으로 박고, `ev//4 = maxhp − 2·baseHP − 141`로 HP EV를 역산해
  `0..63`(=0..252 EV)이면 종족값 시드가 정합. gen5 12종족 전부 합법 → BASE 시드 검증.
- **비-HP 스탯은 prior**(공격형 252·+성격): 실제 세트/EV는 모르므로 prior로 두고, **B4
  풀배틀 divergence가 잔차로 보정 타깃을 지목**(역설계→수정 루프). B2는 spec을 세우는 단계.
- **gen5 고유 상수**: `CRIT_MULT=2.0`(gen6 1.5), 날씨 무한 등 — 데이터로 spec에 실림.
  gen5 고유 *메커니즘*(Psyshock 방어타격·SR 타입스케일·Wish·Trick)은 **B2 범위 밖** —
  B4에서 잔차로 드러날 후속(`EFFECTS`는 빈 슬롯으로 둔다).
- **SETS 비움(gen5)**: 세트(특성/도구)는 RE·사용자수정으로 채울 자리. 시드 0으로 두고
  잔차가 요구하면 채운다(예: gen6 Diggersby Huge Power가 그렇게 채워졌다).

## 생성할 파일 1 — `modules/reference_gen5.py` (전체, 바이트 그대로)

```python
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
}
SPECIES_TYPES = {
    'Politoed': ('Water', ''), 'Jirachi': ('Steel', 'Psychic'),
    'Breloom': ('Grass', 'Fighting'), 'Garchomp': ('Dragon', 'Ground'),
    'Zapdos': ('Electric', 'Flying'), 'Tentacruel': ('Water', 'Poison'),
    'Stoutland': ('Normal', ''), 'Hippowdon': ('Ground', ''),
    'Rotom-Wash': ('Electric', 'Water'), 'Ferrothorn': ('Grass', 'Steel'),
    'Latios': ('Dragon', 'Psychic'), 'Metagross': ('Steel', 'Psychic'),
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
    'Fighting': {'Normal': 2.0, 'Steel': 2.0, 'Rock': 2.0, 'Ice': 2.0, 'Dark': 2.0,
                 'Psychic': 0.5, 'Flying': 0.5, 'Poison': 0.5, 'Bug': 0.5, 'Ghost': 0.0},
    'Electric': {'Water': 2.0, 'Flying': 2.0, 'Ground': 0.0, 'Grass': 0.5,
                 'Electric': 0.5, 'Dragon': 0.5},
}
# 효과 레이어 시드 — 항시형 정적 스탯 배율(코퍼스 잔차가 요구하면 채움). 트리거형은 EFFECTS.
ABILITIES = {'Huge Power': {'atk': 2.0}, 'Pure Power': {'atk': 2.0}}
ITEMS = {'Choice Band': {'atk': 1.5}, 'Choice Specs': {'spa': 1.5},
         'Choice Scarf': {'spe': 1.5}, 'Life Orb': {'atk': 1.3, 'spa': 1.3},
         'Eviolite': {'df': 1.5, 'spd': 1.5}}
# 세트(특성/도구) — gen5는 RE/사용자수정으로 채울 자리. 시드 비움(잔차가 요구하면 채움).
SETS = {}
# 발동형 효과(트리거×조건×효과) — 효과-스키마(PR-E). gen5분은 B4 잔차가 드러내면 채움.
EFFECTS = []


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


def build_game_config():
    """엔진이 gen5 데미지를 독립 계산하도록 — 카테고리·타입표·STAB·크리배율."""
    return {
        'categories': {'phys': {'offense': 'atk', 'defense': 'df'},
                       'spec': {'offense': 'spa', 'defense': 'spd'}},
        'type_table': {atk: dict(row) for atk, row in TYPE.items()},
        'type_columns': ['t1', 't2'], 'stab_factor': 1.5, 'crit_mult': CRIT_MULT,
    }
```

## 생성할 파일 2 — `modules/battle_setup.py` (전체, 바이트 그대로)

```python
"""
풀배틀 셋업 빌더 (세대중립).

정규화 트레이스 + reference(세대별 데이터 모듈) → participants(양팀 스탯·타입·resources·세트)
+ battle_spec(formula·type_table·crit·effects). reference는 reference_gen5/gen6 인터페이스
(BASE / SPECIES_TYPES / MOVES / TYPE / make_char / build_game_config / DAMAGE_FORMULA /
SETS / ABILITIES / ITEMS / (EFFECTS))만 만족하면 됨 — 세대는 ref 교체로만 바뀐다.

핵심: maxhp는 트레이스의 관측 max HP(ground truth)로 박고 HP EV를 역산해 종족값 정합을
자가검증. 비-HP 스탯은 prior(공격형) — 실 세트/EV는 B4 풀배틀 divergence가 잔차로 보정.
엔진을 부르지 않으므로 engine.py truncation 영향권 밖(클린룸 검증).
"""


def _observed_maxhp(trace):
    """트레이스에서 닉네임별 관측 max HP(처음 본 값). switch/move-hit/env에서 수집."""
    mh = {}
    for e in trace["events"]:
        if e.get("action") == "switch" and e.get("max"):
            mh.setdefault(e["actor"], e["max"])
        elif e.get("action") == "move":
            for h in e.get("hits", []):
                if h.get("max"):
                    mh.setdefault(h["who"], h["max"])
        elif e.get("action") == "env" and e.get("max"):
            mh.setdefault(e["who"], e["max"])
    return mh


def _nick_side(trace):
    """닉네임 → 진영(p1/p2). switch 이벤트의 actor_side에서."""
    sd = {}
    for e in trace["events"]:
        if e.get("action") == "switch" and e.get("actor_side"):
            sd.setdefault(e["actor"], e["actor_side"])
    return sd


def build_participants(trace, ref):
    """trace 등장 유닛 → 참가자 char dict 리스트. maxhp는 관측값으로 보정 + HP EV 역산
    자가검증(_hp_ev_legal). 비-HP는 prior. set_data는 ref.SETS. ref에 없는 종족은
    _missing_ref로 표시(lazy 시드 보강 타깃)."""
    mh = _observed_maxhp(trace)
    side = _nick_side(trace)
    parts = []
    for nick, species in trace["nick2species"].items():
        if species not in ref.BASE:
            parts.append({"id": nick, "_species": species, "_missing_ref": True,
                          "side": side.get(nick)})
            continue
        set_data = ref.SETS.get(species)
        ch = ref.make_char(nick, species, set_data=set_data)
        om = mh.get(nick)
        if om is not None:                       # 관측 max HP로 보정 + HP EV 역산 자가검증
            B = ref.BASE[species]
            ev4 = om - 2 * B[0] - 141
            ch["maxhp"] = om
            ch["_hp_ev"] = max(0, ev4) * 4
            ch["_hp_ev_legal"] = 0 <= ev4 <= 63
        ch["hp"] = ch["maxhp"]
        ch["side"] = side.get(nick)
        ch["set"] = set_data or {}
        parts.append(ch)
    return parts


def build_battle_spec(trace, ref):
    """trace + ref → battle_spec(엔진 game_config + 발동형 effects 슬롯)."""
    gc = ref.build_game_config()
    gc["formula"] = ref.DAMAGE_FORMULA
    gc.setdefault("mechanisms", {})["effects"] = getattr(ref, "EFFECTS", [])
    return {"gen": trace["meta"].get("gen"), "tier": trace["meta"].get("tier"),
            "gametype": trace["meta"].get("gametype"), "game_config": gc}
```

## API
- `battle_setup.build_participants(trace, ref) -> [char...]` — 등장 유닛 참가자(스탯·타입·
  resources·set·side). maxhp 관측 보정 + `_hp_ev_legal` 자가검증. `_missing_ref`=ref 미시드.
- `battle_setup.build_battle_spec(trace, ref) -> {gen, tier, gametype, game_config}` —
  game_config에 formula·type_table·crit_mult·mechanisms.effects(슬롯).
- `reference_gen5`: reference_gen6과 동일 인터페이스(BASE/SPECIES_TYPES/MOVES/TYPE/make_char/
  build_game_config/DAMAGE_FORMULA/SETS/ABILITIES/ITEMS/EFFECTS, stat/hp_stat/stage_mult).

## 검증 (클린룸·실 로그 2건, 작성 시 수행 — 적용자 재현용)
- **gen5 골든 로그**(`Gen5OU-2015-...`) + `reference_gen5`: participants **12**(p1 6 / p2 6),
  `_missing_ref` **없음**, max HP 자가검증 **전부 합법**(12종족 HP EV ∈ 0..252). spec gen=5,
  crit_mult=**2.0**, type_table 9개 공격타입, effects=[](B4 슬롯).
- **gen6 로그**(`OUMonotype-2014-...`) + 기존 `reference_gen6`(세대중립 입증): 같은 빌더로
  participants **6**(p1 3 / p2 3 — 등장분만), `_missing_ref` 없음, max HP 자가검증 합법,
  **Diggersby Huge Power 적용(atk 464)** = set/effect 경로 통과. → 빌더가 ref 교체만으로 두
  세대에 동작.

적용자 검증:
1. 두 신규 파일 `ast.parse` OK.
2. ```python
   from modules.showdown_trace import parse_replay
   from modules.battle_setup import build_participants, build_battle_spec
   import modules.reference_gen5 as r5
   t = parse_replay(open('Gen5OU-2015-05-11-reymedy-leftiez.html', encoding='utf-8').read())
   ps = build_participants(t, r5); sp = build_battle_spec(t, r5)
   assert len(ps) == 12 and all(p.get('_hp_ev_legal') for p in ps)
   assert sp['game_config']['crit_mult'] == 2.0
   ```
3. 기존 모듈 import·동작 무변경(reference_gen6 손대지 않음).

## 회귀 0
신규 파일 2개. reference_gen6·engine·step2·turn_manager·showdown_trace·trace_replay·
fullbattle_diff 전부 무변경. 엔진 미호출(클린룸 완결). 어떤 기존 경로도 아직 미소비
(PR-B4 통합 run에서 소비).

## 알려진 후속 (B2 범위 밖 — 명시)
- **gen6 풀배틀 시도 시**: reference_gen6.make_char에 `spe` 키, build_game_config에
  `crit_mult`(1.5)가 없다(PR3 per-event엔 불필요했음). gen6 풀배틀 턴순서/크리에 필요 →
  reference_gen6에 두 줄 추가하는 별도 작은 PR. gen5 골든 파이프라인엔 영향 없음.
- **gen5 고유 메커니즘**: Psyshock(특수무브가 방어 타격)·Stealth Rock 타입스케일·Wish(지연
  회복)·Trick(도구 교환)·날씨 무한 — B4 풀배틀 divergence가 잔차로 지목할 효과-스키마/엔진
  몫. B2 spec의 EFFECTS는 의도적으로 빈 슬롯.

## 다음 (PR-B3 예고)
엔진 — 트레이스 구동 selector(MOVE_SELECT/TARGET_SELECT 오버라이드: 현재 라운드 그 유닛의
로그 행동 반환) + **자발교체 주입**(로그 voluntary switch를 행동으로 — 교체모델 신규 표면).
엔진 FIND/REPLACE, *앱에서* 동작 확인(engine.py truncation). 그 뒤 PR-B4(통합 run +
라운드별 divergence 리포트, fullbattle_diff 소비, 앱 실행).
