"""교차검증 run — held-out gen5 리플레이에 일반 스키마를 던져 과적합을 잰다.
패스1: 데이터-니즈(BASE/MOVES/SETS 결측) 리포트 + (데이터 충분 시) 퍼센트HP-aware 풀런.
프로젝트 루트에서: python run_xval.py [코퍼스.html]   (기본=newatmons-bantyranitar)"""
import os, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
DEFAULT = os.path.join(HERE, "Gen5OU-2026-newatmons-bantyranitar.html")


def data_needs(trace, ref):
    """트레이스에 등장하는 종·무브와 레퍼런스(BASE/SETS/MOVES) 결측을 대조."""
    species = sorted(set(trace["nick2species"].values()))
    moves = sorted({e["move"] for e in trace["events"]
                    if e.get("action") == "move" and e.get("move")})
    miss_base = [s for s in species if s not in ref.BASE]
    miss_set  = [s for s in species if s not in ref.SETS]
    miss_move = [m for m in moves if m not in ref.MOVES]
    return species, moves, miss_base, miss_set, miss_move


def main():
    from modules.showdown_trace import parse_replay
    import modules.reference_gen5 as r5
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    with open(path, encoding="utf-8") as f:
        trace = parse_replay(f.read())

    species, moves, miss_base, miss_set, miss_move = data_needs(trace, r5)

    # HP Percentage Mod 판정 — meta.rules에 "HP Percentage Mod" 있으면 퍼센트
    pct = any("Percentage" in str(r) for r in trace.get("meta", {}).get("rules", []))

    print(f"=== 교차검증 데이터-니즈 ({os.path.basename(path)}) ===")
    print(f"HP 표기: {'퍼센트(max=100)' if pct else '절대'}")
    print(f"등장 종 {len(species)}: {species}")
    print(f"등장 무브 {len(moves)}: {moves}")
    print(f"BASE(종족값) 결측 {len(miss_base)}/{len(species)}: {miss_base}")
    print(f"SETS(특성/도구/EV) 결측 {len(miss_set)}/{len(species)}: {miss_set}")
    print(f"MOVES(위력/타입) 결측 {len(miss_move)}/{len(moves)}: {miss_move}")

    if miss_base:
        print("\n→ 엔진 풀런 보류: 종족값 결측. 패스2에서 BASE/MOVES/SETS를 채운 뒤 재실행.")
        print("  (스키마는 손대지 않는다 -- 데이터만 lazy 추가, 로드맵 C.)")
        return

    XVAL_SET_OVERRIDE = {  # 이 전투 한정. 전역 SETS는 골든 소유로 불변.
        'Garchomp': {'nature': 'Jolly', 'evs': (0, 252, 0, 0, 4, 252), 'item': None, 'ability': 'Rough Skin'},
        # item=None: Yache는 turn3 Knock Off로 이미 소실 → 이후 Ice Shard(turn10)에 Rocky Helmet
        # 팬텀 반동이 안 생기게. Jirachi는 골든 세트(Leftovers·Serene Grace)가 이 전투와도 합치 → 무override.
    }

    # --- 데이터 충분: 퍼센트HP-aware 풀런 (패스2에서 도달) ---
    from modules.fullbattle_run import run_and_diff, format_report
    res = run_and_diff(trace, r5, hp_tol=10, resync=True,
                       hp_mode=("percent" if pct else "absolute"),
                       set_override=XVAL_SET_OVERRIDE)
    print()
    print(format_report(res))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("=== run_xval 에러 (트레이스백 전체를 붙여주세요) ===")
        traceback.print_exc()
        sys.exit(1)
