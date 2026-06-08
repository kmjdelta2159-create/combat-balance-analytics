# Patch script for PR-B3c
# battle_setup.py (FIND/REPLACE 1)
bs_f1 = """    gc["trace_faint_incoming"] = ta["faint_incoming"]
    gc["switch_policy"] = {"type": "trace"}   # 트레이스 구동 — hp_threshold 정책 대체
    return parts, spec, ta"""

bs_r1 = """    gc["trace_faint_incoming"] = ta["faint_incoming"]
    gc["switch_policy"] = {"type": "trace"}   # 트레이스 구동 — hp_threshold 정책 대체
    gc["on_active_faint"] = "replace_from_reserve"  # 기절 시 예비 진입(로그 지정 incoming)
    return parts, spec, ta"""

with open("modules/battle_setup.py", "r", encoding="utf-8") as f:
    text = f.read()
text = text.replace(bs_f1, bs_r1)
with open("modules/battle_setup.py", "w", encoding="utf-8") as f:
    f.write(text)

# turn_manager.py (FIND/REPLACE 2, 3, 4)
tm_f1 = """    def __init__(self, action_registry, turn_executor,
                 speed_stat=None, broadcast_phase_event=None,
                 win_condition: WinCondition = None,
                 resource_module=None, on_active_faint=None, action_priority=None,
                 on_switch_in=None):"""

tm_r1 = """    def __init__(self, action_registry, turn_executor,
                 speed_stat=None, broadcast_phase_event=None,
                 win_condition: WinCondition = None,
                 resource_module=None, on_active_faint=None, action_priority=None,
                 on_switch_in=None, trace_faint_incoming=None):"""

tm_f2 = """        self._on_active_faint = on_active_faint
        self._action_priority = action_priority
        self._on_switch_in = on_switch_in"""

tm_r2 = """        self._on_active_faint = on_active_faint
        self._action_priority = action_priority
        self._on_switch_in = on_switch_in
        self._trace_faint_incoming = trace_faint_incoming
        self._trace_faint_used = set()"""

tm_f3 = """            for p in dead_on_field:
                p['on_field'] = False
            reserve = sorted(
                (p for p in members
                 if not p.get('on_field') and self.resource_module.is_alive(p)),
                key=lambda x: x.get('roster_idx', 0)
            )
            for p in reserve[:len(dead_on_field)]:
                p['on_field'] = True
                add_log(f"🔁 {team} 예비 {p.get('id', '?')} "
                        f"({p.get('name', '?')}) 등장!")
                # 진입 즉시 처리 (S7) — engine 콜백으로 진입 효과·이벤트 발화. 콜백 미전달 시
                # 다음-턴 _act_on_switch fallback을 위해 just_switched_in을 세팅(회귀 0).
                if self._on_switch_in is not None:
                    p['just_switched_in'] = False
                    self._on_switch_in(p, participants, add_log)
                else:
                    p['just_switched_in'] = True"""

tm_r3 = """            for p in dead_on_field:
                p['on_field'] = False
            reserve = sorted(
                (p for p in members
                 if not p.get('on_field') and self.resource_module.is_alive(p)),
                key=lambda x: x.get('roster_idx', 0)
            )
            # incoming 결정: 죽은 유닛별로 트레이스 지정(outgoing→incoming) 우선, 없으면
            # roster_idx 순 폴백(현행). trace_faint_incoming 미설정 시 전부 폴백 = 회귀 0.
            _tfi = self._trace_faint_incoming
            ri = 0
            for dead in dead_on_field:
                inc = None
                if _tfi is not None:
                    ent = next((e for e in _tfi
                                if e.get('outgoing') == dead.get('id')
                                and e.get('outgoing') not in self._trace_faint_used), None)
                    if ent is not None:
                        cand = next((q for q in members
                                     if q.get('id') == ent.get('incoming')
                                     and not q.get('on_field')
                                     and self.resource_module.is_alive(q)), None)
                        if cand is not None:
                            self._trace_faint_used.add(ent['outgoing'])
                            inc = cand
                if inc is None:
                    while ri < len(reserve) and reserve[ri].get('on_field'):
                        ri += 1
                    if ri < len(reserve):
                        inc = reserve[ri]
                        ri += 1
                if inc is None:
                    continue
                inc['on_field'] = True
                add_log(f"🔁 {team} 예비 {inc.get('id', '?')} "
                        f"({inc.get('name', '?')}) 등장!")
                # 진입 즉시 처리 (S7) — engine 콜백으로 진입 효과·이벤트 발화. 콜백 미전달 시
                # 다음-턴 _act_on_switch fallback을 위해 just_switched_in을 세팅(회귀 0).
                if self._on_switch_in is not None:
                    inc['just_switched_in'] = False
                    self._on_switch_in(inc, participants, add_log)
                else:
                    inc['just_switched_in'] = True"""

with open("modules/turn_manager.py", "r", encoding="utf-8") as f:
    text = f.read()
text = text.replace(tm_f1, tm_r1)
text = text.replace(tm_f2, tm_r2)
text = text.replace(tm_f3, tm_r3)
with open("modules/turn_manager.py", "w", encoding="utf-8") as f:
    f.write(text)


# engine.py (FIND/REPLACE 5)
eng_f1 = """        on_active_faint=(game_config or {}).get("on_active_faint"),
        action_priority=_predict_action_priority,
        on_switch_in=lambda _char, _parts, _alog: _fire_switch_in(_char, _parts, game_config, _alog, field_state),
    )"""

eng_r1 = """        on_active_faint=(game_config or {}).get("on_active_faint"),
        action_priority=_predict_action_priority,
        on_switch_in=lambda _char, _parts, _alog: _fire_switch_in(_char, _parts, game_config, _alog, field_state),
        trace_faint_incoming=(game_config or {}).get("trace_faint_incoming"),
    )"""

with open("modules/engine.py", "r", encoding="utf-8") as f:
    text = f.read()
text = text.replace(eng_f1, eng_r1)
with open("modules/engine.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Patch applied to battle_setup.py, turn_manager.py, engine.py")
