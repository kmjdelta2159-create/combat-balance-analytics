"""F2 진단 — 진입 해저드가 실제로 발화하는지, 어느 hazard_by_turn 윈도우(T vs T-1)를
읽는지, 자발/forced 교체 양쪽에서 도는지를 한 번에 가른다.

배경: 분류 결과 under-application 셀(T9 Abomasnow·T10/T11 Jirachi·T11 Gliscor)은 *자발*
교체인데도 엔진이 진입 해저드를 0으로 처리(eng=full). 평결의 'forced 미적용' 모델과 어긋남.
정적 Read로는 _fire_switch_in→_apply_entry_hazard 경로가 도는 *것처럼* 보이지만, resync가
on_field을 직접 세팅하면 switch 액션이 생략돼 _fire_switch_in이 안 불릴 수 있다. 런타임으로 확정.

방법(원본 무수정): engine 모듈전역 _apply_entry_hazard·_fire_switch_in을 래핑해 호출을
관찰. 턴은 resync(on_round_start) 래핑으로 추적. 트레이스 onfield 델타로 '기대 진입집합 +
T-1 해저드'를 독립 계산해 관찰과 대조.

앱사이드 실행: python run_f2diag.py [코퍼스.html]   (출력 전체를 붙여주세요)
일회용 진단(지워도 무방)."""
import os, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
DEFAULT = os.path.join(HERE, "Gen5OU-2026-newatmons-bantyranitar.html")

XVAL_SET_OVERRIDE = {
    'Garchomp': {'nature': 'Jolly', 'evs': (0, 252, 0, 0, 4, 252),
                 'item': None, 'ability': 'Rough Skin'},
}

STATE = {"turn": None}
FIRES = []   # _apply_entry_hazard 발화 기록
ENTERS = []  # _fire_switch_in 진입 기록(해저드 0 포함)


def main():
    from modules.showdown_trace import parse_replay
    import modules.reference_gen5 as r5
    import modules.fullbattle_run as fr
    import modules.engine as eng
    from modules.fullbattle_run import (run_and_diff, build_hazard_by_turn,
                                        build_onfield_timeline)
    from modules.resource import get_current, get_max

    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    with open(path, encoding="utf-8") as f:
        trace = parse_replay(f.read())
    pct = any("Percentage" in str(r) for r in trace.get("meta", {}).get("rules", []))

    # ── 턴 추적: _make_resync가 만든 on_round_start 훅을 래핑 ──
    _orig_mr = fr._make_resync
    def _mr_patched(*a, **k):
        hook = _orig_mr(*a, **k)
        def wrapped(turn, participants):
            STATE["turn"] = turn
            return hook(turn, participants)
        return wrapped
    fr._make_resync = _mr_patched

    # ── 진입 해저드 발화 래핑 ──
    _orig_aeh = eng._apply_entry_hazard
    def _aeh_wrap(char, participants, game_config, add_log, field_state=None):
        before = get_current(char)
        _orig_aeh(char, participants, game_config, add_log, field_state)
        after = get_current(char)
        fh = (field_state or {}).get("hazard")
        FIRES.append({"turn": STATE["turn"], "id": char.get("id"),
                      "team": char.get("team"), "field_hazard": fh,
                      "lost": before - after, "before": before, "after": after})
    eng._apply_entry_hazard = _aeh_wrap

    _orig_fsi = eng._fire_switch_in
    def _fsi_wrap(char, participants, game_config, add_log, field_state=None):
        ENTERS.append({"turn": STATE["turn"], "id": char.get("id"),
                       "field_hazard": (field_state or {}).get("hazard")})
        _orig_fsi(char, participants, game_config, add_log, field_state)
    eng._fire_switch_in = _fsi_wrap

    # ── 독립 기대 계산: 트레이스 onfield 델타 → 턴별 신규 진입 + T-1 해저드 ──
    onf = build_onfield_timeline(trace)        # {turn: set(nick on field)}
    hbt = build_hazard_by_turn(trace)          # {turn: {team: {sr,spikes}}}
    s2t = {"p1": "Ally", "p2": "Enemy"}
    nick_side = {}
    for e in trace["events"]:
        if e.get("actor_side") and e.get("actor") and e["actor"] not in nick_side:
            nick_side[e["actor"]] = e["actor_side"]
    maxt = max(onf) if onf else 0
    expected = []   # (turn, nick, team, hz_at_T-1)
    for t in range(1, maxt + 1):
        prev = onf.get(t - 1, set())
        entered = onf.get(t, set()) - prev
        for nick in sorted(entered):
            team = s2t.get(nick_side.get(nick))
            hz_prev = (hbt.get(t - 1) or {}).get(team) if team else None
            hz_cur = (hbt.get(t) or {}).get(team) if team else None
            expected.append((t, nick, team, hz_prev, hz_cur))

    # ── 풀런 ──
    res = run_and_diff(trace, r5, hp_tol=10, resync=True,
                       hp_mode=("percent" if pct else "absolute"),
                       set_override=XVAL_SET_OVERRIDE)

    print(f"=== [SETUP] {os.path.basename(path)} HP={'percent' if pct else 'absolute'} ===")
    print(f"구조적 divergence {len(res.get('structural', []))}건\n")

    print("=== [A] 기대 진입(트레이스 onfield 델타) + T-1/T 해저드 ===")
    for t, nick, team, hzp, hzc in expected:
        act = lambda d: {k: v for k, v in (d or {}).items() if v}
        print(f"  T{t:>2} {nick:<12} team={team}  T-1해저드={act(hzp)}  T해저드={act(hzc)}")

    print("\n=== [B] 관찰: _fire_switch_in 진입 호출 ===")
    if not ENTERS:
        print("  (없음 — resync가 switch 액션을 생략해 진입 콜백이 전혀 안 불렸을 가능성)")
    for r in ENTERS:
        fh = {k: v for k, v in (r["field_hazard"] or {}).items() if v} if isinstance(r["field_hazard"], dict) else r["field_hazard"]
        print(f"  T{r['turn']} {r['id']:<12} field_state.hazard={fh}")

    print("\n=== [C] 관찰: _apply_entry_hazard 발화(실데미지) ===")
    if not FIRES:
        print("  (없음 — 진입 해저드가 한 번도 적용되지 않음)")
    for r in FIRES:
        fh = {k: v for k, v in (r["field_hazard"] or {}).items() if v} if isinstance(r["field_hazard"], dict) else r["field_hazard"]
        print(f"  T{r['turn']} {r['id']:<12} field_hazard={fh}  lost={round(r['lost'],1)} "
              f"({round(r['before'],1)}→{round(r['after'],1)})")

    print("\n=== [D] 대조: 기대 진입 vs 발화 ===")
    fired_keys = {(r["turn"], r["id"]) for r in FIRES if r["lost"] > 0}
    enter_keys = {(r["turn"], r["id"]) for r in ENTERS}
    for t, nick, team, hzp, hzc in expected:
        hz_present = bool(hzp and (hzp.get("sr") or hzp.get("spikes")))
        called = (t, nick) in enter_keys
        fired = (t, nick) in fired_keys
        # 자발 진입은 그 턴 콜백, forced 진입은 직전 턴에 콜백될 수 있어 ±1 허용 매칭
        if not called:
            called = any(abs(k[0]-t) <= 1 and k[1] == nick for k in enter_keys)
        if not fired:
            fired = any(abs(k[0]-t) <= 1 and k[1] == nick for k in fired_keys)
        verdict = ("OK" if (not hz_present or fired)
                   else ("미발화(콜백O)" if called else "미발화(콜백X)"))
        print(f"  T{t:>2} {nick:<12} T-1해저드={'있음' if hz_present else '없음'}  "
              f"콜백={'O' if called else 'X'}  발화={'O' if fired else 'X'}  → {verdict}")

    print("\n=== 판정 가이드 ===")
    print("기대 진입에 'T-1해저드=있음'인데 발화=X → 그게 under-application 셀의 원인.")
    print("  콜백X = resync가 on_field 직접세팅으로 switch 액션/콜백을 생략(하니스 측 수정).")
    print("  콜백O·발화X = field_state.hazard가 그 시점 비어있음/엔진 게이트(엔진 측 수정).")
    print("발화가 'T해저드'만 보고 'T-1해저드'와 다르면 → 윈도우 오프바이원(T vs T-1).")
    print("T4/T5 over: 기대 진입 아님인데 발화 있음 → 과적용(진입 아닌 유닛에 해저드).")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("=== run_f2diag 에러 (트레이스백 전체를 붙여주세요) ===")
        traceback.print_exc()
        sys.exit(1)
