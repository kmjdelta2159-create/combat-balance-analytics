EFFECT_KEY_ROLES = ("ability", "item", "status")

def is_empty_effect_value(value):
    if value is None:
        return True
    try:
        import math
        if isinstance(value, float) and math.isnan(value):
            return True
    except Exception:
        pass
    
    empty_strings = {
        "", "none", "nan", "null", "없음", "비어 있음", "<na>", "n/a"
    }
    return str(value).strip().lower() in empty_strings

def promote_effect_keys(inst, game_config=None):
    """
    Promote specific gimmicks to top-level keys based on channel configuration or hints.
    """
    if not isinstance(inst, dict) or "gimmicks" not in inst:
        return inst
        
    gimmicks = inst.get("gimmicks", {})
    channels = {}
    if game_config and "channels" in game_config:
        channels = game_config["channels"]
        
    hints = {
        "ability": ("ability", "trait", "passive", "특성", "어빌리티", "능력"),
        "item": ("item", "held_item", "held item", "equipment", "equip", "아이템", "도구", "장비"),
        "status": ("status", "state", "condition", "ailment", "상태", "상태이상"),
    }
    
    for role in EFFECT_KEY_ROLES:
        if role in inst and not is_empty_effect_value(inst.get(role)):
            # Already exists at top level
            continue
            
        role_col = None
        if role in channels:
            role_col = channels[role]
        else:
            # Fallback to hint
            for g_col in gimmicks.keys():
                g_col_lower = str(g_col).lower()
                if any(hint in g_col_lower for hint in hints[role]):
                    role_col = g_col
                    break
                    
        if role_col is None:
            continue
            
        if role_col in gimmicks:
            val = gimmicks[role_col]
            if not is_empty_effect_value(val):
                inst[role] = val
                
    return inst
