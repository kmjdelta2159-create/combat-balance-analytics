eng_f1 = """                   move_stat=None, deck_module=None, game_config=None):"""
eng_r1 = """                   move_stat=None, deck_module=None, game_config=None, on_turn_end=None):"""

eng_f2 = """    if game_config is None: game_config = {}"""
eng_r2 = """    if game_config is None: game_config = {}
    _preserve_ids = bool(game_config.get("preserve_ids"))"""

eng_f3a = """            p = {**inst, "id": f"A{i+1}", "team": "Ally"}"""
eng_r3a = """            p = {**inst, "id": (inst.get("id") or f"A{i+1}") if _preserve_ids else f"A{i+1}", "team": "Ally"}"""

eng_f3b = """            p = {**inst, "id": f"E{i+1}", "team": "Enemy"}"""
eng_r3b = """            p = {**inst, "id": (inst.get("id") or f"E{i+1}") if _preserve_ids else f"E{i+1}", "team": "Enemy"}"""

eng_f4 = """    manager = TurnManagerCls(
        action_registry=registry,
        turn_executor=turn_executor,
        speed_stat=speed_stat,
        broadcast_phase_event=_broadcast_phase_event,"""

eng_r4 = """    _btn = _broadcast_phase_event
    if on_turn_end is not None:
        def _btn(_pk, _ctx, _targets=None, _orig=_broadcast_phase_event, _cb=on_turn_end):
            _orig(_pk, _ctx, _targets)
            if _pk == "TURN_END":
                _cb(_ctx)
    manager = TurnManagerCls(
        action_registry=registry,
        turn_executor=turn_executor,
        speed_stat=speed_stat,
        broadcast_phase_event=_btn,"""

with open("modules/engine.py", "r", encoding="utf-8") as f:
    text = f.read()

count_1 = text.count(eng_f1)
count_2 = text.count(eng_f2)
count_3a = text.count(eng_f3a)
count_3b = text.count(eng_f3b)
count_4 = text.count(eng_f4)

text = text.replace(eng_f1, eng_r1)
text = text.replace(eng_f2, eng_r2)
text = text.replace(eng_f3a, eng_r3a)
text = text.replace(eng_f3b, eng_r3b)
text = text.replace(eng_f4, eng_r4)

with open("modules/engine.py", "w", encoding="utf-8") as f:
    f.write(text)

print(f"Patch applied to engine.py. Counts: {count_1}, {count_2}, {count_3a}, {count_3b}, {count_4}")
