"""NEW 스탯스테이지 진단 — 트레이스의 명시 boosts가 엔진 stat-stage로 들어가는지 가른다.

배경: 분류에서 NEW(스탯스테이지) 3셀(T24·T25 Scrafty 방어부스트, T29 Reuniclus 공격자 부스트).
엔진은 stat-stage 기계(active_states + get_effective_stat의 percent 배율)를 이미 갖췄으나,
부스트 무브(Bulk Up·Swords Dance·Calm Mind·Amnesia)는 reference_gen5 MOVES엔 (0,'status',None)로
'존재'할 뿐 효과가 없고, move_effects는 step2(UI) 경로에서만 생성된다 → 트레이스-리플레이
game_config엔 부스트 스펙이 없어 _apply_move_effects가 no-op → 부스트 미반영.

이 진단이 가르는 것:
  [A] 트레이스-리플레이 game_config의 move_effects에 부스트무브가 있나 (없을 것).
  [B] 트레이스 boosts_by_turn(누적, 교체 시 리셋) — 주입할 ground truth.
  [C] 런타임: _apply_move_effects가 부스트무브에서 실제로 뭔가 적용하나 (안 할 것).
  [D] NEW 셀의 divergence가 기대 stage 배율과 맞나(예: Atk+2=×2.0).

앱사이드 실행: python run_boostdiag.py [코퍼스.html]   (출력 전체를 붙여주세요)
일회용 진단(지워도 무방)."""
import os, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
DEFAULT = os.path.join(HERE, "Gen5OU-2026-newatmons-bantyranitar.html")

XVAL_SET_OVERRIDE = {
    'Garchomp': {'nature': 'Jolly', 'evs': (0, 252, 0, 0, 4, 252),
                 'item': None, 'ability': 'Rough Skin'},
}
BOOST_MOVES = {"Bulk Up", "Swords Dance", "Calm Mind", "Amnesia", "Dragon Dance",
               "Nasty Plot", "Iron Defense", "Cosmic Power", "Quiver Dance",
               "Coil", "Hone Claws", "Curse", "Agility", "Rock Polish"}
MAIN_STATS = {"atk", "def", "spa", "spd", "spe"}
APPLIED = []   # _apply_move_effects 호출 관찰


def _norm_stat(s):
    s = (s or "").lower()
    return {"attack": "atk", "defense": "def"}.get(s, s)


def stage_mult(n):
    """gen5 일반스탯 stage 배율: n>=0 → (2+n)/2, n<0 → 2/(2-n)."""
    return (2 + n) / 2.0 if n >= 0 else 2.0 / (2 - n)


def build_boosts_by_turn(trace):
    """트레이스 → {turn: {nick: {stat: net_stages}}}. 누적이되, 교체(switch/drag)로
    필드를 떠난 유닛은 stage 리셋(gen5 룰), 새 진입 유닛은 빈 stage로 시작."""
    onfield = {}        # side -> 현재 on-field nick
    acc = {}            # nick -> {stat: stages}
    by_turn = {}
    last = None
    for e in trace["events"]:
        tn = e.get("turn")
        if tn is None:
            continue
        if last is not None and tn != last:
            by_turn[last] = {n: dict(acc.get(n, {})) for n in onfield.values()
                             if acc.get(n)}
        a = e.get("action")
        if a in ("switch", "drag"):
            side = e.get("actor_side"); inc = e.get("actor")
            prev = onfield.get(side)
            if prev is not None and prev != inc:
                acc[prev] = {}          # 떠난 유닛 stage 리셋
            acc[inc] = {}               # 진입 유닛 새 stage
            onfield[side] = inc
        elif a == "move":
            for b in e.get("boosts", []):
                who = b.get("who"); st = _norm_stat(b.get("stat"))
                if who and st:
                    acc.setdefault(who, {})
                    acc[who][st] = acc[who].get(st, 0) + (b.get("stages") or 0)
        last = tn
    if last is not None:
        by_turn[last] = {n: dict(acc.get(n, {})) for n in onfield.values()
                         if acc.get(n)}
    return by_turn


def main():
    from modules.showdown_trace import parse_replay
    import modules.reference_gen5 as r5
    import modules.engine as eng
    from modules.fullbattle_run import setup_for_engine, run_and_diff

    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    with open(path, encoding="utf-8") as f:
        trace = parse_replay(f.read())
    pct = any("Percentage" in str(r) for r in trace.get("meta", {}).get("rules", []))

    # ── [A] 트레이스-리플레이 game_config의 move_effects ──
    ally, enemy, gc, spec = setup_for_engine(trace, r5, set_override=XVAL_SET_OVERRIDE)
    me = gc.get("move_effects") or {}
    print("=== [A] 트레이스-리플레이 game_config.move_effects ===")
    print(f"move_effects 키 수: {len(me)}")
    present = sorted(set(me) & BOOST_MOVES)
    absent = sorted(BOOST_MOVES & {e["move"] for e in trace["events"]
                                   if e.get("action") == "move" and e.get("move")} - set(me))
    print(f"  부스트무브 중 등록됨: {present or '(없음)'}")
    print(f"  트레이스에 나오나 move_effects에 없음: {absent or '(없음)'}")

    # ── [B] 트레이스 boosts_by_turn(누적/리셋) ──
    bbt = build_boosts_by_turn(trace)
    print("\n=== [B] 트레이스 boosts_by_turn (누적, 교체 시 리셋) ===")
    for t in sorted(bbt):
        if bbt[t]:
            cells = {n: {s: f"{v:+d}(×{stage_mult(v):.2f})" for s, v in d.items()
                         if s in MAIN_STATS}
                     for n, d in bbt[t].items()}
            cells = {n: d for n, d in cells.items() if d}
            if cells:
                print(f"  T{t:>2}: {cells}")

    # ── [C] 런타임: _act_move_effect가 부스트무브에 뭔가 적용하나 (레지스트리 override) ──
    _orig = eng._act_move_effect
    def _wrap(ctx):
        mv = (ctx.get("current_move") or {}).get("name")
        before = len((ctx.get("active_char") or {}).get("active_states", []))
        _orig(ctx)
        after = len((ctx.get("active_char") or {}).get("active_states", []))
        if mv in BOOST_MOVES:
            APPLIED.append((ctx.get("turn"), (ctx.get("active_char") or {}).get("id"),
                            mv, after - before))
    eng.DEFAULT_ACTION_REGISTRY.register("ON_MOVE_EFFECT", _wrap, override=True)

    res = run_and_diff(trace, r5, hp_tol=10, resync=True,
                       hp_mode=("percent" if pct else "absolute"),
                       set_override=XVAL_SET_OVERRIDE)

    print("\n=== [C] 런타임: 부스트무브 사용 시 active_states 증가량 ===")
    if not APPLIED:
        print("  (부스트무브가 _apply_move_effects 경로를 한 번도 안 탐 — 또는 사용 안 됨)")
    for t, cid, mv, delta in APPLIED:
        flag = "←미적용!" if delta == 0 else ""
        print(f"  T{t} {cid} {mv}: active_states +{delta} {flag}")

    # ── [D] NEW 셀 대조 ──
    print("\n=== [D] NEW 스탯스테이지 셀 대조 ===")
    targets = [(24, "Scrafty"), (25, "Scrafty"), (29, "Reuniclus")]
    for t, unit in targets:
        lg = (res["log"].get(t) or {}).get(unit)
        en = (res["engine"].get(t) or {}).get(unit)
        bz = bbt.get(t, {})
        # 그 턴 unit 자신/공격자 stage
        own = bz.get(unit, {})
        print(f"  T{t} {unit}: log={lg.get('hp') if lg else '-'} "
              f"eng={en.get('hp') if en else '-'}  자기stage={own or '{}'}  "
              f"필드stage={ {n:d for n,d in bz.items() if n!=unit} }")

    print("\n=== 판정 가이드 ===")
    print("[A] 부스트무브가 move_effects에 없음 + [C] active_states +0 → 부스트 미반영 확정.")
    print("[B]가 주입할 ground truth(stage·배율). 교체 리셋이 맞는지 눈으로 확인.")
    print("[D] divergence가 기대 배율과 맞으면(예: 공격자 Atk+2 → 엔진 데미지 ½) stage 원인 확정.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("=== run_boostdiag 에러 (트레이스백 전체를 붙여주세요) ===")
        traceback.print_exc()
        sys.exit(1)
