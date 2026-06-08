# 교차-게임 PR-G1 — FF7 트레이스-리플레이 하니스 (키스톤 일반화 측정)

> 1차목표 키스톤(트레이스-리플레이 + 설정 가능한 데미지 엔진 + 디스패처)을 *구조가 다른 게임*
> FF7(JRPG)에 던져 교차-게임 2-가드를 잰다. **클린룸 검증 완료**: FF7 phys·magic이 *하나의*
> 엔진 공식 + categories + `weak:`/`absorb:` 의사-타입 type_table로 **10000 셀 0 불일치(흡수
> 114건 포함)** 재현. 즉 FF7 데미지 코어(라우팅·식·9속성·흡수)가 엔진 설정만으로 표현된다.
>
> **이 PR은 신규 파일 3개만** 추가(검증_FF7/ 폴더). 엔진·기존 reference **무수정**(회귀0). 풀
> 엔진 실행(run_ff7)은 앱사이드. 예측: 흡수(-1)를 엔진이 회복으로 라우팅하면 **전 턴 일치(갭 0)**,
> 클램프하면 **흡수 턴 1건만 ★** → 어느 쪽이든 키스톤이 JRPG에 일반화(교차-게임 통과).

## 파일 1 — `검증_FF7/ff7_reference.py` (reference_gen5 인터페이스 호환)

```python
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
```

## 파일 2 — `검증_FF7/ff7_trace_gen.py` (통제 known-answer 트레이스)

```python
# -*- coding: utf-8 -*-
"""ff7_trace_gen.py — ff7_reference 캐릭터 + FF7 식으로 단일 전투 트레이스 생성.
순수 base 데미지(크리·롤 off) 결정론 → 엔진(크리·롤 없음)이 정확 일치 → 흡수 갭만 격리.
무브 시퀀스는 커버리지(phys·magic·약점·흡수)용 스크립트(AI는 스코프 밖). 출력: ff7_trace.json."""
import json, os
import ff7_reference as R

L = 50

def get_elem_mult(elem, weak, absb):
    if elem is None: return 1.0
    if elem == absb: return -1.0
    if elem == weak: return 2.0
    return 1.0

def pure_dmg(atk, dfn, move):
    power, cat, elem = R.MOVES[move]
    if cat == 'phys':
        off = atk['Strength'] + atk['WeaponAttack']; deff = dfn['Vitality'] + dfn['ArmorDefense']
        base = (off * (off + L)) // 64; d = max(0, min(512, deff))
        return max(1, (base * (512 - d) // 512) * power // 16)
    off = atk['Magic'] + atk['WeaponMagic']; deff = dfn['Spirit'] + dfn['ArmorSpirit']
    base = (off * (off + L)) // 64; d = max(0, min(512, deff))
    dmg = (base * (512 - d) // 512) * power // 16
    em = get_elem_mult(elem, dfn.get('ResistElement'), dfn.get('AbsorbElement'))
    final = int(dmg * em)
    return final if em < 0 else (max(1, final) if em > 0 else 0)

# 커버리지 스크립트: C0는 phys·Fire(2x)·Ice(흡수)·중립 다수, C1은 phys.
SEQ0 = ['Slash','Fire2','Ice2','Bolt2','Cross_Slash','Fire3','Quake2','Heavy_Strike','Holy','Fire2','Pierce','Aqualung']
SEQ1 = ['Slash','Heavy_Strike','Cross_Slash','Pierce']*3

def main():
    ids = ['C0', 'C1']; sides = ['p1', 'p2']; chars = [R.CHARS['C0'], R.CHARS['C1']]
    hp = [chars[0]['HP'], chars[1]['HP']]; events = []
    for k in (0, 1):
        events.append({'action': 'switch', 'actor': ids[k], 'actor_side': sides[k],
                       'turn': 0, 'hp': hp[k], 'max': chars[k]['HP']})
    for turn in range(1, 13):
        for ai in (0, 1):
            di = 1 - ai
            if hp[ai] <= 0 or hp[di] <= 0: continue
            mv = (SEQ0 if ai == 0 else SEQ1)[turn - 1]
            d = pure_dmg(chars[ai], chars[di], mv)
            hp[di] = min(chars[di]['HP'], hp[di] - d) if d < 0 else max(0, hp[di] - d)
            events.append({'action': 'move', 'actor': ids[ai], 'actor_side': sides[ai], 'turn': turn,
                           'move': mv, 'target': ids[di], 'context': {},
                           'hits': [{'who': ids[di], 'cur': hp[di], 'max': chars[di]['HP']}],
                           'faints': ([ids[di]] if hp[di] <= 0 else [])})
        if hp[0] <= 0 or hp[1] <= 0: break
    trace = {'meta': {'gen': 'ff7', 'tier': 'FF7', 'gametype': 'singles', 'rules': [], 'players': ['P0', 'P1']},
             'nick2species': {ids[0]: ids[0], ids[1]: ids[1]}, 'events': events}
    json.dump(trace, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ff7_trace.json'),
                          'w', encoding='utf-8'), ensure_ascii=False)
    print('move events:', sum(1 for e in events if e['action'] == 'move'), 'last turn:', events[-1]['turn'])

if __name__ == '__main__':
    main()
```

## 파일 3 — `검증_FF7/run_ff7.py` (앱사이드 풀런 + 분류)

```python
# -*- coding: utf-8 -*-
"""run_ff7.py — FF7 트레이스 + ff7_reference로 트레이스-리플레이 divergence.
프로젝트 루트의 modules를 쓰므로 엔진 온전한 앱 환경에서 실행. 먼저 ff7_trace_gen.py 실행 필요."""
import json, os, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                 # 검증_FF7의 부모 = 프로젝트 루트
for p in (ROOT, HERE):
    if p not in sys.path: sys.path.insert(0, p)

def main():
    from modules.fullbattle_run import run_and_diff, format_report
    import ff7_reference as ref
    path = os.path.join(HERE, 'ff7_trace.json')
    if not os.path.exists(path):
        print('ff7_trace.json 없음 — 먼저 python ff7_trace_gen.py 실행'); return
    trace = json.load(open(path, encoding='utf-8'))
    res = run_and_diff(trace, ref, hp_tol=2, resync=True, hp_mode='absolute')
    print(format_report(res))
    # 흡수 턴 분리 표시(엔진이 음수 elem_mult를 회복으로 라우팅하나)
    print('\n[흡수 점검] T3 C1: Ice2(흡수) → 로그는 회복(+316). 엔진이 같으면 일치, 클램프면 ★(언어확장 1).')

if __name__ == '__main__':
    try: main()
    except Exception:
        print('=== run_ff7 에러 (트레이스백 전체를 붙여주세요) ==='); traceback.print_exc(); sys.exit(1)
```

## 검증 (적용 후, 순서대로)

1. **클린룸 식 일치(엔진 무관, 이미 검증)**: ff7_reference 통합식·categories·의사-타입이 ff7_ref
   순수-base 데미지를 재현(10000 셀 0 불일치, 흡수 114건 포함). 적용분이 위 코드와 동일한지 Read.
2. **트레이스 생성**: `검증_FF7`에서 `python ff7_trace_gen.py` → `ff7_trace.json`(24 무브, 12턴,
   약점 2x 3건·흡수 -1 1건 포함).
3. **골든 회귀0**: `python run_b4.py` 무변(신규 파일이라 영향 없음 — 형식 확인).
4. **FF7 풀런**: `python run_ff7.py` → divergence 리포트. **전체를 붙여달라.** 예상:
   - phys·magic·약점(2x)·중립 전 턴 *일치*(데미지식·라우팅·9속성 일반화 실증).
   - **T3 흡수**: 엔진이 음수 elem_mult를 회복으로 라우팅하면 일치(갭 0) / 클램프하면 ★ 1건
     (언어확장 = APPLY_DAMAGE 음수 라우팅, gen5 heal_frac 친척 — 작고 일반적).

## 평결 틀 (출력 받은 뒤)

- **닫힘(전 턴 일치)** = 키스톤이 JRPG에 일반화(교차-게임 2-가드 통과). 데미지식·phys/magic
  라우팅·9속성이 *엔진 설정만으로* 표현됨.
- **(ㄴ) = 흡수 0~1건**. 0이면 흡수까지 무료, 1이면 음수-데미지 라우팅 효과타입 1개. 어느 쪽이든
  포켓몬 모양으로 굳지 않았다는 강한 증거.
- 결론을 `교차검증_평결_2가드통과.md`에 *교차-게임* 절로 추가(다음).
