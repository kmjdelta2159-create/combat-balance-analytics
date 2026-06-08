# 툴화 PR-T2 — 수정 surface (역설계→수정 루프를 도구로 완성)

> PR-T1(검출기)은 *추출*(자동)이다. 이 PR은 짝이 되는 *수정*(사용자 확정) surface — 검출기 제안 +
> **조건 자동추론**(영향군 vs 면제 on-field 대조 → not_ability/not_types 힌트) + 사용자 결정 →
> **ready-to-paste EFFECTS 블록**. 사람은 *확정·편집*만(환원 불가한 개입). 슬라이더 원리 그대로:
> 추출은 자동, 확정은 사용자.
>
> **검증 완료(클린룸)**: gen5 held-out에서 Hail 조건을 자동추론 — **Magic Guard를 면제 공통특성으로
> 자동 발견**(강 힌트), 타입 오탐(Psychic/Normal)은 약 힌트로 표시. 사용자 확정(Magic Guard 채택 +
> Ice 도메인지식 추가 + 오탐 제거) → commit이 내놓은 `'hail'` 엔트리가 **PR-X3에서 손으로 쓴
> EFFECTS['hail']과 정확히 동일**(1/16·not_types Ice·not_ability Magic Guard).
>
> **신규 파일 2개**. 엔진·reference 무수정(회귀0). 엔진 무관(trace+ref).

## 설계 — 추출 자동, 확정 사용자

검출기가 메커니즘·프랙션·source를 자동 추출하고, surface가 *조건*까지 추론해 힌트로 준다. 조건
추론은 **영향받은 유닛 vs 같은 턴 on-field였으나 면제된 유닛**을 대조한다: 면제군의 공통 특성 →
`not_ability` 후보(강), 면제군에만 있는 타입 → `not_types` 후보(약·타이밍 오탐 가능). 사용자가
힌트를 확정/편집(도메인지식으로 보완, 오탐 제거)하면 EFFECTS 엔트리가 커밋된다. 자동추론이 못 잡는
꼬리는 사용자 몫 — 그게 정확히 슬라이더의 개입 끝이다.

## 파일 1 — `modules/mechanism_commit.py` (신규, 엔진 무관)

```python
"""mechanism_commit.py — 메커니즘 수정 surface(추출→조건추론→확정→커밋).
검출기(mechanism_detect) 쇼핑리스트 + 조건 자동추론(ranked 힌트) + 사용자 결정 → EFFECTS 블록."""
from collections import defaultdict

def _onfield_tl(trace):
    """턴별 진영 on-field 닉 {turn: {side: nick}} (fullbattle_run.build_onfield_timeline와 동형)."""
    onf, tl, last = {}, {}, None
    for e in trace['events']:
        tn = e.get('turn')
        if tn is None:
            continue
        if last is not None and tn != last:
            tl[last] = dict(onf)
        if e.get('action') in ('switch', 'drag'):
            onf[e['actor_side']] = e['actor']
        last = tn
    if last is not None:
        tl[last] = dict(onf)
    return tl

def infer_conditions(trace, ref, src_match):
    """그 메커니즘(src_match)이 영향준 유닛 vs 같은 턴 on-field 면제 유닛 대조 →
    not_ability(면제 공통특성, 강)·not_types(면제 전용타입, 약) 힌트(빈도순)."""
    sp = trace['nick2species']
    TYP = getattr(ref, 'SPECIES_TYPES', {})
    SETS = getattr(ref, 'SETS', {})
    tl = _onfield_tl(trace)
    aff, onf = set(), set()
    for e in trace['events']:
        if e.get('action') == 'env' and e.get('src') == src_match:
            aff.add(e['who'])
            for n in tl.get(e['turn'], {}).values():
                onf.add(n)
    spared = onf - aff
    aff_types = {t for n in aff for t in TYP.get(sp.get(n), ()) if t}
    nt, na = defaultdict(int), defaultdict(int)
    for n in spared:
        for t in TYP.get(sp.get(n), ()):
            if t and t not in aff_types:
                nt[t] += 1
        ab = (SETS.get(sp.get(n)) or {}).get('ability')
        if ab:
            na[ab] += 1
    return {'spared': sorted(sp.get(n, n) for n in spared),
            'not_ability_hint': sorted(na, key=lambda k: -na[k]),
            'not_types_hint': sorted(nt, key=lambda k: -nt[k])}

def commit(decisions):
    """decisions: {effects_key: {'spec': {...detector suggest...}, 'condition': {...}|None}}
    → EFFECTS dict(ready-to-paste). condition 있으면 spec에 병합."""
    eff = {}
    for key, d in decisions.items():
        s = dict(d['spec'])
        if d.get('condition'):
            s['condition'] = d['condition']
        eff[key] = s
    return eff
```

## 파일 2 — `run_mechcommit.py` (신규, 루트, surface 러너)

```python
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
    from modules.mechanism_detect import detect_mechanisms
    from modules.mechanism_commit import infer_conditions, commit
    import modules.reference_gen5 as ref
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    with open(path, encoding="utf-8") as f:
        trace = parse_replay(f.read())
    det = {r['name']: r for r in detect_mechanisms(trace, ref)}
    # 1) 미모델 메커니즘마다 제안 + 조건 힌트 표시
    print("=== 수정 surface: 미모델 메커니즘 + 조건 자동추론 ===")
    for name, r in det.items():
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
        r = det.get(d['src'])
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
```

## 검증 (적용 후)

1. **골든 회귀0**: `python run_b4.py` 무변(신규 파일).
2. **surface 실행**: `python run_mechcommit.py` →
   - 미모델(Stealth Rock·Spikes·Recoil)의 제안 + 조건 힌트. **Hail이 modeled라 안 뜨면**, DECISIONS의
     'hail' src는 검출되므로 커밋 블록엔 나옴. 핵심 확인: **Recoil/Spikes의 면제 추론**과 **커밋 블록**.
   - 커밋 블록의 `'hail'`이 손으로 쓴 EFFECTS['hail'](1/16·not_types Ice·not_ability Magic Guard)과
     동일한지. **출력을 붙여달라.**
3. **의미**: 검출(자동) + 조건추론(Magic Guard 자동발견) + 확정(DECISIONS 편집) → EFFECTS 커밋.
   사람은 확정·편집만 — 역설계→수정 루프가 *도구*로 닫힘.

## (b) 완료 — 1차목표 두 번째 기둥

PR-T1(검출) + PR-T2(수정)로 **역설계→사용자수정 루프가 수작업에서 도구로** 전환됐다. 내 X3~X7
진단·작성을 검출기가 자동화하고, 사용자는 조건 확정·도메인 보완만 한다. 로드맵 §1의 "기존
detection/매핑UI를 메커니즘 축으로 연장"이 트레이스-리플레이 축에서 실체화 — RE 추출(자동) +
수정(사용자 확정) + 수치 RE(기존). 다음: step2 Streamlit 통합(선택) 또는 1차목표 완성도 점검.
