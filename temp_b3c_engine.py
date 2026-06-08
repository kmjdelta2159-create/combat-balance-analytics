eng_f1 = """        on_active_faint=(game_config or {}).get("on_active_faint"),
        action_priority=_predict_action_priority,
        on_switch_in=lambda _char, _parts, _alog: _fire_switch_in(_char, _parts, game_config, _alog, field_state),
    )"""

eng_r1 = """        on_active_faint=(game_config or {}).get("on_active_faint"),
        action_priority=_predict_action_priority,
        on_switch_in=lambda _char, _parts, _alog: _fire_switch_in(_char, _parts, game_config, _alog, field_state),
        trace_faint_incoming=(game_config or {}).get("trace_faint_incoming"),
    )"""

with open('modules/engine.py', 'r', encoding='utf-8') as f:
    text = f.read()
count = text.count(eng_f1)
text = text.replace(eng_f1, eng_r1)
with open('modules/engine.py', 'w', encoding='utf-8') as f:
    f.write(text)
print(f'B3c engine patch applied, count: {count}')
