# PR-C2 — 라운드별 resync 모드 (turn_manager 훅 + engine + fullbattle_run)

## 목적
순수 시뮬레이션 풀배틀은 매 턴 미세 오차가 누적돼 기절 타이밍이 어긋나고 desync → 100턴
표류했다(데이터 확인: T10 Rotom-Wash 로그 사망 vs 엔진 생존). 설계안의 "**라운드별 첫
divergence 격리**" 의도대로, **매 라운드 시작에 엔진 상태(HP·on_field)를 로그 관측값으로
재동기화(resync)**한다. 그러면 (a) 기절이 로그 타이밍에 맞아 desync 소멸, (b) divergence가
연쇄 없이 "그 라운드 엔진 예측 vs 로그 관측"을 잰다. run_resid가 per-event에서 하는 일을
풀배틀 흐름(턴순서·교체·효과 타이밍)에서 한다.

## 검증 제약
engine.py truncation으로 전체 실행은 앱사이드. turn_manager(9KB)·fullbattle_run은 샌드박스
정상 — 순수 조각(on_field 타임라인·resync 콜백) 클린룸 검증됨(아래). 앵커는 Read로 고정.

## 대상
`turn_manager.py`(2건) + `engine.py`(2건) + `fullbattle_run.py`(2건: 함수 추가 + run_and_diff
교체). + `run_b4.py`는 resync=True로 호출(이미 갱신).

## 설계 근거 (클린룸 검증됨)
- **resync 시점 = 라운드 시작**: 라운드 T 진입 시 상태를 log[T-1](직전 턴 끝 관측)로 박는다.
  엔진이 라운드 T를 올바른 진입 상태에서 처리 → end-of-T를 log[T]와 비교 = 순수 라운드 오차.
- **HP + on_field 재동기화**로 충분: 기절 유닛은 log[T-1]에서 HP 0 + off-field, 교체된
  incoming이 on-field → 엔진이 옳은 유닛으로 라운드 시작 → desync 불가. 라운드 내 교체/기절은
  엔진이 처리하되 다음 라운드 시작에 재anchor. (검증: T11 진입 resync → Rotom-Wash 0·
  on_field {Latios,Riou} = 로그 일치.)
- status 재동기화는 생략(주 desync 원인은 HP/on_field). status divergence는 별도 잔차(gen5
  무브효과 미모델)로 남되 desync는 안 일으킴.

## FIND/REPLACE — turn_manager.py

### T1 — `__init__` 시그니처에 on_round_start 추가
**FIND**:
```python
                 on_switch_in=None, trace_faint_incoming=None):
```
**REPLACE**:
```python
                 on_switch_in=None, trace_faint_incoming=None, on_round_start=None):
```

### T2 — `__init__` 본문에 self 저장
**FIND**:
```python
        self._trace_faint_incoming = trace_faint_incoming
        self._trace_faint_used = set()
```
**REPLACE**:
```python
        self._trace_faint_incoming = trace_faint_incoming
        self._trace_faint_used = set()
        self._on_round_start = on_round_start
```

### T3 — `run()` 라운드 시작 훅
**FIND**:
```python
        turn = 1
        while turn <= max_turns:
            participants.sort(
```
**REPLACE**:
```python
        turn = 1
        while turn <= max_turns:
            if self._on_round_start is not None:
                self._on_round_start(turn, participants)   # 라운드 시작 resync(트레이스 모드)
            participants.sort(
```

## FIND/REPLACE — engine.py

### E1 — `run_simulation` 시그니처에 on_round_start
**FIND**:
```python
                   move_stat=None, deck_module=None, game_config=None, on_turn_end=None):
```
**REPLACE**:
```python
                   move_stat=None, deck_module=None, game_config=None, on_turn_end=None,
                   on_round_start=None):
```

### E2 — 매니저 생성에 on_round_start 전달
**FIND**:
```python
        trace_faint_incoming=(game_config or {}).get("trace_faint_incoming"),
    )
```
**REPLACE**:
```python
        trace_faint_incoming=(game_config or {}).get("trace_faint_incoming"),
        on_round_start=on_round_start,
    )
```

## FIND/REPLACE — fullbattle_run.py

### F1 — on_field 타임라인 + resync 콜백 추가 (engine_snapshot 위/아무 곳, 함수 정의부에 추가)
**FIND**:
```python
def _make_capture(history):
    """on_turn_end 콜백 — 매 턴 종료 시 엔진 상태를 history[turn]에 스냅샷(마지막이 그 턴
    최종)."""
    def hook(ctx):
        history[ctx.get("turn")] = engine_snapshot(ctx["participants"])
    return hook
```
**REPLACE**:
```python
def _make_capture(history):
    """on_turn_end 콜백 — 매 턴 종료 시 엔진 상태를 history[turn]에 스냅샷(마지막이 그 턴
    최종)."""
    def hook(ctx):
        history[ctx.get("turn")] = engine_snapshot(ctx["participants"])
    return hook


def build_onfield_timeline(trace):
    """턴 경계마다 진영별 on-field 닉 집합 {turn: set(nick)}. switch가 그 진영 on-field 교체."""
    onf = {}
    tl = {}
    last = None
    for e in trace["events"]:
        tn = e.get("turn")
        if tn is None:
            continue
        if last is not None and tn != last:
            tl[last] = set(onf.values())
        if e.get("action") in ("switch", "drag"):
            onf[e["actor_side"]] = e["actor"]
        last = tn
    if last is not None:
        tl[last] = set(onf.values())
    return tl


def _make_resync(log_snaps, onfield_tl):
    """on_round_start 콜백 — 라운드 T 시작에 엔진 상태를 log[T-1]로 재동기화(HP·on_field).
    누적 desync 차단 → divergence가 라운드별 순수 예측오차가 됨."""
    def hook(turn, participants):
        prev = log_snaps.get(turn - 1)
        pof = onfield_tl.get(turn - 1)
        if prev is None:
            return
        for p in participants:
            pid = p.get("id")
            st = prev.get(pid)
            if st and st.get("hp") is not None:
                res = p.setdefault("resources", {}).setdefault("HP", {"current": 0, "max": 0})
                res["current"] = st["hp"]
            if pof is not None:
                p["on_field"] = (pid in pof)
    return hook
```

### F2 — `run_and_diff`에 resync 배선
**FIND**:
```python
def run_and_diff(trace, ref, hp_tol=0, max_turns=100):
    """풀배틀 통합 run + divergence. 엔진은 lazy import(앱 환경).
    반환: {log, engine, divergence, first, summary}."""
    from modules.engine import run_simulation
    ally, enemy, gc, spec = setup_for_engine(trace, ref)
    history = {}
    run_simulation(
        ally, enemy, max_turns=max_turns,
        sys_stats=["atk", "df", "spa", "spd", "spe"], speed_stat="spe",
        global_damage_formula=gc.get("formula"), game_config=gc, silent=True,
        on_turn_end=_make_capture(history),
    )
    log_snaps = build_snapshots(trace)
    rows = divergence(log_snaps, history, hp_tol=hp_tol)
```
**REPLACE**:
```python
def run_and_diff(trace, ref, hp_tol=0, max_turns=100, resync=True):
    """풀배틀 통합 run + divergence. 엔진은 lazy import(앱 환경). resync=True면 라운드별
    재동기화(누적 desync 차단 → 라운드별 순수 예측오차). 반환: {log, engine, divergence, first}."""
    from modules.engine import run_simulation
    ally, enemy, gc, spec = setup_for_engine(trace, ref)
    history = {}
    log_snaps = build_snapshots(trace)
    extra = {}
    if resync:
        extra["on_round_start"] = _make_resync(log_snaps, build_onfield_timeline(trace))
    run_simulation(
        ally, enemy, max_turns=max_turns,
        sys_stats=["atk", "df", "spa", "spd", "spe"], speed_stat="spe",
        global_damage_formula=gc.get("formula"), game_config=gc, silent=True,
        on_turn_end=_make_capture(history), **extra,
    )
    rows = divergence(log_snaps, history, hp_tol=hp_tol)
```

## 검증
- **클린룸(작성 시)**: `build_onfield_timeline` gen5 → 28턴 타임라인 정확(T0 리드·T2 Nanami
  진입·T10 Latios/Riou). `_make_resync` → T11 진입 시 Rotom-Wash HP 0·on_field {Latios,Riou}로
  재동기화(로그 일치). turn_manager round-start 훅이 sort 전에 호출됨.
- **앱사이드**:
  1. `ast.parse`(turn_manager·engine·fullbattle_run) OK.
  2. **회귀**: `on_round_start` 미전달(일반 전투·resync=False) 시 기존 동작 무변경(게이트).
  3. `python run_b4.py`(resync=True) → **엔진 마지막 턴이 100이 아니라 로그(27) 근처**에서
     끝나는지(desync 해소), 라운드별 divergence가 연쇄 없이 실제 예측오차만 남는지 확인.

## 회귀 0
turn_manager: `on_round_start=None`이면 호출 없음(기존 동작). engine: 새 param 기본 None,
미전달 시 매니저에 None 전달(훅 없음). fullbattle_run: resync 기본 True지만 트레이스 전용
경로(run_and_diff)에서만. 일반 run_simulation 호출 전부 무영향.

## 다음
resync로 desync가 풀리면 divergence가 **순수 라운드별 잔차**가 된다 → 남은 타깃을 깨끗이:
Hidden Power 숨김타입·Draco -2 SpA·status 부여(Toxic 등)·날씨 데미지배율. run_resid(per-event)와
run_b4(resync 흐름)가 상보적 루프 도구. 하나씩 닫는다.
```
