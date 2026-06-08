"""셀 분류 진단 — held-out divergence의 구조적 셀을 메커니즘별로 가른다.

F1(Seismic Toss) 이후 남은 셀들이 어느 메커니즘인지 한 번에 분류한다:
  F2(해저드 타이밍)·F3(recoil/locked priority)·NEW(스탯스테이지 미추적)·미상.
run_and_diff의 결과에서 (1) 구조적 under-damage 셀(엔진이 데미지 덜 줌, log<eng)과
(2) 큰 over-damage 셀(엔진이 더 줌, log>eng — Bulk Up류 방어부스트 미추적 후보)을 모두 모아,
각 셀의 그 턴 사건(공격/피격 무브·진입·hazard·weather)과 *이전 부스트 누적*을 트레이스에서
붙여 크기순으로 정렬·분류한다.

앱사이드 실행: python run_cellclass.py [코퍼스.html]   (출력 전체를 붙여주세요)
원본 코드 수정 없음 — 순수 관찰(run_and_diff 호출 + 트레이스 조회). 일회용 진단(지워도 무방)."""
import os, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
DEFAULT = os.path.join(HERE, "Gen5OU-2026-newatmons-bantyranitar.html")

# 이 전투 한정 세트 override — run_xval/run_f1diag와 동일(전역 SETS 불변).
XVAL_SET_OVERRIDE = {
    'Garchomp': {'nature': 'Jolly', 'evs': (0, 252, 0, 0, 4, 252),
                 'item': None, 'ability': 'Rough Skin'},
}

# 반동(자기 데미지) 무브 — gen5 물리 반동.
RECOIL_MOVES = {
    "Brave Bird", "Double-Edge", "Flare Blitz", "Wood Hammer", "Head Smash",
    "Volt Tackle", "Take Down", "Submission", "Wild Charge", "Head Charge",
}
# 우선도/락드(다중턴 고정) — 엔진 우선도·락 처리 의심 후보.
PRIORITY_LOCKED = {
    "Ice Shard", "Bullet Punch", "Mach Punch", "Aqua Jet", "Sucker Punch",
    "Extreme Speed", "Vacuum Wave", "Shadow Sneak", "Quick Attack", "Ice Punch",
    "Outrage", "Petal Dance", "Thrash",
}
# 데미지에 영향 주는 스탯(공/특공=공격측 부스트, 방/특방=방어측 부스트).
OFF_STATS = {"atk", "spa"}
DEF_STATS = {"def", "spd"}


def _norm_stat(s):
    s = (s or "").lower()
    return {"attack": "atk", "defense": "def", "spa": "spa", "spd": "spd",
            "spe": "spe", "atk": "atk", "def": "def"}.get(s, s)


def nick_side_map(trace):
    """nick -> 'p1'/'p2' (switch·move의 actor_side에서)."""
    m = {}
    for e in trace["events"]:
        side = e.get("actor_side")
        nick = e.get("actor")
        if side and nick and nick not in m:
            m[nick] = side
    return m


def boosts_before(trace, unit, turn):
    """turn 이전(< turn)에 unit에게 적용된 부스트 누적 {stat: net_stages}."""
    acc = {}
    for e in trace["events"]:
        if e.get("action") != "move":
            continue
        if (e.get("turn") or 0) >= turn:
            continue
        for b in e.get("boosts", []):
            if b.get("who") == unit:
                st = _norm_stat(b.get("stat"))
                acc[st] = acc.get(st, 0) + (b.get("stages") or 0)
    return {k: v for k, v in acc.items() if v}


def events_at(trace, turn):
    return [e for e in trace["events"] if (e.get("turn") == turn)]


def attacker_of(trace, unit, turn):
    """turn에 unit을 직격한 무브 이벤트(피격자=unit). 없으면 None."""
    for e in events_at(trace, turn):
        if e.get("action") != "move":
            continue
        if e.get("target") == unit or any(h.get("who") == unit for h in e.get("hits", [])):
            return e
    return None


def own_move_at(trace, unit, turn):
    """turn에 unit이 쓴 무브 이벤트. 없으면 None."""
    for e in events_at(trace, turn):
        if e.get("action") == "move" and e.get("actor") == unit:
            return e
    return None


def switch_around(trace, unit, turn):
    """unit이 turn 또는 turn-1에 등장(switch/drag)했나? (forced 여부 포함)."""
    for e in trace["events"]:
        if e.get("action") in ("switch", "drag") and e.get("actor") == unit \
           and (e.get("turn") in (turn, turn - 1)):
            return {"turn": e.get("turn"), "forced": bool(e.get("forced"))}
    return None


def classify(trace, hbt, sidemap, cell):
    """cell=(turn, unit, kind, logv, engv) → (bucket, reason, detail)."""
    turn, unit, kind, lv, ev = cell
    direction = None
    gap = None
    if kind == "hp" and lv is not None and ev is not None:
        gap = abs(lv - ev)
        direction = "under(엔진 적게)" if lv < ev else "over(엔진 많이)"

    own = own_move_at(trace, unit, turn)
    atk = attacker_of(trace, unit, turn)
    sw = switch_around(trace, unit, turn)
    ub = boosts_before(trace, unit, turn)             # unit 자신의 누적 부스트
    ab = boosts_before(trace, atk["actor"], turn) if atk else {}   # 공격자 누적 부스트

    # hazard 상태(진입 직전 턴 기준)
    side = sidemap.get(unit)
    team = "Ally" if side == "p1" else ("Enemy" if side == "p2" else None)
    haz = None
    if team and hbt:
        haz = (hbt.get(turn - 1) or {}).get(team) or (hbt.get(turn) or {}).get(team)
    haz_active = bool(haz and (haz.get("sr") or haz.get("spikes")))

    detail = {
        "direction": direction, "gap": gap,
        "own_move": own.get("move") if own else None,
        "attacker": (atk.get("actor"), atk.get("move"),
                     [f for f in atk.get("flags", [])]) if atk else None,
        "switch": sw, "hazard": haz, "unit_boosts": ub, "attacker_boosts": ab,
    }

    # ── 분류 우선순위 ──
    # 1) 진입(switch/forced) + hazard → F2 해저드 타이밍
    if sw and haz_active and (kind in ("hp", "faint", "missing")):
        return ("F2(해저드 타이밍)",
                f"{('강제' if sw['forced'] else '자발')}교체 진입(T{sw['turn']}) + "
                f"hazard{ {k:v for k,v in haz.items() if v} } 활성", detail)

    # 2) 방어측 부스트 미추적 → over-damage(NEW 스탯스테이지)
    def_boost = {k: v for k, v in ub.items() if k in DEF_STATS and v > 0}
    if direction and "over" in direction and def_boost:
        return ("NEW(스탯스테이지·방어)",
                f"{unit} 이전 방어부스트 {def_boost} 미추적 → 엔진 과데미지", detail)

    # 3) 공격자 공격부스트 미추적 → under-damage(NEW 스탯스테이지)
    off_boost = {k: v for k, v in ab.items() if k in OFF_STATS and v > 0}
    if direction and "under" in direction and off_boost:
        return ("NEW(스탯스테이지·공격)",
                f"공격자 {atk['actor']} 이전 공격부스트 {off_boost} 미추적 → 엔진 과소데미지",
                detail)

    # 4) recoil / priority·locked 무브 → F3 단건
    moves_here = set()
    if own: moves_here.add(own.get("move"))
    if atk: moves_here.add(atk.get("move"))
    rec = moves_here & RECOIL_MOVES
    pri = moves_here & PRIORITY_LOCKED
    if rec:
        return ("F3(recoil)", f"반동무브 {sorted(rec)} 관여", detail)
    if pri:
        return ("F3(priority/locked)", f"우선도/락드무브 {sorted(pri)} 관여", detail)

    # 5) status / faint without other signal
    if kind == "status":
        return ("status", f"상태이상 불일치 log={lv} eng={ev}", detail)

    # 6) 남은 것
    if gap is not None and gap <= 12 and not (ub or ab):
        return ("노이즈?", "작은 갭·신호 없음(롤/세트 추정)", detail)
    return ("미상", "분류 신호 없음 — 수동 확인 필요", detail)


def main():
    from modules.showdown_trace import parse_replay
    import modules.reference_gen5 as r5
    from modules.fullbattle_run import run_and_diff, build_hazard_by_turn

    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    with open(path, encoding="utf-8") as f:
        trace = parse_replay(f.read())

    pct = any("Percentage" in str(r) for r in trace.get("meta", {}).get("rules", []))
    res = run_and_diff(trace, r5, hp_tol=10, resync=True,
                       hp_mode=("percent" if pct else "absolute"),
                       set_override=XVAL_SET_OVERRIDE)

    hbt = build_hazard_by_turn(trace)
    sidemap = nick_side_map(trace)

    structural = res.get("structural", [])
    allrows = res.get("divergence", [])
    # over-damage 셀(구조적 필터엔 빠짐): hp이면서 log>eng, gap≥12
    over = [r for r in allrows
            if r[2] == "hp" and r[3] is not None and r[4] is not None
            and r[3] > r[4] and abs(r[3] - r[4]) >= 12]

    cells = list(structural) + [r for r in over if r not in structural]

    def gap_of(r):
        return abs((r[3] or 0) - (r[4] or 0)) if r[2] == "hp" else 9999
    cells.sort(key=gap_of, reverse=True)

    print(f"=== [SETUP] {os.path.basename(path)}  HP={'percent' if pct else 'absolute'} ===")
    print(f"구조적(under/faint/status/missing) {len(structural)}건 + "
          f"큰 over-damage {len(over)}건 → 분류 대상 {len(cells)}건\n")

    buckets = {}
    print("=== [CELLS] 크기순 분류 ===")
    for c in cells:
        turn, unit, kind, lv, ev = c
        bucket, reason, d = classify(trace, hbt, sidemap, c)
        buckets.setdefault(bucket, []).append(c)
        g = d.get("gap")
        gtxt = f"gap={g}" if g is not None else f"[{kind}]"
        print(f"\n T{turn:>2} {unit:<12} {kind:<7} log={lv} eng={ev}  {gtxt}  {d.get('direction') or ''}")
        print(f"    ▶ {bucket} — {reason}")
        am = d.get("attacker")
        print(f"    · 자기무브={d.get('own_move')}  피격무브={ (am[1], am[2]) if am else None } (by {am[0] if am else None})")
        print(f"    · 진입={d.get('switch')}  hazard={ {k:v for k,v in (d.get('hazard') or {}).items() if v} }")
        print(f"    · 이전부스트 unit={d.get('unit_boosts')}  attacker={d.get('attacker_boosts')}")

    print("\n=== [요약] 버킷별 집계 ===")
    for b in sorted(buckets, key=lambda k: -len(buckets[k])):
        ts = [f"T{c[0]}:{c[1]}" for c in buckets[b]]
        print(f"  {b:<24} {len(buckets[b]):>2}건  {ts}")

    print("\n=== 다음 행동 가이드 ===")
    print("F2 다수 → 해저드 타이밍 PR이 최대 레버리지(hazard_by_turn[T-1]+forced 교체).")
    print("NEW(스탯스테이지) 존재 → 트레이스-리플레이가 boosts를 엔진 stage로 들고 가야 함(신규 PR).")
    print("F3만 소수 → 단건 무브 처리(반동/우선도)로 마감.")
    print("미상 다수 → 셀별 수동 확인(코퍼스 해당 턴 원문) 필요.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("=== run_cellclass 에러 (트레이스백 전체를 붙여주세요) ===")
        traceback.print_exc()
        sys.exit(1)
