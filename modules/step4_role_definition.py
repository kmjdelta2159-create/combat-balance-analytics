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

def render_role_definition():
    st.title("2. Role Definition")
    st.markdown("데이터 스키마를 맵핑하고, 전역 공식을 검증한 뒤, AI 기반 심층 밸런스 분석 파이프라인을 실행합니다.")
    
    if "df" not in st.session_state:
        return False, "⚠️ 1단계에서 CSV 데이터를 업로드해야 합니다."

    df = st.session_state["df"]
    char_col = st.session_state.get("char_col", df.columns[0])
    numeric_cols = st.session_state.get("numeric_cols_raw", df.select_dtypes(include=['int64', 'float64']).columns.tolist())

    is_valid = False

    if not st.session_state.get('mapping_approved', False):
        st.markdown("## 🔍 Data Mapping & Live Formula Validator")
        
        binary_cols = [c for c in df.columns if df[c].nunique() == 2 and set(df[c].dropna().unique()).issubset({0, 1, 0.0, 1.0, True, False, '0', '1', 'True', 'False'})]
        target_names = ['win', 'result', 'target', '승리', '결과', 'label', 'is_win']
        inferred_target = next((col for col in binary_cols if col.lower() in target_names), binary_cols[0] if binary_cols else None)

        col1, col2 = st.columns([1, 1.5])
        with col1:
            st.markdown("#### 1. 🎯 Target Variable (승패 결과)")
            selected_target = st.selectbox("타겟 컬럼", binary_cols if binary_cols else ["None"], index=binary_cols.index(inferred_target) if inferred_target in binary_cols else 0)
            
            st.markdown("#### 2. 📊 Base Stats & Gimmicks")
            base_stats = st.multiselect("숫자형 스탯 (Base Stats)", numeric_cols, default=[c for c in numeric_cols if c != selected_target])
            other_cols = [c for c in df.columns if c not in base_stats and c != char_col and c != selected_target]
            gimmicks = st.multiselect("카테고리/기믹 (Gimmicks)", other_cols, default=other_cols)
            
        with col2:
            st.markdown("#### 3. ⚔️ Live Formula Validator")
            if 'formula_input_ui' not in st.session_state:
                st.session_state['formula_input_ui'] = ""
                
            total_vars = len(base_stats) + len(gimmicks)
            
            if total_vars <= 15:
                st.write("변수 칩 (클릭 시 수식 입력창에 삽입됩니다):")
                chip_cols = st.columns(6)
                chip_idx = 0
                
                for stat in base_stats:
                    if chip_cols[chip_idx % 6].button(stat, key=f"chip_s_{stat}"):
                        st.session_state['formula_input_ui'] += stat.lower() + " "
                        st.rerun()
                    chip_idx += 1
                for gim in gimmicks:
                    if chip_cols[chip_idx % 6].button(gim, key=f"chip_g_{gim}"):
                        st.session_state['formula_input_ui'] += gim.lower() + " "
                        st.rerun()
                    chip_idx += 1
            else:
                st.write("변수 선택 (선택한 변수를 수식에 추가합니다):")
                # 축약형 멀티셀렉트 사용
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
            
            eval_env = {str(k).lower(): float(v) if pd.notnull(v) and isinstance(v, (int, float)) else v for k, v in eval_env_raw.items()}
            formula_str_eval = st.session_state['formula_input_ui'].lower().strip()
            
            if formula_str_eval:
                try:
                    res = eval(formula_str_eval, {"__builtins__": None}, eval_env)
                    st.success(f"✅ 연산 성공! 예상 데미지: {res}")
                    is_valid = True
                except Exception as e:
                    st.error(f"❌ 수식 오류: {e}")
            else:
                st.warning("⚠️ 데미지 공식을 입력해주세요.")
                
        st.divider()
        c_btn, c_json = st.columns(2)
        with c_btn:
            if st.button("🚀 분석 파이프라인 시작 및 매핑 저장", disabled=not is_valid, use_container_width=True, type="primary"):
                st.session_state['mapping_approved'] = True
                st.session_state['global_damage_formula'] = st.session_state['formula_input_ui']
                st.session_state['damage_formula'] = st.session_state['formula_input_ui']
                st.session_state['target_col'] = selected_target if selected_target != "None" else None
                st.session_state['target_variable'] = selected_target if selected_target != "None" else None
                st.session_state['system_stats'] = base_stats
                st.session_state['system_gimmicks'] = gimmicks
                st.session_state['has_ml_data'] = True if selected_target and selected_target != "None" else False
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

        return False, "⚠️ 매핑을 완료하고 '분석 파이프라인 시작' 버튼을 눌러야 다음 단계로 진행할 수 있습니다."

    else:
        st.success("✅ 매핑 완료! 백그라운드에서 AI 데이터 전처리 및 ML 파이프라인 연산이 수행되었습니다.")
        if st.button("🔄 매핑 초기화 (Reset Mapping)"):
            st.session_state['mapping_approved'] = False
            st.rerun()
            
        with st.spinner("🤖 ML 모델 학습 및 라이브러리 파싱 중..."):
            target_col = st.session_state.get('target_col')
            numeric_cols = st.session_state.get('system_stats', [])
            gimmick_cols = st.session_state.get('system_gimmicks', [])
            has_combat_log = st.session_state.get('has_ml_data', False)
            
            st.session_state['gimmick_uniques'] = {g: df[g].dropna().astype(str).unique().tolist() for g in gimmick_cols}

            if not st.session_state.get('library_parsed', False):
                parsed_dict = {}
                for idx, row in df.iterrows():
                    char_key = str(row[char_col])
                    parsed_dict[char_key] = {
                        "stats": {f: float(row[f]) for f in numeric_cols if pd.notnull(row[f])},
                        "gimmicks": {g: str(row[g]) for g in gimmick_cols if pd.notnull(row[g])}
                    }
                    
                st.session_state['character_library'].update(parsed_dict)
                st.session_state['library_parsed'] = True
                
                char_keys = list(parsed_dict.keys())
                for i in range(4):
                    if i < len(char_keys): st.session_state[f"Ally_slot_{i}_select"] = char_keys[i]
                    if i + 4 < len(char_keys): st.session_state[f"Enemy_slot_{i}_select"] = char_keys[i + 4]
                
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

                st.success("✅ 로지스틱 회귀 및 앙상블 모델 기반 심층 분석이 완료되었습니다!")

        return True, ""
