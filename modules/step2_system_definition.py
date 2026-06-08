import streamlit as st
import pandas as pd
import numpy as np
import random
import itertools
from sklearn.ensemble import RandomForestClassifier
from sklearn.cluster import KMeans
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import json
from streamlit_sortables import sort_items
import re
from modules.detection import detect_modules
from modules.symbolic_regression import (
    detect_damage_column, select_feature_cols, infer_formula, gplearn_available,
)
from modules.move_extraction import detect_move_columns, extract_moves, has_move_data

# ═══════════════════════════════════════════════════════════════════════════════
# 엔진 표준 태그 사전 (Standard Tags) — step6_dashboard.py 디스패처 인식 값
# ═══════════════════════════════════════════════════════════════════════════════
ENGINE_STANDARD_TAGS = {
    "trigger": ["Active_Cast", "On_Turn_Start", "Passive_Only"],
    "target":  ["Single_Target", "AoE_All", "AoE_FrontRow", "Lowest_HP", "Attacker"],
    "element": ["Fire", "Water", "Wood", "Light", "Dark", "Neutral"],
}

def _detect_gimmick_category(col_name):
    """기믹 컬럼명에서 엔진 카테고리를 추론한다."""
    lower = col_name.lower()
    if "trigger" in lower or "발동" in lower:  return "trigger"
    if "target" in lower or "타겟" in lower:   return "target"
    if "element" in lower or "속성" in lower:   return "element"
    return None

def _preprocess_dataframe(df, stat_cols, gimmick_cols, impute_strategy="zero"):
    """
    Auto-Imputation: 결측치 자동 방어 전처리.
    - stat_cols (숫자형): NaN → 0.0 또는 중앙값(median)
    - gimmick_cols (카테고리): NaN → "None"
    반환: 정제된 DataFrame 복사본
    """
    df_clean = df.copy()
    for s in stat_cols:
        if s in df_clean.columns:
            df_clean[s] = pd.to_numeric(df_clean[s], errors='coerce')
            if impute_strategy == "median":
                fill_val = df_clean[s].median()
                fill_val = fill_val if pd.notnull(fill_val) else 0.0
            else:
                fill_val = 0.0
            df_clean[s] = df_clean[s].fillna(fill_val)
    for g in gimmick_cols:
        if g in df_clean.columns:
            df_clean[g] = df_clean[g].fillna("None").astype(str)
    return df_clean

def _apply_tag_mapping(df, gimmick_cols, tag_mapping):
    """
    Tag Normalization: 사용자 정의 태그 매핑을 DataFrame에 적용.
    tag_mapping = { "col_name": { "원본태그": "표준태그", ... }, ... }
    """
    df_mapped = df.copy()
    for g in gimmick_cols:
        col_map = tag_mapping.get(g, {})
        if col_map and g in df_mapped.columns:
            df_mapped[g] = df_mapped[g].map(lambda v: col_map.get(str(v), str(v)))
    return df_mapped

def _render_game_profile_panel(game_profile):
    """Phase 6 — 탐지된 모듈 표시 + 모듈별 수동 오버라이드(Auto/ON/OFF) 패널."""
    detection = game_profile.get('detection', {})
    overrides = game_profile.setdefault('overrides', {})

    st.divider()
    st.markdown("## 🎛️ Game Profile — 활성 모듈 탐지")
    st.info("💡 매핑된 컬럼을 분석해 활성 모듈을 **제안**합니다. 탐지는 제안일 뿐이며, "
            "각 모듈을 수동으로 강제 ON/OFF 할 수 있습니다. 활성 모듈만 Dashboard에 표시됩니다.")

    _labels = {
        'resource': '🧪 자원 (다중 자원 / damage_type 라우팅)',
        'spatial':  '🗺️ 공간 (격자 / 사거리 / 이동)',
        'deck':     '🃏 덱 (카드 전투)',
    }
    _ov_opts = ['auto', 'on', 'off']
    _ov_label = {'auto': '자동 (탐지 따름)', 'on': '강제 ON', 'off': '강제 OFF'}

    for _m in ['resource', 'spatial', 'deck']:
        _d = detection.get(_m, {})
        _det = bool(_d.get('detected'))
        _evidence = _d.get('evidence') or []
        _hints = _d.get('hints') or []
        _cur = overrides.get(_m, 'auto')
        if _cur not in _ov_opts:
            _cur = 'auto'

        _c1, _c2 = st.columns([2, 3])
        with _c1:
            _choice = st.radio(
                _labels[_m], _ov_opts, index=_ov_opts.index(_cur),
                format_func=lambda x: _ov_label[x], horizontal=True,
                key=f"p6_override_{_m}")
        overrides[_m] = _choice

        _active = (_choice == 'on') or (_choice == 'auto' and _det)
        with _c2:
            if _det:
                st.success(f"✅ 탐지됨 (high) · 근거 컬럼: {', '.join(map(str, _evidence)) or '—'}")
            elif _hints:
                st.caption(f"🔍 자동 탐지 안 됨 · 관련 가능 컬럼(힌트): {', '.join(map(str, _hints))}")
            else:
                st.caption("자동 탐지 안 됨")
            st.markdown(f"**→ Dashboard 적용: {'🟢 ON' if _active else '⚪ OFF'}**")

    _stoch = detection.get('stochasticity', {})
    _stoch_hints = _stoch.get('hints') or []
    if _stoch_hints:
        st.caption(f"🎲 확률 요소 관련 컬럼 감지: {', '.join(map(str, _stoch_hints))} "
                   f"— 현재 게이팅 대상 UI 없음 (향후 Phase).")


def _short_list(items, limit=8):
    if not items: return "(없음)"
    if len(items) <= limit: return ", ".join(items)
    return ", ".join(items[:limit]) + f" (+{len(items)-limit})"

def _step2_readiness_state(selected_target, base_stats, formula_text, formula_eval_ok, is_db_mode=False):
    target_ok = bool(selected_target and selected_target != "None")
    stats_ok = bool(base_stats and len(base_stats) > 0)
    
    if is_db_mode:
        formula_text_ok = True
        formula_eval_ok = True
        can_start = target_ok and stats_ok
    else:
        formula_text_ok = bool(formula_text and str(formula_text).strip())
        can_start = target_ok and stats_ok and formula_text_ok and formula_eval_ok
    
    blocking_reasons = []
    if not target_ok:
        blocking_reasons.append("타겟 컬럼 선택 안됨")
    if not stats_ok:
        blocking_reasons.append("기본 스탯 선택 안됨")
        
    if not is_db_mode:
        if not formula_text_ok:
            blocking_reasons.append("데미지 공식 미입력")
        elif not formula_eval_ok:
            blocking_reasons.append("데미지 공식 검증 실패")
        
    return {
        "target_ok": target_ok,
        "stats_ok": stats_ok,
        "formula_text_ok": formula_text_ok,
        "formula_eval_ok": formula_eval_ok,
        "can_start": can_start,
        "blocking_reasons": blocking_reasons,
    }

def _step2_optional_summary(move_library_edited, game_config_like):
    moves_cnt = len(move_library_edited) if move_library_edited is not None and hasattr(move_library_edited, "__len__") else 0
    mechs_cnt = len(game_config_like.get("mechanisms", {})) if game_config_like else 0
    return {
        "moves_count": moves_cnt,
        "mechanisms_count": mechs_cnt,
    }

def _ordered_unique(items):
    seen = set()
    out = []
    for item in items:
        if item is None:
            continue
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out

def _is_binary_target_series(series):
    vals = series.dropna()
    if vals.empty:
        return False
    normalized = {str(v).strip().lower() for v in vals.unique()}
    return len(normalized) == 2 and normalized.issubset({"0", "1", "0.0", "1.0", "true", "false"})

def _target_mode_for_column(df, col):
    if not col or col == "None" or col not in df.columns:
        return "none"
    if _is_binary_target_series(df[col]):
        return "classification"
    lower = str(col).lower()
    damage_names = {"damage", "total_damage", "hp_delta", "delta_hp", "damagevalue", "damage_value"}
    if lower in damage_names:
        return "regression"
    if pd.api.types.is_numeric_dtype(df[col]) and df[col].dropna().nunique() > 2:
        return "regression"
    return "classification"

def _build_target_candidates(df, numeric_cols, schema=None, is_db_mode=False):
    schema = schema or {}
    all_cols = list(df.columns)
    binary_cols = [c for c in all_cols if _is_binary_target_series(df[c])]
    target_names = {"win", "result", "target", "label", "is_win", "victory", "winner"}
    damage_names = {"damage", "total_damage", "hp_delta", "delta_hp", "damagevalue", "damage_value"}
    schema_target = schema.get("target_col") if is_db_mode else None

    named_binary = [c for c in binary_cols if str(c).lower() in target_names]
    damage_cols = [c for c in numeric_cols if str(c).lower() in damage_names]
    other_numeric = [c for c in numeric_cols if c not in damage_cols]
    candidates = _ordered_unique(
        [schema_target]
        + named_binary
        + damage_cols
        + binary_cols
        + other_numeric
        + all_cols
    )
    return candidates if candidates else ["None"], binary_cols

def render_system_definition():
    # 상단 공통 타이틀/설명글 삭제 (수직 공간 압축)
    
    if "df" not in st.session_state:
        return False, "💡 1단계에서 CSV 데이터를 로드해야 합니다."

    is_db_mode = st.session_state.get("input_mode") == "structured_battle_package"
    if is_db_mode:
        st.info("📦 **자동 감지된 전투 데이터 구조를 기본값으로 채웠습니다. 필요하면 수정하세요.**")
        with st.expander("자동 추론된 구조 요약 보기", expanded=False):
            report = st.session_state.get("db_corpus_adapter_report", {})
            schema = st.session_state.get("db_corpus_schema", {})
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Battles", report.get("battle_count", 0))
            col2.metric("Participants", report.get("participant_count", 0))
            col3.metric("Events", report.get("event_count", 0))
            col4.metric("Turns", report.get("max_turn", "N/A"))
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Format/Game Type:** `{schema.get('format', 'unknown')}`")
                st.markdown(f"**Sides:** `{schema.get('sides', 'unknown')}`")
                st.markdown(f"**Roster Structure:** `{schema.get('roster_structure', 'unknown')}`")
            with c2:
                st.markdown(f"**Switch Trace:** `{'Yes' if schema.get('switch_trace') else 'No'}`")
                st.markdown(f"**Status Trace:** `{'Yes' if schema.get('status_trace') else 'No'}`")
                st.markdown(f"**Target Column:** `{schema.get('target_col', 'N/A')}`")

    # ── Validation 피드백 영역 (mapping_approved 이전에도 항상 최상단 표시) ──
    if st.session_state.get("validation_warnings"):
        for warning in st.session_state["validation_warnings"]:
            label = warning.get("label", "")
            score = warning.get("score")
            status = warning.get("status", "warn")

            icon = "🚨" if status == "fail" else "⚠️"
            score_str = f"{score:.0%}" if score is not None else "측정 불가"
            st.warning(f"{icon} **{label}** 일치율 {score_str} — 해당 항목 보정을 권장합니다.")

        if st.button("✅ 경고 확인 완료 (배너 닫기)"):
            st.session_state["validation_warnings"] = []
            st.rerun()

        st.divider()

    df = st.session_state["df"]
    char_col = st.session_state.get("char_col", df.columns[0])
    numeric_cols = st.session_state.get("numeric_cols_raw", df.select_dtypes(include=['int64', 'float64']).columns.tolist())

    is_valid = False

    if not st.session_state.get('mapping_approved', False):
        schema = st.session_state.get("db_corpus_schema", {}) if is_db_mode else {}
        target_candidates, binary_cols = _build_target_candidates(df, numeric_cols, schema, is_db_mode)
        target_names = ['win', 'result', 'target', '승리', '결과', 'label', 'is_win']
        if is_db_mode and schema.get("target_col"):
            inferred_target = schema.get("target_col")
            if inferred_target not in target_candidates and inferred_target in df.columns:
                target_candidates.insert(0, inferred_target)
        else:
            inferred_target = next((col for col in target_candidates if str(col).lower() in target_names), target_candidates[0] if target_candidates else None)
        
        def_target = inferred_target if inferred_target else "None"
        
        if is_db_mode and schema.get("system_stats"):
            def_stats = schema.get("system_stats")
            def_stats = [c for c in def_stats if c in numeric_cols]
        else:
            def_stats = [c for c in numeric_cols if c != def_target]
            
        if is_db_mode and schema.get("system_gimmicks"):
            def_other = schema.get("system_gimmicks")
            def_other = [c for c in def_other if c in df.columns]
        else:
            def_other = [c for c in df.columns if c not in def_stats and c != char_col and c != def_target]

        # 1. 상단 요약 (Summary)
        _target = st.session_state.get("ui_step2_target_col", def_target)
        _stats = st.session_state.get("ui_step2_base_stats", def_stats)
        _gimmicks = st.session_state.get("ui_step2_gimmicks", def_other)
        _formula = st.session_state.get("formula_input_ui", "")
        _moves = st.session_state.get("move_library")
        _game_cfg = st.session_state.get("game_config", {})
        _formula_eval_ok = st.session_state.get("formula_eval_ok", False) # We will set this during formula evaluation
        
        _readiness = _step2_readiness_state(_target, _stats, _formula, _formula_eval_ok, is_db_mode=is_db_mode)
        _opt = _step2_optional_summary(_moves, _game_cfg)
        
        t_ok = "OK" if _readiness["target_ok"] else "Needed"
        s_ok = len(_stats)
        f_ok = "Auto" if is_db_mode else ("OK" if _readiness["formula_eval_ok"] else ("Needed" if not _readiness["formula_text_ok"] else "Error"))
        o_ok = "Set" if (_opt["moves_count"] > 0 or _opt["mechanisms_count"] > 0) else "Auto"
        
        st.markdown(f"**Step2 Setup** | Target {t_ok} | Stats {s_ok} | Formula {f_ok} | Optional {o_ok}")
        st.divider()

        # 2. 탭 구성
        tabs = st.tabs(["필수 매핑", "공식 검증", "선택 규칙", "검토/시작"])
        
        with tabs[0]:
            st.markdown("## 🔍 필수 매핑")
            with st.expander("원본 데이터 샘플 (맵핑 참고용)", expanded=False):
                col_config = {}
                for c in df.columns:
                    if pd.api.types.is_numeric_dtype(df[c]):
                        col_config[c] = st.column_config.NumberColumn(c, format="%.1f")
                    else:
                        col_config[c] = st.column_config.TextColumn(c)
                st.dataframe(df.head(5), use_container_width=True, column_config=col_config)

            if True: # was col1
                st.markdown("#### 1. 🎯 타깃 변수 (승패 결과)")
                if st.session_state.get("ui_step2_target_col") not in target_candidates:
                    st.session_state["ui_step2_target_col"] = inferred_target
                selected_target = st.selectbox("타겟 컬럼", target_candidates if target_candidates else ["None"], index=target_candidates.index(inferred_target) if inferred_target in target_candidates else 0, key="ui_step2_target_col")
                selected_target_mode = _target_mode_for_column(df, selected_target)
                st.caption(f"Target mode: {selected_target_mode}")
            
                st.markdown("#### 2. 📊 기본 스탯 & 기믹")
                base_stats = st.multiselect("숫자형 스탯 (Base Stats)", numeric_cols, default=def_stats, key="ui_step2_base_stats")
                other_cols = [c for c in df.columns if c not in base_stats and c != char_col and c != selected_target]
                valid_def_other = [c for c in def_other if c in other_cols]
                gimmicks = st.multiselect("카테고리/기믹 (Gimmicks)", other_cols, default=valid_def_other, key="ui_step2_gimmicks")

                # ── Auto-Imputation 전략 선택 ──
                st.markdown("#### 2-1. 🛡️ 결측치 채우기")
                nan_count = int(df[base_stats].isnull().sum().sum()) if base_stats else 0
                gimmick_nan = int(df[gimmicks].isnull().sum().sum()) if gimmicks else 0
                total_nan = nan_count + gimmick_nan
                if total_nan > 0:
                    st.warning(f"⚠️ 선택된 컬럼에서 총 **{total_nan}건**의 결측치(NaN)가 감지되었습니다. (스탯: {nan_count}, 기믹: {gimmick_nan})")
                else:
                    st.success("✅ 선택된 컬럼에 결측치가 없습니다.")
                impute_strategy = st.radio(
                    "숫자형 결측치 채우기 전략",
                    ["zero", "median"],
                    format_func=lambda x: "0.0으로 채우기 (안전)" if x == "zero" else "중앙값(Median)으로 채우기",
                    horizontal=True, key="ui_impute_strategy"
                )
            
        with tabs[1]:
            st.markdown("## ⚔️ 공식 검증기")
            if st.session_state.get("input_mode") == "structured_battle_package":
                st.info("💡 이 전투 데이터 패키지는 리플레이 이벤트 기반 검증을 우선 사용합니다. 데미지 수식을 수동으로 정의하려면 아래에서 입력할 수 있습니다.")
            if True: # was col2
                if 'formula_input_ui' not in st.session_state:
                    st.session_state['formula_input_ui'] = ""
                
                total_vars = len(base_stats) + len(gimmicks)
            
                def on_chip_click():
                    sel = st.session_state.get('formula_chip_selector')
                    if sel:
                        st.session_state['formula_input_ui'] += sel.lower() + " "
                        st.session_state['formula_chip_selector'] = None

                if total_vars <= 15:
                    st.write("변수 칩 (클릭 시 수식 입력창에 삽입됩니다):")
                    all_vars = base_stats + gimmicks
                    st.pills("Variables", all_vars, key="formula_chip_selector", label_visibility="collapsed", on_change=on_chip_click)
                else:
                    st.write("변수 선택 (선택한 변수를 수식에 추가합니다):")
                    all_vars = base_stats + gimmicks
                    selected_vars = st.multiselect("수식에 추가할 변수 선택", all_vars, default=[])
                    if st.button("➕ 선택한 변수 수식에 추가", use_container_width=True):
                        for v in selected_vars:
                            st.session_state['formula_input_ui'] += v.lower() + " "
                        st.rerun()
                
                st.text_input("전투 데미지 공식 (Damage Formula)", key="formula_input_ui")
            
                row1 = df.iloc[0].to_dict() if len(df) > 0 else {}
                eval_env_raw = {s: row1.get(s, 0) for s in base_stats}
                eval_env_raw.update({"target_" + s: row1.get(s, 0) for s in base_stats})
                eval_env_raw["current_health"] = row1.get("current_health", 0)
                eval_env_raw["max_health"] = row1.get("max_health", 0)
                eval_env_raw["target_current_health"] = row1.get("current_health", 0)
                eval_env_raw["target_max_health"] = row1.get("max_health", 0)
            
                # ── Phase 8a: 무브 공식 검증용 샘플 변수 (attack_log 보조 진입) ──
                _atk_log_df = st.session_state.get("attack_log_df")
                if has_move_data(df):
                    _df_for_validate = df
                elif _atk_log_df is not None and has_move_data(_atk_log_df):
                    _df_for_validate = _atk_log_df
                else:
                    _df_for_validate = None
                if _df_for_validate is not None:
                    _mv_cols = detect_move_columns(_df_for_validate)
                    _pwr_col = _mv_cols.get("power")
                    if _pwr_col and _pwr_col in _df_for_validate.columns:
                        _pw = pd.to_numeric(_df_for_validate[_pwr_col], errors="coerce").dropna()
                        eval_env_raw["move_power"] = float(_pw.mean()) if len(_pw) else 0.0
                        _ss = base_stats[0] if base_stats else None
                        _sv = float(row1.get(_ss, 1) or 1) if _ss else 1.0
                        eval_env_raw["offense"] = _sv
                        eval_env_raw["defense"] = _sv

                eval_env = {str(k).lower(): float(v) if pd.notnull(v) and isinstance(v, (int, float)) else v for k, v in eval_env_raw.items()}
                formula_str_eval = st.session_state['formula_input_ui'].lower().strip()
                st.session_state["formula_eval_ok"] = False
            
                if formula_str_eval:
                    try:
                        res = eval(formula_str_eval, {"__builtins__": None}, eval_env)
                        st.success(f"✅ 연산 성공! 예상 데미지: {res}")
                        st.session_state["formula_eval_ok"] = True
                        is_valid = True
                    except Exception as e:
                        st.error(f"❌ 수식 오류: {e}")
                else:
                    st.warning("⚠️ 데미지 공식을 입력해주세요.")

                # ── Phase 7: 데미지 공식 자동 추정 — 데미지 컬럼 있을 때만 노출 ──
                _sr_dmg_col = detect_damage_column(df, base_stats, selected_target)
                if gplearn_available() and _sr_dmg_col is not None:
                    st.markdown("##### 🔮 데미지 공식 자동 추정")

                    def _sr_apply(_formula):
                        # 위젯 키는 콜백에서만 안전하게 수정 가능 (on_chip_click과 동일 패턴)
                        st.session_state['formula_input_ui'] = _formula
                        st.session_state.pop('sr_candidates', None)

                    st.caption(f"데미지 컬럼 `{_sr_dmg_col}` 감지 — 기호 회귀로 공식 후보를 추정합니다.")
                    if st.button("🔮 공식 자동 추정 실행", use_container_width=True,
                                 key="sr_run_btn"):
                        with st.spinner("gplearn 기호 회귀 연산 중... (수십 초 소요될 수 있음)"):
                            _sr_feats = select_feature_cols(
                                base_stats, _sr_dmg_col,
                                st.session_state.get('game_profile'))
                            st.session_state['sr_candidates'] = infer_formula(
                                df, _sr_dmg_col, _sr_feats)
                    _sr_cands = st.session_state.get('sr_candidates')
                    if _sr_cands:
                        st.caption("후보 (R² 내림차순) — '이 공식 사용' 시 위 입력창에 채워집니다:")
                        for _i, _cand in enumerate(_sr_cands):
                            _cc1, _cc2 = st.columns([4, 1])
                            with _cc1:
                                st.code(_cand['formula'], language="python")
                                _w = "" if _cand['eval_safe'] else " · ⚠️ 0除算 위험"
                                st.caption(f"R² {_cand['r2']:.3f} · 복잡도 {_cand['complexity']}{_w}")
                            with _cc2:
                                st.button("이 공식 사용", key=f"sr_use_{_i}",
                                          on_click=_sr_apply, args=(_cand['formula'],))
                    elif _sr_cands == []:
                        st.info("공식 후보를 찾지 못했습니다 (데이터 부족 또는 적합 실패).")

        with tabs[2]:
            st.markdown("## ⚙️ 선택 규칙")
            st.caption("아래 항목은 모두 선택(고급 설정)입니다.")
            with st.expander("🎯 Move System (무브/어빌리티)", expanded=False):
                move_library_edited = None
                move_categories_cfg = {}
                move_type_table_edited = None
                move_type_columns = []
                move_stab_factor = 1.0

                # ── attack_log 진입 경로 — Step 1에서 업로드됨 ──
                attack_log_df = st.session_state.get("attack_log_df")
                if attack_log_df is not None:
                    st.caption(f"📦 Step 1에서 업로드된 무브 로그 ({len(attack_log_df)}행) 사용 중")
                else:
                    st.caption("ℹ️ 무브 로그 없음 — Step 1에서 무브 로그를 업로드하면 무브 분석이 활성화됩니다.")

                # ── 무브 추출 데이터 출처 결정 ──
                if has_move_data(df):
                    df_for_moves = df
                elif attack_log_df is not None and has_move_data(attack_log_df):
                    df_for_moves = attack_log_df
                    st.info("📎 메인 로그에 무브 컬럼이 없어 무브 로그에서 추출합니다.")
                else:
                    df_for_moves = None
                if df_for_moves is not None:
                    st.info("💡 로그에서 무브 위력/타입/카테고리 컬럼을 감지했습니다. "
                            "추출된 무브를 표에서 검수·수정하세요.")
                    _mv_detect = detect_move_columns(df_for_moves)
                    _opts = ["(없음)"] + list(df_for_moves.columns)
                    def _opt_idx(v):
                        return _opts.index(v) if v in _opts else 0
                    _mcc = st.columns(5)
                    with _mcc[0]:
                        _pcol = st.selectbox("위력 컬럼", _opts, index=_opt_idx(_mv_detect.get("power")), key="ui_move_power_col")
                    with _mcc[1]:
                        _tcol = st.selectbox("타입 컬럼", _opts, index=_opt_idx(_mv_detect.get("type")), key="ui_move_type_col")
                    with _mcc[2]:
                        _ccol = st.selectbox("카테고리 컬럼", _opts, index=_opt_idx(_mv_detect.get("category")), key="ui_move_cat_col")
                    with _mcc[3]:
                        _ncol = st.selectbox("이름 컬럼", _opts, index=_opt_idx(_mv_detect.get("name")), key="ui_move_name_col")
                    with _mcc[4]:
                        _prcol = st.selectbox("우선도 컬럼", _opts, index=_opt_idx(_mv_detect.get("priority")), key="ui_move_priority_col")
                    _moves = extract_moves(
                        df_for_moves,
                        _pcol if _pcol != "(없음)" else None,
                        _tcol if _tcol != "(없음)" else None,
                        _ccol if _ccol != "(없음)" else None,
                        _ncol if _ncol != "(없음)" else None,
                        _prcol if _prcol != "(없음)" else None,
                    )
                    if _moves:
                        st.caption(f"✅ {len(_moves)}개 무브 추출됨 — 표에서 직접 수정 가능:")
                        move_library_edited = st.data_editor(
                            pd.DataFrame(_moves), use_container_width=True,
                            num_rows="dynamic", key="ui_move_library_editor")
                        _cats = sorted({str(m.get("category", "")) for m in _moves
                                        if str(m.get("category", "")).strip()})
                        if _cats and base_stats:
                            st.markdown("#### 카테고리별 공격/방어 스탯 라우팅")
                            st.caption("각 무브 카테고리가 어떤 스탯으로 공격/방어 판정을 하는지 지정합니다.")
                            for _cat in _cats:
                                _rc = st.columns(2)
                                with _rc[0]:
                                    _off = st.selectbox(f"`{_cat}` 공격 스탯", base_stats, key=f"ui_movecat_off_{_cat}")
                                with _rc[1]:
                                    _def = st.selectbox(f"`{_cat}` 방어 스탯", base_stats, key=f"ui_movecat_def_{_cat}")
                                move_categories_cfg[_cat] = {"offense": _off, "defense": _def}
                        elif not base_stats:
                            st.warning("⚠️ 카테고리 라우팅 설정 전에 Base Stats를 먼저 선택하세요.")

                        # ── Phase 8b: 타입 상성표 + STAB ──
                        with st.expander("🔯 타입 상성표", expanded=False):
                            _type_col_default = [g for g in gimmicks
                                                 if 'type' in g.lower() or '타입' in g or '속성' in g]
                            move_type_columns = st.multiselect(
                                "캐릭터 타입이 든 기믹 컬럼 (방어 상성·STAB 판정에 사용)",
                                gimmicks, default=_type_col_default, key="ui_move_type_columns")
                            _move_types = {str(m.get("type", "")) for m in _moves
                                           if str(m.get("type", "")).strip()}
                            _gimmick_types = {str(v) for c in move_type_columns
                                              for v in df[c].dropna().astype(str).unique()}
                            _type_roster = sorted(_move_types | _gimmick_types)
                            if _type_roster:
                                st.caption(f"{len(_type_roster)}개 타입 — 공격(행) × 방어(열) 배율표. "
                                           f"기본값 1.0(무영향)이니 **효과적(2.0)·반감(0.5)·무효(0.0)인 칸만** "
                                           f"바꾸면 됩니다.")
                                _tt_init = pd.DataFrame(1.0, index=_type_roster, columns=_type_roster)
                                move_type_table_edited = st.data_editor(
                                    _tt_init, use_container_width=True, height=320, key="ui_type_table_editor")
                                move_stab_factor = st.number_input(
                                    "STAB 배율 (무브 타입 == 공격자 타입 시 추가 배율, 1.0 = STAB 없음)",
                                    min_value=1.0, max_value=3.0, value=1.0, step=0.1, key="ui_stab_factor")
                            else:
                                st.caption("타입 정보가 없어 상성표를 만들 수 없습니다.")
                    else:
                        st.caption("추출된 무브가 없습니다 — 무브 컬럼 선택을 확인하세요.")
                else:
                    st.caption("로그에 무브 컬럼(위력/타입/카테고리)이 없습니다 — 무브 시스템 비활성. "
                               "단일 데미지 공식으로 동작합니다.")

            # Tag Normalization
            with st.expander("🏷️ Tag Dictionary Mapping (태그 정규화)", expanded=False):
                st.info("💡 CSV에 있는 고유 태그를 엔진이 인식하는 **표준 태그(Standard Tag)**와 1:1로 매핑합니다. 미인식 태그는 엔진에서 기본값으로 폴백됩니다.")

                tag_mapping = {}  # { col_name: { csv_val: engine_val, ... }, ... }
                mappable_gimmicks = [(g, _detect_gimmick_category(g)) for g in gimmicks if _detect_gimmick_category(g)]

                if mappable_gimmicks:
                    for g_col, g_cat in mappable_gimmicks:
                        standard_tags = ENGINE_STANDARD_TAGS.get(g_cat, [])
                        unique_vals = sorted(df[g_col].dropna().astype(str).unique().tolist())
                        if not unique_vals:
                            continue

                        with st.expander(f"📋 `{g_col}` → 엔진 카테고리: **{g_cat.upper()}** ({len(unique_vals)}개 고유값)", expanded=False):
                            col_map = {}
                            # 기존 값이 이미 표준 태그인지 자동 감지
                            map_cols = st.columns(min(3, len(unique_vals)))
                            for idx, csv_val in enumerate(unique_vals):
                                with map_cols[idx % len(map_cols)]:
                                    # 기본값: 정확 일치면 자동 선택, 아니면 첫 번째 표준 태그
                                    options = standard_tags + [f"[원본 유지] {csv_val}"]
                                    if csv_val in standard_tags:
                                        default_idx = standard_tags.index(csv_val)
                                    else:
                                        default_idx = len(standard_tags)  # "[원본 유지]" 선택
                                    mapped = st.selectbox(
                                        f"`{csv_val}`", options, index=default_idx,
                                        key=f"ui_tag_map_{g_col}_{csv_val}"
                                    )
                                    if mapped.startswith("[원본 유지]"):
                                        col_map[csv_val] = csv_val
                                    else:
                                        col_map[csv_val] = mapped
                            tag_mapping[g_col] = col_map

                    # 매핑 미리보기
                    changed_count = sum(
                        1 for col_map in tag_mapping.values()
                        for orig, mapped in col_map.items() if orig != mapped
                    )
                    if changed_count > 0:
                        st.success(f"✅ 총 **{changed_count}건**의 태그가 표준 태그로 변환 예정입니다.")
                    else:
                        st.caption("모든 태그가 이미 엔진 표준과 일치하거나 원본 유지 상태입니다.")
                else:
                    st.caption("🔍 기믹 컬럼 중 엔진 카테고리(trigger/target/element)와 매칭되는 컬럼이 감지되지 않았습니다. 태그 매핑이 필요하지 않습니다.")

            with st.expander("🔄 Logic Execution Order", expanded=False):
                st.info("💡 **가이드:** 각 로직 블록을 드래그(Drag & Drop)하여 시스템 적용 순서를 변경할 수 있습니다.")
                if "combat_flow" not in st.session_state:
                    st.session_state.combat_flow = [
                        {
                            "header": "Phase 1: Pre-calculation", 
                            "items": ["Apply Passives (패시브 적용)", "Base Stat Calculation (기본 스탯 계산)"]
                        },
                        {
                            "header": "Phase 2: Combat Flow", 
                            "items": ["Determine Targeting (타겟팅 결정)", "Calculate Base Damage (기본 데미지 계산)", "Apply Elemental Multipliers (속성 상성 적용)", "Apply Critical Hit (치명타 적용)"]
                        },
                        {
                            "header": "Phase 3: Resolution", 
                            "items": ["Apply Damage (최종 데미지 적용)", "Trigger On-Hit Effects (피격 효과 발동)", "Check Death (사망 판정)"]
                        }
                    ]

                sorted_items = sort_items(st.session_state.combat_flow, multi_containers=True)
                if sorted_items:
                    st.session_state.combat_flow = sorted_items
                    st.caption("✅ 현재 로직 실행 순서가 저장되었습니다.")

            # ── Phase 8d: 기믹 채널 명시 매핑 ──
            with st.expander("🧩 기믹 채널 매핑 (Channel Mapping) — 권장", expanded=False):
                st.caption(
                    "엔진이 어떤 기믹 컬럼을 어느 역할로 읽을지 명시합니다. "
                    "기본 '(자동 감지)'는 영어 키워드(passive·trigger·target 등) 부분일치로 폴백합니다 — "
                    "한국어/다국어 같은 비-영어 명명을 쓰는 게임은 명시 매핑이 필수입니다 "
                    "(그렇지 않으면 엔진이 해당 채널을 조용히 누락)."
                )
                _channel_roles = [
                    ("passive",     "🔁 패시브 로직"),
                    ("trigger",     "⏱ 발동 트리거"),
                    ("target",      "🎯 타겟 규칙"),
                    ("formula",     "🧮 데미지 공식"),
                    ("element",     "🌀 속성 타입"),
                    ("damage_type", "💥 데미지 타입"),
                    ("ability",     "🧬 특성/능력"),
                    ("item",        "🎒 장비/도구"),
                    ("status",      "🔥 상태이상"),
                ]
                _ch_cols = st.columns(3)
                _channel_choices = {}
                for _i, (_role, _label) in enumerate(_channel_roles):
                    with _ch_cols[_i % 3]:
                        _options = ["(자동 감지)", "(없음)"] + list(gimmicks)
                        _key = f"ui_channel_{_role}"
                        _channel_choices[_role] = st.selectbox(
                            _label, _options, index=0, key=_key,
                            help=f"이 기믹 컬럼을 {_label} 채널로 사용. "
                                 "'(자동 감지)'는 컬럼명에 영어 키워드가 있을 때만 작동, "
                                 "'(없음)'은 이 채널을 명시적으로 비활성."
                        )

            # ── 동적 메커니즘 부착 (Leftovers류 턴 종료 회복) — game_config["mechanisms"] ──
            _mech_cfg = {}
            with st.expander("🍃 동적 메커니즘 부착 (Mechanism Attach) — 선택", expanded=False):
                st.caption(
                    "엔진에 실제 연결된 동적 메커니즘만 설정합니다. 단순 항목은 폼으로 지정하고, 복잡한 발동형 효과는 effects JSON으로 입력합니다."
                )
                _lo_on = st.checkbox("Leftovers (턴 종료 HP 회복) 활성", value=False, key="ui_mech_leftovers_on")
                if _lo_on:
                    if gimmicks:
                        _lo_col = st.selectbox(
                            "부착 기준 기믹 컬럼", list(gimmicks), key="ui_mech_leftovers_col",
                            help="이 컬럼의 값이 아래 '부착 값'과 일치하는 캐릭터에 회복을 적용."
                        )
                        _lo_vals = (sorted(df[_lo_col].dropna().astype(str).unique().tolist())
                                    if _lo_col in df.columns else [])
                        if _lo_vals:
                            _lo_match = st.selectbox("부착 값", _lo_vals, key="ui_mech_leftovers_val")
                        else:
                            _lo_match = st.text_input("부착 값", value="Leftovers", key="ui_mech_leftovers_val_txt")
                        _lo_pct = st.number_input(
                            "턴 종료 회복률 (max HP 대비)", min_value=0.0, max_value=1.0,
                            value=0.0625, step=0.01, format="%.4f", key="ui_mech_leftovers_pct"
                        )
                        _mech_cfg["leftovers"] = {
                            "gimmick_col": _lo_col,
                            "match_value": str(_lo_match),
                            "percent": float(_lo_pct),
                        }
                    else:
                        st.warning("기믹 컬럼이 없어 부착 기준을 지정할 수 없습니다.")

                _st_on = st.checkbox("상태이상 (턴 종료 % 데미지) 활성", value=False, key="ui_mech_status_on")
                if _st_on:
                    if gimmicks:
                        _st_col = st.selectbox(
                            "상태이상 기준 기믹 컬럼", list(gimmicks), key="ui_mech_status_col",
                            help="이 컬럼의 값이 아래 '상태이상 값'과 일치하는 캐릭터가 턴 종료마다 데미지를 받음."
                        )
                        _st_vals = (sorted(df[_st_col].dropna().astype(str).unique().tolist())
                                    if _st_col in df.columns else [])
                        if _st_vals:
                            _st_match = st.selectbox("상태이상 값", _st_vals, key="ui_mech_status_val")
                        else:
                            _st_match = st.text_input("상태이상 값", value="Poison", key="ui_mech_status_val_txt")
                        _st_pct = st.number_input(
                            "턴 종료 데미지율 (max HP 대비)", min_value=0.0, max_value=1.0,
                            value=0.125, step=0.01, format="%.4f", key="ui_mech_status_pct"
                        )
                        _mech_cfg["status"] = {
                            "gimmick_col": _st_col,
                            "match_value": str(_st_match),
                            "percent": float(_st_pct),
                        }
                    else:
                        st.warning("기믹 컬럼이 없어 상태이상 기준을 지정할 수 없습니다.")

                _pt_on = st.checkbox("Protean (무브마다 타입 갱신 → STAB 상시) 활성", value=False, key="ui_mech_protean_on")
                if _pt_on:
                    if gimmicks:
                        _pt_col = st.selectbox(
                            "Protean 기준 기믹 컬럼", list(gimmicks), key="ui_mech_protean_col",
                            help="이 컬럼의 값이 아래 'Protean 값'과 일치하는 캐릭터가 무브 사용 시 그 무브 타입으로 갱신됨."
                        )
                        _pt_vals = (sorted(df[_pt_col].dropna().astype(str).unique().tolist())
                                    if _pt_col in df.columns else [])
                        if _pt_vals:
                            _pt_match = st.selectbox("Protean 값", _pt_vals, key="ui_mech_protean_val")
                        else:
                            _pt_match = st.text_input("Protean 값", value="Protean", key="ui_mech_protean_val_txt")
                        _mech_cfg["protean"] = {
                            "gimmick_col": _pt_col,
                            "match_value": str(_pt_match),
                        }
                    else:
                        st.warning("기믹 컬럼이 없어 Protean 기준을 지정할 수 없습니다.")

                _tr_on = st.checkbox("Trace (교체 진입 시 상대 타입 복사 → STAB)", value=False, key="ui_mech_trace_on")
                if _tr_on:
                    if gimmicks:
                        _tr_col = st.selectbox(
                            "Trace 기준 기믹 컬럼", list(gimmicks), key="ui_mech_trace_col",
                            help="이 컬럼의 값이 아래 'Trace 값'과 일치하는 캐릭터가 교체로 진입할 때 상대 on_field 유닛의 타입을 복사함."
                        )
                        _tr_vals = (sorted(df[_tr_col].dropna().astype(str).unique().tolist())
                                    if _tr_col in df.columns else [])
                        if _tr_vals:
                            _tr_match = st.selectbox("Trace 값", _tr_vals, key="ui_mech_trace_val")
                        else:
                            _tr_match = st.text_input("Trace 값", value="Trace", key="ui_mech_trace_val_txt")
                        _tr_type_col = st.selectbox(
                            "복사할 타입이 든 기믹 컬럼 (상대의 이 값을 복사)", list(gimmicks),
                            key="ui_mech_trace_type_col",
                            help="상대 on_field 유닛의 이 기믹 컬럼 값을 진입 유닛의 current_type으로 복사. 상대가 Protean 등 동적 타입(current_type)을 가지면 그것을 우선 사용."
                        )
                        _mech_cfg["trace"] = {
                            "gimmick_col": _tr_col,
                            "match_value": str(_tr_match),
                            "type_col": _tr_type_col,
                        }
                    else:
                        st.warning("기믹 컬럼이 없어 Trace 기준을 지정할 수 없습니다.")

                _hz_on = st.checkbox("해저드 (교체 진입 시 진영 진입 데미지 → Stealth Rock류)",
                                     value=False, key="ui_mech_hazard_on")
                if _hz_on:
                    _hz_team = st.selectbox(
                        "해저드가 깔린 진영", ["Enemy", "Ally", "both"], key="ui_mech_hazard_team",
                        help="이 진영으로 '교체로 진입하는' 유닛이 매 진입 시 데미지를 받음. both면 양 진영 모두. "
                             "초기 리드(첫 액티브)는 교체가 아니므로 면제(Pokemon 해저드와 동일)."
                    )
                    _hz_pct = st.number_input(
                        "진입 데미지 비율 (주 자원 max 대비)", min_value=0.0, max_value=1.0,
                        value=0.125, step=0.0625, format="%.4f", key="ui_mech_hazard_pct",
                        help="예: 0.125 = 진입 시 최대 HP의 1/8 데미지. 1.0이면 진입 즉사."
                    )
                    _mech_cfg["hazard"] = {
                        "team": _hz_team,
                        "percent": float(_hz_pct),
                    }

                _eff_on = st.checkbox(
                    "발동형 효과 스키마 (effects) 직접 입력 — 고급",
                    value=False, key="ui_mech_effects_on"
                )
                if _eff_on:
                    st.caption(
                        "엔진이 이미 소비하는 game_config['mechanisms']['effects'] 입력입니다. (단순 입력면과 중복 입력 주의) "
                        "키는 ability/item/status/weather/move 이름과 맞춰야 하며, 값은 trigger·effect·scope·source를 가진 dict입니다."
                    )
                    _eff_json = st.text_area(
                        "effects JSON",
                        value='{\n'
                              '  "Leftovers": {"trigger": "ON_TURN_END", "effect": {"type": "heal_frac", "frac": 0.0625, "of": "maxhp"}, "scope": "self", "source": "item"},\n'
                              '  "Burn": {"trigger": "ON_TURN_END", "effect": {"type": "damage_frac", "frac": 0.125, "of": "maxhp"}, "scope": "self", "source": "status"}\n'
                              '}',
                        height=220,
                        key="ui_mech_effects_json",
                        help="지원 effect.type: damage_frac, heal_frac, self_faint, swap_item. 조건은 condition dict로 추가합니다."
                    )
                    try:
                        _eff_parsed = json.loads(_eff_json) if _eff_json.strip() else {}
                    except (ValueError, TypeError):
                        _eff_parsed = None
                        st.warning("effects JSON 파싱 실패 — JSON 형식을 확인하세요.")
                    if isinstance(_eff_parsed, dict) and _eff_parsed:
                        _mech_cfg["effects"] = _eff_parsed


                # ── 무브 효과 + 전략 정책 (전략 의사결정 모델) ──
                _move_effects_cfg = {}
                _move_names = []
                if move_library_edited is not None and "name" in getattr(move_library_edited, "columns", []):
                    _move_names = sorted(move_library_edited["name"].dropna().astype(str).unique().tolist())
                _me_on = st.checkbox("무브 효과 (boost/디버프) 부여 활성", value=False, key="ui_mech_moveeffect_on")
                if _me_on:
                    if _move_names and base_stats:
                        _me_move = st.selectbox("효과 무브 선택", _move_names, key="ui_mech_me_move")
                        _me_stats = st.multiselect("올릴/내릴 스탯", list(base_stats), key="ui_mech_me_stats")
                        _me_mod = st.selectbox("증감 방식", ["percent", "flat"], key="ui_mech_me_mod")
                        _me_val = st.number_input(
                            "증감량 (percent는 0.5=+50%, 음수=디버프)", value=0.5, step=0.1,
                            format="%.3f", key="ui_mech_me_val"
                        )
                        _me_scope = st.selectbox("대상", ["self", "target"], key="ui_mech_me_scope")
                        if _me_stats:
                            _move_effects_cfg[_me_move] = [
                                {"target_stat": _s, "mod_type": _me_mod,
                                 "value": float(_me_val), "scope": _me_scope}
                                for _s in _me_stats
                            ]
                    else:
                        st.warning("추출된 무브 또는 기본 스탯이 없어 무브 효과를 지정할 수 없습니다.")

                _hzm_on = st.checkbox("해저드 설치/청소 무브 (무브로 진영에 진입 데미지 설치 → 동적 해저드)",
                                      value=False, key="ui_mech_hazardmove_on")
                if _hzm_on:
                    if _move_names:
                        _hzm_move = st.selectbox("해저드 무브 선택", _move_names, key="ui_mech_hzm_move",
                                                 help="이 무브를 사용하면 아래 설정대로 해저드를 설치/청소함.")
                        _hzm_kind = st.selectbox("동작", ["set_hazard (설치)", "clear_hazard (청소)"],
                                                 key="ui_mech_hzm_kind")
                        _hzm_team = st.selectbox("대상 진영", ["Enemy", "Ally", "both"],
                                                 key="ui_mech_hzm_team",
                                                 help="이 진영으로 교체 진입하는 유닛이 데미지를 받음(설치). both면 양 진영.")
                        _hzm_kind_val = "set_hazard" if _hzm_kind.startswith("set") else "clear_hazard"
                        _hzm_spec = {"kind": _hzm_kind_val, "team": _hzm_team}
                        if _hzm_kind_val == "set_hazard":
                            _hzm_pct = st.number_input(
                                "설치 데미지 비율 (주 자원 max 대비)", min_value=0.0, max_value=1.0,
                                value=0.125, step=0.0625, format="%.4f", key="ui_mech_hzm_pct",
                                help="예: 0.125 = 진입 시 최대 HP의 1/8. 정적 해저드와 겹치면 큰 값 적용."
                            )
                            _hzm_spec["percent"] = float(_hzm_pct)
                        _move_effects_cfg.setdefault(_hzm_move, []).append(_hzm_spec)
                    else:
                        st.warning("추출된 무브가 없어 해저드 무브를 지정할 수 없습니다.")


                _move_policy_sel = st.selectbox(
                    "전략 정책 (무브 선택 방식)",
                    ["(기본) 그리디 — 최대 기대 데미지", "setup_first — 효과 무브 먼저 사용 후 데미지"],
                    index=0, key="ui_mech_move_policy"
                )

                # ── 교체(switch) 모델 — 액티브/예비 회전 (게임 중립, 미설정 시 전원-동시) ──
                st.markdown("**교체(switch) 모델** — 액티브/예비 회전 (미설정 시 현행 전원-동시)")
                _active_count_in = st.number_input(
                    "팀별 액티브 수 (0=전원 동시, 1=싱글, 2=더블 …)",
                    min_value=0, value=0, step=1, key="ui_switch_active_count"
                )
                _faint_rule_sel = st.selectbox(
                    "액티브 사망 시 처리",
                    ["(없음)", "예비에서 교체 (replace_from_reserve)"],
                    index=0, key="ui_switch_faint_rule"
                )
                _switch_policy_sel = st.selectbox(
                    "자발적 교체 정책",
                    ["(없음)", "HP 임계 교체 (hp_threshold)"],
                    index=0, key="ui_switch_policy"
                )
                _switch_thr = st.number_input(
                    "HP 임계 비율 (hp_threshold일 때 적용)",
                    min_value=0.0, max_value=1.0, value=0.25, step=0.05,
                    format="%.2f", key="ui_switch_threshold"
                )
                # ── 행동 순서: 교체 우선도 티어 (교체가 공격보다 먼저 해결; 무브 우선도와 결합) ──
                _switch_prio_in = st.number_input(
                    "교체 행동 우선도 티어 (switch_priority — 높을수록 공격보다 먼저; 기본 6)",
                    min_value=0, value=6, step=1, key="ui_switch_priority"
                )
                st.caption("ℹ️ 무브 우선도 컬럼을 매핑하면 느린 유닛도 우선도 무브로 먼저 행동합니다. "
                           "교체 우선도 티어는 교체를 무브보다 앞에 둡니다.")

        with tabs[3]:
            st.markdown("## 🚀 검토/시작")
            
            # Recalculate readiness since formula validation just ran
            _readiness = _step2_readiness_state(selected_target, base_stats, formula_str_eval, st.session_state.get("formula_eval_ok", False), is_db_mode=is_db_mode)
            
            st.markdown("### 📋 시작 전 확인 (필수)")
            st.markdown(f"- **Target**: {'✅ OK' if _readiness['target_ok'] else '❌ Needed'} — {selected_target}")
            st.markdown(f"- **Stats**: {'✅ OK' if _readiness['stats_ok'] else '❌ Needed'} — {_short_list(base_stats)}")
            if is_db_mode:
                st.markdown(f"- **Formula**: ✅ Auto — DB/ZIP 패키지 모드")
            elif not _readiness['formula_text_ok']:
                st.markdown(f"- **Formula**: ❌ Needed — 공식 텍스트가 없습니다.")
            elif not _readiness['formula_eval_ok']:
                st.markdown(f"- **Formula**: ❌ Error — 수식 계산에 실패했습니다.")
            else:
                st.markdown(f"- **Formula**: ✅ OK — 연산 성공")
            
            if not _readiness["can_start"]:
                st.error("🚨 시작 불가: " + " / ".join(_readiness["blocking_reasons"]))
                
            st.markdown("### ⚙️ 선택 규칙 요약")
            _opt_moves = st.session_state.get("move_library", [])
            _opt_mechs = st.session_state.get("game_config", {}).get("mechanisms", {})
            
            st.write(f"- Move Library: {len(_opt_moves)}개 등록됨" if _opt_moves else "- Move Library: 자동/없음")
            st.write(f"- Mechanisms: {len(_opt_mechs)}개 수동 설정됨" if _opt_mechs else "- Mechanisms: 자동/없음")
            st.write(f"- Gimmicks: {_short_list(gimmicks)}")
            
            validation_errors = []

            c_btn, c_json = st.columns(2)
            with c_btn:
                if st.button("🚀 기획 의도 확립 및 파이프라인 시작", disabled=not _readiness["can_start"], use_container_width=True, type="primary"):
                    # ── Validation Warnings 초기화 ──
                    if "validation_warnings" in st.session_state:
                        del st.session_state["validation_warnings"]
                
                    # ── Auto-Imputation 적용 ──
                    df_clean = _preprocess_dataframe(df, base_stats, gimmicks, impute_strategy)
                    # ── Tag Normalization 적용 ──
                    if tag_mapping:
                        df_clean = _apply_tag_mapping(df_clean, gimmicks, tag_mapping)
                    st.session_state['df'] = df_clean
                    st.session_state['tag_mapping'] = tag_mapping
                    st.session_state['pipeline_impute_strategy'] = impute_strategy

                    st.session_state['mapping_approved'] = True
                    st.session_state['global_damage_formula'] = st.session_state['formula_input_ui']
                    st.session_state['damage_formula'] = st.session_state['formula_input_ui']
                    _selected_target_mode = _target_mode_for_column(df_clean, selected_target)
                    st.session_state['target_col'] = selected_target if selected_target != "None" else None
                    st.session_state['target_variable'] = selected_target if selected_target != "None" else None
                    st.session_state['target_mode'] = _selected_target_mode
                    st.session_state['system_stats'] = base_stats
                    st.session_state['system_gimmicks'] = gimmicks
                    # ── Phase 8a/8b/8d: 무브 시스템 + 채널 매핑 → game_config / move_library ──
                    _gc = {}
                    # Phase 8d — 채널 매핑 수집
                    _ch = {}
                    for _role, _ in _channel_roles:
                        _val = _channel_choices.get(_role, "(자동 감지)")
                        if _val == "(없음)":
                            _ch[_role] = None
                        elif _val and _val != "(자동 감지)":
                            _ch[_role] = _val
                    if _ch:
                        _gc["channels"] = _ch
                    # Phase 8a/8b — 무브 시스템
                    if move_library_edited is not None and len(move_library_edited) > 0:
                        st.session_state['move_library'] = move_library_edited.to_dict('records')
                        _gc["categories"] = move_categories_cfg
                        if move_type_table_edited is not None and move_type_columns:
                            _gc["type_table"] = {
                                str(_atk): {str(_d): float(move_type_table_edited.loc[_atk, _d])
                                            for _d in move_type_table_edited.columns}
                                for _atk in move_type_table_edited.index}
                            _gc["type_columns"] = list(move_type_columns)
                            _gc["stab_factor"] = float(move_stab_factor)
                    else:
                        st.session_state.pop('move_library', None)
                    # ── 동적 메커니즘 부착 → game_config["mechanisms"] ──
                    if _mech_cfg:
                        _gc["mechanisms"] = _mech_cfg
                    # ── 무브 효과 + 전략 정책 → game_config ──
                    if _move_effects_cfg:
                        _gc["move_effects"] = _move_effects_cfg
                    if _move_policy_sel.startswith("setup_first"):
                        _gc["move_policy"] = "setup_first"
                    # ── 교체 모델 설정 → game_config (게임 중립) ──
                    if _active_count_in and int(_active_count_in) > 0:
                        _gc["active_count"] = int(_active_count_in)
                    if _faint_rule_sel.startswith("예비에서 교체"):
                        _gc["on_active_faint"] = "replace_from_reserve"
                    if _switch_policy_sel.startswith("HP 임계"):
                        _gc["switch_policy"] = {"type": "hp_threshold",
                                                "threshold": float(_switch_thr)}
                    # ── 교체 행동 우선도 티어 → game_config (엔진 기본 6과 다를 때만 저장 → 회귀 0) ──
                    if _switch_prio_in is not None and int(_switch_prio_in) != 6:
                        _gc["switch_priority"] = int(_switch_prio_in)
                    if _gc:
                        st.session_state['game_config'] = _gc
                    else:
                        st.session_state.pop('game_config', None)
                    st.session_state['has_ml_data'] = True if _selected_target_mode == "classification" and selected_target and selected_target != "None" else False
                    st.session_state['library_parsed'] = False
                    if 'ml_coefs' in st.session_state:
                        del st.session_state['ml_coefs']
                    st.rerun()
            
            with c_json:
                preset_dict = {
                    "target_col": selected_target if selected_target != "None" else None,
                    "base_stats_list": base_stats,
                    "gimmick_list": gimmicks,
                    "global_damage_formula": st.session_state['formula_input_ui']
                }
                st.download_button("💾 설정 스키마 프리셋 내보내기 (JSON)", data=json.dumps(preset_dict, ensure_ascii=False, indent=2), file_name="mapping_preset.json", mime="application/json", use_container_width=True)

        return False, "⚠️ 매핑을 완료하고 '파이프라인 시작' 버튼을 눌러야 다음 단계로 진행할 수 있습니다."

    else:
            st.success("✅ 시스템 정의 완료! 전투 데이터 전처리와 승률 예측 모델 학습을 마쳤습니다.")
            if st.button("🔄 매핑 초기화 (Reset Mapping)"):
                st.session_state['mapping_approved'] = False
                st.rerun()
        
            with st.spinner("🤖 ML 모델 학습 및 라이브러리 파싱 중..."):
                target_col = st.session_state.get('target_col')
                numeric_cols = st.session_state.get('system_stats', [])
                gimmick_cols = st.session_state.get('system_gimmicks', [])
                has_combat_log = st.session_state.get('has_ml_data', False) and st.session_state.get('target_mode') != 'regression'
        
                st.session_state['gimmick_uniques'] = {g: df[g].dropna().astype(str).unique().tolist() for g in gimmick_cols}

                if not st.session_state.get('library_parsed', False):
                    parsed_dict = {}
                    is_db_mode = st.session_state.get("input_mode") == "structured_battle_package"
                    
                    if is_db_mode and "db_corpus_raw_tables" in st.session_state and "battle_roster_pokemon" in st.session_state["db_corpus_raw_tables"]:
                        roster_df = st.session_state["db_corpus_raw_tables"]["battle_roster_pokemon"]
                        for idx, row in roster_df.iterrows():
                            char_key = str(row.get("species", row.get("name", f"Unknown_{idx}")))
                            if char_key == "nan" or pd.isna(char_key):
                                continue
                            if char_key not in parsed_dict:
                                parsed_dict[char_key] = {
                                    "stats": {f: float(row[f]) for f in numeric_cols if f in row and pd.notnull(row[f])},
                                    "gimmicks": {g: str(row[g]) for g in gimmick_cols if g in row and pd.notnull(row[g])}
                                }
                    else:
                        for idx, row in df.iterrows():
                            char_key = str(row[char_col])
                            if pd.isna(char_key): continue
                            parsed_dict[char_key] = {
                                "stats": {f: float(row[f]) for f in numeric_cols if f in row and pd.notnull(row[f])},
                                "gimmicks": {g: str(row[g]) for g in gimmick_cols if g in row and pd.notnull(row[g])}
                            }
                    
                    st.session_state['character_library'] = parsed_dict
                    st.session_state['library_parsed'] = True
                    
                    if 'ally_df' in st.session_state: del st.session_state['ally_df']
                    if 'enemy_df' in st.session_state: del st.session_state['enemy_df']

                st.info("✅ 캐릭터 로스터 및 라이브러리가 성공적으로 구축되었습니다!")

                if has_combat_log and 'ml_coefs' not in st.session_state:
                    cols_to_drop = [char_col, target_col] + [c for c in df.columns if 'formula' in c.lower() or 'passive' in c.lower()]
                    X_raw = df.drop(columns=cols_to_drop, errors='ignore')
            
                    trigger_col = next((c for c in X_raw.columns if 'trigger' in c.lower()), None)
                    target_col_feat = next((c for c in X_raw.columns if 'target' in c.lower()), None)
                    if trigger_col and target_col_feat:
                        X_raw['Combo_Trigger_Target'] = X_raw[trigger_col].astype(str) + " & " + X_raw[target_col_feat].astype(str)
                        X_raw = X_raw.drop(columns=[trigger_col, target_col_feat])
                
                    num_cols = X_raw.select_dtypes(include=['int64', 'float64']).columns
                    X_raw[num_cols] = X_raw[num_cols].fillna(0)
            
                    cat_cols = X_raw.select_dtypes(exclude=['int64', 'float64']).columns
                    for col in cat_cols:
                        counts = X_raw[col].value_counts(normalize=True, dropna=False)
                        rare_vals = counts[counts < 0.01].index
                        if len(rare_vals) > 0:
                            X_raw[col] = X_raw[col].apply(lambda x: 'Rare_Combo' if x in rare_vals else x)
                
                    X = pd.get_dummies(X_raw, drop_first=False).astype(float)
                    feature_cols = X.columns.tolist()
                    y = df[target_col].copy()
            
                    valid_idx = y.dropna().index
                    X, y = X.loc[valid_idx], y.loc[valid_idx]
                    y_binary = (y == True).astype(int) if str(y.iloc[0]).lower() in ['true', '1', '1.0'] else y
            
                    st.session_state['numeric_cols'] = numeric_cols
                    unique_classes = pd.Series(y_binary).dropna().unique()
                    if len(unique_classes) < 2:
                        msg = '결과 컬럼에 한 종류의 값만 있어 예측 모델 학습을 건너뜁니다.'
                        if st.session_state.get('input_mode') == 'structured_battle_package':
                            msg = '현재 결과 컬럼이 단일 클래스라 승률 예측 모델 학습은 건너뜁니다.\n전투 재현 검증은 리플레이 이벤트 기반으로 진행됩니다.'
                        st.info(f'ℹ️ {msg}')
                    else:
                        win_idx = X[y_binary == 1].index.tolist()
                        lose_idx = X[y_binary == 0].index.tolist()
                
                        num_pairs = min(5000, len(win_idx) * len(lose_idx))
                        if num_pairs > 0:
                            random.seed(42)
                            pairs_win = list(itertools.product(win_idx, lose_idx)) if len(win_idx) * len(lose_idx) <= 5000 else [(random.choice(win_idx), random.choice(lose_idx)) for _ in range(num_pairs)]
                            pairs_lose = [(l, w) for w, l in pairs_win]
                    
                            delta_X, delta_y = [], []
                            for w, l in pairs_win:
                                delta_X.append(X.loc[w] - X.loc[l])
                                delta_y.append(1)
                            for l, w in pairs_lose:
                                delta_X.append(X.loc[l] - X.loc[w])
                                delta_y.append(0)
                        
                            X_delta = pd.DataFrame(delta_X, columns=X.columns)
                            y_delta = np.array(delta_y)
                    
                            scaler = StandardScaler()
                            X_scaled = scaler.fit_transform(X_delta)
                    
                            lr_model = LogisticRegression(max_iter=1000, C=0.01, n_jobs=-1)
                            lr_model.fit(X_scaled, y_delta)
                    
                            w_scaled = lr_model.coef_[0]
                            stdevs = np.where(scaler.scale_ == 0, 1, scaler.scale_)
                            w_eff = w_scaled / stdevs
                            intercept_eff = lr_model.intercept_[0] - np.sum(w_eff * scaler.mean_)
                    
                            st.session_state['ml_coefs'] = dict(zip(feature_cols, w_eff))
                            st.session_state['ml_intercept'] = intercept_eff
                            st.session_state['numeric_cols'] = numeric_cols
                        else:
                            lr_model = LogisticRegression(max_iter=1000, n_jobs=-1)
                            lr_model.fit(X, y_binary)
                            st.session_state['ml_coefs'] = dict(zip(feature_cols, lr_model.coef_[0]))
                            st.session_state['ml_intercept'] = lr_model.intercept_[0]
                            st.session_state['numeric_cols'] = numeric_cols
    
                        win_idx_bool = y_binary == 1
                        X_win = X[win_idx_bool]
                        if len(X_win) >= 3:
                            kmeans = KMeans(n_clusters=3, random_state=42)
                            clusters = kmeans.fit_predict(X_win)
                            unique, counts = np.unique(clusters, return_counts=True)
                            max_ratio = counts.max() / len(X_win)
                            if max_ratio > 0.8:
                                st.session_state['meta_stagnation_warn'] = True
                                st.session_state['meta_stagnation_ratio'] = max_ratio
                            else:
                                st.session_state['meta_stagnation_warn'] = False
    
                        rf_model = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
                        rf_model.fit(X, y_binary)
                        y_prob = rf_model.predict_proba(X)[:, 1]
                        residuals = np.abs(y_prob - np.array(y_binary))
                        threshold = np.percentile(residuals, 95)
                        anomaly_idx = residuals >= threshold
                
                        anomaly_df = df.loc[X[anomaly_idx].index].copy()
                        anomaly_df['Residual_Error'] = residuals[anomaly_idx]
                        anomaly_df = anomaly_df.sort_values('Residual_Error', ascending=False)
                        st.session_state['anomaly_df'] = anomaly_df
    
                        st.success("✅ 승률 예측 모델 학습이 완료되었습니다!")

            # ═══════════════════════════════════════════════════════════
            # Phase 6 — 모듈 자동 탐지 + Game Profile
            # ═══════════════════════════════════════════════════════════
            try:
                _df_p6 = st.session_state.get('df')
                _stat_cols_p6 = st.session_state.get('system_stats', [])
                _gim_cols_p6 = st.session_state.get('system_gimmicks', [])
                _target_p6 = st.session_state.get('target_col')
                _sig_p6 = (tuple(_df_p6.columns), tuple(_stat_cols_p6),
                           tuple(_gim_cols_p6), _target_p6)
                _gp_p6 = st.session_state.get('game_profile')
                if _gp_p6 is None or _gp_p6.get('signature') != _sig_p6:
                    _detection_p6 = detect_modules(_df_p6, _stat_cols_p6,
                                                   _gim_cols_p6, _target_p6)
                    st.session_state['game_profile'] = {
                        'signature': _sig_p6,
                        'detection': _detection_p6,
                        'overrides': {'resource': 'auto', 'spatial': 'auto', 'deck': 'auto'},
                    }
                _render_game_profile_panel(st.session_state['game_profile'])
            except Exception as _e_p6:
                st.session_state.pop('game_profile', None)
                st.warning(f"⚠️ 모듈 자동 탐지를 건너뜁니다 — Dashboard의 모든 모듈 섹션이 "
                           f"표시됩니다. ({_e_p6})")

            return True, ""
