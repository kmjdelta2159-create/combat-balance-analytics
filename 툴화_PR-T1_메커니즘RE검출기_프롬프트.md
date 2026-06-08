# 툴화 PR-T1 — 메커니즘 RE 검출기 (역설계 루프를 도구로)

> 1차목표 두 번째 기둥 = **RE 검출기 + 수정 UI**(로드맵 §1). 지금까지 메커니즘 RE는 *수작업*이었다:
> 내가 트레이스의 `[from]` env 스트림을 읽어(Hail·Leftovers·Poison Heal·Stealth Rock…) 프랙션을
> 추정하고 EFFECTS 한 줄을 썼다(X3~X7). 이 PR은 그 *추출*을 도구화한다 — 트레이스에서 발동형
> 메커니즘을 자동 마이닝해 **미모델 쇼핑리스트 + EFFECTS 후보 spec**을 낸다. 로드맵의 "RE가 로그
> 에서 자동 추출하는 몫(a)"의 메커니즘-축 실체.
>
> **검증 완료(클린룸)**: gen5 held-out 트레이스에서 내가 손으로 닫은 메커니즘을 *전부 자동 재발견*
> — Hail(1/16)·Leftovers(1/16)·Poison Heal(1/8)·Rocky Helmet(1/6)·회복무브(Roost/Rest/Soft-Boiled)·
> Stealth Rock·Spikes(1/8)·Recoil. 미모델 3건(SR·Spikes·Recoil)을 EFFECTS 후보로 제안.
>
> **신규 파일 2개만**. 엔진·기존 reference 무수정(회귀0). 검출기는 트레이스+ref.EFFECTS만 읽음
> (엔진 무관 → 클린룸/앱 양쪽 실행).

## 설계 — 왜 env 스트림인가

트레이스는 부수효과를 `-damage/-heal [from] X`로 *이름째* 기록한다(showdown_trace가 env 이벤트
`{kind, src, who, delta, max}`로 정규화). 그래서 *메커니즘이 데이터로 명시*돼 있다 — 집계 통계(옛
CSV 파이프라인)엔 없던 정보다. 검출기는 이 스트림을:
1. 소스(src)별로 그룹화 → 메커니즘 식별(이름·클래스: weather/item/ability/status/hazard/move).
2. 프랙션 = median(|delta|/max) → 표준 분수 스냅(1/16·1/8·1/6·1/4·1/3·1/2·1).
3. kind → 효과타입(heal_frac/damage_frac), 클래스 → trigger/scope/source 추론.
4. `ref.EFFECTS` 대조 → 모델드/미모델 플래그.
5. 미모델 = **EFFECTS 후보 spec**(수정 surface가 사용자에게 제시할 입력).

검출기는 *제안*이다(슬라이더 원리). 프랙션 스냅·조건(not_types/not_ability)은 사용자가 수정
surface에서 확정한다 — 특히 heal-to-cap 무브(Roost=풀회복)는 관측 프랙션이 가변이라 검출기 추정이
흔들릴 수 있고, 그게 정확히 사용자 확정 지점이다.

## 파일 1 — `modules/mechanism_detect.py` (신규, 엔진 무관)

```python
"""mechanism_detect.py — 트레이스-구동 메커니즘 RE 검출기.
트레이스 [from] env 스트림을 마이닝해 발동형 메커니즘을 자동 추출하고, ref.EFFECTS 대조로
미모델을 가리키며 EFFECTS 후보 spec을 제안한다(수정 surface 입력). streamlit/engine 의존 0."""
import statistics
from collections import defaultdict

_FRAC = [1/16, 1/8, 1/6, 1/4, 1/3, 1/2, 1.0]   # 표준 분수 스냅

def _snap(f):
    return min(_FRAC, key=lambda x: abs(x - f)) if f > 0 else 0

def _norm(src):
    """env src('item: Leftovers'/'ability: Poison Heal'/'Hail'/'Stealth Rock'/'tox'…) → (class, name)."""
    s = (src or '').strip()
    if s.startswith('item:'): return 'item', s[5:].strip()
    if s.startswith('ability:'): return 'ability', s[8:].strip()
    if s in ('Stealth Rock', 'Spikes', 'Toxic Spikes'): return 'hazard', s
    if s in ('tox', 'brn', 'psn', 'par', 'frz'): return 'status', s
    if s == 'Recoil': return 'move', 'Recoil'
    if s.lower() in ('hail', 'sandstorm', 'sand', 'rain', 'sun', 'sunnyday'): return 'weather', s
    return ('weather' if s else 'move'), (s or None)

def detect_mechanisms(trace, ref):
    """트레이스 + ref → 메커니즘 쇼핑리스트(빈도순). 각: class/name/kind/frac/n/affected/modeled/suggest."""
    sp = trace['nick2species']
    eff = getattr(ref, 'EFFECTS', {}) or {}
    mk = {k for k in eff} | {str(k).lower() for k in eff}
    mv = {}                                            # 자가효과 귀속용: (turn, who) → 무브명
    for e in trace['events']:
        if e.get('action') == 'move':
            mv[(e['turn'], e['actor'])] = e['move']
    g = defaultdict(list)
    for e in trace['events']:
        if e.get('action') == 'env' and e.get('max'):
            cls, name = _norm(e.get('src'))
            if name is None:                            # src 없는 자가효과 → 그 턴 그 유닛 무브(회복무브)
                name = mv.get((e['turn'], e['who'])); cls = 'move'
            g[(cls, name, e['kind'])].append((abs(e['delta']) / e['max'], sp.get(e['who'])))
    out = []
    for (cls, name, kind), rows in g.items():
        if not name:
            continue
        frac = _snap(statistics.median(r[0] for r in rows))
        modeled = name in mk or str(name).lower() in mk
        trig = ('ON_SWITCH' if cls == 'hazard'
                else 'ON_MOVE_USE' if (cls == 'move' and kind == 'heal')
                else 'ON_HIT' if cls == 'move' else 'ON_TURN_END')
        etype = 'heal_frac' if kind == 'heal' else 'damage_frac'
        scope = 'attacker' if (cls == 'move' and kind == 'damage' and name != 'Recoil') else 'self'
        out.append({'class': cls, 'name': name, 'kind': kind, 'frac': frac, 'n': len(rows),
                    'affected': sorted(set(r[1] for r in rows if r[1])), 'modeled': modeled,
                    'suggest': {'trigger': trig, 'effect': {'type': etype, 'frac': round(frac, 4), 'of': 'maxhp'},
                                'scope': scope, 'source': cls}})
    out.sort(key=lambda x: -x['n'])
    return out
```

## 파일 2 — `run_mechdetect.py` (신규, 루트, 러너)

```python
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
```

## 검증 (적용 후)

1. **골든 회귀0**: `python run_b4.py` 무변(신규 파일이라 무영향).
2. **검출기 실행**: `python run_mechdetect.py` → gen5 held-out 쇼핑리스트. 기대(클린룸 일치):
   Hail(weather/damage/1/16, YES)·Leftovers(item/heal/1/16, YES)·Poison Heal(ability/heal/1/8, YES)·
   Rocky Helmet(item/damage/1/6, YES)·Rest/Soft-Boiled(move/heal/1/2, YES)·Stealth Rock·Spikes
   (hazard/damage, NO)·Recoil(move/damage, NO). **출력을 붙여달라.**
3. **의미 확인**: 검출기가 *손으로 닫은 메커니즘을 자동 재발견*하고, 미모델(SR·Spikes는 해저드
   기계로 별도 처리·Recoil은 미구현)을 EFFECTS 후보로 가리키는지.

## 다음 (b) 단계 — 수정 surface

검출기는 *추출*(자동)이다. 짝이 되는 *수정*(개입)은: 쇼핑리스트를 받아 사용자가 각 후보를
확정/편집(프랙션·조건 not_types/not_ability·source)해 `EFFECTS`로 커밋하는 surface. step2 매핑 UI의
메커니즘-축 연장(로드맵 §1) 또는 경량 CLI 확정 흐름. PR-T2 후보.

이로써 역설계→수정 루프가 *수작업에서 도구로* — RE 검출(자동) + 수정(사용자 확정) = 1차목표
두 번째 기둥의 토대. 검출기가 내 X3~X7 진단을 그대로 자동화함이 실증.
