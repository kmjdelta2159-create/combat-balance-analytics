# PR-B3b — 엔진 트레이스 구동 selector + 자발교체 주입 (FIND/REPLACE, 앱사이드 검증)

## 목적
PR-B3a가 game_config에 담은 `trace_actions`(move/target + 자발교체)를 엔진이 *읽어* 행동을
로그대로 구동하게 한다. 계산(AI 그리디·정책)을 로그 행동으로 대체 — 세 지점에 **config-게이트
분기**를 넣는다(`trace_actions` 없으면 전부 no-op → 회귀0). engine.py 외 무변경.

## 검증 제약 (먼저)
**engine.py가 74KB(~1595줄)라 샌드박스가 잘라 읽는다** — 전체 실행 검증은 *앱에서*. 아래
FIND/REPLACE 앵커는 Read/Grep으로 고정한 현재 텍스트다(작성 시점 정확). 적용 후 앱에서
gen5 prepare_run 셋업으로 돌려 라운드별 동작 확인(B4에서 통합).

## 대상
`modules/engine.py` — 함수 3개에 FIND/REPLACE 3건. 다른 파일 무변경.

## 설계 근거
- 모든 행동은 `(turn, active_char['id'])`로 키잉됨 — trace_actions가 이 키로 무브·타겟·자발교체를
  지정. 엔진은 participant를 id로 찾아 결합(B3a가 id 정합 보장, dangling 0).
- 자발교체는 기존 `_maybe_voluntary_switch` 훅을 트레이스 분기로 단락 — hp_threshold 정책
  대체. 들어올 유닛은 로그 지정(엔진 기본 reserve[0] 아님).
- move/target은 `_act_target_select`(타겟) + `_act_move_select`(무브) 두 페이즈에 오버라이드.
  target_select가 로그 무브를 `ctx["_trace_move"]`에 심고, move_select가 그걸 사용.
- 로그에 그 (turn, 유닛) 행동이 없으면(기절·이미 교체) targets=[] 로 생략.

## FIND/REPLACE 1 — `_maybe_voluntary_switch` 트레이스 분기

**FIND** (함수 본문 시작 3줄):
```python
    char = ctx["active_char"]
    gc = ctx.get("game_config") or {}
    pol = gc.get("switch_policy")
```

**REPLACE**:
```python
    char = ctx["active_char"]
    gc = ctx.get("game_config") or {}
    # ── 트레이스 구동: trace_actions 있으면 로그가 교체를 지시(hp_threshold 정책 대체) ──
    _ta = gc.get("trace_actions")
    if _ta is not None:
        _sw = (_ta.get("switch") or {}).get((ctx.get("turn"), char.get("id")))
        if not _sw:
            return False
        participants = ctx["participants"]
        incoming = next((p for p in participants if p.get("id") == _sw), None)
        if incoming is None or get_current(incoming) <= 0:
            return False
        char['on_field'] = False
        incoming['on_field'] = True
        ctx["add_log"](
            f"[Turn {ctx['turn']}] {char.get('id','?')} 교체(트레이스) → "
            f"{incoming.get('id','?')} ({incoming.get('name','?')}) 진입"
        )
        incoming['just_switched_in'] = False
        _fire_switch_in(incoming, participants, gc, ctx["add_log"], ctx.get("field_state"))
        return True
    pol = gc.get("switch_policy")
```

## FIND/REPLACE 2 — `_act_target_select` move/target 오버라이드

**FIND** (자발교체 정책 블록):
```python
    # ── 자발적 교체 정책 (선택) — 조건 만족 시 교체로 턴 소모, 이번 턴 공격 생략 ──
    if _maybe_voluntary_switch(ctx):
        ctx["targets"] = []
        return
```

**REPLACE**:
```python
    # ── 자발적 교체 정책 (선택) — 조건 만족 시 교체로 턴 소모, 이번 턴 공격 생략 ──
    if _maybe_voluntary_switch(ctx):
        ctx["targets"] = []
        return

    # ── 트레이스 구동: 로그가 이번 턴 이 유닛의 무브·타겟을 지시 ──
    _ta = (ctx.get("game_config") or {}).get("trace_actions")
    if _ta is not None:
        _ma = (_ta.get("move") or {}).get((ctx.get("turn"), char.get("id")))
        if not _ma:
            ctx["targets"] = []          # 로그상 행동 없음(기절/이미 교체) → 생략
            return
        _tid = _ma.get("target")
        _tgt = next((p for p in participants if p.get("id") == _tid), None)
        ctx["targets"] = [_tgt] if _tgt is not None else []
        ctx["_trace_move"] = _ma.get("move")
        ctx["add_log"](
            f"[Turn {ctx['turn']}] {char['id']} ({char['name']}) "
            f"[Phase: TARGET_SELECT] 트레이스 무브 {_ma['move'].get('name')} "
            f"→ {_tid}"
        )
        return
```

## FIND/REPLACE 3 — `_act_move_select` 로그 무브 사용

**FIND** (함수 전체):
```python
def _act_move_select(ctx):
    """무브 선택 Phase (Phase 8a) — movepool에서 그리디(기대 데미지 최대)로 무브 선택.
    movepool 미보유 시 current_move=None → 단일 global 공식 경로 유지(default=identity).
    선택 본체는 공유 순수 코어 _select_move_pure(행동순서 예측기와 동일 경로)에 위임한다."""
    ctx["current_move"] = _select_move_pure(
        ctx["active_char"], ctx.get("current_target"),
        ctx.get("sys_stats"), ctx.get("game_config"), ctx.get("formula_str"))
```

**REPLACE**:
```python
def _act_move_select(ctx):
    """무브 선택 Phase (Phase 8a) — movepool에서 그리디(기대 데미지 최대)로 무브 선택.
    movepool 미보유 시 current_move=None → 단일 global 공식 경로 유지(default=identity).
    선택 본체는 공유 순수 코어 _select_move_pure(행동순서 예측기와 동일 경로)에 위임한다.
    트레이스 구동 시 target_select가 심어둔 로그 무브를 그대로 사용(계산 우회)."""
    if ctx.get("_trace_move") is not None:
        ctx["current_move"] = ctx["_trace_move"]
        return
    ctx["current_move"] = _select_move_pure(
        ctx["active_char"], ctx.get("current_target"),
        ctx.get("sys_stats"), ctx.get("game_config"), ctx.get("formula_str"))
```

## 검증 (앱사이드 — engine.py truncation으로 샌드박스 실행 불가)
적용 후 *앱에서*:
1. `python -c "import ast; ast.parse(open('modules/engine.py',encoding='utf-8').read())"`로 구문 OK.
2. `trace_actions` **미설정** 일반 전투를 한 판 돌려 기존 동작 무변경 확인(세 분기 전부 no-op).
3. PR-B3a `prepare_run`(gen5)으로 셋업해 짧게 돌려, 로그가 지정한 무브·타겟·자발교체가 반영되는지
   로그 출력으로 확인(전체 라운드 대조는 B4에서 fullbattle_diff로).
*고립 분기 로직*(자발교체 단락·move/target 오버라이드 분기 자체)은 단순 dict 조회 + id 매칭이라
B3a 클린룸 검증(dangling 0·키 정합)이 입력 정합을 이미 보장한다.

## 회귀 0
세 분기 전부 `game_config['trace_actions']`(또는 `_trace_move`) 존재로 게이트 — 미설정 시 즉시
기존 경로. 기존 호출자·시그니처 무변경. `_will_voluntary_switch`(예측기)는 switch_policy
type "trace"에서 자연히 False 반환(기존 코드 그대로) → 크래시 없음. 단 이로 인해 자발교체가
교체 우선 브래킷으로 정렬되진 않음(아래 "알려진 잔차").

## 알려진 잔차 (B4가 라운드 단위로 지목할 후속 — 의도됨)
- **턴내 교체 순서**: 예측기 미수정이라 자발교체가 속도순으로 처리(포켓몬은 교체 우선). move/
  target 오버라이드가 타겟을 로그값으로 강제하므로 데미지 *대상*은 보호되나, 교체-공격 순서가
  얽힌 라운드는 divergence 가능 → verification-mode ordering 후속.
- **기절-교체 incoming**: 엔진 기본 reserve 선택은 PR-B3c가 로그 지정으로 교정(현재 미적용 시
  첫 기절 T10부터 divergence — 격리됨).
- **피벗(Volt Switch)**: 데미지는 계산되나 무브유발 교체-아웃은 미발동(무브효과) → T3 divergence,
  효과-스키마 후속.

## 다음 (PR-B3c)
`turn_manager._resolve_faint`가 `trace_faint_incoming`(outgoing→incoming)대로 예비 진입 —
엔진 기본 roster_idx[0] 대체. 없으면 현행(회귀0). 그 뒤 B4 통합.
