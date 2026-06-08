"""run_mechcommit.py — 수정 surface 실행. 미모델 메커니즘의 제안 spec + 조건 힌트를 보여주고,
DECISIONS(사용자 확정)로 EFFECTS 블록을 커밋한다. 검출은 자동, 확정은 아래 DECISIONS 편집으로."""
import os, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
DEFAULT = os.path.join(HERE, "Gen5OU-2026-newatmons-bantyranitar.html")

# ── 사용자 확정 영역(편집 = 수정 개입) ──────────────────────────────
# 검출기 제안(SUGGEST)을 확정하고, 조건 힌트를 보완(도메인지식)·오탐 제거.
# key=EFFECTS에 들어갈 이름. SUGGEST=검출기 spec 그대로 쓰려면 None(아래서 채움).
DECISIONS = {
    'hail':   {'src': 'Hail',         'condition': {'not_types': ['Ice'], 'not_ability': ['Magic Guard']}},
    'Spikes': {'src': 'Spikes',       'condition': None},
    # 미커밋(보류)은 빼면 됨. frac/scope 편집은 SUGGEST를 복사해 직접 수정.
}

def main():
    from modules.showdown_trace import parse_replay
    from modules.mechanism_detect import detect_mechanisms, canonical_mechanism_key
    from modules.mechanism_commit import infer_conditions, commit
    import modules.reference_gen5 as ref
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    with open(path, encoding="utf-8") as f:
        trace = parse_replay(f.read())
        
    rows = detect_mechanisms(trace, ref)
    det = {}
    for r in rows:
        det[r['name']] = r
        det[(r["class"], r["name"])] = r
        for src in r.get("sources", []):
            det[canonical_mechanism_key(src)] = r

    # 1) 미모델 메커니즘마다 제안 + 조건 힌트 표시
    print("=== 수정 surface: 미모델 메커니즘 + 조건 자동추론 ===")
    for r in rows:
        name = r['name']
        if r['modeled']:
            continue
        ci = infer_conditions(trace, ref, name)
        print(f"\n[{name}] {r['suggest']['trigger']}/{r['suggest']['effect']['type']} "
              f"frac={r['suggest']['effect']['frac']} source={r['suggest']['source']}")
        print(f"   영향: {r['affected'][:8]}")
        print(f"   면제 on-field: {ci['spared']}")
        print(f"   → not_ability 힌트(강): {ci['not_ability_hint']} | not_types 힌트(약): {ci['not_types_hint']}")
        
    # 2) DECISIONS로 EFFECTS 커밋
    decisions = {}
    for key, d in DECISIONS.items():
        src_key = canonical_mechanism_key(d["src"])
        r = det.get(src_key) or det.get(d['src'])
        if not r:
            print(f"\n[경고] '{d['src']}' 검출 안 됨 — 건너뜀"); continue
        decisions[key] = {'spec': r['suggest'], 'condition': d.get('condition')}
    print("\n=== 커밋된 EFFECTS 블록 (reference EFFECTS에 붙여넣기) ===")
    for k, v in commit(decisions).items():
        print(f"    '{k}': {v},")

if __name__ == "__main__":
    try: main()
    except Exception:
        print("=== run_mechcommit 에러 ==="); traceback.print_exc(); sys.exit(1)
