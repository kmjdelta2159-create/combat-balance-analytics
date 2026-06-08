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
