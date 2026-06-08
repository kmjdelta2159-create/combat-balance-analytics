find1 = """    char = ctx["active_char"]
    gc = ctx.get("game_config") or {}
    pol = gc.get("switch_policy")"""

replace1 = """    char = ctx["active_char"]
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
    pol = gc.get("switch_policy")"""

find2 = """    # ── 자발적 교체 정책 (선택) — 조건 만족 시 교체로 턴 소모, 이번 턴 공격 생략 ──
    if _maybe_voluntary_switch(ctx):
        ctx["targets"] = []
        return"""

replace2 = """    # ── 자발적 교체 정책 (선택) — 조건 만족 시 교체로 턴 소모, 이번 턴 공격 생략 ──
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
        return"""

find3 = """def _act_move_select(ctx):
    \"\"\"무브 선택 Phase (Phase 8a) — movepool에서 그리디(기대 데미지 최대)로 무브 선택.
    movepool 미보유 시 current_move=None → 단일 global 공식 경로 유지(default=identity).
    선택 본체는 공유 순수 코어 _select_move_pure(행동순서 예측기와 동일 경로)에 위임한다.\"\"\"
    ctx["current_move"] = _select_move_pure(
        ctx["active_char"], ctx.get("current_target"),
        ctx.get("sys_stats"), ctx.get("game_config"), ctx.get("formula_str"))"""

replace3 = """def _act_move_select(ctx):
    \"\"\"무브 선택 Phase (Phase 8a) — movepool에서 그리디(기대 데미지 최대)로 무브 선택.
    movepool 미보유 시 current_move=None → 단일 global 공식 경로 유지(default=identity).
    선택 본체는 공유 순수 코어 _select_move_pure(행동순서 예측기와 동일 경로)에 위임한다.
    트레이스 구동 시 target_select가 심어둔 로그 무브를 그대로 사용(계산 우회).\"\"\"
    if ctx.get("_trace_move") is not None:
        ctx["current_move"] = ctx["_trace_move"]
        return
    ctx["current_move"] = _select_move_pure(
        ctx["active_char"], ctx.get("current_target"),
        ctx.get("sys_stats"), ctx.get("game_config"), ctx.get("formula_str"))"""

with open("modules/engine.py", "r", encoding="utf-8") as f:
    text = f.read()

count1 = text.count(find1)
count2 = text.count(find2)
count3 = text.count(find3)

text = text.replace(find1, replace1)
text = text.replace(find2, replace2)
text = text.replace(find3, replace3)

with open("modules/engine.py", "w", encoding="utf-8") as f:
    f.write(text)

print(f"Patch applied. Replacements: {count1}, {count2}, {count3}")
