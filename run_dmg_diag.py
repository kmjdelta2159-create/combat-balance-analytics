# run_dmg_diag.py — 과데미지 진단: 데미지 분해를 런타임에서 덤프
import os, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
DEFAULT = os.path.join(HERE, "Gen5OU-2026-newatmons-bantyranitar.html")

def main():
    from modules.showdown_trace import parse_replay
    from modules.fullbattle_run import run_and_diff
    import modules.reference_gen5 as r5
    with open(sys.argv[1] if len(sys.argv) > 1 else DEFAULT, encoding="utf-8") as f:
        trace = parse_replay(f.read())
    OVR = {'Garchomp': {'nature': 'Jolly', 'evs': (0,252,0,0,4,252), 'item': None, 'ability': 'Rough Skin'}}
    run_and_diff(trace, r5, hp_tol=10, resync=True, hp_mode="percent",
                 set_override=OVR, dmg_debug=True)

if __name__ == "__main__":
    try: main()
    except Exception:
        print("=== run_dmg_diag 에러 ==="); traceback.print_exc(); sys.exit(1)
