import streamlit as st
import pandas as pd
import numpy as np
import math
from scipy.optimize import minimize
import plotly.graph_objects as go
import plotly.express as px
import json
import streamlit.components.v1 as components
import copy
import os
import time
import concurrent.futures
import traceback
from modules.validation import calculate_validation_score
from modules.action_registry import ActionRegistry, DEFAULT_ACTION_REGISTRY
from modules.turn_manager import SequentialTurnManager
from modules.stochasticity import StochasticityModule, NoVariance
from modules.resource import init_resources, get_current, get_max, apply_delta, ResourceModule
from modules.win_condition import ResourceDepletion

from modules.engine import run_simulation, run_monte_carlo, default_stochasticity_factory, DEFAULT_COMBAT_FLOW
from modules.optimizer import optimize_allocation
from modules.spatial import SpatialModule
from modules.deck import DeckModule
from modules.detection import module_active
from modules.effect_key_roles import promote_effect_keys


def _select_backtest_stochasticity_factory(log_schema):
    if log_schema and log_schema.get("state_trace_enabled"):
        if bool(log_schema.get("state_score_deterministic", True)):
            return None
    return default_stochasticity_factory

def _json_safe(val):
    if isinstance(val, (int, float, str, bool, type(None))):
        if isinstance(val, float) and math.isnan(val):
            return None
        return val
    if isinstance(val, (list, tuple)):
        return [_json_safe(x) for x in val]
    if isinstance(val, dict):
        return {str(k): _json_safe(v) for k, v in val.items()}
    if pd.isna(val):
        return None
    try:
        import numpy as np
        if isinstance(val, np.generic):
            return _json_safe(val.item())
    except ImportError:
        pass
    return str(val)

def _build_db_corpus_schema_payload(system_stats, system_gimmicks, health_stat, target_col, battle_size, log_schema, session_state_like):
    import copy
    from modules.engine import DEFAULT_COMBAT_FLOW
    gc = copy.deepcopy(session_state_like.get("game_config") or {})
    if log_schema and log_schema.get("entity_id_col"):
        gc["preserve_ids"] = True

    payload = {
        "schema_version": "db_corpus_backtest.v1",
        "generated_from": "step6_dashboard",
        "system_stats": system_stats,
        "system_gimmicks": system_gimmicks,
        "health_stat": health_stat,
        "resource_config": session_state_like.get("resource_config"),
        "game_config": gc,
        "log_schema": log_schema,
        "target_col": target_col,
        "battle_size": battle_size,
        "combat_flow": session_state_like.get("combat_flow", DEFAULT_COMBAT_FLOW),
        "speed_stat": session_state_like.get("speed_stat"),
        "global_damage_formula": session_state_like.get("global_damage_formula", "0"),
        "sim_max_turns": session_state_like.get("sim_max_turns", 100),
        "move_library": session_state_like.get("move_library"),
        "damage_type_map": session_state_like.get("damage_type_map"),
        "range_stat": session_state_like.get("range_stat"),
        "move_stat": session_state_like.get("move_stat")
    }
    return _json_safe(payload)


def calc_instance_score(inst, coefs):
    val = 0.0
    sys_stats = st.session_state.get('system_stats', [])
    sys_gimmicks = st.session_state.get('system_gimmicks', [])
    for feat, weight in coefs.items():
        if feat in sys_stats:
            val += float(inst.get(feat, 0)) * weight
        elif feat.startswith('Combo_Trigger_Target_'):
            val_cat = feat.replace('Combo_Trigger_Target_', '')
            parts = val_cat.split(" & ")
            if len(parts) == 2:
                trigger_col = next((c for c in sys_gimmicks if 'trigger' in c.lower()), None)
                target_col = next((c for c in sys_gimmicks if 'target' in c.lower()), None)
                if trigger_col and target_col and str(inst.get('gimmicks', {}).get(trigger_col)) == parts[0] and str(inst.get('gimmicks', {}).get(target_col)) == parts[1]:
                    val += weight
        else:
            for g in sys_gimmicks:
                prefix = f"{g}_"
                if feat.startswith(prefix) and str(inst.get('gimmicks', {}).get(g)) == feat[len(prefix):]:
                    val += weight
    return val

def calculate_win_rate(ally_instances, enemy_instances):
    if not st.session_state.get('has_ml_data') or 'ml_coefs' not in st.session_state: return None
    coefs = st.session_state['ml_coefs']
    intercept = st.session_state['ml_intercept']
    ally_score = sum([calc_instance_score(inst, coefs) for inst in ally_instances if inst])
    enemy_score = sum([calc_instance_score(inst, coefs) for inst in enemy_instances if inst])
    diff = ally_score - enemy_score + intercept
    try: return (1.0 / (1.0 + math.exp(-diff))) * 100
    except OverflowError: return 100.0 if diff > 0 else 0.0



def _deck_df_to_cards(deck_df):
    """덱 DataFrame을 카드 dict 리스트로 전개한다 (Count 만큼 복제)."""
    cards = []
    if deck_df is None:
        return cards
    for _, row in deck_df.iterrows():
        name = row.get("Name")
        if name is None or str(name).strip() == "" or str(name).strip().lower() == "nan":
            continue
        try:
            count = int(row.get("Count", 1) or 1)
        except (ValueError, TypeError):
            count = 1
        try:
            cost = int(row.get("Cost", 0) or 0)
        except (ValueError, TypeError):
            cost = 0
        for _ in range(max(1, count)):
            cards.append({
                "name": str(name),
                "cost": cost,
                "gimmicks": {
                    "Target_Logic": str(row.get("Target_Logic") or "Single_Target"),
                    "Formula": str(row.get("Formula") or "0"),
                },
            })
    return cards

def get_default_df(team_keys):
    data = []
    sys_stats = st.session_state.get('system_stats', [])
    sys_gimmicks = st.session_state.get('system_gimmicks', [])
    for i in range(4):
        hero_name = team_keys[i] if i < len(team_keys) else "비어 있음"
        row_dict = {"Hero": hero_name}
        if hero_name and hero_name != "비어 있음" and hero_name in st.session_state.get('character_library', {}):
            lib_char = st.session_state['character_library'][hero_name]
            for s in sys_stats: row_dict[s] = float(lib_char['stats'].get(s, 0.0))
            for g in sys_gimmicks: row_dict[g] = lib_char.get('gimmicks', {}).get(g, "None")
        else:
            for s in sys_stats: row_dict[s] = 0.0
            for g in sys_gimmicks: row_dict[g] = "None"
        data.append(row_dict)
    return pd.DataFrame(data)

def check_df_changes(old_df, new_df):
    changed = False
    sys_stats = st.session_state.get('system_stats', [])
    sys_gimmicks = st.session_state.get('system_gimmicks', [])
    for i in range(len(new_df)):
        if new_df.loc[i, "Hero"] != old_df.loc[i, "Hero"]:
            changed = True
            hero_name = new_df.loc[i, "Hero"]
            if hero_name and hero_name != "비어 있음" and hero_name in st.session_state.get('character_library', {}):
                lib_char = st.session_state['character_library'][hero_name]
                for s in sys_stats: new_df.loc[i, s] = float(lib_char['stats'].get(s, 0.0))
                for g in sys_gimmicks: new_df.loc[i, g] = lib_char.get('gimmicks', {}).get(g, "None")
            elif hero_name == "비어 있음":
                for s in sys_stats: new_df.loc[i, s] = 0.0
                for g in sys_gimmicks: new_df.loc[i, g] = "None"
    return changed, new_df

def _mismatch_row_from_score(battle_index, score_type, score):
    _fm = score.get("first_mismatch")
    if not _fm:
        return None
    checks = max(1, score.get("checks", 1) or 1)
    mismatches = score.get("mismatches", 0) or 0
    accuracy = score.get("accuracy")
    if accuracy is None:
        accuracy = (1.0 - (mismatches / checks)) * 100.0
    return {
        "battle_index": battle_index,
        "score_type": score_type,
        "turn": _fm.get("turn"),
        "id": _fm.get("id"),
        "kind": _fm.get("kind"),
        "resource": _fm.get("resource"),
        "expected": _fm.get("expected"),
        "actual": _fm.get("actual"),
        "checks": score.get("checks"),
        "mismatches": score.get("mismatches"),
        "accuracy": accuracy,
        "expected_full": repr(_fm.get("expected_full", _fm.get("expected"))),
        "actual_full": repr(_fm.get("actual_full", _fm.get("actual")))
    }

def _extend_mismatch_rows_from_metrics(rows, battle_index, metrics):
    if not metrics:
        return
    for stype in ["state_score", "action_damage_score", "action_resource_delta_score"]:
        if metrics.get(stype):
            row = _mismatch_row_from_score(battle_index, stype.replace("_score", ""), metrics[stype])
            if row:
                rows.append(row)

def render_dashboard():
    # 1. 불필요한 타이틀 및 설명글 제거 (상단 압축)
    
    if "df" not in st.session_state or not st.session_state.get('mapping_approved', False):
        return False, "⚠️ 2단계(System Definition)에서 데이터를 맵핑해야 합니다."

    df = st.session_state["df"]
    sys_stats = st.session_state.get('system_stats', [])
    sys_gimmicks = st.session_state.get('system_gimmicks', [])

    # Phase 6 — Game Profile 기반 모듈 게이팅
    _gp6 = st.session_state.get('game_profile')
    _resource_on = module_active(_gp6, 'resource')
    _spatial_on = module_active(_gp6, 'spatial')
    _deck_on = module_active(_gp6, 'deck')
    
    st.markdown("""
        <style>
        .sidebar-content { padding: 10px; border-radius: 5px; margin-bottom: 15px; }
        </style>
    """, unsafe_allow_html=True)
    
    # 3. 토글 버튼 위치 조정 (Inline) 및 2. Config 영역 접기 (Expander)
    top_col1, top_col2 = st.columns([5, 1.5])
    
    with top_col2:
        st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
        is_fullscreen = st.toggle("📺 뷰어 전체화면", key="dashboard_fullscreen")

    with top_col1:
        with st.expander("⚙️ 스탯 매핑 & 예산 가중치 (Weights) 설정", expanded=False):
            col_s1, col_s2, col_s3 = st.columns(3)
            def_anchor = next((s for s in sys_stats if 'atk' in s.lower() or '공격' in s), sys_stats[0] if sys_stats else "")
            def_health = next((s for s in sys_stats if 'hp' in s.lower() or '체력' in s), sys_stats[0] if sys_stats else "")
            def_speed = next((s for s in sys_stats if 'spd' in s.lower() or '속도' in s or 'speed' in s.lower()), sys_stats[0] if sys_stats else "")
            
            with col_s1: anchor_stat = st.selectbox("🎯 Anchor Stat", sys_stats, index=sys_stats.index(def_anchor) if def_anchor in sys_stats else 0)
            with col_s2: health_stat = st.selectbox("❤️ Health Stat", sys_stats, index=sys_stats.index(def_health) if def_health in sys_stats else 0)
            with col_s3: speed_stat = st.selectbox("⚡ Speed Stat", sys_stats, index=sys_stats.index(def_speed) if def_speed in sys_stats else 0)
            
            st.session_state['anchor_stat'] = anchor_stat
            st.session_state['health_stat'] = health_stat
            st.session_state['speed_stat'] = speed_stat
            
            # ── 자원 선언 (Phase 3.5b-i) ──
            # health_stat = HP(vital) 자원. 그 외 스탯을 Pool/Shield 역할로 선언.
            if _resource_on:
                st.markdown("##### 🧪 추가 자원 선언 (Pool / Shield)")
                extra_candidates = [s for s in sys_stats if s != health_stat]
                extra_stats = st.multiselect(
                    "추가 자원으로 쓸 스탯 (HP 외 비-치명 자원)",
                    extra_candidates, default=[], key="ui_pool_stats"
                )
                resource_config = {"HP": {"role": "vital", "stat": health_stat, "regen": 0.0}}
                for es in extra_stats:
                    rc1, rc2 = st.columns(2)
                    with rc1:
                        role = st.selectbox(
                            f"{es} 역할", ["pool", "shield"], key=f"ui_role_{es}",
                            help="pool = 턴 재생 가능한 비-치명 자원 / shield = 데미지를 HP보다 먼저 흡수"
                        )
                    with rc2:
                        regen = st.number_input(f"{es} 턴당 재생", value=0.0, step=1.0,
                                                format="%.1f", key=f"ui_regen_{es}")
                    resource_config[es] = {"role": role, "stat": es, "regen": regen}
                st.session_state['resource_config'] = resource_config
                resource_role_stats = set(spec["stat"] for spec in resource_config.values())

                # ── damage_type 라우팅 맵 (Phase 3.5b-ii) ──
                sys_gimmicks = st.session_state.get('system_gimmicks', [])
                damage_type_col = next(
                    (c for c in sys_gimmicks
                     if 'damage_type' in c.lower() or 'dmg_type' in c.lower()),
                    None,
                )
                df = st.session_state.get('df')

                if not damage_type_col or df is None:
                    st.session_state['damage_type_map'] = {}
                else:
                    st.markdown("##### 🎯 데미지 타입 → 자원 라우팅")
                    st.caption("damage_type을 HP(vital)에 매핑하거나 미매핑하면 shield가 먼저 흡수합니다. pool/shield로 매핑하면 해당 자원으로 직격합니다.")

                    unique_dmg_types = [x for x in df[damage_type_col].dropna().unique() if str(x).strip() and str(x).strip() != "None"]
                    resource_names = list(resource_config.keys())
                    damage_type_map = {}

                    if unique_dmg_types:
                        rc_cols = st.columns(min(len(unique_dmg_types), 4))
                        for idx, dt in enumerate(unique_dmg_types):
                            with rc_cols[idx % len(rc_cols)]:
                                sel = st.selectbox(
                                    str(dt),
                                    options=resource_names,
                                    index=0,
                                    key=f"ui_dmgroute_{dt}_{'|'.join(resource_names)}"
                                )
                                damage_type_map[dt] = sel
                    st.session_state['damage_type_map'] = damage_type_map
            else:
                # 자원 모듈 OFF — HP 단일 자원(현행 baseline) 강제
                resource_config = {"HP": {"role": "vital", "stat": health_stat, "regen": 0.0}}
                st.session_state['resource_config'] = resource_config
                resource_role_stats = set(spec["stat"] for spec in resource_config.values())
                st.session_state['damage_type_map'] = {}

            st.markdown("##### ⚖️ 스탯 예산 환산 가중치 (Budget Weights)")
            if sys_stats:
                weight_cols = st.columns(len(sys_stats))
                stat_weights = {}
                for i, stat in enumerate(sys_stats):
                    default_weight = 0.1 if stat in resource_role_stats else 1.0
                    with weight_cols[i % len(weight_cols)]:
                        stat_weights[stat] = st.number_input(f"{stat} W.", value=default_weight, step=0.1, format="%.2f", key=f"weight_{stat}_{'res' if stat in resource_role_stats else 'base'}")
                st.session_state['stat_weights'] = stat_weights
            else:
                st.session_state['stat_weights'] = {}

            # ── 공간 시스템: 사거리/이동력 스탯 + 격자 (Phase 4a-UI / 4b-UI) ──
            if _spatial_on:
                st.markdown("##### 🗺️ 공간 시스템 (격자 + 사거리 + 이동)")
                sp_c1, sp_c2, sp_c3, sp_c4, sp_c5 = st.columns(5)
                with sp_c1:
                    range_stat_sel = st.selectbox(
                        "🎯 사거리 스탯", ["(없음)"] + sys_stats, index=0,
                        help="사거리로 쓸 스탯. (없음) = 사거리 무제한 = 현행 동작과 동일")
                with sp_c2:
                    move_stat_sel = st.selectbox(
                        "🏃 이동력 스탯", ["(없음)"] + sys_stats, index=0,
                        help="턴당 이동 타일 수로 쓸 스탯. (없음) = 이동 없음 = 현행 동작과 동일")
                with sp_c3:
                    grid_w = st.number_input("격자 너비", min_value=1, value=10, step=1, key="ui_grid_w")
                with sp_c4:
                    grid_h = st.number_input("격자 높이", min_value=1, value=10, step=1, key="ui_grid_h")
                with sp_c5:
                    dist_metric = st.selectbox("거리 방식", ["manhattan", "chebyshev"],
                                               index=0, key="ui_dist_metric")
                st.session_state['range_stat'] = None if range_stat_sel == "(없음)" else range_stat_sel
                st.session_state['move_stat'] = None if move_stat_sel == "(없음)" else move_stat_sel
                st.session_state['grid_config'] = {
                    "width": int(grid_w), "height": int(grid_h), "distance_metric": dist_metric
                }
            else:
                # 공간 모듈 OFF — 사거리/이동 미사용(현행 baseline)
                st.session_state['range_stat'] = None
                st.session_state['move_stat'] = None
                st.session_state['grid_config'] = {"width": 10, "height": 10,
                                                   "distance_metric": "manhattan"}

        if _deck_on:
            with st.expander("🃏 덱 전투 (Card Combat)", expanded=False):
                deck_mode = st.checkbox(
                    "덱 전투 모드 사용", value=False, key="ui_deck_mode",
                    help="켜면 캐릭터가 매 턴 카드를 드로우/플레이한다. 끄면 현행 전투 그대로.")
                st.session_state['deck_mode'] = deck_mode

                dc1, dc2 = st.columns(2)
                with dc1:
                    hand_size = st.number_input("핸드 크기 (턴당 드로우)", min_value=1,
                                                value=5, step=1, key="ui_hand_size")
                with dc2:
                    energy_per_turn = st.number_input("턴당 에너지", min_value=1,
                                                      value=3, step=1, key="ui_energy")
                st.session_state['deck_config'] = {
                    "hand_size": int(hand_size), "energy_per_turn": int(energy_per_turn)
                }

                _card_cols = {
                    "Name": st.column_config.TextColumn("카드 이름"),
                    "Cost": st.column_config.NumberColumn("코스트", min_value=0, step=1),
                    "Target_Logic": st.column_config.SelectboxColumn(
                        "타겟", options=["Single_Target", "AoE_All", "Lowest_HP"]),
                    "Formula": st.column_config.TextColumn("데미지 공식"),
                    "Count": st.column_config.NumberColumn("덱 매수", min_value=1, step=1),
                }
                _default_deck = [{"Name": "Strike", "Cost": 1,
                                  "Target_Logic": "Single_Target",
                                  "Formula": "phys_power - target_armor_class", "Count": 8}]
                if 'ally_deck_df' not in st.session_state:
                    st.session_state['ally_deck_df'] = pd.DataFrame(_default_deck)
                if 'enemy_deck_df' not in st.session_state:
                    st.session_state['enemy_deck_df'] = pd.DataFrame(_default_deck)

                st.markdown("##### 🔵 Ally 덱")
                st.session_state['ally_deck_df'] = st.data_editor(
                    st.session_state['ally_deck_df'], column_config=_card_cols,
                    num_rows="dynamic", use_container_width=True, hide_index=True,
                    key="ui_ally_deck_editor")
                st.markdown("##### 🔴 Enemy 덱")
                st.session_state['enemy_deck_df'] = st.data_editor(
                    st.session_state['enemy_deck_df'], column_config=_card_cols,
                    num_rows="dynamic", use_container_width=True, hide_index=True,
                    key="ui_enemy_deck_editor")
        else:
            # 덱 모듈 OFF — 덱 전투 미사용(현행 baseline)
            st.session_state['deck_mode'] = False

    tab1, tab2 = st.tabs(["GM Mode: Team Setup", "Global Character Builder"])

    with tab1:
        df_margin = None
        if st.session_state.get('has_ml_data') and 'ml_coefs' in st.session_state:
            coefs = st.session_state['ml_coefs']
            orig_numeric_cols = st.session_state.get('numeric_cols', [])
            base_stat_feat = anchor_stat
            if not base_stat_feat or base_stat_feat not in coefs:
                base_stat_feat = next((f for f, c in coefs.items() if f in orig_numeric_cols), list(coefs.keys())[0] if coefs else None)
            
            if base_stat_feat:
                base_marginal = float(coefs.get(base_stat_feat, 0.0001) * 0.25 * 100)
                if base_marginal == 0: base_marginal = 0.0001
                
                m_data_base, m_data_combo = [], []
                for feat, coef in coefs.items():
                    marginal = float(coef * 0.25 * 100)
                    is_cat = feat not in orig_numeric_cols
                    conversion_val = marginal / base_marginal
                    conv_text = f"기준 ({base_stat_feat} 1.0 포인트)" if feat == base_stat_feat else f"{base_stat_feat} {conversion_val:.1f} 포인트"
                    row_data = {"요소 이름": feat, "승률 변화(%p)": f"{marginal:+.3f}%p", "환산 가치": conv_text, "절대 가치": abs(marginal), "원시 가치": marginal}
                    if is_cat: m_data_combo.append(row_data)
                    else: m_data_base.append(row_data)
                        
                df_margin_base = pd.DataFrame(m_data_base).sort_values("원시 가치", ascending=False) if m_data_base else pd.DataFrame()
                df_margin_combo = pd.DataFrame(m_data_combo).sort_values("원시 가치", ascending=False) if m_data_combo else pd.DataFrame()
                if not df_margin_combo.empty: df_margin_combo["랭킹"] = [f"{i}위" for i in range(1, len(df_margin_combo) + 1)]
                if not df_margin_combo.empty or not df_margin_base.empty:
                    df_margin = pd.concat([df_margin_combo, df_margin_base]).sort_values("원시 가치", ascending=False)
        
        # 레이아웃 분할 분기 처리
        if is_fullscreen:
            col_input = None
            col_output = st.container()
        else:
            col_input, col_output = st.columns([1.2, 1])
            
        all_heroes = ["비어 있음"] + list(st.session_state.get('character_library', {}).keys())
        
        if 'ally_df' not in st.session_state:
            st.session_state['ally_df'] = get_default_df([st.session_state.get(f"Ally_slot_{i}_select", "비어 있음") for i in range(4)])
        if 'enemy_df' not in st.session_state:
            st.session_state['enemy_df'] = get_default_df([st.session_state.get(f"Enemy_slot_{i}_select", "비어 있음") for i in range(4)])
            
        if col_input is not None:
            with col_input:
                st.markdown("### ⚔️ 조작부: 파티 편성 및 스탯 조정")
                def calc_char_value(row, weights):
                    if row["Hero"] == "비어 있음" or pd.isna(row["Hero"]): return 0.0
                    val = 0.0
                    for stat in sys_stats:
                        val += float(row.get(stat, 0.0)) * weights.get(stat, 1.0)
                    return val
    
                weights = st.session_state.get('stat_weights', {})
                st.session_state['ally_df']['Total_Value'] = st.session_state['ally_df'].apply(lambda r: calc_char_value(r, weights), axis=1)
                st.session_state['enemy_df']['Total_Value'] = st.session_state['enemy_df'].apply(lambda r: calc_char_value(r, weights), axis=1)
    
                ally_team_total = st.session_state['ally_df']['Total_Value'].sum()
                enemy_team_total = st.session_state['enemy_df']['Total_Value'].sum()
                team_delta = ally_team_total - enemy_team_total
    
                column_config = {
                    "Hero": st.column_config.SelectboxColumn("Hero", options=all_heroes),
                    "Total_Value": st.column_config.NumberColumn("Total_Value", format="%.2f", disabled=True)
                }
                # 3. 프로페셔널 NumberColumn 적용
                for s in sys_stats:
                    column_config[s] = st.column_config.NumberColumn(s, format="%.1f")
                    
                for g in sys_gimmicks: column_config[g] = st.column_config.SelectboxColumn(g, options=st.session_state.get('gimmick_uniques', {}).get(g, ["None"]))
                
                st.markdown("##### 🔵 Ally 파티")
                st.metric("🔵 팀 총합 체급 (Ally)", f"{ally_team_total:.2f}", f"{team_delta:+.2f} 우세" if team_delta >= 0 else f"{team_delta:+.2f} 열세")
                edited_ally = st.data_editor(st.session_state['ally_df'], column_config=column_config, use_container_width=True, hide_index=True)
                if not edited_ally.equals(st.session_state['ally_df']):
                    changed, new_ally = check_df_changes(st.session_state['ally_df'], edited_ally)
                    st.session_state['ally_df'] = new_ally
                    st.rerun()
    
                st.markdown("##### 🔴 Enemy 파티")
                st.metric("🔴 팀 총합 체급 (Enemy)", f"{enemy_team_total:.2f}", f"{-team_delta:+.2f} 우세" if -team_delta >= 0 else f"{-team_delta:+.2f} 열세")
                edited_enemy = st.data_editor(st.session_state['enemy_df'], column_config=column_config, use_container_width=True, hide_index=True)
                if not edited_enemy.equals(st.session_state['enemy_df']):
                    changed, new_enemy = check_df_changes(st.session_state['enemy_df'], edited_enemy)
                    st.session_state['enemy_df'] = new_enemy
                    st.rerun()

                # ── 캐릭터 격자 배치 (Phase 4a-UI / 4b-UI) ──
                char_positions = {}
                _range_stat = st.session_state.get('range_stat')
                _move_stat = st.session_state.get('move_stat')
                if _range_stat or _move_stat:
                    _grid_cfg = st.session_state.get('grid_config', {})
                    _gw = _grid_cfg.get('width', 10)
                    _gh = _grid_cfg.get('height', 10)
                    st.markdown("##### 🗺️ 캐릭터 격자 배치")
                    st.caption(f"격자 {_gw}×{_gh} · 거리 {_grid_cfg.get('distance_metric','manhattan')} "
                               f"— 좌표는 0부터")
                    for _team, _tdf in [("Ally", st.session_state['ally_df']),
                                        ("Enemy", st.session_state['enemy_df'])]:
                        for _idx, (_, _row) in enumerate(_tdf.iterrows()):
                            _hero = _row["Hero"]
                            if _hero and _hero != "비어 있음" and not pd.isna(_hero):
                                _pc1, _pc2 = st.columns(2)
                                with _pc1:
                                    _px = st.number_input(
                                        f"{_team} · {_hero} — X", min_value=0, value=0, step=1,
                                        key=f"ui_posx_{_team}_{_idx}")
                                with _pc2:
                                    _py = st.number_input(
                                        f"{_team} · {_hero} — Y", min_value=0, value=0, step=1,
                                        key=f"ui_posy_{_team}_{_idx}")
                                char_positions[f"{_team}_{_idx}"] = {"x": int(_px), "y": int(_py)}
                st.session_state['char_positions'] = char_positions
    
                def df_to_instances(df_target, team=None):
                    instances = []
                    resource_config = st.session_state.get('resource_config')
                    if not resource_config:
                        # 폴백 — 자원 설정 미존재 시 health_stat 기반 HP 단일 자원
                        h_stat = st.session_state.get('health_stat')
                        resource_config = {"HP": {"role": "vital", "stat": h_stat, "regen": 0.0}}
                    char_positions = st.session_state.get('char_positions', {})
                    for _idx, (_, row) in enumerate(df_target.iterrows()):
                        if row["Hero"] and row["Hero"] != "비어 있음" and not pd.isna(row["Hero"]):
                            inst = {"name": row["Hero"], "gimmicks": {}}
                            for g in sys_gimmicks: inst["gimmicks"][g] = row.get(g, "None")
                            promote_effect_keys(inst, st.session_state.get("game_config"))
                            for s in sys_stats: inst[s] = float(row[s])
                            # 자원 설정 기반 다중 자원 빌드
                            inst['resources'] = {}
                            for rname, rspec in resource_config.items():
                                stat = rspec.get('stat')
                                val = float(inst[stat]) if (stat and stat in inst) else 1.0
                                inst['resources'][rname] = {"current": val, "max": val}
                            # ── Phase 8a: 무브풀 부착 (글로벌 무브 라이브러리) ──
                            _move_lib = st.session_state.get('move_library')
                            if _move_lib:
                                inst['movepool'] = _move_lib
                            # 격자 좌표 부착 (공간 OFF면 char_positions가 비어 있어 미부착)
                            _pos = char_positions.get(f"{team}_{_idx}")
                            if _pos is not None:
                                inst['position'] = _pos
                            # 덱 부착 (덱 전투 모드일 때만)
                            if st.session_state.get('deck_mode'):
                                _deck_df = (st.session_state.get('ally_deck_df')
                                            if team == "Ally"
                                            else st.session_state.get('enemy_deck_df'))
                                inst['deck'] = _deck_df_to_cards(_deck_df)
                            instances.append(inst)
                    return instances
                
                ally_instances = df_to_instances(st.session_state['ally_df'], team="Ally")
                enemy_instances = df_to_instances(st.session_state['enemy_df'], team="Enemy")

        with col_output:
            st.markdown("### 📊 결과부: 예측 승률 및 시뮬레이션")
            if st.session_state.get('meta_stagnation_warn'):
                st.error(f"🚨 **메타 고착화 위험 감지:** 지배적 조합 비중 {st.session_state.get('meta_stagnation_ratio', 0)*100:.1f}%")

            current_win_rate = calculate_win_rate(ally_instances, enemy_instances) if st.session_state.get('has_ml_data') else None
            m1, m2 = st.columns(2)
            with m1:
                if current_win_rate is not None:
                    delta_val = current_win_rate - st.session_state.get('initial_win_rate', current_win_rate)
                    st.session_state['initial_win_rate'] = st.session_state.get('initial_win_rate', current_win_rate)
                    st.metric("🏆 예측 승률 (Logistic Regression)", f"{current_win_rate:.1f}%", f"{delta_val:+.2f}% vs 초기")
                else: st.metric("🏆 예측 승률", "N/A", "데이터 부족")
            with m2: mc_metric_placeholder = st.empty()
            mc_metric_placeholder.metric("🎲 Monte Carlo (1만회)", "대기 중", "버튼을 눌러 실행", delta_color="off")

            if current_win_rate is not None:
                st.markdown(f"<p style='color: #4B9BFF; margin-bottom: 2px; font-size: 14px;'><b>🔵 Ally Advantage ({current_win_rate:.1f}%)</b></p>" if current_win_rate >= 50 else f"<p style='color: #FF4B4B; margin-bottom: 2px; font-size: 14px;'><b>🔴 Enemy Advantage ({(100 - current_win_rate):.1f}%)</b></p>", unsafe_allow_html=True)
                st.progress(current_win_rate / 100.0)
                
            # 2. 수직 스크롤 통제 (st.tabs 사용)
            chart_tabs = st.tabs(["Top 5 요소", "다변량 시각화", "시뮬레이션 로그"])
            
            with chart_tabs[0]:
                if df_margin is not None:
                    st.subheader("📈 핵심 기믹 & 최우선 스탯 (Top 5 요소)", divider="gray")
                    top_m_data = df_margin.head(5)
                    fig_m = go.Figure(go.Bar(x=top_m_data["절대 가치"], y=top_m_data["요소 이름"].astype(str), orientation='h', marker_color='#4B9BFF'))
                    fig_m.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="가치 기여도(Abs)", yaxis_title="")
                    fig_m.update_yaxes(autorange="reversed")
                    st.plotly_chart(fig_m, use_container_width=True, config={'displayModeBar': False})

            with chart_tabs[1]:
                # ═══════════════════════════════════════════════════════════
                # Apache ECharts 네이티브 평행 좌표계 (SVG 렌더러)
                # ═══════════════════════════════════════════════════════════
                st.markdown("##### 🕸️ 범용 다변량 시각화 (Parallel Coordinates — SVG)")
                try:
                    comb_df = pd.concat([
                        st.session_state['ally_df'].assign(Team="Ally"),
                        st.session_state['enemy_df'].assign(Team="Enemy")
                    ]).reset_index(drop=True)

                    # ── Safe String Casting ──
                    def _safe_hero_str(val):
                        if val is None or (isinstance(val, float) and pd.isna(val)):
                            return ""
                        if isinstance(val, float):
                            return str(int(val)) if val == int(val) else str(val)
                        return str(val).strip()

                    comb_df["Hero"] = comb_df["Hero"].apply(_safe_hero_str)
                    _invalid = {"", "nan", "None", "비어 있음", "0"}
                    comb_df = comb_df[~comb_df["Hero"].isin(_invalid)].reset_index(drop=True)

                    _tm = {0: "Ally", 1: "Enemy", 0.0: "Ally", 1.0: "Enemy",
                           "0": "Ally", "1": "Enemy", "Ally": "Ally", "Enemy": "Enemy"}
                    comb_df["Team"] = comb_df["Team"].apply(
                        lambda v: _tm.get(v, _tm.get(str(v).strip(), "Ally"))
                    ).astype(str)

                    for s in sys_stats:
                        comb_df[s] = pd.to_numeric(comb_df[s], errors="coerce").fillna(0.0)

                    if not comb_df.empty and len(sys_stats) > 0:
                        comb_df["_uid"] = (
                            comb_df["Team"].astype(str) + " | " +
                            comb_df["Hero"].astype(str) + " #" +
                            comb_df.groupby(["Team", "Hero"]).cumcount().add(1).astype(str)
                        )

                        # ── 1. 하이라이트 Dropdown ──
                        hl_options = ["전체 보기 (팀 색상)"] + comb_df["_uid"].tolist()
                        selected_hl = st.selectbox(
                            "🔍 캐릭터 하이라이트", hl_options, index=0,
                            key="parcoords_highlight_select",
                            help="특정 캐릭터를 선택하면 해당 선만 강조(금색)되고 나머지는 반투명 회색으로 표시됩니다."
                        )

                        # ── ECharts parallelAxis 동적 생성 ──
                        stat_ranges = {}
                        parallel_axis_list = []
                        for i, s in enumerate(sys_stats):
                            s_min = float(comb_df[s].min())
                            s_max = float(comb_df[s].max())
                            if s_min == s_max:
                                s_min -= 1.0
                                s_max += 1.0
                            stat_ranges[s] = (s_min, s_max)
                            parallel_axis_list.append({
                                "dim": i,
                                "name": s,
                                "min": s_min,
                                "max": s_max,
                                "nameTextStyle": {"fontWeight": "bold", "fontSize": 13},
                                "axisLabel": {"fontWeight": "bold", "fontSize": 12}
                            })

                        # ── ECharts series 데이터 구성 ──
                        team_colors = {"Ally": "#3182bd", "Enemy": "#e6550d"}
                        hl_color = "#FFD700"
                        dim_color = "rgba(100,100,100,0.15)"

                        series_list = []
                        for _, row in comb_df.iterrows():
                            uid = str(row["_uid"])
                            team = str(row["Team"])
                            data_vals = [float(row[s]) for s in sys_stats]

                            if selected_hl == "전체 보기 (팀 색상)":
                                line_color = team_colors.get(team, "#888")
                                line_w = 2.0
                                line_opacity = 0.7
                            elif uid == selected_hl:
                                line_color = hl_color
                                line_w = 4.0
                                line_opacity = 1.0
                            else:
                                line_color = dim_color
                                line_w = 1.5
                                line_opacity = 0.15

                            series_list.append({
                                "type": "parallel",
                                "name": uid,
                                "data": [data_vals],
                                "lineStyle": {
                                    "color": line_color,
                                    "width": line_w,
                                    "opacity": line_opacity
                                },
                                "emphasis": {
                                    "lineStyle": {"width": 4, "opacity": 1.0}
                                }
                            })

                        # ── ECharts Option 조립 ──
                        option = {
                            "tooltip": {"trigger": "item", "formatter": "{a}"},
                            "parallel": {
                                "left": 60, "right": 60, "top": "15%", "bottom": "10%",
                                "parallelAxisDefault": {
                                    "nameLocation": "start",
                                    "nameGap": 25,
                                    "nameTextStyle": {"fontWeight": "bold", "fontSize": 13},
                                    "axisLabel": {"fontSize": 12, "fontWeight": "bold"}
                                }
                            },
                            "parallelAxis": parallel_axis_list,
                            "series": series_list
                        }

                        # 팀 색상 모드일 때 범례를 차트 상단에 인라인 표시
                        if selected_hl == "전체 보기 (팀 색상)":
                            option["legend"] = {"show": False}
                            st.markdown("🔵 <span style='color:#3182bd;font-weight:bold'>Ally</span>&emsp;🔴 <span style='color:#e6550d;font-weight:bold'>Enemy</span>", unsafe_allow_html=True)

                        _opt_json = json.dumps(option, ensure_ascii=False)
                        _echarts_html = f"""
                        <!DOCTYPE html><html><head>
                        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
                        </head><body>
                        <div id="pc_chart" style="width:100%;height:380px;"></div>
                        <script>
                            var chart = echarts.init(document.getElementById('pc_chart'), null, {{renderer:'svg'}});
                            chart.setOption({_opt_json});
                            window.addEventListener('resize', function(){{ chart.resize(); }});
                        </script>
                        </body></html>
                        """
                        components.html(_echarts_html, height=420)

                        st.caption("💡 각 세로축이 스탯, 선 하나가 캐릭터 1명입니다. X자 교차 구간은 반비례 밸런스를 의미합니다.")

                        # ── 2. 축 필터링 연동 명단 (Expander 접기) ──
                        with st.expander("📊 축 필터링 연동 명단 및 세부 스탯 보기", expanded=False):
                            filter_mask = pd.Series([True] * len(comb_df))
                            filter_cols = st.columns(min(4, len(sys_stats)))
                            for idx, s in enumerate(sys_stats):
                                s_min_val, s_max_val = stat_ranges[s]
                                with filter_cols[idx % len(filter_cols)]:
                                    f_range = st.slider(
                                        f"{s}", min_value=s_min_val, max_value=s_max_val,
                                        value=(s_min_val, s_max_val),
                                        key=f"pcoord_filter_{s}"
                                    )
                                    filter_mask &= (comb_df[s] >= f_range[0]) & (comb_df[s] <= f_range[1])

                            filtered_df = comb_df[filter_mask].copy()
                            display_cols = ["Hero", "Team"] + sys_stats
                            display_df = filtered_df[[c for c in display_cols if c in filtered_df.columns]].copy()

                            st.dataframe(
                                display_df, use_container_width=True, hide_index=True,
                                column_config={
                                    "Hero": st.column_config.TextColumn("Hero ID", width="medium"),
                                    "Team": st.column_config.TextColumn("진영", width="small"),
                                    **{s: st.column_config.NumberColumn(s, format="%.1f") for s in sys_stats}
                                }
                            )
                            st.caption(f"필터 결과: 전체 {len(comb_df)}명 중 **{len(filtered_df)}명** 표시 중")
                    else:
                        st.info("📭 편성된 캐릭터가 없습니다. 조작부에서 캐릭터를 배치해주세요.")
                except Exception as e:
                    st.warning(f"다변량 시각화 렌더링 중 오류가 발생했습니다: {e}")

            with chart_tabs[2]:
                # ── 상단: 엔진 공통 설정 ──
                with st.container(border=True):
                    st.markdown("**⚙️ 시뮬레이션 엔진 환경 설정**")
                    sim_max_turns = st.slider(
                        "⏱️ 최대 시뮬레이션 턴 수", min_value=10, max_value=500,
                        value=100, step=10, key="sim_max_turns",
                        help="전투가 이 턴 수 내에 끝나지 않으면 무승부로 종료됩니다."
                    )
                    st.caption("※ 설정된 최대 턴 수는 단일 전투 및 몬테카를로 시뮬레이션에 모두 공통 적용됩니다.")

                # ── 중간 여백 ──
                st.write("")

                # ── 하단: 시뮬레이션 실행 ──
                st.markdown("**🚀 시뮬레이션 실행**")
                btn_col1, btn_col2 = st.columns(2)
                
                # 공통 환경 변수 (st.session_state 의존성을 여기서 추출하여 전달)
                combat_flow_val = st.session_state.get('combat_flow', DEFAULT_COMBAT_FLOW)
                speed_stat_val = st.session_state.get('speed_stat')
                sys_stats_val = st.session_state.get('system_stats', [])
                global_formula_val = st.session_state.get('global_damage_formula', '0')
                
                range_stat_val = st.session_state.get('range_stat')
                move_stat_val = st.session_state.get('move_stat')
                _grid = st.session_state.get('grid_config') or {}
                spatial_module_val = (SpatialModule(
                    width=_grid.get('width'), height=_grid.get('height'),
                    distance_metric=_grid.get('distance_metric', 'manhattan'))
                    if _spatial_on else None)
                _deck_cfg = st.session_state.get('deck_config') or {}
                deck_module_val = (DeckModule(
                    hand_size=_deck_cfg.get('hand_size', 5),
                    energy_per_turn=_deck_cfg.get('energy_per_turn', 3))
                    if st.session_state.get('deck_mode') else None)
                
                with btn_col1:
                    if st.button("⚔️ 단일 전투 시작 (1회)", type="primary", use_container_width=True):
                        with st.spinner("단일 전투 중..."):
                            winner, battle_logs, sim_metrics = run_simulation(
                                ally_instances, enemy_instances, max_turns=sim_max_turns,
                                combat_flow=combat_flow_val, speed_stat=speed_stat_val,
                                sys_stats=sys_stats_val, global_damage_formula=global_formula_val,
                                resource_module=ResourceModule(
                                    st.session_state.get('resource_config') or None,
                                    damage_type_map=st.session_state.get('damage_type_map') or None
                                ),
                                spatial_module=spatial_module_val,
                                range_stat=range_stat_val,
                                move_stat=move_stat_val,
                                deck_module=deck_module_val,
                                game_config=st.session_state.get('game_config')
                            )
                            st.markdown("#### 📜 1회 전투 로그")
                            log_container = st.container(height=300)
                            with log_container:
                                for log in battle_logs:
                                    if "🏆" in log or "⚔️" in log: st.markdown(f"**{log}**")
                                    elif "❌" in log or "☠️" in log: st.error(log)
                                    elif "->" in log: st.caption(log)
                                    else: st.text(log)
                with btn_col2:
                    if st.button("🎲 1만회 Monte Carlo 실행", use_container_width=True):
                        with st.spinner("Executing True 1만 MC runs (Multiprocessing)..."):
                            progress_bar = st.progress(0.0)
                            status_text = st.empty()
                            
                            start_time = time.time()
                            def progress_cb(completed, total):
                                pct = completed / total
                                progress_bar.progress(pct)
                                elapsed = time.time() - start_time
                                eta = (elapsed / completed) * (total - completed) if completed > 0 else 0
                                status_text.text(f"진행 상황: {completed}/{total} ({pct*100:.1f}%) - 예상 남은 시간: {eta:.1f}초")
                            
                            # 모듈 레벨 default_stochasticity_factory 사용 (Pickling 안전)
                            
                            mc_result = run_monte_carlo(
                                ally_instances, enemy_instances, combat_flow_val,
                                speed_stat_val, sys_stats_val, global_formula_val,
                                num_simulations=10000, max_turns=sim_max_turns,
                                progress_callback=progress_cb,
                                stochasticity_factory=default_stochasticity_factory,
                                resource_module=ResourceModule(
                                    st.session_state.get('resource_config') or None,
                                    damage_type_map=st.session_state.get('damage_type_map') or None
                                ),
                                spatial_module=spatial_module_val,
                                range_stat=range_stat_val,
                                move_stat=move_stat_val,
                                deck_module=deck_module_val,
                                game_config=st.session_state.get('game_config')
                            )
                            
                            status_text.text(f"시뮬레이션 완료! 소요 시간: {time.time() - start_time:.1f}초")
                            
                            if isinstance(mc_result, dict) and mc_result.get("status") == "error":
                                st.error("🚨 몬테카를로 병렬 연산 중 치명적 에러가 발생했습니다.")
                                st.code(mc_result.get("message", ""), language="python")
                            else:
                                # ── 결과를 session_state에 저장하고 렌더링은 바깥에서 처리 ──
                                win_rate = mc_result.get("win_rate", 0.0)
                                mc_metric_placeholder.metric(
                                    "🎲 Monte Carlo (1만회)", f"{win_rate:.2f}%", "True MC", delta_color="normal"
                                )
                                
                                # Validation 계산
                                original_log = st.session_state.get("df", pd.DataFrame())
                                column_mapping = {
                                    "target_col": st.session_state.get("target_col") or st.session_state.get("target_variable"),
                                    "damage_col": next((c for c in sys_stats if 'damage' in c.lower() or '데미지' in c or '딜' in c), None),
                                    "element_col": next((c for c in sys_gimmicks if 'element' in c.lower() or '속성' in c), None),
                                    "buff_duration_col": next((c for c in sys_gimmicks if 'buff' in c.lower() or '지속' in c), None),
                                    "system_stats": sys_stats,
                                    "system_gimmicks": sys_gimmicks
                                }
                                validation = calculate_validation_score(
                                    simulation_results=copy.deepcopy(mc_result),
                                    original_log=original_log,
                                    column_mapping=column_mapping
                                )
                                
                                warnings_list = [
                                    {"label": k, "score": v["score"], "status": v["status"]}
                                    for k, v in validation.items()
                                    if v["status"] in ("warn", "fail") and v["score"] is not None
                                ]
                                
                                # session_state에 저장 (렌더링은 버튼 블록 바깥에서)
                                st.session_state["mc_result_cache"] = mc_result
                                st.session_state["validation_result"] = validation
                                st.session_state["validation_warnings"] = warnings_list

                # ── Monte Carlo 결과 렌더링 (session_state 기반, 탭 안으로 이동) ──
                if st.session_state.get("mc_result_cache"):
                    mc_result = st.session_state["mc_result_cache"]
                    validation = st.session_state.get("validation_result", {})
                    warnings_list = st.session_state.get("validation_warnings", [])
                    win_rate = mc_result.get("win_rate", 0.0)

                    st.markdown("---")
                    st.success(f"🎲 10,000회 시뮬레이션 결과: Ally 승률 **{win_rate:.2f}%**")

                    st.markdown("#### 🔍 로그 대조 검증 결과")

                    label_map = {
                        "damage_formula": "⚔️ 데미지 공식",
                        "element_chart":  "🌀 속성 상성",
                        "win_rate":       "🏆 승률",
                        "buff_duration":  "⏱️ 버프 지속",
                    }

                    with st.container(border=True):
                        for key, label in label_map.items():
                            v = validation.get(key, {})
                            score = v.get("score")
                            status = v.get("status", "unknown")

                            col_label, col_bar, col_badge = st.columns([2, 4, 2])

                            with col_label:
                                st.markdown(f"**{label}**")

                            with col_bar:
                                if score is not None:
                                    st.progress(score)
                                else:
                                    st.caption("측정 불가 (매핑 필요)")

                            with col_badge:
                                if status == "pass":
                                    st.success(f"{score*100:.0f}% ✅")
                                elif status == "warn":
                                    st.warning(f"{score*100:.0f}% ⚠️")
                                elif status == "fail":
                                    st.error(f"{score*100:.0f}% ❌")
                                else:
                                    st.caption("N/A")

                        st.divider()

                        ov = validation.get("overall", {})
                        ov_score = ov.get("score")
                        ov_status = ov.get("status", "unknown")

                        col_label, col_bar, col_badge = st.columns([2, 4, 2])
                        with col_label:
                            st.markdown("**📊 전체 일치율**")
                        with col_bar:
                            if ov_score is not None:
                                st.progress(ov_score)
                            else:
                                st.caption("측정 불가")
                        with col_badge:
                            if ov_status == "pass":
                                st.success(f"{ov_score*100:.0f}% ✅")
                            elif ov_status == "warn":
                                st.warning(f"{ov_score*100:.0f}% ⚠️")
                            elif ov_status == "fail":
                                st.error(f"{ov_score*100:.0f}% ❌")
                            else:
                                st.caption("N/A")

                    if warnings_list:
                        if st.button("🔧 보정하러 가기", type="primary", key="go_to_calibration"):
                            st.session_state.current_step = 2
                            st.session_state['mapping_approved'] = False
                            st.session_state.pop("mc_result_cache", None)
                            st.session_state.pop("validation_result", None)
                            st.rerun()

                # ══════════════════════════════════════════════════════════════
                # Phase 8c-α — Per-Battle Backtest (전투별 백테스트)
                # ══════════════════════════════════════════════════════════════
                st.markdown("---")
                with st.container(border=True):
                    st.markdown("#### 🔬 전투별 백테스트 (Per-Battle Backtest)")
                    st.caption(
                        "로그의 각 전투를 엔진으로 재시뮬해 **예측 승자 vs 실제 승자 일치율**을 측정합니다. "
                        "기존 검증의 \"승률\"(1매치업↔로그평균 비교)과 달리, 이건 *로그 안의 모든 전투*를 "
                        "1대1로 검사합니다. 의미 있는 시뮬레이터 충실도 지표."
                    )

                    _bb_df = st.session_state.get("df")
                    _bb_target = (st.session_state.get("target_col")
                                  or st.session_state.get("target_variable"))
                    _bb_health = st.session_state.get("health_stat")
                    _bb_ready = (_bb_df is not None and _bb_target
                                 and _bb_target in _bb_df.columns
                                 and bool(sys_stats))

                    if not _bb_ready:
                        st.info(
                            "ℹ️ 백테스트를 실행하려면 Step 2에서 **target_col**(전투 결과 컬럼)과 "
                            "**system_stats**(전투에 쓰는 스탯)가 매핑돼 있어야 합니다."
                        )
                    else:
                        _bb_n_rows = len(_bb_df)
                        
                        _bb_method = st.radio(
                            "전투 구성 방식",
                            ["행 개수로 묶기 (기존)", "DB 역할 컬럼으로 묶기"],
                            horizontal=True,
                            help="로그 구조에 따라 선택하세요. 'DB 역할 컬럼'은 전투ID와 진영 컬럼을 기반으로 구성합니다."
                        )
                        
                        _bb_size = 2
                        _bb_max = 500
                        _bb_log_schema = None
                        
                        if _bb_method == "행 개수로 묶기 (기존)":
                            _bb_c1, _bb_c2 = st.columns(2)
                            with _bb_c1:
                                _bb_size = st.number_input(
                                    "전투당 행 수 (1v1=2 · 2v2=4 · 4v4=8 — 로그가 캐릭터-per-행 패턴일 때)",
                                    min_value=2, max_value=20, value=2, step=2,
                                    key="ui_backtest_size",
                                    help="로그가 캐릭터당 한 행이라면, 한 전투의 모든 참가자가 연속해서 행으로 들어 있다고 가정합니다. 앞쪽 절반 = Ally, 뒤쪽 절반 = Enemy."
                                )
                            with _bb_c2:
                                _bb_max_cap = max(10, _bb_n_rows // max(int(_bb_size), 2))
                                _bb_max_default = min(500, _bb_max_cap)
                                _bb_max = st.number_input(
                                    f"최대 전투 수 (로그 전체 = {_bb_max_cap})",
                                    min_value=10, max_value=max(_bb_max_cap, 10),
                                    value=_bb_max_default, step=50,
                                    key="ui_backtest_max_legacy"
                                )
                        else:
                            st.markdown("##### 🗂️ DB 역할 컬럼 매핑")
                            _all_cols = ["(없음)"] + list(_bb_df.columns)
                            
                            def _guess_col(hints):
                                for col in _bb_df.columns:
                                    cl = str(col).lower()
                                    if any(h in cl for h in hints):
                                        return col
                                return "(없음)"
                                
                            _g_battle = _guess_col(["battle", "match", "combat", "game", "전투", "매치"])
                            _g_team = _guess_col(["team", "side", "camp", "faction", "player", "진영", "팀"])
                            _g_entity = _guess_col(["unit", "actor", "character", "hero", "pokemon", "entity", "slot", "유닛", "캐릭터"])
                            _g_sort = _guess_col(["turn", "round", "order", "seq", "index", "턴", "순서"])
                            
                            _bc1, _bc2 = st.columns(2)
                            with _bc1:
                                _bb_id_col = st.selectbox("전투 ID 컬럼", _all_cols, index=_all_cols.index(_g_battle) if _g_battle in _all_cols else 0)
                                _bb_team_col = st.selectbox("팀/진영 컬럼", _all_cols, index=_all_cols.index(_g_team) if _g_team in _all_cols else 0)
                            with _bc2:
                                _bb_ent_col = st.selectbox("참가자 ID 컬럼 (선택)", _all_cols, index=_all_cols.index(_g_entity) if _g_entity in _all_cols else 0)
                                _bb_sort_cols = st.multiselect("정렬 컬럼 (선택)", list(_bb_df.columns), default=[_g_sort] if _g_sort != "(없음)" else [])
                                
                            _rc1, _rc2 = st.columns(2)
                            with _rc1:
                                _bb_res_mode = st.selectbox("결과 해석 방식", ["battle_level", "side_signal"], index=0, help="battle_level: 그룹 첫 행의 승리 여부를 전투 결과로 봄 / side_signal: 팀 멤버별 결과의 합산 비교")
                            with _rc2:
                                _bb_max = st.number_input(
                                    "최대 전투 수",
                                    min_value=10, max_value=max(10, _bb_n_rows),
                                    value=min(500, max(10, _bb_n_rows)), step=50,
                                    key="ui_backtest_max_db"
                                )
                                
                            with st.expander("팀 값(문자열) 상세 매핑", expanded=False):
                                _ac1, _ac2 = st.columns(2)
                                with _ac1:
                                    _bb_ally_vals = st.text_input("Ally로 인식할 추가 값 (쉼표 구분)", "Ally, ally, A, blue, player")
                                with _ac2:
                                    _bb_enemy_vals = st.text_input("Enemy로 인식할 추가 값 (쉼표 구분)", "Enemy, enemy, E, red, opponent")
                                    
                            with st.expander("초기 필드 상태 (선택)", expanded=False):
                                _if_use = st.checkbox("initial active/on-field 사용", value=False)
                                
                                _ic1, _ic2 = st.columns(2)
                                with _ic1:
                                    _g_i_on_field = _guess_col(["on_field", "active", "lead", "starter", "front", "slot_active", "initial_active", "is_active", "field", "선발", "초기", "활성", "필드", "전열"])
                                    _bb_initial_on_field_col = st.selectbox("initial on-field 컬럼", _all_cols, index=_all_cols.index(_g_i_on_field) if _g_i_on_field in _all_cols else 0)
                                with _ic2:
                                    _bb_initial_values = st.text_input("active로 인식할 값 목록 (쉼표 구분)", "1, true, yes, y, active, lead, on, field, front, starter, 초기, 선발, 활성, 필드, 전열")
                                    
                                _g_i_order = _guess_col(["roster_idx", "slot", "position", "party_order", "team_order", "order", "seq", "배치", "순서", "슬롯"])
                                _bb_initial_order_col = st.selectbox("initial roster/order 컬럼 (선택)", _all_cols, index=_all_cols.index(_g_i_order) if _g_i_order in _all_cols else 0)

                            with st.expander("관측 상태 trace (선택)", expanded=False):
                                _st_use = st.checkbox("state snapshot trace 사용", value=False)
                                
                                _sc1, _sc2 = st.columns(2)
                                with _sc1:
                                    _g_s_turn = _guess_col(["turn", "round", "턴", "라운드"])
                                    _bb_state_turn_col = st.selectbox("state turn 컬럼", _all_cols, index=_all_cols.index(_g_s_turn) if _g_s_turn in _all_cols else 0)
                                with _sc2:
                                    _g_s_id = _guess_col(["unit", "entity", "actor", "character", "hero", "pokemon", "참가자", "유닛"])
                                    _bb_state_id_col = st.selectbox("state entity ID 컬럼", _all_cols, index=_all_cols.index(_g_s_id) if _g_s_id in _all_cols else 0)
                                    
                                _sc3, _sc4, _sc5 = st.columns(3)
                                with _sc3:
                                    _g_s_hp = _guess_col(["hp", "health", "current_hp", "remain_hp", "hp_after", "체력", "잔여"])
                                    _bb_state_hp_col = st.selectbox("state HP 컬럼 (선택)", _all_cols, index=_all_cols.index(_g_s_hp) if _g_s_hp in _all_cols else 0)
                                with _sc4:
                                    _g_s_status = _guess_col(["status", "condition", "state", "상태", "상태이상"])
                                    _bb_state_status_col = st.selectbox("state status 컬럼 (선택)", _all_cols, index=_all_cols.index(_g_s_status) if _g_s_status in _all_cols else 0)
                                with _sc5:
                                    _g_s_fainted = _guess_col(["fainted", "dead", "ko", "down", "is_dead", "is_fainted", "기절", "쓰러짐"])
                                    _bb_state_fainted_col = st.selectbox("state fainted 컬럼 (선택)", _all_cols, index=_all_cols.index(_g_s_fainted) if _g_s_fainted in _all_cols else 0)
                                    
                                _sc6, _sc7 = st.columns(2)
                                with _sc6:
                                    _bb_state_hp_mode = st.selectbox("state HP mode", ["absolute", "percent"], index=0)
                                with _sc7:
                                    _bb_state_hp_tol = st.number_input("HP 허용 오차", min_value=0.0, value=0.0, step=1.0)
                                    
                                _bb_state_resource_cols = {}
                                _resource_config_for_state = st.session_state.get("resource_config") or {}
                                _resource_names_for_state = [
                                    r for r in _resource_config_for_state.keys()
                                    if str(r) != "HP"
                                ]
                                _bb_state_resource_names = st.multiselect(
                                    "state resource 컬럼 추가",
                                    _resource_names_for_state,
                                    default=[],
                                    help="HP 외 MP/Shield/Cost 등 임의 자원의 관측 current 값을 비교합니다."
                                )
                                for _rname in _bb_state_resource_names:
                                    _guess = _guess_col([str(_rname).lower(), str(_rname), f"{_rname}_after", f"{_rname}_current"])
                                    _col = st.selectbox(
                                        f"state {_rname} 컬럼",
                                        _all_cols,
                                        index=_all_cols.index(_guess) if _guess in _all_cols else 0,
                                        key=f"bb_state_resource_col_{_rname}",
                                    )
                                    if _col != "(없음)":
                                        _bb_state_resource_cols[str(_rname)] = _col

                                _sc8, _sc9 = st.columns(2)
                                with _sc8:
                                    _bb_state_resource_mode = st.selectbox(
                                        "state resource mode",
                                        ["absolute", "percent"],
                                        index=0,
                                        key="bb_state_resource_mode",
                                    )
                                with _sc9:
                                    _bb_state_resource_tol = st.number_input(
                                        "resource 허용 오차",
                                        min_value=0.0,
                                        value=0.0,
                                        step=1.0,
                                        key="bb_state_resource_tol",
                                    )

                                _bb_state_deterministic = st.checkbox(
                                    "state score는 결정론으로 계산",
                                    value=True,
                                    help="DB 관측 상태와 엔진 상태를 비교할 때 데미지 분산을 끄고 복제 오차만 봅니다."
                                )

                            with st.expander("행동 trace 연결 (선택)", expanded=False):
                                _tc_use = st.checkbox("move trace 사용", value=False)
                                
                                _tc1, _tc2, _tc3 = st.columns(3)
                                with _tc1:
                                    _g_turn = _guess_col(["turn", "round", "턴", "라운드"])
                                    _bb_turn_col = st.selectbox("turn 컬럼", _all_cols, index=_all_cols.index(_g_turn) if _g_turn in _all_cols else 0)
                                with _tc2:
                                    _g_actor = _guess_col(["actor", "attacker", "source", "caster", "user", "unit", "entity", "행동자", "공격자", "시전자"])
                                    _bb_actor_col = st.selectbox("actor ID 컬럼", _all_cols, index=_all_cols.index(_g_actor) if _g_actor in _all_cols else 0)
                                with _tc3:
                                    _g_target = _guess_col(["target", "defender", "victim", "target_id", "대상", "타겟", "피격자"])
                                    _bb_target_col = st.selectbox("target ID 컬럼", _all_cols, index=_all_cols.index(_g_target) if _g_target in _all_cols else 0)
                                    
                                _tc4, _tc5 = st.columns(2)
                                with _tc4:
                                    _g_move = _guess_col(["move", "skill", "action_name", "ability_name", "무브", "스킬", "행동명"])
                                    _bb_move_name_col = st.selectbox("move name 컬럼", _all_cols, index=_all_cols.index(_g_move) if _g_move in _all_cols else 0)
                                    _g_action = _guess_col(["action", "event", "type", "kind", "행동", "이벤트", "종류"])
                                    _bb_action_col = st.selectbox("action type 컬럼 (선택)", _all_cols, index=_all_cols.index(_g_action) if _g_action in _all_cols else 0)
                                with _tc5:
                                    _bb_action_vals = st.text_input("move action 값 목록 (쉼표 구분)", "move, attack, skill, cast, use, use_move, act, 공격, 스킬, 무브, 행동")
                                
                                st.markdown("**무브 속성 오버라이드 컬럼 (선택)**")
                                _tp1, _tp2, _tp3, _tp4 = st.columns(4)
                                with _tp1: _bb_move_pwr = st.selectbox("power", _all_cols, index=0)
                                with _tp2: _bb_move_typ = st.selectbox("type", _all_cols, index=0)
                                with _tp3: _bb_move_cat = st.selectbox("category", _all_cols, index=0)
                                with _tp4: _bb_move_pri = st.selectbox("priority", _all_cols, index=0)
                                    
                                st.markdown("**행동 순서 (선택)**")
                                _to1, _to2 = st.columns(2)
                                with _to1:
                                    _g_order = _guess_col(["action_order", "order", "sequence", "seq", "action_seq", "turn_order", "timeline_order", "log_index", "행동순서", "순서"])
                                    _bb_move_order = st.selectbox("action order 컬럼", _all_cols, index=_all_cols.index(_g_order) if _g_order in _all_cols else 0)
                                with _to2:
                                    _bb_move_order_dir = st.selectbox("order 방향", ["ascending_first", "descending_first"])
                                    
                                st.markdown("---")
                                _ts_use = st.checkbox("switch trace 사용", value=False)
                                
                                _sc1, _sc2, _sc3 = st.columns(3)
                                with _sc1:
                                    _g_s_turn = _guess_col(["turn", "round", "턴", "라운드"])
                                    _bb_switch_turn_col = st.selectbox("switch turn 컬럼", _all_cols, index=_all_cols.index(_g_s_turn) if _g_s_turn in _all_cols else 0)
                                with _sc2:
                                    _g_s_out = _guess_col(["outgoing", "switch_from", "actor", "unit", "entity", "old_unit", "switch_out_id", "교체자", "이탈"])
                                    _bb_switch_out_col = st.selectbox("switch outgoing ID 컬럼", _all_cols, index=_all_cols.index(_g_s_out) if _g_s_out in _all_cols else 0)
                                with _sc3:
                                    _g_s_in = _guess_col(["incoming", "switch_to", "next_unit", "new_unit", "replacement", "bench_in", "switch_in_id", "교체대상", "진입", "등장"])
                                    _bb_switch_in_col = st.selectbox("switch incoming ID 컬럼", _all_cols, index=_all_cols.index(_g_s_in) if _g_s_in in _all_cols else 0)
                                    
                                _sc4, _sc5 = st.columns(2)
                                with _sc4:
                                    _g_s_action = _guess_col(["action", "event", "type", "kind", "switch", "교체", "스위치", "태그"])
                                    _bb_switch_action_col = st.selectbox("switch action type 컬럼 (선택)", _all_cols, index=_all_cols.index(_g_s_action) if _g_s_action in _all_cols else 0)
                                with _sc5:
                                    _bb_switch_action_vals = st.text_input("switch action 값 목록 (쉼표 구분)", "switch, swap, tag, change, substitute, switch_out, switch_in, 교체, 스위치, 태그, 변경")
                                    
                                st.markdown("---")
                                _tf_use = st.checkbox("faint incoming trace 사용", value=False)
                                
                                _fc1, _fc2 = st.columns(2)
                                with _fc1:
                                    _g_f_turn = _guess_col(["turn", "round", "턴", "라운드"])
                                    _bb_faint_turn_col = st.selectbox("faint turn 컬럼", _all_cols, index=_all_cols.index(_g_f_turn) if _g_f_turn in _all_cols else 0)
                                with _fc2:
                                    _g_f_side = _guess_col(["side", "team", "camp", "faction", "player", "진영", "팀"])
                                    _bb_faint_side_col = st.selectbox("faint side 컬럼 (선택)", _all_cols, index=_all_cols.index(_g_f_side) if _g_f_side in _all_cols else 0)
                                    
                                _fc3, _fc4 = st.columns(2)
                                with _fc3:
                                    _g_f_out = _guess_col(["fainted", "faint", "ko", "dead", "defeated", "outgoing", "old_unit", "unit", "actor", "쓰러짐", "기절", "이탈"])
                                    _bb_faint_out_col = st.selectbox("faint outgoing ID 컬럼", _all_cols, index=_all_cols.index(_g_f_out) if _g_f_out in _all_cols else 0)
                                with _fc4:
                                    _g_f_in = _guess_col(["incoming", "replacement", "replace", "send_out", "next_unit", "new_unit", "bench_in", "진입", "등장", "교체대상"])
                                    _bb_faint_in_col = st.selectbox("faint incoming ID 컬럼", _all_cols, index=_all_cols.index(_g_f_in) if _g_f_in in _all_cols else 0)
                                    
                                _fc5, _fc6 = st.columns(2)
                                with _fc5:
                                    _g_f_action = _guess_col(["action", "event", "type", "kind", "faint", "ko", "replace", "send_out", "기절", "쓰러짐", "등장", "진입"])
                                    _bb_faint_action_col = st.selectbox("faint action type 컬럼 (선택)", _all_cols, index=_all_cols.index(_g_f_action) if _g_f_action in _all_cols else 0)
                                with _fc6:
                                    _bb_faint_action_vals = st.text_input("faint action 값 목록 (쉼표 구분)", "faint_replace, replace, replacement, send_out, enter_after_faint, fainted_switch, faint_incoming, ko_replace, forced_switch, 기절교체, 쓰러짐교체, 강제교체, 등장, 진입")
                                    
                                st.markdown("---")
                                _td_use = st.checkbox("damage trace score 사용", value=False)
                                
                                _td1, _td2, _td3 = st.columns(3)
                                with _td1:
                                    _g_dt = _guess_col(["turn", "round", "턴", "라운드"])
                                    _bb_damage_turn_col = st.selectbox("damage turn 컬럼", _all_cols, index=_all_cols.index(_g_dt) if _g_dt in _all_cols else 0)
                                with _td2:
                                    _g_da = _guess_col(["actor", "attacker", "source", "caster", "user", "unit", "entity", "행동자", "공격자", "시전자"])
                                    _bb_damage_actor_col = st.selectbox("damage actor ID 컬럼", _all_cols, index=_all_cols.index(_g_da) if _g_da in _all_cols else 0)
                                with _td3:
                                    _g_dtg = _guess_col(["target", "defender", "victim", "target_id", "대상", "타겟", "피격자"])
                                    _bb_damage_target_col = st.selectbox("damage target ID 컬럼", _all_cols, index=_all_cols.index(_g_dtg) if _g_dtg in _all_cols else 0)
                                    
                                _td4, _td5 = st.columns(2)
                                with _td4:
                                    _g_dval = _guess_col(["damage", "dmg", "hp_delta", "damage_done", "damage_amount", "피해", "데미지", "딜", "체력감소"])
                                    _bb_damage_value_col = st.selectbox("damage value 컬럼", _all_cols, index=_all_cols.index(_g_dval) if _g_dval in _all_cols else 0)
                                    _bb_damage_value_kind = st.selectbox(
                                        "damage 값 의미",
                                        ["damage", "hp_delta"],
                                        index=0,
                                        help="damage는 엔진 계산 데미지, hp_delta는 실제 HP 감소량과 비교합니다."
                                    )
                                    _bb_damage_tol = st.number_input("damage 허용 오차", min_value=0.0, value=0.0, step=1.0)
                                with _td5:
                                    _g_dact = _guess_col(["action", "event", "type", "kind", "행동", "이벤트", "종류"])
                                    _bb_damage_action_col = st.selectbox("damage action type 컬럼 (선택)", _all_cols, index=_all_cols.index(_g_dact) if _g_dact in _all_cols else 0)
                                    _bb_damage_action_vals = st.text_input("damage action 값 목록 (쉼표 구분)", "damage, hit, apply_damage, dmg, 피해, 데미지, 피격")
                                    
                                _td6, _td7, _td8 = st.columns(3)
                                with _td6:
                                    _g_dmv = _guess_col(["move", "skill", "action_name", "ability_name", "무브", "스킬", "행동명"])
                                    _bb_damage_move_name_col = st.selectbox("damage move name 컬럼 (선택)", _all_cols, index=_all_cols.index(_g_dmv) if _g_dmv in _all_cols else 0)
                                with _td7:
                                    _g_dord = _guess_col(["action_order", "order", "sequence", "seq", "action_seq", "turn_order", "timeline_order", "log_index", "행동순서", "순서"])
                                    _bb_damage_order_col = st.selectbox("damage action order 컬럼 (선택)", _all_cols, index=_all_cols.index(_g_dord) if _g_dord in _all_cols else 0)
                                with _td8:
                                    _bb_damage_order_dir = st.selectbox("damage order 방향", ["ascending_first", "descending_first"])
                                    
                                st.markdown("---")
                                _trd_use = st.checkbox("resource delta trace score 사용", value=False)
                                
                                _trd1, _trd2, _trd3 = st.columns(3)
                                with _trd1:
                                    _g_trd_t = _guess_col(["turn", "round", "턴", "라운드"])
                                    _bb_resource_delta_turn_col = st.selectbox("resource delta turn 컬럼", _all_cols, index=_all_cols.index(_g_trd_t) if _g_trd_t in _all_cols else 0)
                                with _trd2:
                                    _g_trd_a = _guess_col(["actor", "attacker", "source", "caster", "user", "unit", "entity", "행동자", "공격자", "시전자"])
                                    _bb_resource_delta_actor_col = st.selectbox("resource delta actor ID 컬럼", _all_cols, index=_all_cols.index(_g_trd_a) if _g_trd_a in _all_cols else 0)
                                with _trd3:
                                    _g_trd_tg = _guess_col(["target", "defender", "victim", "target_id", "대상", "타겟", "피격자"])
                                    _bb_resource_delta_target_col = st.selectbox("resource delta target ID 컬럼", _all_cols, index=_all_cols.index(_g_trd_tg) if _g_trd_tg in _all_cols else 0)
                                    
                                _bb_resource_delta_cols = {}
                                _resource_config_for_delta = st.session_state.get("resource_config") or {}
                                _resource_names_for_delta = list(_resource_config_for_delta.keys())
                                _bb_resource_delta_names = st.multiselect(
                                    "resource delta 컬럼 추가",
                                    _resource_names_for_delta,
                                    default=[],
                                    help="APPLY_DAMAGE로 감소한 HP/Shield/Armor 등 target resource loss를 비교합니다."
                                )
                                for _rname in _bb_resource_delta_names:
                                    _guess = _guess_col([
                                        f"{_rname}_loss", f"{_rname}_delta", f"{_rname}_damage",
                                        str(_rname).lower(), str(_rname),
                                    ])
                                    _col = st.selectbox(
                                        f"{_rname} loss/delta 컬럼",
                                        _all_cols,
                                        index=_all_cols.index(_guess) if _guess in _all_cols else 0,
                                        key=f"bb_resource_delta_col_{_rname}",
                                    )
                                    if _col != "(없음)":
                                        _bb_resource_delta_cols[str(_rname)] = _col

                                _trd4, _trd5 = st.columns(2)
                                with _trd4:
                                    _g_trd_act = _guess_col(["action", "event", "type", "kind", "행동", "이벤트", "종류"])
                                    _bb_resource_delta_action_col = st.selectbox("resource delta action type 컬럼 (선택)", _all_cols, index=_all_cols.index(_g_trd_act) if _g_trd_act in _all_cols else 0)
                                with _trd5:
                                    _bb_resource_delta_action_vals = st.text_input("resource delta action 값 목록 (쉼표 구분)", "damage, hit, apply_damage, dmg, 피해, 데미지, 피격")

                                _trd6, _trd7, _trd8 = st.columns(3)
                                with _trd6:
                                    _g_trd_ord = _guess_col(["action_order", "order", "sequence", "seq", "action_seq", "turn_order", "timeline_order", "log_index", "행동순서", "순서"])
                                    _bb_resource_delta_order_col = st.selectbox("resource delta order 컬럼 (선택)", _all_cols, index=_all_cols.index(_g_trd_ord) if _g_trd_ord in _all_cols else 0)
                                with _trd7:
                                    _bb_resource_delta_order_dir = st.selectbox("resource delta order 방향", ["ascending_first", "descending_first"])
                                with _trd8:
                                    _bb_resource_delta_tol = st.number_input("resource delta 허용 오차", min_value=0.0, value=0.0, step=1.0)
                                    _bb_resource_delta_strict_extra = st.checkbox(
                                        "관측하지 않은 resource delta도 extra로 벌점",
                                        value=False,
                                        help="꺼두면 매핑한 resource 컬럼만 score 대상으로 삼습니다."
                                    )
                                    
                            if _bb_id_col != "(없음)" and _bb_team_col != "(없음)":
                                _bb_log_schema = {
                                    "battle_id_col": _bb_id_col,
                                    "team_col": _bb_team_col,
                                    "entity_id_col": None if _bb_ent_col == "(없음)" else _bb_ent_col,
                                    "sort_cols": _bb_sort_cols,
                                    "result_mode": _bb_res_mode,
                                    "ally_values": [x.strip() for x in _bb_ally_vals.split(",") if x.strip()],
                                    "enemy_values": [x.strip() for x in _bb_enemy_vals.split(",") if x.strip()]
                                }
                                if _if_use:
                                    if _bb_initial_on_field_col == "(없음)":
                                        st.warning("⚠️ initial active/on-field를 사용하려면 initial on-field 컬럼을 선택해야 합니다.")
                                    else:
                                        _bb_log_schema.update({
                                            "initial_on_field_enabled": True,
                                            "initial_on_field_col": _bb_initial_on_field_col,
                                            "initial_on_field_values": [x.strip() for x in _bb_initial_values.split(",") if x.strip()],
                                            "initial_order_col": None if _bb_initial_order_col == "(없음)" else _bb_initial_order_col,
                                        })
                                        
                                if _st_use:
                                    if _bb_state_turn_col == "(없음)" or _bb_state_id_col == "(없음)":
                                        st.warning("⚠️ state snapshot trace를 사용하려면 state turn, state entity ID 컬럼을 모두 선택해야 합니다.")
                                    elif _bb_state_hp_col == "(없음)" and _bb_state_status_col == "(없음)" and _bb_state_fainted_col == "(없음)" and not _bb_state_resource_cols:
                                        st.warning("⚠️ state snapshot trace를 사용하려면 HP, status, fainted, 또는 resource 컬럼 중 하나 이상을 선택해야 합니다.")
                                    else:
                                        _bb_log_schema.update({
                                            "state_trace_enabled": True,
                                            "state_turn_col": _bb_state_turn_col,
                                            "state_entity_id_col": _bb_state_id_col,
                                            "state_hp_col": None if _bb_state_hp_col == "(없음)" else _bb_state_hp_col,
                                            "state_status_col": None if _bb_state_status_col == "(없음)" else _bb_state_status_col,
                                            "state_fainted_col": None if _bb_state_fainted_col == "(없음)" else _bb_state_fainted_col,
                                            "state_hp_mode": _bb_state_hp_mode,
                                            "state_hp_tolerance": float(_bb_state_hp_tol),
                                            "state_score_deterministic": bool(_bb_state_deterministic),
                                            "state_resource_cols": dict(_bb_state_resource_cols),
                                            "state_resource_mode": _bb_state_resource_mode,
                                            "state_resource_tolerance": float(_bb_state_resource_tol),
                                        })
                                        
                                if _tc_use:
                                    if _bb_ent_col == "(없음)":
                                        st.warning("⚠️ move trace를 사용하려면 참가자 ID 컬럼이 필요합니다.")
                                    elif _bb_turn_col == "(없음)" or _bb_actor_col == "(없음)" or _bb_target_col == "(없음)" or _bb_move_name_col == "(없음)":
                                        st.warning("⚠️ move trace를 사용하려면 turn, actor ID, target ID, move name 컬럼을 모두 선택해야 합니다.")
                                    else:
                                        _bb_log_schema.update({
                                            "trace_moves_enabled": True,
                                            "turn_col": _bb_turn_col,
                                            "actor_id_col": _bb_actor_col,
                                            "target_id_col": _bb_target_col,
                                            "move_name_col": _bb_move_name_col,
                                            "action_col": None if _bb_action_col == "(없음)" else _bb_action_col,
                                            "move_action_values": [x.strip() for x in _bb_action_vals.split(",") if x.strip()],
                                            "move_order_col": None if _bb_move_order == "(없음)" else _bb_move_order,
                                            "move_order_direction": _bb_move_order_dir,
                                            "move_power_col": None if _bb_move_pwr == "(없음)" else _bb_move_pwr,
                                            "move_type_col": None if _bb_move_typ == "(없음)" else _bb_move_typ,
                                            "move_category_col": None if _bb_move_cat == "(없음)" else _bb_move_cat,
                                            "move_priority_col": None if _bb_move_pri == "(없음)" else _bb_move_pri,
                                        })
                                        
                                if _ts_use:
                                    if _bb_ent_col == "(없음)":
                                        st.warning("⚠️ switch trace를 사용하려면 참가자 ID 컬럼이 필요합니다.")
                                    elif _bb_switch_turn_col == "(없음)" or _bb_switch_out_col == "(없음)" or _bb_switch_in_col == "(없음)":
                                        st.warning("⚠️ switch trace를 사용하려면 switch turn, outgoing ID, incoming ID 컬럼을 모두 선택해야 합니다.")
                                    else:
                                        _bb_log_schema.update({
                                            "trace_switches_enabled": True,
                                            "switch_turn_col": _bb_switch_turn_col,
                                            "switch_outgoing_id_col": _bb_switch_out_col,
                                            "switch_incoming_id_col": _bb_switch_in_col,
                                            "switch_action_col": None if _bb_switch_action_col == "(없음)" else _bb_switch_action_col,
                                            "switch_action_values": [x.strip() for x in _bb_switch_action_vals.split(",") if x.strip()],
                                        })
                                        
                                if _tf_use:
                                    if _bb_ent_col == "(없음)":
                                        st.warning("⚠️ faint incoming trace를 사용하려면 참가자 ID 컬럼이 필요합니다.")
                                    elif _bb_faint_turn_col == "(없음)" or _bb_faint_out_col == "(없음)" or _bb_faint_in_col == "(없음)":
                                        st.warning("⚠️ faint incoming trace를 사용하려면 faint turn, outgoing ID, incoming ID 컬럼을 모두 선택해야 합니다.")
                                    else:
                                        _bb_log_schema.update({
                                            "trace_faint_incoming_enabled": True,
                                            "faint_turn_col": _bb_faint_turn_col,
                                            "faint_side_col": None if _bb_faint_side_col == "(없음)" else _bb_faint_side_col,
                                            "faint_outgoing_id_col": _bb_faint_out_col,
                                            "faint_incoming_id_col": _bb_faint_in_col,
                                            "faint_action_col": None if _bb_faint_action_col == "(없음)" else _bb_faint_action_col,
                                            "faint_action_values": [x.strip() for x in _bb_faint_action_vals.split(",") if x.strip()],
                                        })
                                        
                                if _td_use:
                                    if _bb_ent_col == "(없음)":
                                        st.warning("⚠️ damage trace를 사용하려면 참가자 ID 컬럼이 필요합니다.")
                                    elif _bb_damage_turn_col == "(없음)" or _bb_damage_actor_col == "(없음)" or _bb_damage_target_col == "(없음)" or _bb_damage_value_col == "(없음)":
                                        st.warning("⚠️ damage trace를 사용하려면 damage turn, actor ID, target ID, damage value 컬럼을 모두 선택해야 합니다.")
                                    else:
                                        _bb_log_schema.update({
                                            "damage_trace_enabled": True,
                                            "damage_turn_col": _bb_damage_turn_col,
                                            "damage_actor_id_col": _bb_damage_actor_col,
                                            "damage_target_id_col": _bb_damage_target_col,
                                            "damage_value_col": _bb_damage_value_col,
                                            "damage_action_col": None if _bb_damage_action_col == "(없음)" else _bb_damage_action_col,
                                            "damage_action_values": [x.strip() for x in _bb_damage_action_vals.split(",") if x.strip()],
                                            "damage_order_col": None if _bb_damage_order_col == "(없음)" else _bb_damage_order_col,
                                            "damage_order_direction": _bb_damage_order_dir,
                                            "damage_move_name_col": None if _bb_damage_move_name_col == "(없음)" else _bb_damage_move_name_col,
                                            "damage_tolerance": float(_bb_damage_tol),
                                            "damage_value_kind": _bb_damage_value_kind,
                                        })
                                        
                                if _trd_use:
                                    if _bb_ent_col == "(없음)":
                                        st.warning("⚠️ resource delta trace를 사용하려면 참가자 ID 컬럼이 필요합니다.")
                                    elif _bb_resource_delta_turn_col == "(없음)" or _bb_resource_delta_actor_col == "(없음)" or _bb_resource_delta_target_col == "(없음)":
                                        st.warning("⚠️ resource delta trace를 사용하려면 turn, actor ID, target ID 컬럼을 모두 선택해야 합니다.")
                                    elif not _bb_resource_delta_cols:
                                        st.warning("⚠️ resource delta trace를 사용하려면 매핑된 resource loss/delta 컬럼이 1개 이상 필요합니다.")
                                    else:
                                        _bb_log_schema.update({
                                            "resource_delta_trace_enabled": True,
                                            "resource_delta_turn_col": _bb_resource_delta_turn_col,
                                            "resource_delta_actor_id_col": _bb_resource_delta_actor_col,
                                            "resource_delta_target_id_col": _bb_resource_delta_target_col,
                                            "resource_delta_cols": dict(_bb_resource_delta_cols),
                                            "resource_delta_action_col": None if _bb_resource_delta_action_col == "(없음)" else _bb_resource_delta_action_col,
                                            "resource_delta_action_values": [x.strip() for x in _bb_resource_delta_action_vals.split(",") if x.strip()],
                                            "resource_delta_order_col": None if _bb_resource_delta_order_col == "(없음)" else _bb_resource_delta_order_col,
                                            "resource_delta_order_direction": _bb_resource_delta_order_dir,
                                            "resource_delta_tolerance": float(_bb_resource_delta_tol),
                                            "resource_delta_strict_extra": bool(_bb_resource_delta_strict_extra),
                                        })
                            else:
                                st.warning("전투 ID 컬럼과 팀/진영 컬럼을 모두 선택해야 DB 역할 컬럼 방식으로 실행할 수 있습니다.")

                        if _bb_method == "DB 역할 컬럼으로 묶기" and _bb_log_schema:
                            try:
                                _export_payload = _build_db_corpus_schema_payload(
                                    sys_stats, sys_gimmicks, _bb_health, _bb_target, int(_bb_size), _bb_log_schema, st.session_state
                                )
                                _export_json_str = json.dumps(_export_payload, ensure_ascii=False, indent=2)
                                st.download_button(
                                    label="DB 코퍼스 schema JSON 다운로드",
                                    data=_export_json_str,
                                    file_name="db_corpus_schema.json",
                                    mime="application/json",
                                    use_container_width=True
                                )
                                st.session_state["bb_last_corpus_schema"] = _export_payload
                                st.session_state["bb_last_log_schema"] = _bb_log_schema
                            except Exception as e:
                                st.error(f"schema JSON 생성 중 오류: {str(e)}")

                        if st.button("🔬 백테스트 실행", use_container_width=True, key="run_backtest", disabled=(_bb_method == "DB 역할 컬럼으로 묶기" and not _bb_log_schema)):
                            from modules.per_battle_backtest import build_battles, score_predictions
                            from modules.engine import _worker_simulate_match
                            import copy
                            
                            _bb_gc = copy.deepcopy(st.session_state.get("game_config") or {})
                            if _bb_log_schema and _bb_log_schema.get("entity_id_col"):
                                _bb_gc["preserve_ids"] = True

                            _battles = build_battles(
                                _bb_df, int(_bb_size), _bb_target,
                                sys_stats, sys_gimmicks, _bb_health,
                                move_library=st.session_state.get("move_library"),
                                resource_config=st.session_state.get("resource_config"),
                                max_battles=int(_bb_max),
                                game_config=_bb_gc,
                                log_schema=_bb_log_schema,
                            )

                            if not _battles:
                                st.warning("⚠️ 전투를 구성할 수 없습니다 — 행 수 또는 전투당 행 수 설정을 확인하세요.")
                            else:
                                _bb_cf = st.session_state.get("combat_flow", DEFAULT_COMBAT_FLOW)
                                _bb_spd = st.session_state.get("speed_stat")
                                _bb_gf = st.session_state.get("global_damage_formula", "0")
                                _bb_mt = int(st.session_state.get("sim_max_turns", 100))
                                _bb_rm = ResourceModule(
                                    st.session_state.get("resource_config") or None,
                                    damage_type_map=st.session_state.get("damage_type_map") or None,
                                )

                                _bb_tasks = []
                                _bb_actuals = []
                                _bb_stochasticity_factory = _select_backtest_stochasticity_factory(_bb_log_schema)
                                for _bb_i, _battle in enumerate(_battles):
                                    if len(_battle) == 4:
                                        _a_team, _e_team, _ally_wins, _battle_gc = _battle
                                    else:
                                        _a_team, _e_team, _ally_wins = _battle
                                        _battle_gc = None

                                    _task_gc = copy.deepcopy(_bb_gc)
                                    if _battle_gc:
                                        _task_gc.update(_battle_gc)

                                    _bb_tasks.append((
                                        _a_team, _e_team, _bb_cf, _bb_spd, sys_stats, _bb_gf,
                                        _bb_mt, _bb_stochasticity_factory, _bb_rm,
                                        None, None, None, None, _task_gc, _bb_i,
                                    ))
                                    _bb_actuals.append(_ally_wins)

                                _bb_total = len(_bb_tasks)
                                _bb_prog = st.progress(0.0)
                                _bb_status = st.empty()
                                _bb_t0 = time.time()
                                _bb_predictions = []
                                _bb_state_scores = []
                                _bb_action_damage_scores = []
                                _bb_action_resource_delta_scores = []
                                _bb_errors = 0
                                _bb_workers = os.cpu_count() or 4
                                _bb_mismatch_rows = []

                                with st.spinner(f"백테스트 실행 중... ({_bb_total}전투, 멀티코어 병렬)"):
                                    with concurrent.futures.ProcessPoolExecutor(
                                            max_workers=_bb_workers) as _bb_pool:
                                        _bb_step = max(1, _bb_total // 50)
                                        for _bb_r in _bb_pool.map(
                                                _worker_simulate_match, _bb_tasks, chunksize=4):
                                            _bb_idx = len(_bb_predictions) + 1
                                            if isinstance(_bb_r, str):
                                                _bb_errors += 1
                                                _bb_predictions.append(False)
                                                _bb_mismatch_rows.append({
                                                    "battle_index": _bb_idx,
                                                    "score_type": "engine_error",
                                                    "actual_full": repr(_bb_r)
                                                })
                                            else:
                                                _bb_predictions.append(_bb_r[0] == 1)
                                                _metrics = _bb_r[1] if len(_bb_r) > 1 else {}
                                                if isinstance(_metrics, dict):
                                                    if _metrics.get("state_score"):
                                                        _bb_state_scores.append(_metrics["state_score"])
                                                    if _metrics.get("action_damage_score"):
                                                        _bb_action_damage_scores.append(_metrics["action_damage_score"])
                                                    if _metrics.get("action_resource_delta_score"):
                                                        _bb_action_resource_delta_scores.append(_metrics["action_resource_delta_score"])
                                                    _extend_mismatch_rows_from_metrics(_bb_mismatch_rows, _bb_idx, _metrics)
                                            _bb_done = len(_bb_predictions)
                                            if _bb_done % _bb_step == 0 or _bb_done == _bb_total:
                                                _bb_prog.progress(min(1.0, _bb_done / float(_bb_total)))
                                                _bb_status.text(
                                                    f"백테스트: {_bb_done}/{_bb_total} · "
                                                    f"경과 {time.time() - _bb_t0:.0f}초"
                                                )

                                _bb_prog.progress(1.0)
                                _bb_sc = score_predictions(_bb_predictions, _bb_actuals)
                                _bb_elapsed = time.time() - _bb_t0
                                _bb_acc_pct = _bb_sc["accuracy"] * 100.0

                                if _bb_acc_pct >= 90:
                                    _bb_grade = "🟢 우수 (완벽 메커니즘 권역)"
                                elif _bb_acc_pct >= 70:
                                    _bb_grade = "🟡 양호 (typeless 천장 권역)"
                                elif _bb_acc_pct >= 50:
                                    _bb_grade = "🟠 미흡 (동전 던지기 이상이지만 보정 필요)"
                                else:
                                    _bb_grade = "🔴 매핑·공식 점검 필요 (동전 던지기 이하)"

                                st.success(
                                    f"🎯 백테스트 완료! **전체 일치율 {_bb_acc_pct:.1f}%** — {_bb_grade} "
                                    f"({_bb_sc['correct']}/{_bb_sc['total']} 전투 · {_bb_elapsed:.0f}초)"
                                )

                                _bbm1, _bbm2, _bbm3 = st.columns(3)
                                with _bbm1:
                                    st.metric("전체 일치율", f"{_bb_acc_pct:.1f}%",
                                              f"{_bb_sc['correct']}/{_bb_sc['total']}")
                                with _bbm2:
                                    _bb_ar = _bb_sc["ally_wins_recall"] * 100.0
                                    st.metric("Ally 승 정확도",
                                              f"{_bb_ar:.1f}%",
                                              f"실제 Ally 승 {_bb_sc['ally_wins_actual']}건 중 적중")
                                with _bbm3:
                                    _bb_nr = _bb_sc["not_ally_recall"] * 100.0
                                    st.metric("Enemy/무승부 정확도",
                                              f"{_bb_nr:.1f}%",
                                              f"실제 비-Ally 승 {_bb_sc['not_ally_actual']}건 중 적중")

                                if _bb_errors:
                                    st.warning(f"⚠️ {_bb_errors}전투가 엔진 에러로 제외됐습니다 "
                                               f"(결과는 그 외 전투 기준).")

                                st.caption(
                                    "**해석 가이드** — 100%는 결정론적 완벽 시뮬, 95.8%는 Pokemon 기준 "
                                    "이론적 천장(난수 4.2%), 71.6%는 무브/타입 도입 전 Pokemon best-effort, "
                                    "50%는 동전 던지기. 50%대면 매핑/공식부터 점검하세요."
                                )
                                
                                if _bb_log_schema and _bb_log_schema.get("state_trace_enabled"):
                                    if _bb_log_schema.get("state_score_deterministic", True):
                                        st.caption("state score는 결정론 모드(NoVariance)로 계산되었습니다.")
                                    else:
                                        st.caption("state score는 현재 stochasticity 설정을 포함해 계산되었습니다.")
                                        
                                if _bb_state_scores:
                                    _s_checks = sum(int(s.get("checks", 0) or 0) for s in _bb_state_scores)
                                    _s_mismatch = sum(int(s.get("mismatches", 0) or 0) for s in _bb_state_scores)
                                    _s_acc = (1.0 - (_s_mismatch / _s_checks)) * 100.0 if _s_checks > 0 else 0.0
                                    
                                    _s_hp_miss = sum(int(s.get("hp_mismatches", 0) or 0) for s in _bb_state_scores)
                                    _s_st_miss = sum(int(s.get("status_mismatches", 0) or 0) for s in _bb_state_scores)
                                    _s_ft_miss = sum(int(s.get("faint_mismatches", 0) or 0) for s in _bb_state_scores)
                                    _s_res_miss = sum(int(s.get("resource_mismatches", 0) or 0) for s in _bb_state_scores)
                                    _s_missing = sum(int(s.get("missing", 0) or 0) for s in _bb_state_scores)
                                    
                                    st.divider()
                                    st.markdown("### 📊 관측 상태 스냅샷 일치율")
                                    _sc1, _sc2, _sc3, _sc4 = st.columns(4)
                                    with _sc1:
                                        st.metric("상태 일치율", f"{_s_acc:.1f}%", f"{_s_checks - _s_mismatch}/{_s_checks} 검사")
                                    with _sc2:
                                        st.metric("HP 불일치", f"{_s_hp_miss}건", delta_color="off")
                                    with _sc3:
                                        st.metric("상태/기절 불일치", f"{_s_st_miss + _s_ft_miss}건", delta_color="off")
                                    with _sc4:
                                        st.metric("자원 불일치", f"{_s_res_miss}건", delta_color="off")
                                        
                                    _s_first = next((s.get("first_mismatch") for s in _bb_state_scores if s.get("first_mismatch")), None)
                                    if _s_first:
                                        st.caption(f"**첫 번째 불일치 샘플:** Turn {_s_first.get('turn')} - {_s_first.get('id')} ({_s_first.get('kind')}) expected: {_s_first.get('expected')}, actual: {_s_first.get('actual')}")
                                    if _s_missing > 0:
                                        st.caption(f"⚠️ 엔진에서 찾을 수 없는 참가자 상태 누락: {_s_missing}건")

                                if _bb_action_damage_scores:
                                    _d_checks = sum(int(s.get("checks", 0) or 0) for s in _bb_action_damage_scores)
                                    _d_mismatch = sum(int(s.get("mismatches", 0) or 0) for s in _bb_action_damage_scores)
                                    _d_acc = (1.0 - (_d_mismatch / _d_checks)) * 100.0 if _d_checks > 0 else 0.0
                                    
                                    _d_id_miss = sum(int(s.get("identity_mismatches", 0) or 0) for s in _bb_action_damage_scores)
                                    _d_dmg_miss = sum(int(s.get("damage_mismatches", 0) or 0) for s in _bb_action_damage_scores)
                                    _d_missing = sum(int(s.get("missing", 0) or 0) for s in _bb_action_damage_scores)
                                    _d_extra = sum(int(s.get("extra", 0) or 0) for s in _bb_action_damage_scores)
                                    
                                    st.divider()
                                    st.markdown("### 💥 관측 데미지 일치율")
                                    _dc1, _dc2, _dc3, _dc4 = st.columns(4)
                                    with _dc1:
                                        st.metric("행동 데미지 일치율", f"{_d_acc:.1f}%", f"{_d_checks - _d_mismatch}/{_d_checks} 검사")
                                    with _dc2:
                                        st.metric("damage 불일치", f"{_d_dmg_miss}건", delta_color="off")
                                    with _dc3:
                                        st.metric("actor/target 불일치", f"{_d_id_miss}건", delta_color="off")
                                    with _dc4:
                                        st.metric("누락/추가 이벤트", f"{_d_missing}/{_d_extra}건", delta_color="off")
                                        
                                    _d_first = next((s.get("first_mismatch") for s in _bb_action_damage_scores if s.get("first_mismatch")), None)
                                    if _d_first:
                                        st.caption(f"**첫 번째 불일치 샘플:** Turn {_d_first.get('turn')} - {_d_first.get('id')} ({_d_first.get('kind')}) expected: {_d_first.get('expected')}, actual: {_d_first.get('actual')}")

                                if _bb_action_resource_delta_scores:
                                    _rd_checks = sum(int(s.get("checks", 0) or 0) for s in _bb_action_resource_delta_scores)
                                    _rd_mismatch = sum(int(s.get("mismatches", 0) or 0) for s in _bb_action_resource_delta_scores)
                                    _rd_acc = (1.0 - (_rd_mismatch / _rd_checks)) * 100.0 if _rd_checks > 0 else 0.0
                                    
                                    _rd_id_miss = sum(int(s.get("identity_mismatches", 0) or 0) for s in _bb_action_resource_delta_scores)
                                    _rd_delta_miss = sum(int(s.get("delta_mismatches", 0) or 0) for s in _bb_action_resource_delta_scores)
                                    _rd_missing = sum(int(s.get("missing", 0) or 0) for s in _bb_action_resource_delta_scores)
                                    _rd_extra = sum(int(s.get("extra", 0) or 0) for s in _bb_action_resource_delta_scores)
                                    
                                    st.divider()
                                    st.markdown("### 💠 자원 delta 일치율")
                                    _rdc1, _rdc2, _rdc3, _rdc4 = st.columns(4)
                                    with _rdc1:
                                        st.metric("자원 delta 일치율", f"{_rd_acc:.1f}%", f"{_rd_checks - _rd_mismatch}/{_rd_checks} 검사")
                                    with _rdc2:
                                        st.metric("delta 불일치", f"{_rd_delta_miss}건", delta_color="off")
                                    with _rdc3:
                                        st.metric("identity 불일치", f"{_rd_id_miss}건", delta_color="off")
                                    with _rdc4:
                                        st.metric("누락/추가 이벤트", f"{_rd_missing}/{_rd_extra}건", delta_color="off")
                                        
                                    _rd_first = next((s.get("first_mismatch") for s in _bb_action_resource_delta_scores if s.get("first_mismatch")), None)
                                    if _rd_first:
                                        st.caption(f"**첫 번째 불일치 샘플:** Turn {_rd_first.get('turn')} - {_rd_first.get('id')} ({_rd_first.get('kind')}) expected: {_rd_first.get('expected')}, actual: {_rd_first.get('actual')}")

                                st.session_state["bb_last_backtest_has_run"] = True
                                st.session_state["bb_last_mismatch_rows"] = list(_bb_mismatch_rows)
                                st.session_state["bb_last_backtest_summary"] = {
                                    "total": _bb_sc["total"],
                                    "correct": _bb_sc["correct"],
                                    "accuracy_pct": _bb_acc_pct,
                                    "elapsed": _bb_elapsed,
                                    "errors": _bb_errors,
                                }

                        if st.session_state.get("bb_last_backtest_has_run"):
                            _cached_rows = st.session_state.get("bb_last_mismatch_rows", [])
                            st.divider()
                            st.markdown("### 📋 Mismatch Report")
                            if _cached_rows:
                                _df_miss = pd.DataFrame(_cached_rows)
                                st.dataframe(_df_miss, use_container_width=True)
                                st.download_button(
                                    label="📥 Mismatch Report CSV 다운로드",
                                    data=_df_miss.to_csv(index=False).encode("utf-8-sig"),
                                    file_name="mismatch_report.csv",
                                    mime="text/csv",
                                )
                            else:
                                st.success("🎉 최근 score mismatch가 없습니다!")

                            with st.expander("메커니즘 RE / EFFECTS 후보 생성", expanded=bool(_cached_rows)):
                                try:
                                    from modules.step_mechanism_re import render_mechanism_re
                                    render_mechanism_re()
                                except Exception as e:
                                    st.warning(f"Mechanism RE surface 로드 실패: {e}")

    with tab2:
        st.markdown("## 🛠️ Global Character Builder")
        st.markdown("### 👑 Data-Driven Target Optimizer (타겟팅 스탯 자동 분배)")
        
        col_t1, col_t2 = st.columns(2)
        with col_t1: target_win_rate = st.slider("🎯 희망 승률 (%)", min_value=0.0, max_value=100.0, value=50.0, step=0.1)
        with col_t2: target_team = st.radio("🤝 합류할 진영 선택", ["Ally", "Enemy"], horizontal=True)
        
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1: opt_budget = st.number_input("💰 목표 총합 체급 예산", min_value=10.0, max_value=50000.0, value=1500.0, step=50.0)
        with col_opt2: std_n = st.slider("📏 탐색 범위 (Standard Deviation Multiplier)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
        
        if st.button("🚀 데이터 기반 스탯 최적화 실행 (Optimize)", use_container_width=True):
            # ── Phase 9 — 엔진-인-더-루프 vs 레거시 SLSQP 디스패치 ──
            _use_engine_opt = bool(
                st.session_state.get('game_config') or st.session_state.get('move_library')
            )
            if not sys_stats:
                st.warning("⚠️ 시스템 스탯 스키마가 로드되지 않았습니다.")
            elif _use_engine_opt:
                # ═══ Phase 9 — 실제 전투 엔진 MC 승률 목적함수 최적화 (멀티코어 병렬) ═══
                from modules.engine import _worker_simulate_match

                _OPT_ITERATIONS = 8
                _OPT_POPULATION = 8
                _OPT_ELITE = 3
                _OPT_INNER_MC = 50
                _OPT_FINAL_MC = 1000

                stat_weights = st.session_state.get('stat_weights', {})
                opt_weights = [float(stat_weights.get(s, 1.0)) for s in sys_stats]

                # x0 / bounds — 원본 로그 평균을 예산으로 스케일 (SLSQP 경로와 동일 로직)
                try:
                    _means = df[sys_stats].mean().fillna(0).values.astype(float)
                    _stds = df[sys_stats].std().fillna(1).values.astype(float)
                except Exception:
                    _uniform = float(opt_budget) / max(len(sys_stats), 1)
                    _means = np.array([_uniform] * len(sys_stats), dtype=float)
                    _stds = np.array([1.0] * len(sys_stats), dtype=float)
                _wsum = sum(_means[i] * opt_weights[i] for i in range(len(_means)))
                if _wsum <= 0:
                    _wsum = 1.0
                _scale = float(opt_budget) / _wsum
                _scaled_means = [float(m * _scale) for m in _means]
                _scaled_stds = [float(s * _scale) for s in _stds]
                opt_bounds = [
                    (max(0.0, m - s * std_n),
                     max(max(0.0, m - s * std_n) + 0.1, m + s * std_n))
                    for m, s in zip(_scaled_means, _scaled_stds)
                ]

                # 엔진 환경 — session_state에서 자체 추출 (베이스라인 전투: 공간/덱 미사용)
                _cf = st.session_state.get('combat_flow', DEFAULT_COMBAT_FLOW)
                _spd = st.session_state.get('speed_stat')
                _gf = st.session_state.get('global_damage_formula', '0')
                _gc = st.session_state.get('game_config')
                _max_turns = int(st.session_state.get('sim_max_turns', 100))
                _OPT_MAX_TURNS = min(_max_turns, 60)   # 탐색용 내부 전투 턴 상한
                _res_mod = ResourceModule(
                    st.session_state.get('resource_config') or None,
                    damage_type_map=st.session_state.get('damage_type_map') or None
                )
                _move_lib = st.session_state.get('move_library')
                _resource_config = st.session_state.get('resource_config') or {
                    "HP": {"role": "vital",
                           "stat": st.session_state.get('health_stat'), "regen": 0.0}
                }
                cur_gimmicks = {
                    g: st.session_state.get(f'builder_gimmick_{g}', "None")
                    for g in sys_gimmicks
                }

                def _opt_coerce(v):
                    try:
                        v = float(v)
                    except (TypeError, ValueError):
                        return 0.0
                    return v if v == v else 0.0

                def _opt_build_inst(name, stat_dict, gimmick_dict):
                    inst = {"name": str(name), "gimmicks": dict(gimmick_dict)}
                    promote_effect_keys(inst, _gc)
                    for s in sys_stats:
                        inst[s] = _opt_coerce(stat_dict.get(s, 0.0))
                    inst['resources'] = {}
                    for rname, rspec in _resource_config.items():
                        rstat = rspec.get('stat')
                        rval = float(inst[rstat]) if (rstat and rstat in inst) else 1.0
                        inst['resources'][rname] = {"current": rval, "max": rval}
                    if _move_lib:
                        inst['movepool'] = _move_lib
                    return inst

                def _opt_team_from_df(team_df):
                    insts = []
                    if team_df is None:
                        return insts
                    for _, row in team_df.iterrows():
                        h = row.get("Hero")
                        if h and h != "비어 있음" and not pd.isna(h):
                            sd = {s: row.get(s, 0.0) for s in sys_stats}
                            gd = {g: row.get(g, "None") for g in sys_gimmicks}
                            insts.append(_opt_build_inst(h, sd, gd))
                    return insts

                _ally_df = st.session_state.get('ally_df')
                _enemy_df = st.session_state.get('enemy_df')
                if target_team == "Ally":
                    _mate_team = _opt_team_from_df(
                        _ally_df.iloc[1:] if _ally_df is not None else None)
                    _opp_team = _opt_team_from_df(_enemy_df)
                else:
                    _mate_team = _opt_team_from_df(
                        _enemy_df.iloc[1:] if _enemy_df is not None else None)
                    _opp_team = _opt_team_from_df(_ally_df)

                if not _opp_team:
                    st.warning("⚠️ 상대 진영에 캐릭터가 없습니다. "
                               "조작부(GM Mode: Team Setup)에서 상대 팀을 먼저 편성해주세요.")
                else:
                    _total_evals = 1 + _OPT_ITERATIONS * _OPT_POPULATION
                    _eval_count = [0]
                    _opt_err = {"n": 0, "msg": ""}
                    _prog_bar = st.progress(0.0)
                    _prog_txt = st.empty()
                    _t_start = time.time()
                    _max_workers = os.cpu_count() or 4

                    with st.spinner("실제 전투 엔진 인-더-루프 최적화 연산 중... (멀티코어 병렬)"):
                        with concurrent.futures.ProcessPoolExecutor(
                                max_workers=_max_workers) as _pool:

                            def _reduced_win_rate(ally_team, enemy_team, n_sims, max_turns):
                                _tasks = [
                                    (ally_team, enemy_team, _cf, _spd, sys_stats, _gf,
                                     max_turns, default_stochasticity_factory, _res_mod,
                                     None, None, None, None, _gc, _j)
                                    for _j in range(n_sims)
                                ]
                                wins = 0
                                done = 0
                                for _r in _pool.map(_worker_simulate_match, _tasks,
                                                    chunksize=4):
                                    if isinstance(_r, str):
                                        _opt_err["n"] += 1
                                        if not _opt_err["msg"]:
                                            _opt_err["msg"] = _r
                                    else:
                                        wins += _r[0]
                                    done += 1
                                return (wins / float(done) * 100.0) if done else 0.0

                            def objective(x):
                                cand_stats = {s: x[i] for i, s in enumerate(sys_stats)}
                                cand = _opt_build_inst("OPT_CANDIDATE", cand_stats,
                                                       cur_gimmicks)
                                full_team = [cand] + _mate_team
                                if target_team == "Ally":
                                    ally_wr = _reduced_win_rate(
                                        full_team, _opp_team, _OPT_INNER_MC, _OPT_MAX_TURNS)
                                    wr_interest = ally_wr
                                else:
                                    ally_wr = _reduced_win_rate(
                                        _opp_team, full_team, _OPT_INNER_MC, _OPT_MAX_TURNS)
                                    wr_interest = 100.0 - ally_wr
                                _eval_count[0] += 1
                                _prog_bar.progress(
                                    min(1.0, _eval_count[0] / float(_total_evals)))
                                _prog_txt.text(
                                    f"엔진 최적화: 평가 {_eval_count[0]}/{_total_evals} "
                                    f"· 경과 {time.time() - _t_start:.0f}초"
                                )
                                return -abs(wr_interest - target_win_rate)

                            opt_res = optimize_allocation(
                                objective, _scaled_means, float(opt_budget),
                                weights=opt_weights, bounds=opt_bounds,
                                iterations=_OPT_ITERATIONS, population=_OPT_POPULATION,
                                elite=_OPT_ELITE, seed=0
                            )
                            best_x = list(opt_res["best_x"])

                            # 최종 검증 — best_x를 풀 턴·풀 횟수로 1회 재평가
                            _final_cand = _opt_build_inst(
                                "OPT_CANDIDATE",
                                {s: best_x[i] for i, s in enumerate(sys_stats)},
                                cur_gimmicks
                            )
                            _final_team = [_final_cand] + _mate_team
                            if target_team == "Ally":
                                _fa, _fe = _final_team, _opp_team
                            else:
                                _fa, _fe = _opp_team, _final_team
                            _final_ally_wr = _reduced_win_rate(
                                _fa, _fe, _OPT_FINAL_MC, _max_turns)

                    _prog_bar.progress(1.0)
                    if _opt_err["n"]:
                        st.warning(f"⚠️ 시뮬레이션 {_opt_err['n']}건이 엔진 에러로 "
                                   f"제외됐습니다 (결과 신뢰도 저하 가능).")
                        with st.expander("엔진 에러 메시지 (첫 건)"):
                            st.code(_opt_err["msg"], language="python")
                    _final_interest = (_final_ally_wr if target_team == "Ally"
                                       else 100.0 - _final_ally_wr)
                    st.success(
                        f"✅ 엔진 최적화 완료! 목표 승률 {target_win_rate}% 대비 "
                        f"검증 승률 {_final_interest:.2f}% "
                        f"(오차 {abs(_final_interest - target_win_rate):.2f}%p · "
                        f"{opt_res['evals']} evals · 검증 MC {_OPT_FINAL_MC}회 · "
                        f"총 {time.time() - _t_start:.0f}초)"
                    )
                    for i, stat in enumerate(sys_stats):
                        st.session_state[f'builder_stat_input_{stat}'] = float(best_x[i])
            elif not st.session_state.get('has_ml_data'):
                st.warning("⚠️ 데이터가 부족하거나 시스템 스탯 스키마가 로드되지 않았습니다.")
            else:
                with st.spinner("Scipy SLSQP 최적화 연산 중..."):
                    coefs = st.session_state['ml_coefs']
                    intercept = st.session_state['ml_intercept']
                    means = df[sys_stats].mean().fillna(0).values
                    stds = df[sys_stats].std().fillna(1).values
                    stat_weights = st.session_state.get('stat_weights', {})
                    weighted_sum_means = sum(means[i] * stat_weights.get(sys_stats[i], 1.0) for i in range(len(means)))
                    if weighted_sum_means <= 0: weighted_sum_means = 1.0
                    scale_ratio = opt_budget / weighted_sum_means
                    scaled_means, scaled_stds = means * scale_ratio, stds * scale_ratio
                    bounds = [(max(0, m - s * std_n), max(max(0, m - s * std_n) + 0.1, m + s * std_n)) for m, s in zip(scaled_means, scaled_stds)]
                    
                    enemy_const_score = sum(calc_instance_score({"gimmicks": {g: row.get(g, "None") for g in sys_gimmicks}, **{s: float(row.get(s, 0.0)) for s in sys_stats}}, coefs) for idx, row in st.session_state.get('enemy_df', pd.DataFrame()).iterrows() if (target_team != "Enemy" or idx > 0) and row["Hero"] not in ["비어 있음", None] and not pd.isna(row["Hero"]))
                    ally_const_score = sum(calc_instance_score({"gimmicks": {g: row.get(g, "None") for g in sys_gimmicks}, **{s: float(row.get(s, 0.0)) for s in sys_stats}}, coefs) for idx, row in st.session_state.get('ally_df', pd.DataFrame()).iterrows() if (target_team != "Ally" or idx > 0) and row["Hero"] not in ["비어 있음", None] and not pd.isna(row["Hero"]))
                    cur_gimmicks = {g: st.session_state.get(f'builder_gimmick_{g}', "None") for g in sys_gimmicks}
                    cat_score = calc_instance_score({"gimmicks": cur_gimmicks}, coefs)

                    def objective(x):
                        stat_score = sum(stat_val * coefs.get(stat_name, 0.0) for stat_name, stat_val in zip(sys_stats, x))
                        diff = (ally_const_score + cat_score + stat_score - enemy_const_score) if target_team == "Ally" else (ally_const_score - enemy_const_score - cat_score - stat_score)
                        diff += intercept
                        try: prob = 1.0 / (1.0 + math.exp(-diff))
                        except OverflowError: prob = 1.0 if diff > 0 else 0.0
                        return abs(prob * 100.0 - target_win_rate)

                    constraints = ({'type': 'eq', 'fun': lambda x: sum(x[i] * stat_weights.get(sys_stats[i], 1.0) for i in range(len(x))) - opt_budget})
                    result = minimize(objective, scaled_means.copy(), method='SLSQP', bounds=bounds, constraints=constraints)
                    
                    if result.success:
                        best_stat_score = sum(stat_val * coefs.get(stat_name, 0.0) for stat_name, stat_val in zip(sys_stats, result.x))
                        best_diff = (ally_const_score + cat_score + best_stat_score - enemy_const_score) if target_team == "Ally" else (ally_const_score - enemy_const_score - cat_score - best_stat_score)
                        best_diff += intercept
                        try: best_prob = 1.0 / (1.0 + math.exp(-best_diff)) * 100.0
                        except OverflowError: best_prob = 100.0 if best_diff > 0 else 0.0

                        st.success(f"✅ 최적화 완료! 목표 승률 {target_win_rate}% 대비 예측 승률 {best_prob:.2f}% (오차 {abs(best_prob - target_win_rate):.2f}%p)")
                        for i, stat in enumerate(sys_stats): st.session_state[f'builder_stat_input_{stat}'] = float(result.x[i])
                    else: st.error("❌ 최적화에 실패했습니다.")
        
        st.divider()
        with st.expander("Create Custom Character Database Entry", expanded=True):
            char_name = st.text_input("Character Name", "New Hero Template")
            if sys_gimmicks:
                g_cols = st.columns(min(4, len(sys_gimmicks)))
                for i, g in enumerate(sys_gimmicks):
                    with g_cols[i % len(g_cols)]: st.session_state[f'builder_gimmick_{g}'] = st.selectbox(f"Global {g}", st.session_state.get('gimmick_uniques', {}).get(g, ["None"]), key=f'opt_g_{g}')
            if sys_stats:
                cols = st.columns(min(5, len(sys_stats)))
                for i, stat in enumerate(sys_stats):
                    if f'builder_stat_input_{stat}' not in st.session_state: st.session_state[f'builder_stat_input_{stat}'] = 100.0
                    with cols[i % len(cols)]: st.number_input(f"Global {stat}", key=f'builder_stat_input_{stat}')
            
            if st.button("Save to Global Library", type="primary"):
                st.session_state.setdefault('character_library', {})[char_name] = {"stats": {s: st.session_state.get(f'builder_stat_input_{s}', 100.0) for s in sys_stats}, "gimmicks": {g: st.session_state.get(f'builder_gimmick_{g}', "None") for g in sys_gimmicks}}
                st.success(f"✅ '{char_name}' 저장 완료!")
                



    return True, ""
