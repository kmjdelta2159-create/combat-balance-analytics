"""mechanism_detect.py — 트레이스-구동 메커니즘 RE 검출기.
트레이스 [from] env 스트림을 마이닝해 발동형 메커니즘을 자동 추출하고, ref.EFFECTS 대조로
미모델을 가리키며 EFFECTS 후보 spec을 제안한다(수정 surface 입력). streamlit/engine 의존 0."""
import statistics
from collections import defaultdict

_FRAC = [1/16, 1/8, 1/6, 1/4, 1/3, 1/2, 1.0]   # 표준 분수 스냅

_WEATHER_ALIASES = {
    "hail": "hail",
    "sand": "sand",
    "sandstorm": "sand",
    "sand storm": "sand",
    "rain": "rain",
    "raindance": "rain",
    "rain dance": "rain",
    "sun": "sun",
    "sunnyday": "sun",
    "sunny day": "sun",
}

_STATUS_ALIASES = {
    "brn": "brn",
    "burn": "brn",
    "burned": "brn",
    "psn": "psn",
    "poison": "psn",
    "poisoned": "psn",
    "tox": "tox",
    "toxic": "tox",
    "badly poisoned": "tox",
    "par": "par",
    "paralysis": "par",
    "paralyzed": "par",
    "frz": "frz",
    "freeze": "frz",
    "frozen": "frz",
    "slp": "slp",
    "sleep": "slp",
    "asleep": "slp",
}

_SUPPORTED_ENTRY_HAZARDS = {"Stealth Rock", "Spikes"}

_HAZARD_ALIASES = {
    "stealth rock": "Stealth Rock",
    "spikes": "Spikes",
    "toxic spikes": "Toxic Spikes",
}

def _snap(f):
    return min(_FRAC, key=lambda x: abs(x - f)) if f > 0 else 0

def _norm(src):
    """env src('item: Leftovers'/'ability: Poison Heal'/'Hail'/'Stealth Rock'/'tox'…) → (class, name)."""
    s = (src or '').strip()
    if s.startswith('item:'): return 'item', s[5:].strip()
    if s.startswith('ability:'): return 'ability', s[8:].strip()
    s_lower = s.lower()
    if s_lower in _HAZARD_ALIASES: return 'hazard', _HAZARD_ALIASES[s_lower]
    if s_lower in _STATUS_ALIASES: return 'status', _STATUS_ALIASES[s_lower]
    if s == 'Recoil': return 'move', 'Recoil'
    if s_lower in _WEATHER_ALIASES: return 'weather', _WEATHER_ALIASES[s_lower]
    return ('weather' if s else 'move'), (s or None)

def _is_modeled(cls, name, ref):
    eff = getattr(ref, 'EFFECTS', {}) or {}
    mk = {k for k in eff} | {str(k).lower() for k in eff}
    
    if name in mk or str(name).lower() in mk:
        return True
        
    if cls == "weather":
        cname = _WEATHER_ALIASES.get(str(name).lower())
        if cname and cname in mk:
            return True
            
    if cls == "status":
        cname = _STATUS_ALIASES.get(str(name).lower())
        if cname and cname in mk:
            return True
            
    if cls == "move":
        if name == "Recoil":
            recoil_moves = getattr(ref, "RECOIL_MOVES", {}) or {}
            if len(recoil_moves) > 0:
                return True
        else:
            recoil_moves = getattr(ref, "RECOIL_MOVES", {}) or {}
            if name in recoil_moves:
                return True
            fixed_damage_moves = getattr(ref, "FIXED_DAMAGE_MOVES", {}) or {}
            if name in fixed_damage_moves:
                return True
                
    if cls == "hazard":
        if name in _SUPPORTED_ENTRY_HAZARDS:
            return True
            
    return False

def canonical_mechanism_key(cls_or_src, name=None):
    if name is None:
        return _norm(cls_or_src)

    cls = str(cls_or_src or "").strip()
    n = str(name or "").strip()
    nl = n.lower()

    if cls == "weather":
        return cls, _WEATHER_ALIASES.get(nl, n)
    if cls == "status":
        return cls, _STATUS_ALIASES.get(nl, n)
    if cls == "hazard":
        return cls, _HAZARD_ALIASES.get(nl, n)
    if cls == "move":
        return cls, "Recoil" if nl == "recoil" else n
    if cls in ("item", "ability"):
        return cls, n
    return cls, n

def detect_mechanisms(trace, ref):
    """트레이스 + ref → 메커니즘 쇼핑리스트(빈도순). 각: class/name/kind/frac/n/affected/modeled/suggest/sources."""
    sp = trace['nick2species']
    mv = {}                                            # 자가효과 귀속용: (turn, who) → 무브명
    for e in trace['events']:
        if e.get('action') == 'move':
            mv[(e['turn'], e['actor'])] = e['move']
    g = defaultdict(list)
    src_map = defaultdict(set)
    for e in trace['events']:
        if e.get('action') == 'env' and e.get('max'):
            raw_src = e.get('src')
            cls, name = _norm(raw_src)
            if name is None:                            # src 없는 자가효과 → 그 턴 그 유닛 무브(회복무브)
                name = mv.get((e['turn'], e['who'])); cls = 'move'
            g[(cls, name, e['kind'])].append((abs(e['delta']) / e['max'], sp.get(e['who'])))
            if raw_src:
                src_map[(cls, name, e['kind'])].add(raw_src)
    out = []
    for (cls, name, kind), rows in g.items():
        if not name:
            continue
        frac = _snap(statistics.median(r[0] for r in rows))
        modeled = _is_modeled(cls, name, ref)
        trig = ('ON_SWITCH' if cls == 'hazard'
                else 'ON_MOVE_USE' if (cls == 'move' and kind == 'heal')
                else 'ON_HIT' if cls == 'move' else 'ON_TURN_END')
        etype = 'heal_frac' if kind == 'heal' else 'damage_frac'
        scope = 'attacker' if (cls == 'move' and kind == 'damage' and name != 'Recoil') else 'self'
        out.append({'class': cls, 'name': name, 'kind': kind, 'frac': frac, 'n': len(rows),
                    'affected': sorted(set(r[1] for r in rows if r[1])), 'modeled': modeled,
                    'suggest': {'trigger': trig, 'effect': {'type': etype, 'frac': round(frac, 4), 'of': 'maxhp'},
                                'scope': scope, 'source': cls},
                    'sources': sorted(src_map.get((cls, name, kind), []))})
    out.sort(key=lambda x: -x['n'])
    return out
