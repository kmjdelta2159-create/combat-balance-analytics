"""mechanism_commit.py — 메커니즘 수정 surface(추출→조건추론→확정→커밋).
검출기(mechanism_detect) 쇼핑리스트 + 조건 자동추론(ranked 힌트) + 사용자 결정 → EFFECTS 블록."""
from collections import defaultdict

def _onfield_tl(trace):
    """턴별 진영 on-field 닉 {turn: {side: nick}} (fullbattle_run.build_onfield_timeline와 동형)."""
    onf, tl, last = {}, {}, None
    for e in trace['events']:
        tn = e.get('turn')
        if tn is None:
            continue
        if last is not None and tn != last:
            tl[last] = dict(onf)
        if e.get('action') in ('switch', 'drag'):
            onf[e['actor_side']] = e['actor']
        last = tn
    if last is not None:
        tl[last] = dict(onf)
    return tl

from modules.mechanism_detect import canonical_mechanism_key

def infer_conditions(trace, ref, src_match):
    """그 메커니즘(src_match)이 영향준 유닛 vs 같은 턴 on-field 면제 유닛 대조 →
    not_ability(면제 공통특성, 강)·not_types(면제 전용타입, 약) 힌트(빈도순)."""
    sp = trace['nick2species']
    TYP = getattr(ref, 'SPECIES_TYPES', {})
    SETS = getattr(ref, 'SETS', {})
    tl = _onfield_tl(trace)
    aff, onf = set(), set()
    
    target_cls, target_name = canonical_mechanism_key(src_match)
    
    for e in trace['events']:
        if e.get('action') == 'env':
            raw_src = e.get('src')
            if raw_src:
                e_cls, e_name = canonical_mechanism_key(raw_src)
                is_match = (e_cls, e_name) == (target_cls, target_name)
            else:
                is_match = (raw_src == src_match)
                
            if is_match:
                aff.add(e['who'])
                for n in tl.get(e['turn'], {}).values():
                    onf.add(n)
    spared = onf - aff
    aff_types = {t for n in aff for t in TYP.get(sp.get(n), ()) if t}
    nt, na = defaultdict(int), defaultdict(int)
    for n in spared:
        for t in TYP.get(sp.get(n), ()):
            if t and t not in aff_types:
                nt[t] += 1
        ab = (SETS.get(sp.get(n)) or {}).get('ability')
        if ab:
            na[ab] += 1
    return {'spared': sorted(sp.get(n, n) for n in spared),
            'not_ability_hint': sorted(na, key=lambda k: -na[k]),
            'not_types_hint': sorted(nt, key=lambda k: -nt[k])}

def commit(decisions):
    """decisions: {effects_key: {'spec': {...detector suggest...}, 'condition': {...}|None}}
    → EFFECTS dict(ready-to-paste). condition 있으면 spec에 병합."""
    eff = {}
    for key, d in decisions.items():
        s = dict(d['spec'])
        if d.get('condition'):
            s['condition'] = d['condition']
        eff[key] = s
    return eff
