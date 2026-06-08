"""
풀배틀 리플레이 B4 실행 + 진단 스크립트.

프로젝트 루트(modules/ 와 gen5 리플레이 html이 있는 폴더)에서:
    python run_b4.py
engine.py 전체가 온전한 환경에서 돌려야 한다.

이 버전은 raw HP 스냅샷 덤프 대신 *데미지 delta 진단*을 낸다:
- turn 0(리드 셋업, 엔진 미발생) 제외.
- 데미지가 실제 난 (턴, 유닛)만 로그 delta vs 엔진 delta 비교 → carry-forward 노이즈 제거.
- 각 줄에 그 턴 그 유닛에 무슨 일이 있었는지(누가 무슨 무브로) 붙여 잔차 원인을 가리킴.
출력 전체를 대화창에 붙여주면 첫 실질 divergence(=다음 수정 타깃)를 함께 읽는다.
"""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
REPLAY = os.path.join(HERE, "Gen5OU-2015-05-11-reymedy-leftiez.html")


def main():
    from modules.showdown_trace import parse_replay
    from modules.fullbattle_run import run_and_diff
    from modules.battle_setup import build_trace_actions
    import modules.reference_gen5 as r5

    with open(REPLAY, encoding="utf-8") as f:
        trace = parse_replay(f.read())

    res = run_and_diff(trace, r5, hp_tol=10, resync=True)
    log = res["log"]            # {turn: {nick: {hp,status,fainted}}}
    eng = res["engine"]         # {turn: {nick: {hp,status,fainted}}}
    ta = build_trace_actions(trace, r5)

    # 무브 사건 인덱스: 각 (turn, defender) → (attacker, move) (그 턴 그 유닛이 맞은 무브)
    hit_by = {}
    for (tn, actor), mv in ta["move_actions"].items():
        if mv.get("target"):
            hit_by[(tn, mv["target"])] = (actor, mv["move"]["name"])

    turns = sorted(t for t in log if t >= 1)
    all_nicks = set()
    for t in log:
        all_nicks |= set(log[t])

    def hp_at(snaps, t, nick):
        # t시점 그 유닛 hp(없으면 직전 값/풀피). t=0은 풀피로 간주(리드/예비 진입 전).
        return (snaps.get(t, {}).get(nick) or {}).get("hp")

    print("=== 풀배틀 데미지 delta 진단 (turn>=1, 데미지 난 셀만) ===")
    print(f"{'T':>3} {'unit':12} {'logΔ':>6} {'engΔ':>6} {'logHP':>6} {'engHP':>6}  사건")
    first_div = None
    rows = 0
    for t in turns:
        prev = t - 1
        for nick in sorted(all_nicks):
            lh, ph = hp_at(log, t, nick), hp_at(log, prev, nick)
            eh = hp_at(eng, t, nick)
            if lh is None or ph is None:
                continue
            log_d = lh - ph
            # resync 모드: 진입 baseline은 log[prev]로 동일 → engΔ = eng[t] - log[prev]
            eng_d = (eh - ph) if eh is not None else None
            # 데미지/회복이 실제 난 셀만(로그 기준 변화)
            if log_d == 0:
                continue
            ev = hit_by.get((t, nick))
            evs = f"{ev[0]}→{nick} {ev[1]}" if ev else ""
            mark = ""
            if eng_d is None:
                mark = "★(엔진 무변화)"
            elif abs(log_d - eng_d) > 10:
                mark = "★"
            if mark and first_div is None:
                first_div = (t, nick, log_d, eng_d, evs)
            print(f"{t:>3} {nick:12} {log_d:>6} {str(eng_d):>6} "
                  f"{str(lh):>6} {str(eh):>6}  {mark}{evs}")
            rows += 1

    print("\n----")
    print(f"비교한 데미지 셀: {rows}")
    if first_div:
        t, nick, ld, ed, evs = first_div
        print(f"[첫 실질 divergence] T{t} {nick}: 로그Δ={ld} 엔진Δ={ed}  ({evs})")
    else:
        print("[첫 실질 divergence] 없음 — 데미지 delta 전부 ±10 이내")

    # 승패·턴 수
    print(f"엔진 마지막 캡처 턴: {max(eng) if eng else '없음'} / 로그 마지막 턴: {max(log)}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("=== 실행 에러 (트레이스백 전체를 붙여주세요) ===")
        traceback.print_exc()
        sys.exit(1)
