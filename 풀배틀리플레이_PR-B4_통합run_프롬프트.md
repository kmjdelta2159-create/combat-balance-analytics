# PR-B4 — 풀배틀 통합 run + 라운드별 divergence 리포트 (신규 모듈 + 엔진 훅, 앱사이드)

## 목적
A 하니스의 마지막 조각·골드 스탠다드. `prepare_run`(B2/B3) 셋업을 엔진 턴루프로 *전투 전체*
구동하고(트레이스 selector·자발교체·기절 incoming 발동), 라운드별 엔진 상태를 로그 스냅샷과
대조해 **divergence 리포트**를 낸다. 첫 divergence가 미모델 메커니즘을 라운드 단위로 지목 →
역설계→수정 루프가 전투 스케일로 작동. 신규 모듈 `fullbattle_run.py` + engine.py에 게이트
훅 2개. 전체 실행은 앱사이드(truncation), 순수 조각은 클린룸 검증됨.

## 검증 제약
engine.py truncation으로 *전체 run은 앱에서*. 아래 엔진 FIND/REPLACE 앵커는 Read로 고정한
현재 텍스트. 신규 모듈의 순수 함수(engine_snapshot·capture·리포트·divergence 파이프라인)는
클린룸 검증됨(아래 §검증).

## 통합에서 드러난 두 정합 이슈 (Read로 확인 — B4가 해결)
1. **엔진이 id를 A1/E1로 재할당**(`run_simulation` L1458/1468) → 닉 키잉 trace_actions가 안
   맞는다. → `game_config['preserve_ids']`로 닉 보존(게이트, 회귀0).
2. **HP는 `char['resources']['HP']={current,max}`에 산다**(엔진 `get_current`) — B2 char의
   `hp/maxhp` 필드와 다름. → run 직전 `init_resources(p, maxhp)`로 자원 초기화.
3. **라운드 상태 캡처 훅 부재** → `run_simulation`에 `on_turn_end` 콜백 추가(TURN_END
   브로드캐스터 합성, 게이트).

## 대상
**신규 파일** `modules/fullbattle_run.py` + **engine.py FIND/REPLACE 4건**.

## 생성할 파일 — `modules/fullbattle_run.py` (전체, 바이트 그대로)

```python
"""
풀배틀 통합 run — prepare_run → 엔진 실행(트레이스 구동) → 라운드별 divergence.

A 하니스의 골드 스탠다드. per-event(데미지 1건씩)와 달리 엔진의 턴 스케줄러·전 페이즈·효과를
*전투 전체* 동안 로그대로 구동하고, 라운드별 엔진 상태를 로그 스냅샷과 대조한다. 엔진 호출은
run_and_diff 안에서 lazy import(앱 환경) — 순수 함수(engine_snapshot·capture·리포트)는 엔진
무관이라 클린룸 검증된다.

정직한 한계(B4 리포트가 드러낼 후속): 데미지 롤(0.85~1.0) 미관측이라 엔진 max-roll vs 로그
실측 HP는 롤 폭만큼 어긋난다 → 작은 hp 차이는 롤 노이즈, **구조적 신호는 faint·status·큰 hp
차이**(미모델 효과: Psyshock 방어타격·SR 타입스케일·Life Orb·status 부여·피벗·크리). 첫 구조적
divergence를 격리하는 게 이 리포트의 핵심.
"""
from modules.battle_setup import prepare_run
from modules.fullbattle_diff import build_snapshots, divergence
from modules.resource import get_current, init_resources


def _status_of(p):
    """participant active_states에서 상태이상 토큰(gate_status/status) 추출. 없으면 None."""
    for s in p.get("active_states", []):
        st = s.get("gate_status") or s.get("status")
        if st:
            return st
    return None


def engine_snapshot(participants):
    """엔진 participant 리스트 → {id: {hp, status, fainted}} (로그 스냅샷과 동일 스키마)."""
    return {p["id"]: {"hp": int(get_current(p)), "status": _status_of(p),
                      "fainted": get_current(p) <= 0}
            for p in participants}


def _make_capture(history):
    """on_turn_end 콜백 — 매 턴 종료 시 엔진 상태를 history[turn]에 스냅샷(마지막이 그 턴
    최종)."""
    def hook(ctx):
        history[ctx.get("turn")] = engine_snapshot(ctx["participants"])
    return hook


def setup_for_engine(trace, ref):
    """prepare_run → 엔진 호출용 (ally_instances, enemy_instances, game_config) 조립.
    닉 보존(preserve_ids) + HP 자원 초기화 + 진영별 roster_idx 정렬."""
    parts, spec, ta = prepare_run(trace, ref)
    gc = spec["game_config"]
    gc["preserve_ids"] = True
    for p in parts:
        init_resources(p, p["maxhp"])           # 엔진 HP 모델(resources.HP)
    ally = sorted([p for p in parts if p.get("side") == "p1"],
                  key=lambda x: x.get("roster_idx", 0))
    enemy = sorted([p for p in parts if p.get("side") == "p2"],
                   key=lambda x: x.get("roster_idx", 0))
    return ally, enemy, gc, spec


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
    structural = [r for r in rows if r[2] in ("faint", "status", "missing")
                  or (r[2] == "hp" and r[3] is not None and r[4] is not None
                      and r[3] < r[4])]   # 로그HP<엔진HP = 엔진이 데미지 덜 줌(미모델)
    first = min(structural, key=lambda r: r[0]) if structural else None
    return {"log": log_snaps, "engine": history, "divergence": rows,
            "structural": structural, "first": first}


def format_report(result):
    """divergence 결과 → 사람이 읽는 리포트(첫 구조적 divergence 격리 + 전체 목록)."""
    rows = result["divergence"]
    log = result["log"]
    max_turn = max(log) if log else 0
    lines = [f"=== 풀배틀 divergence 리포트 (턴 0~{max_turn}) ==="]
    if not rows:
        lines.append("divergence 없음 — 전 라운드 일치 ✅")
        return "\n".join(lines)
    first = result.get("first")
    if first:
        lines.append(f"첫 구조적 divergence: T{first[0]} {first[1]} "
                     f"[{first[2]}] 로그={first[3]} 엔진={first[4]}")
    else:
        lines.append("구조적 divergence 없음 (잔차는 롤 노이즈 추정)")
    lines.append(f"총 {len(rows)}건 (구조적 {len(result['structural'])}건):")
    for r in rows[:50]:
        tag = "★" if r in result["structural"] else " "
        lines.append(f" {tag}T{r[0]:>2} {str(r[1]):12} [{r[2]:7}] "
                     f"로그={r[3]} 엔진={r[4]}")
    return "\n".join(lines)
```

## engine.py FIND/REPLACE

### F/R 1 — `run_simulation` 시그니처에 on_turn_end 추가
**FIND**:
```python
                   move_stat=None, deck_module=None, game_config=None):
```
**REPLACE**:
```python
                   move_stat=None, deck_module=None, game_config=None, on_turn_end=None):
```

### F/R 2 — preserve_ids 플래그
**FIND**:
```python
    if game_config is None: game_config = {}
```
**REPLACE**:
```python
    if game_config is None: game_config = {}
    _preserve_ids = bool(game_config.get("preserve_ids"))
```

### F/R 3 — 닉 id 보존 (ally·enemy 두 줄)
**FIND**:
```python
            p = {**inst, "id": f"A{i+1}", "team": "Ally"}
```
**REPLACE**:
```python
            p = {**inst, "id": (inst.get("id") or f"A{i+1}") if _preserve_ids else f"A{i+1}", "team": "Ally"}
```
**FIND**:
```python
            p = {**inst, "id": f"E{i+1}", "team": "Enemy"}
```
**REPLACE**:
```python
            p = {**inst, "id": (inst.get("id") or f"E{i+1}") if _preserve_ids else f"E{i+1}", "team": "Enemy"}
```

### F/R 4 — TURN_END 캡처 훅 (브로드캐스터 합성)
**FIND**:
```python
    manager = TurnManagerCls(
        action_registry=registry,
        turn_executor=turn_executor,
        speed_stat=speed_stat,
        broadcast_phase_event=_broadcast_phase_event,
```
**REPLACE**:
```python
    _btn = _broadcast_phase_event
    if on_turn_end is not None:
        def _btn(_pk, _ctx, _targets=None, _orig=_broadcast_phase_event, _cb=on_turn_end):
            _orig(_pk, _ctx, _targets)
            if _pk == "TURN_END":
                _cb(_ctx)
    manager = TurnManagerCls(
        action_registry=registry,
        turn_executor=turn_executor,
        speed_stat=speed_stat,
        broadcast_phase_event=_btn,
```

## 검증 (클린룸 — 순수 조각, 작성 시 수행)
gen5 로그 스냅샷 기준:
- `engine_snapshot`: mock participant(resources.HP + active_states) → {hp,status,fainted} 스키마
  정확(기절·tox 반영).
- **perfect-engine self-diff = 0**: 로그 스냅샷을 엔진 산출로 흉내 → divergence 0.
- **오차 주입**: 미모델 status(엔진이 Toxic 미부여 → status 셀 26건) + 한 턴 hp −6 → divergence
  **27건** 포착, 첫 구조적 divergence(T5 hp) 격리, 리포트 포맷 정상.

## 앱사이드 검증 (engine 통합 — 전체 run)
1. `ast.parse`(engine·fullbattle_run) OK.
2. **회귀**: `on_turn_end`·`preserve_ids` 미설정 일반 전투 한 판 → id 여전히 A1/E1, 동작 무변경
   (두 훅 다 게이트).
3. **풀배틀 run**:
   ```python
   from modules.showdown_trace import parse_replay
   from modules.fullbattle_run import run_and_diff, format_report
   import modules.reference_gen5 as r5
   t = parse_replay(open('Gen5OU-2015-05-11-reymedy-leftiez.html', encoding='utf-8').read())
   res = run_and_diff(t, r5, hp_tol=10)
   print(format_report(res))
   ```
   → 첫 구조적 divergence 지점·전체 목록 확인. 로그를 붙여주면 함께 점검.

## 예상 잔차 (리포트가 라운드 단위로 지목 — 역설계→수정 루프 입력)
- **롤 노이즈**(작은 hp 차): 데미지 롤 미관측 → 엔진 max-roll. 구조적 아님.
- **status 미부여**: Toxic·Spore·burn = gen5 무브효과 미설정 → status 셀 divergence(효과-스키마).
- **피벗(Volt Switch)**: T3 교체-아웃 미발동(무브효과).
- **Psyshock 방어타격·SR 타입스케일·Hidden Power 타입·크리 미재생·턴내 교체순서**: 각각
  해당 라운드 hp/faint divergence로 표면화 → 효과-스키마/엔진/ordering 후속.

## 회귀 0
신규 파일 1개 + engine 게이트 훅 2개(`on_turn_end`·`preserve_ids` 미설정 시 기존 경로 그대로).
기존 호출자 시그니처 무변경(새 param 기본값).

## payoff
이로써 *임의의 실 싱글 전투*를 넣어 효과·해결·턴순서·교체를 라운드별로 대조하는 골드
스탠다드가 선다. divergence가 미모델 메커니즘·세트를 라운드 단위로 지목 → 역설계→수정 루프가
전투 스케일로 작동. 1차목표("실 전투를 수치까지 재현")의 합격 시험 그 자체.
```
