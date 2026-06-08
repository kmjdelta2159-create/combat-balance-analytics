"""F1 진단 — Seismic Toss fixed_damage가 (1) 무브 액션에 붙는지, (2) 올바른 (turn,actor)
키인지, (3) 엔진이 실제로 그 무브에서 _act_damage_calc에 도달해 100을 내는지를 한 번에 가른다.
앱사이드 실행: python run_f1diag.py   (출력 전체를 붙여주세요)
원본 코드 수정 없음 — 레지스트리 몽키패치로 런타임만 관찰."""
import os, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
DEFAULT = os.path.join(HERE, "Gen5OU-2026-newatmons-bantyranitar.html")


def main():
    from modules.showdown_trace import parse_replay
    import modules.reference_gen5 as r5
    from modules.battle_setup import build_trace_actions
    from modules.fullbattle_run import setup_for_engine

    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    with open(path, encoding="utf-8") as f:
        trace = parse_replay(f.read())

    # ── 가설1: build_trace_actions의 Seismic Toss 액션에 fixed_damage가 붙는가 ──
    print("=== [A] 데이터 검사: reference_gen5 ===")
    print(f"FIXED_DAMAGE_MOVES = {getattr(r5, 'FIXED_DAMAGE_MOVES', '<없음!>')}")
    print(f"MOVES['Seismic Toss'] = {r5.MOVES.get('Seismic Toss')}")

    ta = build_trace_actions(trace, r5)
    ma = ta["move_actions"]
    st_keys = [(k, v) for k, v in ma.items()
               if (v.get("move") or {}).get("name") == "Seismic Toss"]
    print(f"\n=== [B] build_trace_actions: Seismic Toss 무브 액션 {len(st_keys)}건 ===")
    for k, v in sorted(st_keys, key=lambda kv: kv[0][0]):
        mv = v.get("move") or {}
        print(f"  키(turn,actor)={k}  target={v.get('target')}  "
              f"fixed_damage={mv.get('fixed_damage')}  cat={mv.get('category')}  type={mv.get('type')}")

    # 참가자 id (engine char id) — move_actions의 actor와 매칭되는지 비교용
    ally, enemy, gc, spec = setup_for_engine(trace, r5)
    print(f"\n=== [C] 참가자 id (엔진 char.id) ===")
    print(f"  {[p.get('id') for p in (ally + enemy)]}")

    # ── 런타임 훅: TARGET_SELECT / DAMAGE_CALC를 래핑해 Seismic Toss 경로 관찰 ──
    import modules.engine as eng
    _orig_ts = eng._act_target_select
    _orig_dc = eng._act_damage_calc

    def _wrap_ts(ctx):
        _orig_ts(ctx)
        tm = ctx.get("_trace_move") or {}
        if tm.get("name") == "Seismic Toss":
            tgts = ctx.get("targets") or []
            print(f"  [TGT] turn={ctx.get('turn')} actor={(ctx.get('active_char') or {}).get('id')} "
                  f"ST found, fixed_damage={tm.get('fixed_damage')} targets={[t.get('id') for t in tgts]}")

    def _wrap_dc(ctx):
        mv = ctx.get("current_move") or {}
        _orig_dc(ctx)
        if mv.get("name") == "Seismic Toss":
            print(f"  [DMG] turn={ctx.get('turn')} {(ctx.get('active_char') or {}).get('id')}"
                  f"→{(ctx.get('current_target') or {}).get('id')} "
                  f"fixed_damage={mv.get('fixed_damage')} dmg={ctx.get('dmg')} flag={ctx.get('fixed_damage')}")

    eng.DEFAULT_ACTION_REGISTRY.register("TARGET_SELECT", _wrap_ts, override=True)
    eng.DEFAULT_ACTION_REGISTRY.register("DAMAGE_CALC", _wrap_dc, override=True)

    print(f"\n=== [D] 런타임 — run_and_diff 실행, Seismic Toss 경로 추적 ===")
    pct = any("Percentage" in str(r) for r in trace.get("meta", {}).get("rules", []))
    XVAL_SET_OVERRIDE = {
        'Garchomp': {'nature': 'Jolly', 'evs': (0, 252, 0, 0, 4, 252), 'item': None, 'ability': 'Rough Skin'},
    }
    from modules.fullbattle_run import run_and_diff
    res = run_and_diff(trace, r5, hp_tol=10, resync=True,
                       hp_mode=("percent" if pct else "absolute"),
                       set_override=XVAL_SET_OVERRIDE)

    print(f"\n=== [E] Seismic Toss 턴 전후 HP (로그 vs 엔진) ===")
    print(f"구조적 divergence 총 {len(res.get('structural', []))}건")
    for unit in ["Skarmory", "Scrafty"]:
        print(f"--- {unit} ---")
        for t in range(18, 25):
            lg = (res["log"].get(t) or {}).get(unit)
            en = (res["engine"].get(t) or {}).get(unit)
            if lg or en:
                lh = lg.get("hp") if lg else "-"
                eh = en.get("hp") if en else "-"
                mark = "" if (lg and en and abs((lg.get("hp") or 0) - (en.get("hp") or 0)) <= 10) else "  ← 불일치"
                print(f"  T{t}: log={lh} eng={eh}{mark}")

    print("\n=== 판정 가이드 ===")
    print("[B]에 fixed_damage=100이 없으면 → 데이터 미부착(battle_setup/FIXED_DAMAGE_MOVES).")
    print("[D]에 [TGT]가 안 뜨면 → 엔진이 그 턴에 Seismic Toss 무브 액션을 못 찾음(turn/actor 키 불일치).")
    print("[TGT]는 뜨는데 [DMG]가 안 뜨면 → 타겟 없음 또는 데미지 단계 스킵.")
    print("[DMG] dmg가 100이 아니면 → override 미발동(flag/fixed_damage 확인).")
    print("[DMG] dmg=100인데 출력 안 바뀌면 → F1은 정상, divergence는 resync/턴-인덱스 해석 문제.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("=== run_f1diag 에러 (트레이스백 전체를 붙여주세요) ===")
        traceback.print_exc()
        sys.exit(1)
