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


def build_participants(trace, ref, set_override=None):
    """trace 등장 유닛 → 참가자 char dict 리스트. maxhp는 관측값으로 보정 + HP EV 역산
    자가검증(_hp_ev_legal). 비-HP는 prior. set_data는 ref.SETS. ref에 없는 종족은
    _missing_ref로 표시(lazy 시드 보강 타깃)."""
    mh = _observed_maxhp(trace)
    side = _nick_side(trace)
    # HP Percentage Mod: 관측 max=100은 실 maxhp가 아님 → 보정 생략, make_char 계산값 사용.
    # (Golden 트레이스도 meta rules에 Percentage가 포함될 수 있으므로 실제 관측값 기반 판정)
    pct = all(v <= 100 for v in mh.values()) if mh else False
    parts = []
    for nick, species in trace["nick2species"].items():
        if species not in ref.BASE:
            parts.append({"id": nick, "_species": species, "_missing_ref": True,
                          "side": side.get(nick)})
            continue
        set_data = (set_override or {}).get(species) or ref.SETS.get(species)
        ch = ref.make_char(nick, species, set_data=set_data)
        om = mh.get(nick)
        if om is not None and not pct:          # ← 절대 HP 로그에서만 관측값으로 보정
            B = ref.BASE[species]
            ev4 = om - 2 * B[0] - 141
            ch["maxhp"] = om
            ch["_hp_ev"] = max(0, ev4) * 4
            ch["_hp_ev_legal"] = 0 <= ev4 <= 63
        ch["hp"] = ch["maxhp"]                   # 퍼센트면 make_char 계산 maxhp 그대로
        ch["side"] = side.get(nick)
        ch["set"] = set_data or {}
        ch["ability"] = (set_data or {}).get("ability")   # 효과 디스패처 owner 매칭(PR-E′)
        ch["item"] = (set_data or {}).get("item")
        parts.append(ch)
    return parts


def build_battle_spec(trace, ref):
    """trace + ref → battle_spec(엔진 game_config + 발동형 effects 슬롯)."""
    gc = ref.build_game_config()
    gc["formula"] = ref.DAMAGE_FORMULA
    gc.setdefault("mechanisms", {})["effects"] = getattr(ref, "EFFECTS", [])
    return {"gen": trace["meta"].get("gen"), "tier": trace["meta"].get("tier"),
            "gametype": trace["meta"].get("gametype"), "game_config": gc}


# 피벗(데미지 후 자기 교체) 무브 — 교체를 무브가 유발(자발교체와 구분). B3 범위 밖(B4 후속).
PIVOT_MOVES = {"Volt Switch", "U-turn"}


def build_trace_actions(trace, ref, pivot_moves=PIVOT_MOVES):
    """트레이스 → (turn, 행위자 id)별 행동 분류. on-field·HP·기절 타임라인 복원으로 switch를
    리드/기절교체/피벗/자발로 가른다. 무브 dict는 ref.MOVES로 해석. 엔진 무관.

    반환 dict:
      move_actions    {(turn, actor_id): {'move': {name,power,category,type}, 'target': id}}
      vol_switch      {(turn, actor_id): incoming_id}            # 자발교체(엔진 selector)
      faint_incoming  [{turn, side, outgoing, incoming}, ...]    # 기절교체 incoming(엔진 faint 경로)
      pivot_switch    {(turn, actor_id): incoming_id}            # 피벗(B4 후속)
      leads           {side: nick}                                # 초기 on_field
    """
    onfield = {}
    hp = {}
    fainted = set()
    move_actions = {}
    vol = {}
    faint_incoming = []
    pivot = {}
    leads = {}
    moves_by_ta = {}
    for e in trace["events"]:
        if e.get("action") == "move":
            moves_by_ta.setdefault((e["turn"], e["actor"]), set()).add(e["move"])
    for e in trace["events"]:
        a = e.get("action")
        tn = e.get("turn")
        if a == "move":
            for w in e.get("faints", []):
                hp[w] = 0
                fainted.add(w)
            for h in e.get("hits", []):
                if h.get("cur") is not None:
                    hp[h["who"]] = h["cur"]
            tgt = e.get("target") or (e["hits"][0]["who"] if e.get("hits") else None)
            md = ref.MOVES.get(e["move"])
            mtype = md[2] if md else None
            if e["move"] == "Hidden Power" and mtype is None:   # 숨김타입: 공격자 세트 hp_type
                asp = trace["nick2species"].get(e["actor"])
                mtype = (ref.SETS.get(asp) or {}).get("hp_type")
            mv = {"name": e["move"], "power": (md[0] if md else 0),
                  "category": (md[1] if md else None), "type": mtype,
                  "contact": e["move"] in getattr(ref, "CONTACT_MOVES", set()),
                  "fixed_damage": getattr(ref, "FIXED_DAMAGE_MOVES", {}).get(e["move"]),
                  "recoil": getattr(ref, "RECOIL_MOVES", {}).get(e["move"])}
            move_actions[(tn, e["actor"])] = {"move": mv, "target": tgt}
        elif a == "env":
            if e.get("cur") is not None:
                hp[e["who"]] = e["cur"]
            if e.get("cur") == 0:
                fainted.add(e["who"])
        elif a == "faint":
            fainted.add(e["who"])
            hp[e["who"]] = 0
        elif a == "switch":
            side = e["actor_side"]
            inc = e["actor"]
            out = onfield.get(side)
            if out is None or tn == 0:
                leads[side] = inc                                   # 리드(셋업)
            elif out in fainted or hp.get(out, 1) == 0:
                faint_incoming.append({"turn": tn, "side": side,
                                       "outgoing": out, "incoming": inc})   # 기절교체
            elif moves_by_ta.get((tn, out), set()) & pivot_moves:
                pivot[(tn, out)] = inc                               # 피벗(B4 후속)
            else:
                vol[(tn, out)] = inc                                 # 자발교체
            onfield[side] = inc
            if e.get("hp") is not None:
                hp[inc] = e["hp"]
            fainted.discard(inc)
    return {"move_actions": move_actions, "vol_switch": vol,
            "faint_incoming": faint_incoming, "pivot_switch": pivot, "leads": leads}


def prepare_run(trace, ref, set_override=None):
    """B2 participants + B3 trace_actions를 엔진이 바로 먹을 형태로 조립.
    participant에 team(Ally/Enemy)·on_field(리드)·roster_idx(진영 등장순) 부여, game_config에
    trace_actions(move/switch)·trace_faint_incoming·switch_policy(trace) 주입.
    반환: (participants, battle_spec, trace_actions_dict)."""
    parts = build_participants(trace, ref, set_override=set_override)
    spec = build_battle_spec(trace, ref)
    ta = build_trace_actions(trace, ref)
    side2team = {"p1": "Ally", "p2": "Enemy"}
    idx = {}
    leads = set(ta["leads"].values())
    for p in parts:
        sd = p.get("side")
        p["team"] = side2team.get(sd, sd)
        p["on_field"] = (p["id"] in leads)
        idx[sd] = idx.get(sd, 0)
        p["roster_idx"] = idx[sd]
        idx[sd] += 1
    gc = spec["game_config"]
    gc["trace_actions"] = {"move": ta["move_actions"], "switch": ta["vol_switch"]}
    gc["trace_faint_incoming"] = ta["faint_incoming"]
    gc["switch_policy"] = {"type": "trace"}   # 트레이스 구동 — hp_threshold 정책 대체
    gc["on_active_faint"] = "replace_from_reserve"  # 기절 시 예비 진입(로그 지정 incoming)
    return parts, spec, ta
