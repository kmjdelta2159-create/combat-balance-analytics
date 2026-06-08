# -*- coding: utf-8 -*-
"""run_ff7.py — FF7 트레이스 + ff7_reference로 트레이스-리플레이 divergence.
프로젝트 루트의 modules를 쓰므로 엔진 온전한 앱 환경에서 실행. 먼저 ff7_trace_gen.py 실행 필요."""
import json, os, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                 # 검증_FF7의 부모 = 프로젝트 루트
for p in (ROOT, HERE):
    if p not in sys.path: sys.path.insert(0, p)

def main():
    from modules.fullbattle_run import run_and_diff, format_report
    import ff7_reference as ref
    path = os.path.join(HERE, 'ff7_trace.json')
    if not os.path.exists(path):
        print('ff7_trace.json 없음 — 먼저 python ff7_trace_gen.py 실행'); return
    trace = json.load(open(path, encoding='utf-8'))
    res = run_and_diff(trace, ref, hp_tol=2, resync=True, hp_mode='absolute', dmg_debug=True)
    print(format_report(res))
    # 흡수 턴 분리 표시(엔진이 음수 elem_mult를 회복으로 라우팅하나)
    print('\n[흡수 점검] T3 C1: Ice2(흡수) → 로그는 회복(+316). 엔진이 같으면 일치, 클램프면 ★(언어확장 1).')

if __name__ == '__main__':
    try: main()
    except Exception:
        print('=== run_ff7 에러 (트레이스백 전체를 붙여주세요) ==='); traceback.print_exc(); sys.exit(1)
