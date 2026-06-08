"""
Showdown 리플레이 → 정규화 트레이스 IR.

트레이스-리플레이 검증(A 하니스)의 입력 어댑터. 쇼다운 리플레이 HTML(또는 raw
`|`-프로토콜 텍스트)을 받아, 엔진이 이벤트별로 대조할 수 있는 정규화 트레이스를 만든다.
엔진/게임 중립 — 포켓몬 고유 분기 없음. 관측값(데미지 delta·상성플래그·크리·기절)이
*답안지*이고, 엔진은 이를 독립 계산해 대조한다(이 모듈은 답안지만 생성).

핵심 설계:
- `-damage`를 `[from]` 유무로 분리: [from] 없음 = 무브 직격(검증 타깃), 있음 = 부수
  데미지(날씨/해저드/상태/도구 — 별도 스트림 env).
- 발효 날씨·공격자 상태를 move 이벤트에 컨텍스트로 부착 → "깨끗한 이벤트" 필터 가능.
- HP 필드의 상태 접미사(tox/brn/par/slp/frz/psn) 파싱.
"""
import re

_STATUS_TOKENS = {"tox", "brn", "par", "slp", "frz", "psn"}


def _extract_protocol(text):
    """HTML이면 battle-log-data script 블록 추출, 아니면 그대로. 이스케이프 슬래시 복원."""
    m = re.search(r'class="battle-log-data">(.*?)</script>', text, re.S)
    body = m.group(1) if m else text
    return body.replace('\\/', '/')


def _slot(s):
    """'p1a: Nick' -> ('p1', 'Nick'). 슬롯 표기 아니면 (None, s)."""
    m = re.match(r'(p\d)[a-c]?:\s*(.+)', s)
    return (m.group(1), m.group(2)) if m else (None, s)


def _hp(s):
    """'213/292' / '0 fnt' / '60/420 tox' -> (cur, max, status). 상태 없으면 None."""
    s = s.strip()
    status = None
    parts = s.split()
    if len(parts) > 1:
        tok = parts[1]
        if tok in _STATUS_TOKENS:
            status = tok
    head = parts[0]
    if head == "0" and "fnt" in s:
        return (0, None, status)
    m = re.match(r'(\d+)/(\d+)', head)
    if m:
        return (int(m.group(1)), int(m.group(2)), status)
    m = re.match(r'(\d+)', head)
    if m:
        return (int(m.group(1)), None, status)
    return (None, None, status)


def _from_tag(parts):
    """이벤트 잔여 토큰에서 '[from] X' 추출. 없으면 None."""
    for x in parts:
        m = re.match(r'\[from\]\s*(.+)', x)
        if m:
            return m.group(1).strip()
    return None


def parse_replay(text):
    """쇼다운 리플레이(HTML 또는 raw 프로토콜) → 정규화 트레이스 IR dict."""
    proto = _extract_protocol(text)
    lines = [l for l in proto.split('\n') if l.startswith('|')]

    meta = {"rules": [], "teams": {"p1": [], "p2": []}, "players": {}}
    nick2species = {}
    events = []

    # 러닝 상태(컨텍스트 스탬프용)
    weather = None
    hp_cur = {}          # nick -> 마지막 알려진 cur
    status_of = {}       # nick -> 상태(tox/brn/...)
    turn = 0
    cur_move = None      # 직전 move 이벤트(직격 데미지/플래그 부착 대상)

    def species_of(nick):
        return nick2species.get(nick)

    for raw in lines:
        p = raw.split('|')          # p[0]=='' (선두 '|')
        k = p[1] if len(p) > 1 else ''

        if k == 'gen':
            meta['gen'] = p[2] if len(p) > 2 else None
        elif k == 'tier':
            meta['tier'] = p[2] if len(p) > 2 else None
        elif k == 'gametype':
            meta['gametype'] = p[2] if len(p) > 2 else None
        elif k == 'rule':
            meta['rules'].append(p[2] if len(p) > 2 else '')
        elif k == 'player' and len(p) >= 4 and p[3]:
            meta['players'][p[2]] = p[3]
        elif k == 'poke' and len(p) >= 4:
            meta['teams'].setdefault(p[2], []).append(p[3].split(',')[0])

        elif k == 'turn':
            turn = int(p[2]); cur_move = None

        elif k in ('switch', 'drag') and len(p) >= 4:
            side, nick = _slot(p[2])
            species = p[3].split(',')[0]
            nick2species[nick] = species
            cur, mx, stt = _hp(p[4]) if len(p) >= 5 else (None, None, None)
            if cur is not None:
                hp_cur[nick] = cur
            if stt is not None:
                status_of[nick] = stt
            events.append({"turn": turn, "action": "switch", "actor_side": side,
                           "actor": nick, "species": species, "hp": cur, "max": mx,
                           "status": stt, "forced": (k == 'drag'),
                           "weather": weather})
            cur_move = None

        elif k == 'move' and len(p) >= 4:
            side, nick = _slot(p[2])
            tside, tnick = _slot(p[4]) if len(p) > 4 else (None, None)
            cur_move = {"turn": turn, "action": "move", "actor_side": side,
                        "actor": nick, "species": species_of(nick), "move": p[3],
                        "target": tnick, "hits": [], "flags": [], "boosts": [],
                        "faints": [],
                        "context": {"weather": weather,
                                    "attacker_status": status_of.get(nick)}}
            events.append(cur_move)

        elif k == '-damage' and len(p) >= 4:
            side, nick = _slot(p[2])
            cur, mx, stt = _hp(p[3])
            src = _from_tag(p[4:])
            prev = hp_cur.get(nick)
            delta = (cur - prev) if (prev is not None and cur is not None) else None
            if cur is not None:
                hp_cur[nick] = cur
            if stt is not None:
                status_of[nick] = stt
            rec = {"who": nick, "prev": prev, "cur": cur, "max": mx, "delta": delta}
            if src is None and cur_move is not None:
                # 무브 직격 — 직전 move에 부착(검증 타깃)
                cur_move["hits"].append(rec)
            else:
                # 부수 데미지 — 별도 env 스트림
                events.append({"turn": turn, "action": "env", "kind": "damage",
                               "src": src, **rec, "weather": weather})

        elif k == '-heal' and len(p) >= 4:
            side, nick = _slot(p[2])
            cur, mx, stt = _hp(p[3])
            src = _from_tag(p[4:])
            prev = hp_cur.get(nick)
            delta = (cur - prev) if (prev is not None and cur is not None) else None
            if cur is not None:
                hp_cur[nick] = cur
            events.append({"turn": turn, "action": "env", "kind": "heal", "src": src,
                           "who": nick, "prev": prev, "cur": cur, "max": mx,
                           "delta": delta, "weather": weather})

        elif k == '-weather':
            w = p[2] if len(p) > 2 else None
            weather = None if (w in (None, '', 'none')) else w

        elif k in ('-supereffective', '-resisted', '-immune', '-crit'):
            if cur_move is not None:
                cur_move["flags"].append(k[1:])

        elif k == '-boost' and len(p) >= 5:
            _, who = _slot(p[2])
            if cur_move is not None:
                cur_move["boosts"].append({"who": who, "stat": p[3],
                                           "stages": int(p[4])})
        elif k == '-unboost' and len(p) >= 5:
            _, who = _slot(p[2])
            if cur_move is not None:
                cur_move["boosts"].append({"who": who, "stat": p[3],
                                           "stages": -int(p[4])})

        elif k == '-status' and len(p) >= 4:
            _, who = _slot(p[2])
            status_of[who] = p[3]
            events.append({"turn": turn, "action": "status", "who": who, "status": p[3]})
            if cur_move is not None:
                cur_move["flags"].append("status:" + p[3])

        elif k == '-curestatus' and len(p) >= 4:
            _, who = _slot(p[2])
            status_of.pop(who, None)
            events.append({"turn": turn, "action": "status", "who": who, "status": None})

        elif k == 'cant' and len(p) >= 4:
            _, who = _slot(p[2])
            events.append({"turn": turn, "action": "cant", "actor": who,
                           "reason": p[3]})
            cur_move = None

        elif k in ('-start', '-end', '-activate') and len(p) >= 3:
            _, who = _slot(p[2])
            events.append({"turn": turn, "action": k[1:], "actor": who,
                           "what": '|'.join(p[3:])})

        elif k == '-sidestart' and len(p) >= 4:
            sp_side = p[2].split(":")[0].strip()
            name = p[3].replace("move:", "").strip()
            events.append({"action": "sidestart", "actor_side": sp_side,
                           "name": name, "turn": turn})

        elif k == '-sideend' and len(p) >= 4:
            sp_side = p[2].split(":")[0].strip()
            name = p[3].replace("move:", "").strip()
            events.append({"action": "sideend", "actor_side": sp_side,
                           "name": name, "turn": turn})

        elif k == 'faint' and len(p) >= 3:
            _, who = _slot(p[2])
            hp_cur[who] = 0
            if cur_move is not None:
                cur_move["faints"].append(who)
            else:
                events.append({"turn": turn, "action": "faint", "who": who})

        elif k == 'win':
            events.append({"turn": turn, "action": "win", "who": p[2] if len(p) > 2 else None})

    return {"meta": meta, "nick2species": nick2species, "events": events}


def clean_damage_events(trace):
    """코어 검증용 — 무브 직격 데미지 중 '깨끗한' 것만. 깨끗 = 발효 날씨 없음 +
    공격자 데미지영향 상태(화상) 없음. 각 (move, hit) 페어를 평탄화해 반환."""
    out = []
    for ev in trace["events"]:
        if ev.get("action") != "move":
            continue
        ctx = ev.get("context", {})
        if ctx.get("weather"):
            continue
        if ctx.get("attacker_status") in ("brn",):
            continue
        for h in ev["hits"]:
            if h.get("delta") is None:
                continue
            if h["who"] == ev["actor"]:
                continue  # 자가 데미지(Substitute 비용 등) 제외 — 공식 검증 대상 아님
            out.append({"turn": ev["turn"], "attacker": ev["actor"],
                        "attacker_species": ev["species"], "move": ev["move"],
                        "defender": h["who"], "damage": -h["delta"],
                        "def_prev": h["prev"], "def_max": h["max"],
                        "crit": "crit" in ev["flags"],
                        "effect": [f for f in ev["flags"]
                                   if f in ("supereffective", "resisted", "immune")]})
    return out
