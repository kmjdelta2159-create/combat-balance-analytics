"""run_mechdetect.py — 메커니즘 RE 검출기 실행. 트레이스에서 발동형 메커니즘 쇼핑리스트 출력.
    python run_mechdetect.py [코퍼스.html]   (기본=gen5 held-out)"""
import os, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
DEFAULT = os.path.join(HERE, "Gen5OU-2026-newatmons-bantyranitar.html")

def main():
    from modules.showdown_trace import parse_replay
    from modules.mechanism_detect import detect_mechanisms
    import modules.reference_gen5 as ref
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    with open(path, encoding="utf-8") as f:
        trace = parse_replay(f.read())
    rows = detect_mechanisms(trace, ref)
    print("=== 메커니즘 RE 쇼핑리스트 (auto, %s) ===" % os.path.basename(path))
    print("{:9} {:14} {:6} {:6} {:>3} {:9} 제안".format('class','mechanism','kind','frac','n','modeled'))
    for r in rows:
        sg = r['suggest']; fr = '1/%d' % round(1/r['frac']) if r['frac'] else '0'
        print("{:9} {:14} {:6} {:6} {:>3} {:9} {}/{}/{}".format(
            r['class'], str(r['name'])[:14], r['kind'], fr, r['n'],
            'YES' if r['modeled'] else 'NO', sg['trigger'], sg['effect']['type'], sg['scope']))
    print("\n--- 미모델(NO) = 사용자 수정 surface로 보낼 EFFECTS 후보 ---")
    for r in rows:
        if not r['modeled']:
            print("  %-14s %s  (영향: %s)" % (r['name'], r['suggest'], ', '.join(r['affected'][:6])))

if __name__ == "__main__":
    try: main()
    except Exception:
        print("=== run_mechdetect 에러 ==="); traceback.print_exc(); sys.exit(1)
