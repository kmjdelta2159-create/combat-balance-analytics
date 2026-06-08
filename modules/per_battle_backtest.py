# -*- coding: utf-8 -*-
"""
per_battle_backtest.py — Phase 8c-α.

전투 로그의 각 전투를 엔진으로 재시뮬해 예측 승자 vs 실제 승자 일치율을 측정한다.
검증 패널의 기존 "승률"(1매치업↔로그평균 비교)이 구조적으로 부서져 있어 의미 없는
점수를 내는 문제를 해결한다 — Pokemon 클린룸 harness가 외부에서 한 일을 앱 안에서
직접 한다.

순수 모듈 — pandas + 표준 라이브러리만 의존. Streamlit/engine 직접 import 없음.
엔진 호출은 호출부(step6)에서 ProcessPoolExecutor + _worker_simulate_match로 한다.
"""
import pandas as pd
from modules.effect_key_roles import promote_effect_keys


def _safe_float(v):
    """str/int/float/NaN → float (NaN/실패 → 0.0)."""
    try:
        v = float(v)
        return v if v == v else 0.0
    except (TypeError, ValueError):
        return 0.0


def _is_win_signal(v):
    """target_col 값을 'ally가 이김'으로 해석할지 판정.
    숫자형(0/1, True/False)과 흔한 문자열(Win/Victory/Ally)을 모두 처리."""
    if v is None:
        return False
    try:
        if pd.isna(v):
            return False
    except (TypeError, ValueError):
        pass
    s = str(v).strip().lower()
    _truthy = {"1", "1.0", "true", "yes", "y", "win", "victory", "victorious",
               "ally", "won", "winner"}
    _falsy = {"0", "0.0", "false", "no", "n", "lose", "loss", "defeat",
              "defeated", "enemy", "lost", "loser"}
    if s in _truthy:
        return True
    if s in _falsy:
        return False
    try:
        return float(s) > 0
    except (TypeError, ValueError):
        return False


def _is_empty_id(v):
    if v is None:
        return True
    try:
        import math
        if isinstance(v, float) and math.isnan(v):
            return True
    except Exception:
        pass
    empty_strings = {"", "none", "nan", "null", "없음", "비어 있음", "<na>", "n/a"}
    return str(v).strip().lower() in empty_strings

def _coerce_turn(v):
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None

def _move_from_row(row, log_schema, move_library=None):
    move_name_col = log_schema.get("move_name_col")
    if not move_name_col or move_name_col not in row:
        return None
    move_name = row.get(move_name_col)
    if _is_empty_id(move_name):
        return None
    
    move_name_str = str(move_name).strip()
    
    move_dict = None
    if move_library:
        if isinstance(move_library, dict) and move_name_str in move_library:
            move_dict = move_library[move_name_str].copy()
        elif isinstance(move_library, list):
            for m in move_library:
                if str(m.get("name", "")).strip() == move_name_str:
                    move_dict = m.copy()
                    break
                    
    if move_dict is None:
        move_dict = {"name": move_name_str, "power": 0.0, "category": None, "type": None, "priority": 0}
        
    pwr_col = log_schema.get("move_power_col")
    if pwr_col and pwr_col in row and not _is_empty_id(row.get(pwr_col)):
        try:
            move_dict["power"] = float(row.get(pwr_col))
        except (TypeError, ValueError):
            pass
            
    pri_col = log_schema.get("move_priority_col")
    if pri_col and pri_col in row and not _is_empty_id(row.get(pri_col)):
        try:
            move_dict["priority"] = int(float(row.get(pri_col)))
        except (TypeError, ValueError):
            pass
            
    cat_col = log_schema.get("move_category_col")
    if cat_col and cat_col in row and not _is_empty_id(row.get(cat_col)):
        move_dict["category"] = str(row.get(cat_col)).strip()
        
    typ_col = log_schema.get("move_type_col")
    if typ_col and typ_col in row and not _is_empty_id(row.get(typ_col)):
        move_dict["type"] = str(row.get(typ_col)).strip()
        
    return move_dict

def _order_sort_key(v):
    if v is None:
        return (2, 0)
    try:
        fv = float(v)
        return (0, fv)
    except (ValueError, TypeError):
        return (1, str(v))

def build_move_trace_actions_from_group(group, log_schema, move_library=None):
    if not log_schema.get("trace_moves_enabled"):
        return None
        
    turn_col = log_schema.get("turn_col")
    actor_id_col = log_schema.get("actor_id_col")
    target_id_col = log_schema.get("target_id_col")
    move_name_col = log_schema.get("move_name_col")
    
    if not (turn_col and actor_id_col and target_id_col and move_name_col):
        return {}
        
    action_col = log_schema.get("action_col")
    valid_actions = set(log_schema.get("move_action_values", ["move", "attack", "skill", "cast", "use", "use_move", "act", "공격", "스킬", "무브", "행동"]))
    valid_actions = {str(x).strip().lower() for x in valid_actions}
    
    move_order_col = log_schema.get("move_order_col")
    order_dir = log_schema.get("move_order_direction", "ascending_first")
    
    candidates_by_turn = {}
    row_seq = 0
    
    for _, row in group.iterrows():
        row_seq += 1
        if action_col and action_col in row:
            act_val = row.get(action_col)
            if _is_empty_id(act_val) or str(act_val).strip().lower() not in valid_actions:
                continue
        else:
            if move_name_col not in row or _is_empty_id(row.get(move_name_col)):
                continue
                
        turn_val = row.get(turn_col) if turn_col in row else None
        turn = _coerce_turn(turn_val)
        if turn is None:
            continue
            
        actor_val = row.get(actor_id_col) if actor_id_col in row else None
        if _is_empty_id(actor_val):
            continue
        actor_id = str(actor_val).strip()
        
        target_val = row.get(target_id_col) if target_id_col in row else None
        if _is_empty_id(target_val):
            continue
        target_id = str(target_val).strip()
        
        move_dict = _move_from_row(row, log_schema, move_library)
        if not move_dict:
            continue
            
        order_val = row.get(move_order_col) if move_order_col and move_order_col in row else None
        if _is_empty_id(order_val):
            order_val = None
            
        if turn not in candidates_by_turn:
            candidates_by_turn[turn] = []
        candidates_by_turn[turn].append({
            "turn": turn,
            "actor_id": actor_id,
            "target": target_id,
            "move": move_dict,
            "_row_seq": row_seq,
            "_order": order_val,
        })
        
    trace_move = {}
    for turn, candidates in candidates_by_turn.items():
        has_valid_order = move_order_col and any(c["_order"] is not None for c in candidates)
        if has_valid_order:
            valid_c = [c for c in candidates if c["_order"] is not None]
            invalid_c = [c for c in candidates if c["_order"] is None]
            
            valid_c.sort(key=lambda c: c["_row_seq"])
            nums = [c for c in valid_c if _order_sort_key(c["_order"])[0] == 0]
            strs = [c for c in valid_c if _order_sort_key(c["_order"])[0] == 1]
            
            if order_dir == "descending_first":
                nums.sort(key=lambda c: _order_sort_key(c["_order"])[1], reverse=True)
                strs.sort(key=lambda c: _order_sort_key(c["_order"])[1], reverse=True)
            else:
                nums.sort(key=lambda c: _order_sort_key(c["_order"])[1])
                strs.sort(key=lambda c: _order_sort_key(c["_order"])[1])
                
            sorted_candidates = nums + strs + invalid_c
            
            total_c = len(sorted_candidates)
            for idx, c in enumerate(sorted_candidates):
                c["move"]["priority"] = total_c - idx
                trace_move[(c["turn"], c["actor_id"])] = {
                    "move": c["move"],
                    "target": c["target"]
                }
        else:
            for c in candidates:
                trace_move[(c["turn"], c["actor_id"])] = {
                    "move": c["move"],
                    "target": c["target"]
                }
                
    return {"move": trace_move, "switch": {}}

def build_switch_trace_actions_from_group(group, log_schema):
    if not log_schema.get("trace_switches_enabled"):
        return {"move": {}, "switch": {}}
        
    turn_col = log_schema.get("switch_turn_col") or log_schema.get("turn_col")
    out_col = log_schema.get("switch_outgoing_id_col") or log_schema.get("actor_id_col")
    in_col = log_schema.get("switch_incoming_id_col")
    
    if not (turn_col and out_col and in_col):
        return {"move": {}, "switch": {}}
        
    action_col = log_schema.get("switch_action_col") or log_schema.get("action_col")
    
    valid_actions = log_schema.get("switch_action_values", ["switch", "swap", "tag", "change", "substitute", "switch_out", "switch_in", "교체", "스위치", "태그", "변경"])
    valid_actions = {str(x).strip().lower() for x in valid_actions}
    
    trace_switch = {}
    
    for _, row in group.iterrows():
        if action_col and action_col in row:
            act_val = row.get(action_col)
            if _is_empty_id(act_val) or str(act_val).strip().lower() not in valid_actions:
                continue
        else:
            in_val = row.get(in_col) if in_col in row else None
            if _is_empty_id(in_val):
                continue
                
        turn_val = row.get(turn_col) if turn_col in row else None
        turn = _coerce_turn(turn_val)
        if turn is None:
            continue
            
        out_val = row.get(out_col) if out_col in row else None
        if _is_empty_id(out_val):
            continue
        out_id = str(out_val).strip()
        
        in_val = row.get(in_col) if in_col in row else None
        if _is_empty_id(in_val):
            continue
        in_id = str(in_val).strip()
        
        trace_switch[(turn, out_id)] = in_id
        
    return {"move": {}, "switch": trace_switch}

def build_faint_incoming_trace_from_group(group, log_schema):
    if not log_schema.get("trace_faint_incoming_enabled"):
        return []
        
    turn_col = log_schema.get("faint_turn_col") or log_schema.get("switch_turn_col") or log_schema.get("turn_col")
    out_col = log_schema.get("faint_outgoing_id_col") or log_schema.get("switch_outgoing_id_col") or log_schema.get("actor_id_col")
    in_col = log_schema.get("faint_incoming_id_col")
    side_col = log_schema.get("faint_side_col") or log_schema.get("team_col")
    
    if not (turn_col and out_col and in_col):
        return []
        
    action_col = log_schema.get("faint_action_col") or log_schema.get("switch_action_col") or log_schema.get("action_col")
    
    valid_actions = log_schema.get("faint_action_values", [
        "faint_replace", "replace", "replacement", "send_out", "enter_after_faint",
        "fainted_switch", "faint_incoming", "ko_replace", "forced_switch",
        "기절교체", "쓰러짐교체", "강제교체", "등장", "진입"
    ])
    valid_actions = {str(x).strip().lower() for x in valid_actions}
    
    dedup = {}
    
    for _, row in group.iterrows():
        if action_col and action_col in row:
            act_val = row.get(action_col)
            if _is_empty_id(act_val) or str(act_val).strip().lower() not in valid_actions:
                continue
        else:
            in_val = row.get(in_col) if in_col in row else None
            if _is_empty_id(in_val):
                continue
                
        turn_val = row.get(turn_col) if turn_col in row else None
        turn = _coerce_turn(turn_val)
        if turn is None:
            continue
            
        out_val = row.get(out_col) if out_col in row else None
        if _is_empty_id(out_val):
            continue
        out_id = str(out_val).strip()
        
        in_val = row.get(in_col) if in_col in row else None
        if _is_empty_id(in_val):
            continue
        in_id = str(in_val).strip()
        
        entry = {"turn": turn, "outgoing": out_id, "incoming": in_id}
        if side_col and side_col in row:
            side_val = row.get(side_col)
            if not _is_empty_id(side_val):
                entry["side"] = str(side_val).strip()
                
        dedup[(turn, out_id)] = entry
        
    return list(dedup.values())

def _participant_ids(*teams):
    p_ids = set()
    for team in teams:
        for inst in team:
            i_id = inst.get("id")
            if not _is_empty_id(i_id):
                p_ids.add(str(i_id).strip())
    return p_ids

def _filter_trace_actions_for_participants(trace_actions, participant_ids):
    filtered_move = {}
    if trace_actions and trace_actions.get("move"):
        for (turn, actor_id), m_dict in trace_actions["move"].items():
            if actor_id in participant_ids and m_dict.get("target") in participant_ids:
                filtered_move[(turn, actor_id)] = m_dict
                
    filtered_switch = {}
    if trace_actions and trace_actions.get("switch"):
        for (turn, outgoing_id), incoming_id in trace_actions["switch"].items():
            if outgoing_id in participant_ids and incoming_id in participant_ids:
                filtered_switch[(turn, outgoing_id)] = incoming_id
                
    return {"move": filtered_move, "switch": filtered_switch}

def _filter_faint_incoming_for_participants(entries, participant_ids):
    filtered = []
    for entry in entries:
        if entry["outgoing"] in participant_ids and entry["incoming"] in participant_ids:
            filtered.append(entry)
    return filtered

def build_state_snapshots_from_group(group, log_schema):
    if not log_schema.get("state_trace_enabled"):
        return {}
        
    turn_col = (
        log_schema.get("state_turn_col")
        or log_schema.get("turn_col")
        or log_schema.get("switch_turn_col")
        or log_schema.get("faint_turn_col")
    )
    id_col = log_schema.get("state_entity_id_col") or log_schema.get("entity_id_col")
    hp_col = log_schema.get("state_hp_col")
    status_col = log_schema.get("state_status_col")
    fainted_col = log_schema.get("state_fainted_col")
    resource_cols = log_schema.get("state_resource_cols") or {}
    
    if not turn_col or not id_col:
        return {}
    if not hp_col and not status_col and not fainted_col and not resource_cols:
        return {}
        
    faint_truthy = {"1", "true", "yes", "y", "fainted", "dead", "ko", "down", "기절", "쓰러짐", "사망"}
    
    snaps = {}
    for _, row in group.iterrows():
        turn = _coerce_turn(row.get(turn_col))
        if turn is None:
            continue
        pid_raw = row.get(id_col)
        if _is_empty_id(pid_raw):
            continue
        pid = str(pid_raw).strip()
        
        state_entry = {}
        if hp_col and hp_col in row:
            v = row.get(hp_col)
            if not _is_empty_id(v):
                try:
                    state_entry["hp"] = float(v)
                except ValueError:
                    pass
                    
        if status_col and status_col in row:
            v = row.get(status_col)
            if not _is_empty_id(v):
                state_entry["status"] = str(v)
                
        has_fainted_field = False
        if fainted_col and fainted_col in row:
            v = row.get(fainted_col)
            if not _is_empty_id(v):
                state_entry["fainted"] = str(v).strip().lower() in faint_truthy
                has_fainted_field = True
                
        if not has_fainted_field and "hp" in state_entry and state_entry["hp"] <= 0:
            state_entry["fainted"] = True
            
        if resource_cols:
            extra_resources = {}
            for rname, rcol in resource_cols.items():
                if rcol and rcol in row:
                    v = row.get(rcol)
                    if not _is_empty_id(v):
                        try:
                            extra_resources[rname] = float(v)
                        except ValueError:
                            pass
            if extra_resources:
                state_entry["resources"] = extra_resources
            
        if not state_entry:
            continue
            
        if turn not in snaps:
            snaps[turn] = {}
        snaps[turn][pid] = state_entry
        
    return snaps

def _filter_state_snapshots_for_participants(snapshots, participant_ids):
    filtered = {}
    for turn, snap in snapshots.items():
        fsnap = {pid: state for pid, state in snap.items() if pid in participant_ids}
        if fsnap:
            filtered[turn] = fsnap
    return filtered

def build_observed_status_trace_from_group(group, log_schema):
    if not log_schema.get("observed_status_trace_enabled"):
        return []

    event_type_col = log_schema.get("status_event_type_col")
    entity_id_col = log_schema.get("status_entity_id_col")
    status_val_col = log_schema.get("status_value_col")
    status_effect_col = log_schema.get("status_effect_col")
    turn_col = log_schema.get("status_turn_col") or log_schema.get("turn_col")

    if not event_type_col or not entity_id_col or not turn_col:
        return []

    trace = []
    for _, row in group.iterrows():
        etype = str(row.get(event_type_col, "")).strip()
        if etype not in ("StatusApplied", "StatusCured"):
            continue

        turn_val = row.get(turn_col)
        turn = _coerce_turn(turn_val)
        if turn is None:
            continue

        pid_raw = row.get(entity_id_col)
        if _is_empty_id(pid_raw):
            continue
        pid = str(pid_raw).strip()

        op = "apply" if etype == "StatusApplied" else "clear"
        status_val = ""
        if op == "apply":
            status_val = str(row.get(status_val_col, "")).strip()
            if not status_val or status_val == "nan":
                status_val = str(row.get(status_effect_col, "")).strip()
            if status_val == "nan":
                status_val = ""
        else:
            status_val = ""

        trace.append({
            "turn": turn,
            "entity_id": pid,
            "status": status_val,
            "op": op
        })

    return trace

def _filter_observed_status_trace_for_participants(trace, participant_ids):
    return [e for e in trace if e["entity_id"] in participant_ids]

def build_observed_hp_trace_from_group(group, log_schema):
    if not log_schema.get("observed_hp_trace_enabled"):
        return []

    event_type_col = log_schema.get("hp_event_type_col")
    entity_id_col = log_schema.get("hp_entity_id_col")
    val_col = log_schema.get("hp_value_col")
    max_col = log_schema.get("hp_max_col")
    fainted_col = log_schema.get("hp_fainted_col")
    turn_col = log_schema.get("hp_turn_col") or log_schema.get("turn_col")
    order_col = log_schema.get("hp_order_col")

    if not event_type_col or not entity_id_col or not turn_col:
        return []

    trace = []
    for _, row in group.iterrows():
        etype = str(row.get(event_type_col, "")).strip()
        if etype not in ("PokemonSwitched", "DamageApplied", "HealApplied", "PokemonFainted"):
            continue

        turn_val = row.get(turn_col)
        turn = _coerce_turn(turn_val)
        if turn is None:
            continue

        pid_raw = row.get(entity_id_col)
        if _is_empty_id(pid_raw):
            continue
        pid = str(pid_raw).strip()

        entry = {
            "turn": turn,
            "entity_id": pid,
            "event_type": etype,
            "seq": row.get(order_col, 0) if order_col and order_col in row else 0
        }

        if val_col and val_col in row and not pd.isna(row.get(val_col)):
            entry["hp"] = float(row.get(val_col))
        
        if max_col and max_col in row and not pd.isna(row.get(max_col)):
            entry["hp_max"] = float(row.get(max_col))
            
        is_faint = False
        if etype == "PokemonFainted":
            is_faint = True
        elif fainted_col and fainted_col in row:
            fval = row.get(fainted_col)
            if not _is_empty_id(fval):
                is_faint = str(fval).strip().lower() in {"1", "true", "yes", "y", "fainted", "dead", "ko", "down", "기절", "쓰러짐", "사망"}
        
        if is_faint:
            entry["fainted"] = True
            
        trace.append(entry)

    trace.sort(key=lambda x: (x["turn"], x["seq"]))
    return trace

def _filter_observed_hp_trace_for_participants(trace, participant_ids):
    return [e for e in trace if e["entity_id"] in participant_ids]

def build_observed_switch_trace_from_group(group, log_schema):
    if not log_schema.get("observed_switch_trace_enabled"):
        return {"switch": {}, "faint_incoming": []}

    event_type_col = log_schema.get("switch_event_type_col")
    entity_id_col = log_schema.get("switch_entity_id_col")
    turn_col = log_schema.get("switch_turn_col") or log_schema.get("turn_col")
    order_col = log_schema.get("switch_order_col")

    if not event_type_col or not entity_id_col or not turn_col:
        return {"switch": {}, "faint_incoming": []}

    trace = {"switch": {}, "faint_incoming": []}
    
    events = []
    for _, row in group.iterrows():
        etype = str(row.get(event_type_col, "")).strip()
        turn_val = row.get(turn_col)
        turn = _coerce_turn(turn_val)
        pid_raw = row.get(entity_id_col)
        pid = str(pid_raw).strip() if not _is_empty_id(pid_raw) else ""
        
        seq = row.get(order_col, 0) if order_col and order_col in row else 0
        events.append({
            "turn": turn,
            "seq": seq,
            "event_type": etype,
            "entity_id": pid
        })
        
    events.sort(key=lambda x: (x["turn"] if x["turn"] is not None else -1, x["seq"]))
    
    active_by_side = {}
    fainted_entities = set()
    
    for ev in events:
        pid = ev["entity_id"]
        if not pid:
            continue
            
        parts = pid.split(":")
        side = parts[0] if len(parts) > 1 else "unknown"
        
        etype = ev["event_type"]
        turn = ev["turn"]
        
        if etype == "PokemonFainted":
            fainted_entities.add(pid)
            
        elif etype == "PokemonSwitched":
            if turn is None or turn <= 0:
                active_by_side[side] = pid
            else:
                outgoing = active_by_side.get(side)
                incoming = pid
                
                if outgoing and outgoing != incoming:
                    if outgoing in fainted_entities:
                        trace["faint_incoming"].append({
                            "turn": turn,
                            "outgoing": outgoing,
                            "incoming": incoming
                        })
                    else:
                        trace["switch"][(turn, outgoing)] = incoming
                
                active_by_side[side] = incoming

    return trace

def build_action_damage_trace_from_group(group, log_schema):
    if not log_schema.get("damage_trace_enabled"):
        return []
        
    turn_col = log_schema.get("damage_turn_col") or log_schema.get("turn_col")
    actor_col = log_schema.get("damage_actor_id_col") or log_schema.get("entity_id_col")
    target_col = log_schema.get("damage_target_id_col")
    val_col = log_schema.get("damage_value_col")
    
    if not turn_col or not actor_col or not target_col or not val_col:
        return []
        
    action_col = log_schema.get("damage_action_col")
    action_vals = set(log_schema.get("damage_action_values") or [])
    move_name_col = log_schema.get("damage_move_name_col")
    order_col = log_schema.get("damage_order_col")
    order_dir = log_schema.get("damage_order_direction", "ascending_first")

    events = []
    for _, row in group.iterrows():
        if action_col and action_vals:
            ac_val = str(row.get(action_col, "")).strip()
            if ac_val not in action_vals:
                continue
                
        turn = _coerce_turn(row.get(turn_col))
        if turn is None:
            continue
            
        actor_raw = row.get(actor_col)
        target_raw = row.get(target_col)
        if _is_empty_id(actor_raw) or _is_empty_id(target_raw):
            continue
            
        actor = str(actor_raw).strip()
        target = str(target_raw).strip()
        
        v = row.get(val_col)
        if _is_empty_id(v):
            continue
        try:
            dmg = float(v)
            if dmg != dmg:
                continue
        except (ValueError, TypeError):
            continue
            
        evt = {
            "turn": turn,
            "actor": actor,
            "target": target,
        }
        
        kind = str(log_schema.get("damage_value_kind") or "damage")
        if kind == "hp_delta":
            evt["hp_delta"] = dmg
            evt["damage"] = dmg
        else:
            evt["damage"] = dmg
        
        if move_name_col and move_name_col in row:
            mv = row.get(move_name_col)
            if not _is_empty_id(mv):
                evt["move"] = str(mv).strip()
                
        if order_col and order_col in row:
            o_val = row.get(order_col)
            if not pd.isna(o_val):
                evt["_ord"] = o_val
                
        if evt not in events:
            events.append(evt)
        
    if any("_ord" in e for e in events):
        def _get_sort_tuple(x):
            ord_val = x.get("_ord")
            cat, val = _order_sort_key(ord_val)
            if order_dir == "descending_first":
                # For numbers and strings, we negate/invert to sort descending
                if cat == 0:
                    val = -val
                elif cat == 1:
                    # simplistic string invert for sorting
                    # or just use a custom key
                    pass
            return (x.get("turn", 0), cat, val)
            
        events.sort(key=_get_sort_tuple)
        
        if order_dir == "descending_first":
            # To handle string descending properly, it's easier to sort per turn
            events_by_turn = {}
            for e in events:
                events_by_turn.setdefault(e.get("turn", 0), []).append(e)
            
            new_events = []
            for turn in sorted(events_by_turn.keys()):
                turn_events = events_by_turn[turn]
                nums = [e for e in turn_events if _order_sort_key(e.get("_ord"))[0] == 0]
                strs = [e for e in turn_events if _order_sort_key(e.get("_ord"))[0] == 1]
                nans = [e for e in turn_events if _order_sort_key(e.get("_ord"))[0] == 2]
                
                nums.sort(key=lambda x: _order_sort_key(x.get("_ord"))[1], reverse=True)
                strs.sort(key=lambda x: _order_sort_key(x.get("_ord"))[1], reverse=True)
                new_events.extend(nums + strs + nans)
            events = new_events
            
        for e in events:
            e.pop("_ord", None)
            
    return sorted(events, key=lambda x: x.get("_ord", 0))

def build_action_resource_delta_trace_from_group(group, log_schema):
    if not log_schema.get("resource_delta_trace_enabled"):
        return []

    turn_col = log_schema.get("resource_delta_turn_col") or log_schema.get("turn_col")
    actor_col = log_schema.get("resource_delta_actor_id_col") or log_schema.get("entity_id_col")
    target_col = log_schema.get("resource_delta_target_id_col")
    delta_cols = log_schema.get("resource_delta_cols") or {}
    
    if not turn_col or not actor_col or not target_col or not delta_cols:
        return []

    action_col = log_schema.get("resource_delta_action_col")
    action_vals = set(log_schema.get("resource_delta_action_values") or [])
    order_col = log_schema.get("resource_delta_order_col")
    order_dir = log_schema.get("resource_delta_order_direction", "ascending_first")

    events = []
    for _, row in group.iterrows():
        if action_col and action_vals:
            ac_val = str(row.get(action_col, "")).strip()
            if ac_val not in action_vals:
                continue

        turn = _coerce_turn(row.get(turn_col))
        if turn is None:
            continue

        actor_raw = row.get(actor_col)
        target_raw = row.get(target_col)
        if _is_empty_id(actor_raw) or _is_empty_id(target_raw):
            continue

        actor = str(actor_raw).strip()
        target = str(target_raw).strip()
        
        ord_val = row.get(order_col) if order_col and order_col in row else 0
        try:
            ord_num = float(ord_val) if not pd.isna(ord_val) else 0.0
            if order_dir == "descending_first":
                ord_num = -ord_num
        except:
            ord_num = 0.0

        for rname, rcol in delta_cols.items():
            if not rcol or rcol not in row:
                continue
            v = row.get(rcol)
            if _is_empty_id(v):
                continue
            try:
                delta = float(v)
                if delta != delta or delta <= 0:
                    continue
            except (ValueError, TypeError):
                continue
                
            events.append({
                "turn": turn,
                "actor": actor,
                "target": target,
                "resource": str(rname),
                "delta": delta,
                "_ord": ord_num
            })

    unique_events = []
    seen = set()
    for e in sorted(events, key=lambda x: x.get("_ord", 0)):
        sig = (e["turn"], e["actor"], e["target"], e["resource"], e["delta"], e["_ord"])
        if sig not in seen:
            seen.add(sig)
            e_out = dict(e)
            e_out.pop("_ord", None)
            unique_events.append(e_out)
            
    return unique_events

def _filter_action_damage_trace_for_participants(events, participant_ids):
    return [
        e for e in events
        if e.get("actor") in participant_ids and e.get("target") in participant_ids
    ]

def _filter_action_resource_delta_trace_for_participants(events, participant_ids):
    return [
        e for e in events
        if e.get("actor") in participant_ids and e.get("target") in participant_ids
    ]

def _row_to_inst(row, system_stats, system_gimmicks, health_stat,
                 move_library=None, resource_config=None, game_config=None,
                 instance_id_col=None):
    """로그의 한 행을 엔진 인스턴스 dict로 변환."""
    inst = {"name": "log_row", "gimmicks": {}}
    if instance_id_col and instance_id_col in row:
        raw_id = row.get(instance_id_col)
        if not _is_empty_id(raw_id):
            inst["id"] = str(raw_id).strip()
    for g in system_gimmicks:
        inst["gimmicks"][g] = row.get(g, "None")
    promote_effect_keys(inst, game_config)
    for s in system_stats:
        inst[s] = _safe_float(row.get(s, 0.0))
    rc = resource_config or (
        {"HP": {"role": "vital", "stat": health_stat, "regen": 0.0}}
        if health_stat else
        {"HP": {"role": "vital", "stat": None, "regen": 0.0}}
    )
    inst["resources"] = {}
    for rname, rspec in rc.items():
        rstat = rspec.get("stat")
        rval = float(inst[rstat]) if (rstat and rstat in inst) else 1.0
        inst["resources"][rname] = {"current": rval, "max": rval}
    if move_library:
        inst["movepool"] = move_library
    return inst

def _is_initial_on_field_value(v, active_values):
    if _is_empty_id(v):
        return False
    s = str(v).strip().lower()
    if s in {"0", "false", "no", "bench", "reserve"}:
        return False
    if s in active_values:
        return True
    try:
        return float(s) > 0
    except ValueError:
        return False

def build_battles_from_log_schema(df, target_col, system_stats, system_gimmicks,
                                  health_stat, move_library=None,
                                  resource_config=None, max_battles=None,
                                  game_config=None, log_schema=None):
    if log_schema is None:
        log_schema = {}
        
    battle_id_col = log_schema.get("battle_id_col")
    team_col = log_schema.get("team_col")
    entity_id_col = log_schema.get("entity_id_col")
    sort_cols = log_schema.get("sort_cols", [])
    result_mode = log_schema.get("result_mode", "battle_level")
    
    ally_values = set(log_schema.get("ally_values", [])) | {"ally", "a", "blue", "player", "home", "left", "1", "true"}
    enemy_values = set(log_schema.get("enemy_values", [])) | {"enemy", "e", "red", "opponent", "away", "right", "2", "false"}
    ally_values = {str(x).strip().lower() for x in ally_values}
    enemy_values = {str(x).strip().lower() for x in enemy_values}
    
    battles = []
    
    if not battle_id_col or not team_col or battle_id_col not in df.columns or team_col not in df.columns:
        return battles
        
    df_valid = df.dropna(subset=[battle_id_col])
    
    if sort_cols:
        existing_sort_cols = [c for c in sort_cols if c in df_valid.columns]
        if existing_sort_cols:
            df_valid = df_valid.sort_values(by=existing_sort_cols)
            
    grouped = df_valid.groupby(battle_id_col, sort=False)
    
    b_count = 0
    for battle_id, group in grouped:
        if max_battles is not None and b_count >= int(max_battles):
            break
            
        ally_rows = []
        enemy_rows = []
        
        for _, row in group.iterrows():
            side = str(row[team_col]).strip().lower()
            if side in ally_values:
                ally_rows.append(row)
            elif side in enemy_values:
                enemy_rows.append(row)
                
        if not ally_rows or not enemy_rows:
            continue
            
        def dedup(rows):
            if not rows:
                return []
            if entity_id_col and entity_id_col in df_valid.columns:
                unit_dict = {}
                for r in rows:
                    uid = r[entity_id_col]
                    unit_dict[uid] = r
                return list(unit_dict.values())
            return rows
            
        final_ally = dedup(ally_rows)
        final_enemy = dedup(enemy_rows)
        
        initial_order_col = log_schema.get("initial_order_col")
        if initial_order_col:
            def _sort_key(r):
                v = r.get(initial_order_col)
                if pd.isna(v) or v is None or str(v).strip() == "":
                    return (1, "")
                try:
                    return (0, float(v))
                except ValueError:
                    return (0, str(v))
            if initial_order_col in df.columns:
                final_ally.sort(key=_sort_key)
                final_enemy.sort(key=_sort_key)
        
        if not final_ally or not final_enemy:
            continue
        
        ally_wins = False
        if result_mode == "battle_level":
            target_val = None
            for _, row in group.iterrows():
                v = row.get(target_col)
                if not pd.isna(v) and v is not None:
                    target_val = v
                    break
                        
            if target_val is not None:
                ally_wins = _is_win_signal(target_val)
            else:
                ally_signal = sum(1 if _is_win_signal(r.get(target_col)) else 0 for r in final_ally)
                enemy_signal = sum(1 if _is_win_signal(r.get(target_col)) else 0 for r in final_enemy)
                ally_wins = ally_signal > enemy_signal
        else:
            ally_signal = sum(1 if _is_win_signal(r.get(target_col)) else 0 for r in final_ally)
            enemy_signal = sum(1 if _is_win_signal(r.get(target_col)) else 0 for r in final_enemy)
            ally_wins = ally_signal > enemy_signal
            
        ally_team = [_row_to_inst(r, system_stats, system_gimmicks, health_stat,
                                  move_library, resource_config, game_config,
                                  instance_id_col=entity_id_col)
                     for r in final_ally]
        enemy_team = [_row_to_inst(r, system_stats, system_gimmicks, health_stat,
                                   move_library, resource_config, game_config,
                                   instance_id_col=entity_id_col)
                      for r in final_enemy]
                      
        initial_applied = False
        if log_schema.get("initial_on_field_enabled"):
            on_field_col = log_schema.get("initial_on_field_col")
            on_field_vals = log_schema.get("initial_on_field_values", [
                "1", "true", "yes", "y", "active", "lead", "on", "field", "front", "starter",
                "초기", "선발", "활성", "필드", "전열"
            ])
            on_field_vals = {str(x).strip().lower() for x in on_field_vals}
            
            if on_field_col:
                for inst, r in zip(ally_team, final_ally):
                    if on_field_col in r and _is_initial_on_field_value(r[on_field_col], on_field_vals):
                        inst["on_field"] = True
                        initial_applied = True
                    else:
                        inst["on_field"] = False
                for inst, r in zip(enemy_team, final_enemy):
                    if on_field_col in r and _is_initial_on_field_value(r[on_field_col], on_field_vals):
                        inst["on_field"] = True
                        initial_applied = True
                    else:
                        inst["on_field"] = False
                        
        trace_actions = {"move": {}, "switch": {}}
        faint_incoming = []
        if log_schema.get("trace_moves_enabled"):
            mt = build_move_trace_actions_from_group(group, log_schema, move_library)
            if mt and mt.get("move"):
                trace_actions["move"] = mt["move"]
        if log_schema.get("trace_switches_enabled"):
            st = build_switch_trace_actions_from_group(group, log_schema)
            if st and st.get("switch"):
                trace_actions["switch"] = st["switch"]
        if log_schema.get("trace_faint_incoming_enabled"):
            faint_incoming = build_faint_incoming_trace_from_group(group, log_schema)
            
        if log_schema.get("observed_switch_trace_enabled"):
            obs_switch = build_observed_switch_trace_from_group(group, log_schema)
            if obs_switch:
                faint_incoming.extend(obs_switch.get("faint_incoming", []))
                for k, v in obs_switch.get("switch", {}).items():
                    trace_actions["switch"][k] = v
            
        state_snapshots = {}
        if log_schema.get("state_trace_enabled"):
            state_snapshots = build_state_snapshots_from_group(group, log_schema)
            
        action_damage_trace = []
        if log_schema.get("damage_trace_enabled"):
            action_damage_trace = build_action_damage_trace_from_group(group, log_schema)
            
        action_resource_delta_trace = []
        if log_schema.get("resource_delta_trace_enabled"):
            action_resource_delta_trace = build_action_resource_delta_trace_from_group(group, log_schema)
            
        observed_status_trace = []
        if log_schema.get("observed_status_trace_enabled"):
            observed_status_trace = build_observed_status_trace_from_group(group, log_schema)
            
        observed_hp_trace = []
        if log_schema.get("observed_hp_trace_enabled"):
            observed_hp_trace = build_observed_hp_trace_from_group(group, log_schema)
                
        if trace_actions["move"] or trace_actions["switch"] or faint_incoming or initial_applied or state_snapshots or action_damage_trace or action_resource_delta_trace or observed_status_trace or observed_hp_trace:
            participant_ids = _participant_ids(ally_team, enemy_team)
            
            battle_gc = {"preserve_ids": True}
            has_battle_gc = False
            
            if initial_applied:
                battle_gc["preserve_initial_on_field"] = True
                has_battle_gc = True
                
            filtered_state = _filter_state_snapshots_for_participants(state_snapshots, participant_ids)
            if filtered_state:
                battle_gc["_expected_state_snapshots"] = filtered_state
                battle_gc["_state_score_config"] = {
                    "hp_mode": log_schema.get("state_hp_mode", "absolute"),
                    "hp_tol": float(log_schema.get("state_hp_tolerance", 0.0) or 0.0),
                    "resource_names": list((log_schema.get("state_resource_cols") or {}).keys()),
                    "resource_mode": log_schema.get("state_resource_mode", "absolute"),
                    "resource_tol": float(log_schema.get("state_resource_tolerance", 0.0) or 0.0),
                }
                has_battle_gc = True
                
            filtered_damage = _filter_action_damage_trace_for_participants(action_damage_trace, participant_ids)
            if filtered_damage:
                battle_gc["_expected_action_damage_trace"] = filtered_damage
                battle_gc["_action_damage_score_config"] = {
                    "damage_tol": float(log_schema.get("damage_tolerance", 0.0) or 0.0),
                    "compare_field": str(log_schema.get("damage_value_kind") or "damage"),
                }
                has_battle_gc = True
                
            filtered_resource_delta = _filter_action_resource_delta_trace_for_participants(action_resource_delta_trace, participant_ids)
            if filtered_resource_delta:
                battle_gc["_expected_action_resource_delta_trace"] = filtered_resource_delta
                _rd_cols = log_schema.get("resource_delta_cols") or {}
                battle_gc["_action_resource_delta_score_config"] = {
                    "delta_tol": float(log_schema.get("resource_delta_tolerance", 0.0) or 0.0),
                    "resource_names": [str(x) for x in _rd_cols.keys()],
                    "strict_extra": bool(log_schema.get("resource_delta_strict_extra", False)),
                }
                has_battle_gc = True
                
            if observed_status_trace:
                filtered_observed_status = _filter_observed_status_trace_for_participants(observed_status_trace, participant_ids)
                if filtered_observed_status:
                    battle_gc["_observed_status_trace"] = filtered_observed_status
                    has_battle_gc = True
                    
            if observed_hp_trace:
                filtered_observed_hp = _filter_observed_hp_trace_for_participants(observed_hp_trace, participant_ids)
                if filtered_observed_hp:
                    battle_gc["_observed_hp_trace"] = filtered_observed_hp
                    has_battle_gc = True
                
            if len(participant_ids) >= (len(ally_team) + len(enemy_team)):
                filtered_trace = _filter_trace_actions_for_participants(trace_actions, participant_ids)
                filtered_faint = _filter_faint_incoming_for_participants(faint_incoming, participant_ids)
                if filtered_trace.get("move") or filtered_trace.get("switch"):
                    battle_gc["trace_actions"] = filtered_trace
                    has_battle_gc = True
                if filtered_faint:
                    battle_gc["trace_faint_incoming"] = filtered_faint
                    battle_gc["on_active_faint"] = "replace_from_reserve"
                    has_battle_gc = True
                    
            if has_battle_gc:
                battles.append((ally_team, enemy_team, ally_wins, battle_gc))
            else:
                battles.append((ally_team, enemy_team, ally_wins))
        else:
            battles.append((ally_team, enemy_team, ally_wins))
            
        b_count += 1
        
    return battles


def build_battles(df, battle_size, target_col, system_stats, system_gimmicks,
                  health_stat, move_library=None, resource_config=None,
                  max_battles=None, game_config=None, log_schema=None):
    """df를 battle_size 행씩 그룹화해 1전투씩 추출.

    한 전투의 행 N개를 절반으로 잘라 앞쪽 N/2 = Ally, 뒤쪽 N/2 = Enemy로 본다.
    실제 ally_wins = (ally 측 target_col 합 > enemy 측 합).

    반환: [(ally_team_insts, enemy_team_insts, ally_wins_bool), ...]
    """
    if log_schema and log_schema.get("battle_id_col") and log_schema.get("team_col"):
        return build_battles_from_log_schema(
            df, target_col, system_stats, system_gimmicks, health_stat,
            move_library, resource_config, max_battles, game_config, log_schema
        )
        
    battles = []
    if battle_size < 2 or battle_size % 2 != 0:
        return battles
    n_per_team = battle_size // 2
    total_battles = len(df) // battle_size
    if max_battles is not None:
        total_battles = min(total_battles, int(max_battles))
    for b in range(total_battles):
        rows = [df.iloc[b * battle_size + k] for k in range(battle_size)]
        ally_rows = rows[:n_per_team]
        enemy_rows = rows[n_per_team:]
        ally_signal = sum(1 if _is_win_signal(r.get(target_col)) else 0 for r in ally_rows)
        enemy_signal = sum(1 if _is_win_signal(r.get(target_col)) else 0 for r in enemy_rows)
        ally_wins = ally_signal > enemy_signal
        ally_team = [_row_to_inst(r, system_stats, system_gimmicks, health_stat,
                                  move_library, resource_config, game_config)
                     for r in ally_rows]
        enemy_team = [_row_to_inst(r, system_stats, system_gimmicks, health_stat,
                                   move_library, resource_config, game_config)
                      for r in enemy_rows]
        battles.append((ally_team, enemy_team, ally_wins))
    return battles


def score_predictions(predicted_ally_wins, actual_ally_wins):
    """예측 ally-win 여부 vs 실제 ally-win 여부 이진 비교."""
    total = len(predicted_ally_wins)
    if total == 0 or len(actual_ally_wins) != total:
        return {"accuracy": 0.0, "total": 0, "correct": 0,
                "ally_wins_actual": 0, "ally_wins_recall": 0.0,
                "not_ally_actual": 0, "not_ally_recall": 0.0}
    correct = sum(1 for p, a in zip(predicted_ally_wins, actual_ally_wins) if p == a)
    ally_actual = sum(1 for a in actual_ally_wins if a)
    not_ally_actual = total - ally_actual
    ally_hit = sum(1 for p, a in zip(predicted_ally_wins, actual_ally_wins) if a and p)
    not_ally_hit = sum(1 for p, a in zip(predicted_ally_wins, actual_ally_wins)
                       if (not a) and (not p))
    return {
        "accuracy": correct / total,
        "total": total,
        "correct": correct,
        "ally_wins_actual": ally_actual,
        "ally_wins_recall": (ally_hit / ally_actual) if ally_actual else 0.0,
        "not_ally_actual": not_ally_actual,
        "not_ally_recall": (not_ally_hit / not_ally_actual) if not_ally_actual else 0.0,
    }
