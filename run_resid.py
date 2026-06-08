"""
per-event 데미지 잔차 진단 (연쇄 없음 — 로그의 실제 방어자 HP로 무브별 비교).

역설계→수정 루프의 반복 도구. reference_gen5의 make_char(세트/EV/item 반영) + 데미지식
(base × STAB × 타입 × 크리)으로 무브별 기대치 R을 내고 관측과 비교한다. 엔진을 안 부르므로
어디서든(샌드박스/앱) 돈다. 세트를 고칠 때마다 이걸 돌려 잔차가 [0.85,1.0]로 닫히는지 본다.

    python run_resid.py

obs/R 해석: ~0.85~1.0 정합 / >1.05 과소(SE·STAB·공격EV 미반영, 예: Hidden Power 타입) /
<0.80 과다(방어EV·저항·도구·자기디버프 미반영).
"""
import os
import sys
import math

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
REPLAY = os.path.join(HERE, "Gen5OU-2015-05-11-reymedy-leftiez.html")

# 자기 SpA/Atk 디버프 무브(2번째 사용부터 누적) — 단순 모델: 사용 횟수 n → 단계 -2n.
SELF_DROP = {"Draco Meteor": ("spa", 2), "Superpower": None, "Leaf Storm": ("spa", 2)}


def stage_mult(stages):
    return (2 + stages) / 2 if stages >= 0 else 2 / (2 - stages)


def main():
    from modules.showdown_trace import parse_replay
    import modules.reference_gen5 as r5

    with open(REPLAY, encoding="utf-8") as f:
        trace = parse_replay(f.read())

    def types_of(sp):
        a, b = r5.SPECIES_TYPES.get(sp, ("Normal", ""))
        return [x for x in (a, b) if x]

    def type_mult(at, dts):
        if at is None:
            return 1.0
        row = r5.TYPE.get(at, {})
        m = 1.0
        for dt in dts:
            m *= row.get(dt, 1.0)
        return m

    drops = {}   # (actor, stat) -> 누적 단계(음수)
    print(f"{'T':>3} {'atk':10} {'move':13} {'def':10} {'obs':>5} {'R':>6} {'obs/R':>6} {'eff':>4} {'crit':>4}  flag")
    n = 0
    for e in trace["events"]:
        if e.get("action") != "move":
            continue
        asp = e.get("species")
        mv = e.get("move")
        md = r5.MOVES.get(mv)
        drop = SELF_DROP.get(mv)
        if md and md[0] > 0:
            pw, cat, mtype = md
            if mv == "Hidden Power" and mtype is None:           # 숨김타입: 공격자 세트 hp_type
                mtype = (r5.SETS.get(asp) or {}).get("hp_type")
            for h in e["hits"]:
                if h["who"] == e["actor"] or h.get("delta") is None:
                    continue
                dsp = trace["nick2species"].get(h["who"])
                if asp not in r5.BASE or dsp not in r5.BASE:
                    continue
                atk = r5.make_char(e["actor"], asp)
                dfd = r5.make_char(h["who"], dsp)
                ostat = "atk" if cat == "phys" else "spa"
                off = atk[ostat]
                if drop:
                    off = math.floor(off * stage_mult(drops.get((e["actor"], drop[0]), 0)))
                dfn = dfd["df"] if cat == "phys" else dfd["spd"]
                base = math.floor(math.floor(42 * pw * off / dfn) / 50) + 2
                stab = r5.build_game_config().get("stab_factor", 1.5) if mtype in types_of(asp) else 1.0
                eff = type_mult(mtype, types_of(dsp))
                crit = r5.CRIT_MULT if "crit" in e["flags"] else 1.0
                R = int(base * stab * eff * crit)
                obs = -h["delta"]
                ratio = obs / R if R else 0
                flag = ("HiddenPower(type?)" if mtype is None else
                        f"UNDER x{ratio:.2f}" if ratio > 1.05 else
                        f"OVER x{ratio:.2f}" if ratio < 0.80 else "")
                print(f"{e['turn']:>3} {asp:10} {mv:13} {dsp:10} {obs:>5} {R:>6} "
                      f"{ratio:>6.2f} {eff:>4.1f} {('Y' if crit > 1 else ''):>4}  {flag}")
                n += 1
        # 자기 디버프 누적(이 무브 사용 후)
        if drop:
            drops[(e["actor"], drop[0])] = drops.get((e["actor"], drop[0]), 0) - drop[1]

    print(f"\n총 직격 비교: {n}")
    print("→ flag 없는 줄 = 정합. UNDER/HiddenPower = 타입/공격세트, OVER = 방어세트/저항/도구.")


if __name__ == "__main__":
    main()
