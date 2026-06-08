"""
풀배틀 트레이스 리플레이 — 비교 인프라 (엔진 무관).

정규화 트레이스 IR(showdown_trace.parse_replay 산출)에서 풀배틀 검증의 세 축을 만든다:
- build_action_queue: 로그 순서의 행위자 액션 시퀀스(move + 자발교체) — 엔진에 주입할 대본.
- build_snapshots: 턴 경계마다 전 유닛의 (hp, status, fainted) — 엔진 산출과 대조할 답안지.
- divergence: 라운드별 expected(로그) vs actual(엔진) 대조 — 첫 불일치 격리.

게임/엔진 중립. 이 모듈은 로그에서 '대본'과 '답안지'만 뽑고, 비교만 한다. 엔진을 부르지
않으므로 engine.py truncation 영향권 밖 — 클린룸으로 완결 검증된다(아래 검증 절).
"""


def build_action_queue(trace):
    """로그 순서대로 행위자 액션(move / 자발교체) 시퀀스를 반환.

    forced(drag = 기절구동 강제교체)는 엔진이 자체 처리하므로 제외 — 자발교체만 주입 대상.
    각 액션: {turn, side, actor, kind('move'|'switch'), move/target | species}.
    """
    q = []
    for e in trace["events"]:
        a = e.get("action")
        if a == "move":
            q.append({"turn": e["turn"], "side": e.get("actor_side"),
                      "actor": e["actor"], "kind": "move",
                      "move": e["move"], "target": e.get("target")})
        elif a == "switch" and not e.get("forced"):
            q.append({"turn": e["turn"], "side": e.get("actor_side"),
                      "actor": e["actor"], "kind": "switch",
                      "species": e.get("species")})
    return q


def build_snapshots(trace):
    """턴 경계마다 등장 유닛의 (hp, status, fainted) 누적 스냅샷.

    각 턴의 *끝* 상태(그 턴까지 마지막으로 관측된 값)를 기록. turn 0(리드 등장)부터 포함.
    반환: {turn: {nick: {'hp', 'status', 'fainted'}}}.
    """
    hp = {}
    st = {}
    fnt = set()
    snaps = {}

    def apply(e):
        a = e.get("action")
        if a in ("switch", "drag"):
            n = e["actor"]
            if e.get("hp") is not None:
                hp[n] = e["hp"]
            if e.get("status"):
                st[n] = e["status"]
            fnt.discard(n)               # 재등장 = 생존
        elif a == "move":
            for h in e.get("hits", []):
                if h.get("cur") is not None:
                    hp[h["who"]] = h["cur"]
            for w in e.get("faints", []):
                hp[w] = 0
                fnt.add(w)
                st.pop(w, None)
        elif a == "env":
            if e.get("cur") is not None:
                hp[e["who"]] = e["cur"]
        elif a == "faint":
            hp[e["who"]] = 0
            fnt.add(e["who"])
            st.pop(e["who"], None)
        elif a == "status":
            if e.get("status"):
                st[e["who"]] = e["status"]      # -status: 비휘발 상태 부여(이후 턴 carry)
            else:
                st.pop(e["who"], None)           # -curestatus: 해제

    def snapshot():
        return {n: {"hp": hp.get(n), "status": st.get(n), "fainted": n in fnt}
                for n in hp}

    last = None
    for e in trace["events"]:
        tn = e.get("turn")
        if tn is None:
            continue
        if last is not None and tn != last:
            snaps[last] = snapshot()
        apply(e)
        last = tn
    if last is not None:
        snaps[last] = snapshot()
    return snaps


def divergence(expected, actual, hp_tol=0):
    """라운드별 expected(로그) vs actual(엔진) 상태 대조. 전 불일치를 (turn 오름차순) 보고.

    expected/actual: build_snapshots 형식. hp_tol: HP 허용 오차(데미지 롤 흡수, 기본 0).
    반환: [(turn, nick, kind, expected_val, actual_val)] — kind ∈
    {'missing','faint','hp','status'}.
    """
    out = []
    for tn in sorted(expected):
        ex = expected[tn]
        ac = actual.get(tn, {})
        for n, exv in ex.items():
            acv = ac.get(n)
            if acv is None:
                out.append((tn, n, "missing", exv, None))
                continue
            if exv.get("fainted") != acv.get("fainted"):
                out.append((tn, n, "faint", exv.get("fainted"), acv.get("fainted")))
            eh, ah = exv.get("hp"), acv.get("hp")
            if eh is not None and ah is not None and abs(eh - ah) > hp_tol:
                out.append((tn, n, "hp", eh, ah))
            if exv.get("status") != acv.get("status"):
                out.append((tn, n, "status", exv.get("status"), acv.get("status")))
    return out
