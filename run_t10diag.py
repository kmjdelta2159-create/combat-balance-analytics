"""T10 진단 — Garchomp이 Abomasnow Ice Shard(Ice, 4×SE on Dragon/Ground)에 과소 데미지받는
원인을 가른다. 크기상 엔진이 거의 중립(1×)을 적용하는 듯(log=21 took~79 vs eng=82 took~18≈79/4).

후보 셋:
  (가) 타입배율 1× — Garchomp gimmicks의 타입이 gc type_columns로 안 읽혀 _move_type_multiplier가
       4× 대신 1× 반환.
  (나) 공격 미처리 — Abomasnow Ice Shard(우선도+1) 액션이 T10에 엔진서 처리 안 됨(순서/우선도/
       트레이스 액션 누락) → Garchomp이 그 히트를 아예 안 받음.
  (다) raw_dmg 문제 — 배율은 맞는데 기초 데미지가 작음.

방법(원본 무수정): ELEMENT_MULT·DAMAGE_CALC를 레지스트리 래핑해 T10 Garchomp 피격 경로만 관찰.
앱사이드 실행: python run_t10diag.py [코퍼스.html]   (출력 전체를 붙여주세요). 일회용."""
import os, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
DEFAULT = os.path.join(HERE, "Gen5OU-2026-newatmons-bantyranitar.html")

XVAL_SET_OVERRIDE = {
    'Garchomp': {'nature': 'Jolly', 'evs': (0, 252, 0, 0, 4, 252),
                 'item': None, 'ability': 'Rough Skin'},
}
HITS = []


def _is_garchomp(c):
    return c and "Garchomp" in str(c.get("id", ""))


def main():
    from modules.showdown_trace import parse_replay
    import modules.reference_gen5 as r5
    import modules.engine as eng
    from modules.fullbattle_run import setup_for_engine, run_and_diff

    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    with open(path, encoding="utf-8") as f:
        trace = parse_replay(f.read())
    pct = any("Percentage" in str(r) for r in trace.get("meta", {}).get("rules", []))

    # ── [A] 트레이스: T10 전후 Garchomp 관련 사건 ──
    print("=== [A] 트레이스 T9~T11 사건(move/switch) ===")
    for e in trace["events"]:
        if e.get("turn") in (9, 10, 11) and e.get("action") in ("move", "switch", "drag"):
            if e.get("action") == "move":
                hits = [(h.get("who"), h.get("delta")) for h in e.get("hits", [])]
                print(f"  T{e['turn']} move {e.get('actor')}→{e.get('target')} "
                      f"{e.get('move')} flags={e.get('flags')} hits={hits}")
            else:
                print(f"  T{e['turn']} {e['action']} {e.get('actor')} ({e.get('species')})")

    # ── [B] 엔진 셋업: Garchomp gimmicks 타입 + gc type_columns/Ice행 ──
    ally, enemy, gc, spec = setup_for_engine(trace, r5, set_override=XVAL_SET_OVERRIDE)
    gar = next((p for p in (ally + enemy) if _is_garchomp(p)), None)
    print("\n=== [B] 엔진 셋업 ===")
    print(f"  type_columns = {gc.get('type_columns')}")
    print(f"  type_table['Ice'] = {(gc.get('type_table') or {}).get('Ice')}")
    if gar:
        g = gar.get("gimmicks", {})
        cols = gc.get("type_columns", [])
        print(f"  Garchomp gimmicks 타입칸: { {c: g.get(c) for c in cols} }")
        print(f"  Garchomp gimmicks 키(타입관련): "
              f"{ {k: v for k, v in g.items() if 't' == k or 'type' in k.lower() or k in ('t1','t2')} }")

    # ── [C] 런타임: ELEMENT_MULT·DAMAGE_CALC 래핑(Garchomp 피격만) ──
    _o_em = eng._act_element_mult
    def _w_em(ctx):
        t = ctx.get("current_target"); mv = ctx.get("current_move") or {}
        dmg_before = ctx.get("dmg")
        _o_em(ctx)
        if _is_garchomp(t):
            HITS.append(("EM", ctx.get("turn"), (ctx.get("active_char") or {}).get("id"),
                         mv.get("name"), mv.get("type"),
                         (t or {}).get("gimmicks", {}),
                         ctx.get("elem_mult"), dmg_before, ctx.get("dmg")))
    eng.DEFAULT_ACTION_REGISTRY.register("ELEMENT_MULT", _w_em, override=True)

    _o_dc = eng._act_damage_calc
    def _w_dc(ctx):
        _o_dc(ctx)
        t = ctx.get("current_target"); mv = ctx.get("current_move") or {}
        if _is_garchomp(t):
            HITS.append(("DC", ctx.get("turn"), (ctx.get("active_char") or {}).get("id"),
                         mv.get("name"), mv.get("type"), None,
                         ctx.get("elem_mult"), ctx.get("raw_dmg"), ctx.get("dmg")))
    eng.DEFAULT_ACTION_REGISTRY.register("DAMAGE_CALC", _w_dc, override=True)

    res = run_and_diff(trace, r5, hp_tol=10, resync=True,
                       hp_mode=("percent" if pct else "absolute"),
                       set_override=XVAL_SET_OVERRIDE)

    print("\n=== [C] 런타임: Garchomp 피격 경로(EM=ElementMult, DC=DamageCalc) ===")
    if not HITS:
        print("  (Garchomp 피격이 한 번도 데미지 경로에 안 들어옴 → 공격 미처리(후보 나) 강함)")
    for h in HITS:
        kind, turn, atk, mv, mtype, gim, em, b, a = h
        extra = ""
        if kind == "EM" and gim is not None:
            cols = gc.get("type_columns", [])
            extra = f" 방어타입칸={ {c: gim.get(c) for c in cols} }"
        print(f"  [{kind}] T{turn} {atk}→Garchomp {mv}({mtype}) elem_mult={em} "
              f"dmg {b}→{a}{extra}")

    print("\n=== [D] T10 Garchomp HP (로그 vs 엔진) ===")
    for t in (9, 10, 11):
        lg = (res["log"].get(t) or {}).get("Garchomp")
        en = (res["engine"].get(t) or {}).get("Garchomp")
        print(f"  T{t}: log={lg.get('hp') if lg else '-'} eng={en.get('hp') if en else '-'}")

    print("\n=== 판정 가이드 ===")
    print("[C]에 T10 Ice Shard→Garchomp EM이 없음 → 공격 미처리(후보 나): 우선도/순서/트레이스액션.")
    print("EM 있는데 elem_mult=1.0(4.0 아님) → 타입배율 손실(후보 가): type_columns/gimmicks 타입칸.")
    print("elem_mult=4.0인데 dmg 작음 → raw_dmg(후보 다): 스탯/위력/공식.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("=== run_t10diag 에러 (트레이스백 전체를 붙여주세요) ===")
        traceback.print_exc()
        sys.exit(1)
