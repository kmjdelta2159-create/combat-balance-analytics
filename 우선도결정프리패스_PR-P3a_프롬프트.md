# PR-P3a (무브 우선도 결정 프리패스 — 순수 코어 추출) Antigravity 프롬프트

## 목적
`modules/engine.py`의 타겟 선택·무브 선택 로직을 **부작용 없는 공유 순수 코어**로 추출하고,
기존 액션 함수가 그 코어를 호출하도록 리팩터한다. **동작은 바꾸지 않는다(회귀 0)** — 이후
PR-P3b의 행동순서 예측기가 같은 코어를 호출해 "예측한 무브 = 실제 실행하는 무브"를 구조적으로
보장하기 위한 준비 단계다. 이 PR 자체는 행동을 도입하지 않는 순수 리팩터다.

## 제약
- `modules/engine.py` **한 파일만** 수정. 다른 파일(turn_manager.py·move_extraction.py·step2 등) 손대지 말 것.
- 아래 find/replace **2건만** 적용. 곁가지 수정·포매팅 변경·import 추가 금지.
- 들여쓰기는 4-space, 기존 코드 스타일 그대로.

## 적용 1 — `_act_target_select` 앞에 `_candidate_targets` 추가 + `_act_target_select` 리팩터

다음 블록을 **정확히** 찾아서:

```python
def _act_target_select(ctx):
    """트리거 조건 확인 후 사거리 내 타겟 선택"""
    char = ctx["active_char"]
    participants = ctx["participants"]
    trigger_val = ctx["trigger_val"]
    target_val = ctx["target_val"]

    # 비전투 트리거만 행동 생략. 미인식 트리거는 행동하도록 fail-safe.
    if str(trigger_val).strip() in NON_ACTING_TRIGGERS:
        ctx["targets"] = []
        return

    # ── 자발적 교체 정책 (선택) — 조건 만족 시 교체로 턴 소모, 이번 턴 공격 생략 ──
    if _maybe_voluntary_switch(ctx):
        ctx["targets"] = []
        return

    # 타겟 후보: 상대 팀의 on_field(액티브) 유닛만. 예비(reserve)는 제외.
    # on_field 미설정 시 True → 현행 전원-동시 동작과 동일(회귀 0).
    opponents_all = [p for p in participants
                     if p['team'] != char['team'] and get_current(p) > 0
                     and p.get('on_field', True)]
    if not opponents_all:
        # on_field 적이 없음. 예비 포함 상대 팀 전멸 여부로만 전투 종료를 판정한다.
        team_alive = any(p['team'] != char['team'] and get_current(p) > 0
                         for p in participants)
        if not team_alive:
            ctx["add_log"](f"  [Phase: TARGET_SELECT] 🏆 {char['team']} 반대 진영 궤멸!")
            ctx["battle_over"] = True
        ctx["targets"] = []
        return

    # ── 사거리 필터 (SpatialModule + attack_range 둘 다 있을 때만) ──
    spatial = ctx.get("spatial_module")
    attack_range = ctx.get("attack_range")
    if spatial is not None and attack_range is not None:
        opponents = [o for o in opponents_all
                     if spatial.in_range(char, o, attack_range)]
    else:
        opponents = opponents_all

    if not opponents:
        # 적은 살아있으나 사거리 내 타겟 없음 → 이번 턴 행동 생략 (battle_over 아님)
        ctx["add_log"](
            f"[Turn {ctx['turn']}] {char['id']} ({char['name']}) "
            f"[Phase: TARGET_SELECT] 사거리 내 타겟 없음 — 행동 생략"
        )
        ctx["targets"] = []
        return

    norm_target = _normalize_target_tag(target_val)
    if norm_target == "AoE_All":
        ctx["targets"] = opponents
    elif norm_target == "Lowest_HP":
        ctx["targets"] = [min(opponents, key=lambda x: get_current(x))]
    else:  # Single_Target
        ctx["targets"] = [opponents[0]]

    ctx["add_log"](
        f"[Turn {ctx['turn']}] {char['id']} ({char['name']}) 행동! "
        f"[Phase: TARGET_SELECT] 타겟: {', '.join(t['id'] for t in ctx['targets'])}"
    )
```

다음으로 **교체**:

```python
def _candidate_targets(char, participants, target_val, spatial_module, attack_range):
    """read-only 타겟 후보 결정 — 상대 on_field 후보 → 사거리 필터 → target 태그 정규화로
    최종 타겟 리스트를 만든다. 부작용 없음(로그·battle_over·교체 없음). 후보 없거나 사거리
    내 타겟이 없으면 빈 리스트. _act_target_select(실행)와 행동순서 예측기가 공유한다 —
    예측=실행 보장을 위해 타겟 선택 로직은 이 함수 1벌로만 존재한다."""
    opponents_all = [p for p in participants
                     if p['team'] != char['team'] and get_current(p) > 0
                     and p.get('on_field', True)]
    if not opponents_all:
        return []
    if spatial_module is not None and attack_range is not None:
        opponents = [o for o in opponents_all
                     if spatial_module.in_range(char, o, attack_range)]
    else:
        opponents = opponents_all
    if not opponents:
        return []
    norm_target = _normalize_target_tag(target_val)
    if norm_target == "AoE_All":
        return opponents
    elif norm_target == "Lowest_HP":
        return [min(opponents, key=lambda x: get_current(x))]
    else:  # Single_Target
        return [opponents[0]]


def _act_target_select(ctx):
    """트리거 조건 확인 후 사거리 내 타겟 선택. 후보·사거리·태그 선택은 공유 순수 코어
    _candidate_targets(행동순서 예측기와 동일 경로)에 위임한다 — 셸은 비전투 트리거 스킵,
    자발적 교체, battle_over 판정, 로그만 담당한다."""
    char = ctx["active_char"]
    participants = ctx["participants"]
    trigger_val = ctx["trigger_val"]
    target_val = ctx["target_val"]

    # 비전투 트리거만 행동 생략. 미인식 트리거는 행동하도록 fail-safe.
    if str(trigger_val).strip() in NON_ACTING_TRIGGERS:
        ctx["targets"] = []
        return

    # ── 자발적 교체 정책 (선택) — 조건 만족 시 교체로 턴 소모, 이번 턴 공격 생략 ──
    if _maybe_voluntary_switch(ctx):
        ctx["targets"] = []
        return

    # 타겟 후보: 상대 팀의 on_field(액티브) 유닛만. 예비(reserve)는 제외.
    # on_field 미설정 시 True → 현행 전원-동시 동작과 동일(회귀 0).
    opponents_all = [p for p in participants
                     if p['team'] != char['team'] and get_current(p) > 0
                     and p.get('on_field', True)]
    if not opponents_all:
        # on_field 적이 없음. 예비 포함 상대 팀 전멸 여부로만 전투 종료를 판정한다.
        team_alive = any(p['team'] != char['team'] and get_current(p) > 0
                         for p in participants)
        if not team_alive:
            ctx["add_log"](f"  [Phase: TARGET_SELECT] 🏆 {char['team']} 반대 진영 궤멸!")
            ctx["battle_over"] = True
        ctx["targets"] = []
        return

    # ── 후보 → 사거리 → target 태그 (공유 순수 코어; 예측기와 동일 경로) ──
    targets = _candidate_targets(char, participants, target_val,
                                 ctx.get("spatial_module"), ctx.get("attack_range"))
    if not targets:
        # 적은 살아있으나 사거리 내 타겟 없음 → 이번 턴 행동 생략 (battle_over 아님)
        ctx["add_log"](
            f"[Turn {ctx['turn']}] {char['id']} ({char['name']}) "
            f"[Phase: TARGET_SELECT] 사거리 내 타겟 없음 — 행동 생략"
        )
        ctx["targets"] = []
        return

    ctx["targets"] = targets
    ctx["add_log"](
        f"[Turn {ctx['turn']}] {char['id']} ({char['name']}) 행동! "
        f"[Phase: TARGET_SELECT] 타겟: {', '.join(t['id'] for t in ctx['targets'])}"
    )
```

## 적용 2 — `_act_move_select` 앞에 `_select_move_pure` 추가 + `_act_move_select` 리팩터

다음 블록을 **정확히** 찾아서:

```python
def _act_move_select(ctx):
    """무브 선택 Phase (Phase 8a) — movepool에서 그리디(기대 데미지 최대)로 무브 선택.
    movepool 미보유 시 current_move=None → 단일 global 공식 경로 유지(default=identity)."""
    char = ctx["active_char"]
    movepool = char.get("movepool")
    if not movepool:
        ctx["current_move"] = None
        return
    # ── 전략 정책 (선택): setup_first — 아직 안 쓴 효과 무브를 데미지보다 먼저 고른다 ──
    _gc_pol = ctx.get("game_config") or {}
    if _gc_pol.get("move_policy") == "setup_first":
        _eff_map = _gc_pol.get("move_effects") or {}
        for _smv in movepool:
            _snm = _smv.get("name")
            if _snm in _eff_map and not any(
                str(_s.get("id", "")).startswith(f"move_effect_{_snm}_")
                for _s in char.get("active_states", [])
            ):
                ctx["current_move"] = _smv
                return
    t = ctx.get("current_target")
    if t is None:
        ctx["current_move"] = movepool[0]
        return
    import math
    sys_stats = ctx["sys_stats"]
    game_config = ctx.get("game_config") or {}
    formula_eval = str(ctx["formula_str"]).lower() if ctx.get("formula_str") else "0"
    base_env = {s: get_effective_stat(char, s) for s in sys_stats}
    base_env.update({"target_" + s: get_effective_stat(t, s) for s in sys_stats})
    base_env["current_health"] = get_current(char)
    base_env["max_health"] = get_max(char)
    base_env["target_current_health"] = get_current(t)
    base_env["target_max_health"] = get_max(t)
    best, best_dmg = movepool[0], -1.0
    for _mv in movepool:
        env = dict(base_env)
        env["move_power"] = float(_mv.get("power", 0))
        _cat = game_config.get("categories", {}).get(_mv.get("category"))
        if _cat:
            env["offense"] = get_effective_stat(char, _cat["offense"])
            env["defense"] = get_effective_stat(t, _cat["defense"])
        env = {str(k).lower(): float(v) for k, v in env.items()}
        try:
            _base = max(0, int(float(eval(formula_eval, {"__builtins__": None, "math": math}, env))))
        except Exception:
            _base = 0.0
        _d = _base * _move_type_multiplier(_mv, t, game_config) * _move_stab_multiplier(_mv, char, game_config)
        if _d > best_dmg:
            best, best_dmg = _mv, _d
    ctx["current_move"] = best
```

다음으로 **교체**:

```python
def _select_move_pure(char, target, sys_stats, game_config, formula_str):
    """read-only 무브 선택 — setup_first 정책 분기 + 그리디(기대 데미지 최대) 선택.
    movepool 미보유 시 None, 타겟 None 시 movepool[0]. 상태 변경 없음(읽기만).
    _act_move_select(실행)와 행동순서 예측기가 공유한다 — 예측=실행 보장을 위해 무브
    선택 로직은 이 함수 1벌로만 존재한다. (game_config None은 {}로 정규화해 현행 동일.)"""
    movepool = char.get("movepool")
    if not movepool:
        return None
    gc = game_config or {}
    # ── 전략 정책 (선택): setup_first — 아직 안 쓴 효과 무브를 데미지보다 먼저 고른다 ──
    if gc.get("move_policy") == "setup_first":
        _eff_map = gc.get("move_effects") or {}
        for _smv in movepool:
            _snm = _smv.get("name")
            if _snm in _eff_map and not any(
                str(_s.get("id", "")).startswith(f"move_effect_{_snm}_")
                for _s in char.get("active_states", [])
            ):
                return _smv
    t = target
    if t is None:
        return movepool[0]
    import math
    formula_eval = str(formula_str).lower() if formula_str else "0"
    base_env = {s: get_effective_stat(char, s) for s in sys_stats}
    base_env.update({"target_" + s: get_effective_stat(t, s) for s in sys_stats})
    base_env["current_health"] = get_current(char)
    base_env["max_health"] = get_max(char)
    base_env["target_current_health"] = get_current(t)
    base_env["target_max_health"] = get_max(t)
    best, best_dmg = movepool[0], -1.0
    for _mv in movepool:
        env = dict(base_env)
        env["move_power"] = float(_mv.get("power", 0))
        _cat = gc.get("categories", {}).get(_mv.get("category"))
        if _cat:
            env["offense"] = get_effective_stat(char, _cat["offense"])
            env["defense"] = get_effective_stat(t, _cat["defense"])
        env = {str(k).lower(): float(v) for k, v in env.items()}
        try:
            _base = max(0, int(float(eval(formula_eval, {"__builtins__": None, "math": math}, env))))
        except Exception:
            _base = 0.0
        _d = _base * _move_type_multiplier(_mv, t, gc) * _move_stab_multiplier(_mv, char, gc)
        if _d > best_dmg:
            best, best_dmg = _mv, _d
    return best


def _act_move_select(ctx):
    """무브 선택 Phase (Phase 8a) — movepool에서 그리디(기대 데미지 최대)로 무브 선택.
    movepool 미보유 시 current_move=None → 단일 global 공식 경로 유지(default=identity).
    선택 본체는 공유 순수 코어 _select_move_pure(행동순서 예측기와 동일 경로)에 위임한다."""
    ctx["current_move"] = _select_move_pure(
        ctx["active_char"], ctx.get("current_target"),
        ctx.get("sys_stats"), ctx.get("game_config"), ctx.get("formula_str"))
```

## 적용 후 자가 점검 (보고만, 코드 변경 금지)
1. `def _candidate_targets(` 1회, `def _select_move_pure(` 1회 존재.
2. `_act_target_select`가 `_candidate_targets(`를 호출, `_act_move_select`가 `_select_move_pure(`를 호출.
3. `modules/engine.py`가 구문 오류 없이 import/compile 됨.
4. turn_manager.py·move_extraction.py·step2_system_definition.py는 **변경 없음**.

## 회귀 0 근거
- `_candidate_targets`는 기존 `_act_target_select`의 후보→사거리→태그 로직을 그대로 옮긴 것이고,
  비어있을 때의 battle_over·로그 분기는 셸(`_act_target_select`)에 그대로 남아 3-way 동작이 동일.
- `_select_move_pure`는 setup_first 분기 + 그리디 본체를 그대로 옮긴 것(`game_config or {}`로 정규화).
- 보조자 측 하니스(verify_priority_p3a.py)에서 구·신 15개 케이스 출력 동일 확인 완료.
