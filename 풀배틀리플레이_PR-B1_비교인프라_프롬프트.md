# PR-B1 — 풀배틀 비교 인프라 (신규 모듈)

## 목적
풀배틀 트레이스 리플레이(`풀배틀리플레이_설계안.md`)의 1조각이자 **엔진 무관**한 비교 인프라.
정규화 트레이스 IR(`showdown_trace.parse_replay` 산출)에서 ① **행동 큐**(엔진이 따라야 할
로그 순서의 행위자 액션 시퀀스), ② **라운드별 상태 스냅샷**(턴 경계마다 전 유닛의 HP/상태/
기절 — 엔진 산출과 대조할 답안지), ③ **divergence 리포트**(라운드별 expected[로그] vs
actual[엔진] 대조, 첫 불일치 격리)를 만드는 신규 모듈. 엔진·step2·기존 모듈 **무변경**(신규
파일 1개, 곁가지 0). per-event 잔차 리포트의 *전투 스케일* 버전이다.

## 대상
**신규 파일** `modules/fullbattle_diff.py` 생성. 다른 파일 변경 없음.

## 설계 근거 (실 로그 2건·2세대로 검증됨)
- **행동 큐** = 로그 순서대로 `move` + **자발교체(voluntary switch)**. 강제교체(drag,
  기절구동)는 엔진이 자체 처리하므로 제외. 실측 Gen5전: 큐 60 = move 36 + 자발교체 24.
  Gen6전: 큐 25 = move 18 + 자발교체 7. (자발교체가 엔진 주입 표면이 되는 신규 행동 — PR-B3.)
- **상태 스냅샷** = 턴 경계마다 그때까지 마지막 관측된 각 유닛의 `(hp, status, fainted)`.
  **turn 0**(리드 등장)부터 기록 → Gen5전 28 스냅샷(turn 0~27), Gen6전 13(turn 0~12).
  부스트·날씨 누적이 라운드를 넘어 연쇄하므로 *라운드별*로 끊어 첫 divergence 지점을 격리한다.
- **divergence** = 순수 함수. HP는 허용구간(`hp_tol` — 데미지 롤 흡수용, 기본 0) 내면 일치,
  벗어나면 보고. faint·status 불일치도 별도 보고. expected를 기준 순회(엔진이 못 만든
  스냅샷도 `missing`으로 포착).

## 생성할 파일 내용 (전체 — 바이트 그대로)

```python
"""
풀배틀 트레이스 리플레이 — 비교 인프라 (엔진 무관).

정규화 트레이스 IR(showdown_trace.parse_replay 산출)에서 풀배틀 검증의 세 축을 만든다:
- build_action_queue: 로그 순서의 행위자 액션 시퀀스(move + 자발교체) — 엔진에 주입할 대본.
- build_snapshots: 턴 경계마다 전 유닛의 (hp, status, fainted) — 엔진 산출과 대조할 답안지.
- divergence: 라운드별 expected(로그) vs actual(엔진) 대조 — 첫 불일치 격리.

게임/엔진 중립. 이 모듈은 로그에서 '대본'과 '답안지'만 뽑고, 비교만 한다. 엔진을 부르지
않으므로 engine.py truncation 영향권 밖 — 클린룸으로 완결 검증된다(아래 검증 절).
"""


def build_action_queue(trace):
    """로그 순서대로 행위자 액션(move / 자발교체) 시퀀스를 반환.

    forced(drag = 기절구동 강제교체)는 엔진이 자체 처리하므로 제외 — 자발교체만 주입 대상.
    각 액션: {turn, side, actor, kind('move'|'switch'), move/target | species}.
    """
    q = []
    for e in trace["events"]:
        a = e.get("action")
        if a == "move":
            q.append({"turn": e["turn"], "side": e.get("actor_side"),
                      "actor": e["actor"], "kind": "move",
                      "move": e["move"], "target": e.get("target")})
        elif a == "switch" and not e.get("forced"):
            q.append({"turn": e["turn"], "side": e.get("actor_side"),
                      "actor": e["actor"], "kind": "switch",
                      "species": e.get("species")})
    return q


def build_snapshots(trace):
    """턴 경계마다 등장 유닛의 (hp, status, fainted) 누적 스냅샷.

    각 턴의 *끝* 상태(그 턴까지 마지막으로 관측된 값)를 기록. turn 0(리드 등장)부터 포함.
    반환: {turn: {nick: {'hp', 'status', 'fainted'}}}.
    """
    hp = {}
    st = {}
    fnt = set()
    snaps = {}

    def apply(e):
        a = e.get("action")
        if a in ("switch", "drag"):
            n = e["actor"]
            if e.get("hp") is not None:
                hp[n] = e["hp"]
            if e.get("status"):
                st[n] = e["status"]
            fnt.discard(n)               # 재등장 = 생존
        elif a == "move":
            for h in e.get("hits", []):
                if h.get("cur") is not None:
                    hp[h["who"]] = h["cur"]
            for w in e.get("faints", []):
                hp[w] = 0
                fnt.add(w)
        elif a == "env":
            if e.get("cur") is not None:
                hp[e["who"]] = e["cur"]
        elif a == "faint":
            hp[e["who"]] = 0
            fnt.add(e["who"])

    def snapshot():
        return {n: {"hp": hp.get(n), "status": st.get(n), "fainted": n in fnt}
                for n in hp}

    last = None
    for e in trace["events"]:
        tn = e.get("turn")
        if tn is None:
            continue
        if last is not None and tn != last:
            snaps[last] = snapshot()
        apply(e)
        last = tn
    if last is not None:
        snaps[last] = snapshot()
    return snaps


def divergence(expected, actual, hp_tol=0):
    """라운드별 expected(로그) vs actual(엔진) 상태 대조. 전 불일치를 (turn 오름차순) 보고.

    expected/actual: build_snapshots 형식. hp_tol: HP 허용 오차(데미지 롤 흡수, 기본 0).
    반환: [(turn, nick, kind, expected_val, actual_val)] — kind ∈
    {'missing','faint','hp','status'}.
    """
    out = []
    for tn in sorted(expected):
        ex = expected[tn]
        ac = actual.get(tn, {})
        for n, exv in ex.items():
            acv = ac.get(n)
            if acv is None:
                out.append((tn, n, "missing", exv, None))
                continue
            if exv.get("fainted") != acv.get("fainted"):
                out.append((tn, n, "faint", exv.get("fainted"), acv.get("fainted")))
            eh, ah = exv.get("hp"), acv.get("hp")
            if eh is not None and ah is not None and abs(eh - ah) > hp_tol:
                out.append((tn, n, "hp", eh, ah))
            if exv.get("status") != acv.get("status"):
                out.append((tn, n, "status", exv.get("status"), acv.get("status")))
    return out
```

## API
- `build_action_queue(trace) -> [{turn, side, actor, kind, move?, target?, species?}]`
  — 로그 순서의 행위자 액션(move + 자발교체). drag 제외.
- `build_snapshots(trace) -> {turn: {nick: {hp, status, fainted}}}`
  — 턴 경계 누적 상태(turn 0 리드부터). 엔진 산출과 대조할 답안지.
- `divergence(expected, actual, hp_tol=0) -> [(turn, nick, kind, exp, act)]`
  — 라운드별 대조. kind ∈ {missing, faint, hp, status}. 순수 함수.

입력 `trace`는 `showdown_trace.parse_replay`의 산출 그대로.

## 검증 (클린룸·실 로그 2건, 작성 시 수행 — 적용자 재현용)
두 업로드 로그로 `parse_replay` → 위 세 함수:
- **Gen5 OU전**(`Gen5OU-2015-05-11-reymedy-leftiez.html`): 행동 큐 **60**(move 36 +
  자발교체 24) · 스냅샷 **28**(turn 0~27) · `divergence(snaps, snaps)` = **0**(자기 대조
  무오차) · 모의 엔진(한 턴 HP −5 + 마지막 턴 faint 뒤집기) 주입 시 divergence가 **정확히
  2건** 포착: `(14,'Gengen','hp',69,64)` · `(27,'Gengen','faint',True,False)`. 최종 기절
  8유닛 정확(p1 전멸).
- **Gen6 Monotype전**(`OUMonotype-2014-01-29-kdarewolf-onox.html`, 교차-게임 가드):
  행동 큐 **25**(move 18 + 자발교체 7) · 스냅샷 **13**(turn 0~12). 다른 세대·티어에서도
  큐/스냅샷 추출 동일 동작 — 일반성 확인.

적용자 검증:
1. 파일 생성 후 `python -c "import ast; ast.parse(open('modules/fullbattle_diff.py',encoding='utf-8').read())"`.
2. ```python
   from modules.showdown_trace import parse_replay
   from modules.fullbattle_diff import build_action_queue, build_snapshots, divergence
   t = parse_replay(open('Gen5OU-2015-05-11-reymedy-leftiez.html', encoding='utf-8').read())
   q = build_action_queue(t); s = build_snapshots(t)
   assert len(q) == 60 and len(s) == 28
   assert divergence(s, s) == []
   ```
   로 큐 60·스냅샷 28·자기대조 0 확인.
3. 기존 모듈 import·동작 무변경(신규 파일이라 곁가지 0).

## 회귀 0
신규 파일 1개. 엔진·step2·turn_manager·showdown_trace·trace_replay·reference_gen6 전부
무변경. 엔진을 호출하지 않으므로 engine.py truncation 영향권 밖 — 클린룸 완결. 어떤 기존
경로도 이 모듈을 아직 호출하지 않음(PR-B4 통합 run에서 소비).

## 다음 (PR-B2 예고)
셋업 빌더 — trace 양팀(meta.teams + 등장 세트) → participants(reference 스탯·ability/item·
resources) + game_config(formula·type_table·mechanisms.effects). reference_gen6 확장,
클린룸 검증. 그 뒤 PR-B3(엔진 — 트레이스 구동 selector + 자발교체 주입, 앱 검증) →
PR-B4(통합 run + 라운드별 divergence 리포트, 앱 실행).
