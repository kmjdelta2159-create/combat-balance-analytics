"""
Combat Balance Analytics - AI Combat Roster & System Mechanics Extraction Engine
"""
import streamlit as st
import pandas as pd
import numpy as np
import math
import random
import itertools
from scipy.optimize import minimize
from sklearn.ensemble import RandomForestClassifier
from sklearn.cluster import KMeans
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor, export_text
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import euclidean_distances
import plotly.graph_objects as go

# --------------------------------------------------------------------------------
# 1. Page Config & Session State Initialization
# --------------------------------------------------------------------------------
st.set_page_config(page_title="Combat Balance Analytics: Master Balance Engine", page_icon="⚔️", layout="wide")

if 'character_library' not in st.session_state:
    st.session_state['character_library'] = {}
if 'ally_team' not in st.session_state:
    st.session_state['ally_team'] = [None] * 4
if 'enemy_team' not in st.session_state:
    st.session_state['enemy_team'] = [None] * 4
if 'system_stats' not in st.session_state:
    st.session_state['system_stats'] = []

# --------------------------------------------------------------------------------
# 2. Custom CSS & Theme
# --------------------------------------------------------------------------------
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background-color: #0E1117; }
    [data-testid="stSidebar"] { background-color: #161A22; border-right: 1px solid #2D333B; }
    h1, h2, h3, h4, h5, h6, span, p, label {
        color: #E6EDF3 !important;
        font-family: 'Inter', sans-serif;
    }
    .stDataFrame { border-radius: 8px; overflow: hidden; border: 1px solid #30363D; }
    
    [data-testid="stVerticalBlock"] div[style*="border"] {
        border-radius: 12px;
        background-color: #1A1F2B;
        border: 1px solid #30363D !important;
        padding: 10px;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1rem;
    }
    header {
        background-color: transparent !important;
    }
    .stDeployButton {
        display: none !important;
    }
    #MainMenu {
        visibility: hidden !important;
    }
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------------
# 3. Data Loading & Preprocessing
# --------------------------------------------------------------------------------
st.sidebar.title("⚔️ Combat Balance Analytics")
st.sidebar.caption("Dev Master Balance Engine")

st.sidebar.divider()
selected_nav = st.sidebar.radio("Menu", ["GM Mode: Team Setup", "System Mechanics Extraction", "Global Character Builder"], label_visibility="collapsed")
st.sidebar.divider()

st.sidebar.header("📥 Load System Data")
st.sidebar.info(f"📚 현재 라이브러리 캐릭터 총 개수: {len(st.session_state.get('character_library', {}))}명")
uploaded_file = st.sidebar.file_uploader("Upload Combat Logs (CSV)", type=["csv"], help="영웅 ID와 스탯이 포함된 CSV 데이터셋을 업로드하면, 즉시 캐릭터 명단을 자동 구축합니다.")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    char_col = df.columns[0]
    numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    
    if st.session_state.get('current_file_name') != uploaded_file.name:
        st.session_state['current_file_name'] = uploaded_file.name
        st.session_state['mapping_approved'] = False
        st.session_state['formula_input_ui'] = ""

    # --- JSON Preset Logic ---
    preset_file = st.sidebar.file_uploader("Upload Mapping Preset (JSON)", type=["json"], help="저장된 매핑 설정을 불러옵니다.")
    if preset_file:
        import json
        preset_data = json.load(preset_file)
        st.session_state['mapping_approved'] = True
        st.session_state['global_damage_formula'] = preset_data.get('global_damage_formula', '')
        st.session_state['target_col'] = preset_data.get('target_col')
        st.session_state['system_stats'] = preset_data.get('base_stats_list', [])
        st.session_state['system_gimmicks'] = preset_data.get('gimmick_list', [])
        st.session_state['has_ml_data'] = True if preset_data.get('target_col') and preset_data.get('target_col') != "None" else False
        st.session_state['formula_input_ui'] = preset_data.get('global_damage_formula', '')
    
    # --- Auto-Schema Inference & Live Formula Validator ---
    if not st.session_state.get('mapping_approved', False):
        st.markdown("## 🔍 Data Mapping Review")
        st.caption("AI가 추론한 스키마를 확인하고, 글로벌 전투 공식을 검증하세요.")
        
        binary_cols = []
        for c in df.columns:
            unique_vals = set(df[c].dropna().unique())
            if df[c].nunique() == 2 and unique_vals.issubset({0, 1, 0.0, 1.0, True, False, '0', '1', 'True', 'False'}):
                binary_cols.append(c)

        target_names = ['win', 'result', 'target', '승리', '결과', 'label', 'is_win']
        inferred_target = next((col for col in binary_cols if col.lower() in target_names), binary_cols[0] if binary_cols else None)

        col1, col2 = st.columns([1, 1.5])
        with col1:
            st.markdown("#### 1. 🎯 Target Variable")
            selected_target = st.selectbox("승패 결과 변수 (Target)", binary_cols if binary_cols else ["None"], index=binary_cols.index(inferred_target) if inferred_target in binary_cols else 0)
            
            st.markdown("#### 2. 📊 Base Stats & Gimmicks")
            base_stats = st.multiselect("숫자형 스탯 (Base Stats)", numeric_cols, default=[c for c in numeric_cols if c != selected_target])
            other_cols = [c for c in df.columns if c not in base_stats and c != char_col and c != selected_target]
            gimmicks = st.multiselect("카테고리/기믹 (Gimmicks)", other_cols, default=other_cols)
            
        with col2:
            st.markdown("#### 3. ⚔️ Live Formula Validator")
            
            if 'formula_input_ui' not in st.session_state:
                st.session_state['formula_input_ui'] = ""
                
            st.write("변수 칩 (클릭 시 소문자로 삽입):")
            chip_cols = st.columns(6)
            chip_idx = 0
            
            for stat in base_stats:
                if chip_cols[chip_idx % 6].button(stat, key=f"chip_s_{stat}"):
                    st.session_state['formula_input_ui'] += stat.lower()
                    st.rerun()
                chip_idx += 1
            for gim in gimmicks:
                if chip_cols[chip_idx % 6].button(gim, key=f"chip_g_{gim}"):
                    st.session_state['formula_input_ui'] += gim.lower()
                    st.rerun()
                chip_idx += 1
                
            st.text_input("전투 공식 (Damage Formula)", key="formula_input_ui")
            
            st.markdown("**Live Preview (Row 1 거울전 검증)**")
            row1 = df.iloc[0].to_dict() if len(df) > 0 else {}
            eval_env_raw = {s: row1.get(s, 0) for s in base_stats}
            eval_env_raw.update({"target_" + s: row1.get(s, 0) for s in base_stats})
            eval_env_raw["current_health"] = row1.get("current_health", 0)
            eval_env_raw["max_health"] = row1.get("max_health", 0)
            eval_env_raw["target_current_health"] = row1.get("current_health", 0)
            eval_env_raw["target_max_health"] = row1.get("max_health", 0)
            
            eval_env = {str(k).lower(): float(v) if pd.notnull(v) and isinstance(v, (int, float)) else v for k, v in eval_env_raw.items()}
            formula_str_eval = st.session_state['formula_input_ui'].lower().strip()
            
            is_valid = False
            if formula_str_eval:
                try:
                    res = eval(formula_str_eval, {"__builtins__": None}, eval_env)
                    st.success(f"✅ 연산 성공! 결과값: {res}")
                    is_valid = True
                except Exception as e:
                    st.error(f"❌ 수식 오류: {e}")
            else:
                st.warning("⚠️ 수식을 입력해주세요.")
                
        st.divider()
        c_btn, c_json = st.columns(2)
        with c_btn:
            if st.button("🚀 분석 시작 (Confirm)", disabled=not is_valid, use_container_width=True, type="primary"):
                st.session_state['mapping_approved'] = True
                st.session_state['global_damage_formula'] = st.session_state['formula_input_ui']
                st.session_state['target_col'] = selected_target if selected_target != "None" else None
                st.session_state['system_stats'] = base_stats
                st.session_state['system_gimmicks'] = gimmicks
                st.session_state['has_ml_data'] = True if selected_target and selected_target != "None" else False
                st.rerun()
                
        with c_json:
            import json
            preset_dict = {
                "target_col": selected_target if selected_target != "None" else None,
                "base_stats_list": base_stats,
                "gimmick_list": gimmicks,
                "global_damage_formula": st.session_state['formula_input_ui']
            }
            st.download_button("💾 Preset 다운로드 (JSON)", data=json.dumps(preset_dict, ensure_ascii=False, indent=2), file_name="mapping_preset.json", mime="application/json", use_container_width=True)
            
        st.stop()
        
    # --- Post-Mapping Logic ---
    target_col = st.session_state.get('target_col')
    numeric_cols = st.session_state.get('system_stats', [])
    gimmick_cols = st.session_state.get('system_gimmicks', [])
    has_combat_log = st.session_state.get('has_ml_data', False)
    st.session_state['gimmick_uniques'] = {g: df[g].dropna().astype(str).unique().tolist() for g in gimmick_cols}

    # 3. Parse Character Library
    parsed_dict = {}
    for idx, row in df.iterrows():
        char_key = str(row[char_col])
        new_stats = {f: float(row[f]) for f in st.session_state.get('system_stats', []) if pd.notnull(row[f])}
        new_gimmicks = {g: str(row[g]) for g in gimmick_cols if pd.notnull(row[g])}
        
        parsed_dict[char_key] = {
            "stats": new_stats,
            "gimmicks": new_gimmicks
        }
        
    st.session_state['character_library'].update(parsed_dict)
    
    if st.session_state.get('last_processed_file') != uploaded_file.name:
        st.session_state['last_processed_file'] = uploaded_file.name
        
        if 'initial_win_rate' in st.session_state:
            del st.session_state['initial_win_rate']
            
        char_keys = list(parsed_dict.keys())
        for i in range(4):
            if i < len(char_keys):
                st.session_state[f"Ally_slot_{i}_select"] = char_keys[i]
            if i + 4 < len(char_keys):
                st.session_state[f"Enemy_slot_{i}_select"] = char_keys[i + 4]
                
        if 'ally_df' in st.session_state: del st.session_state['ally_df']
        if 'enemy_df' in st.session_state: del st.session_state['enemy_df']
                
        st.rerun()

    st.sidebar.success("✅ 명단 및 자동 편성이 성공적으로 적용되었습니다!")
    
    if has_combat_log:
        cols_to_drop = [char_col, target_col] + [c for c in df.columns if 'formula' in c.lower() or 'passive' in c.lower()]
        X_raw = df.drop(columns=cols_to_drop, errors='ignore')
        
        trigger_col = next((c for c in X_raw.columns if 'trigger' in c.lower()), None)
        target_col_feat = next((c for c in X_raw.columns if 'target' in c.lower()), None)
        
        if trigger_col and target_col_feat:
            X_raw['Combo_Trigger_Target'] = X_raw[trigger_col].astype(str) + " & " + X_raw[target_col_feat].astype(str)
            X_raw = X_raw.drop(columns=[trigger_col, target_col_feat])
            
        num_cols = X_raw.select_dtypes(include=['int64', 'float64']).columns
        X_raw[num_cols] = X_raw[num_cols].fillna(0)
        
        # Rare_Combo 빈도수 제한 (차원 폭발 방어)
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
            if len(win_idx) * len(lose_idx) <= 5000:
                pairs_win = list(itertools.product(win_idx, lose_idx))
            else:
                pairs_win = [(random.choice(win_idx), random.choice(lose_idx)) for _ in range(num_pairs)]
                
            pairs_lose = [(l, w) for w, l in pairs_win]
            
            delta_X = []
            delta_y = []
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
            
            lr_model = LogisticRegression(max_iter=1000, C=0.01)
            lr_model.fit(X_scaled, y_delta)
            
            w_scaled = lr_model.coef_[0]
            stdevs = np.where(scaler.scale_ == 0, 1, scaler.scale_)
            w_eff = w_scaled / stdevs
            intercept_eff = lr_model.intercept_[0] - np.sum(w_eff * scaler.mean_)
            
            st.session_state['ml_coefs'] = dict(zip(feature_cols, w_eff))
            st.session_state['ml_intercept'] = intercept_eff
            st.session_state['numeric_cols'] = numeric_cols
        else:
            lr_model = LogisticRegression(max_iter=1000)
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

        rf_model = RandomForestClassifier(n_estimators=50, random_state=42)
        rf_model.fit(X, y_binary)
        y_prob = rf_model.predict_proba(X)[:, 1]
        residuals = np.abs(y_prob - np.array(y_binary))
        threshold = np.percentile(residuals, 95)
        anomaly_idx = residuals >= threshold
        
        anomaly_df = df.loc[X[anomaly_idx].index].copy()
        anomaly_df['Residual_Error'] = residuals[anomaly_idx]
        anomaly_df = anomaly_df.sort_values('Residual_Error', ascending=False)
        st.session_state['anomaly_df'] = anomaly_df

    else:
        st.success("✅ 명단이 성공적으로 적재되었습니다! (전투 승패 결과가 없어 머신러닝 분석을 건너뜁니다.)")
        st.session_state['has_ml_data'] = False


system_stats = st.session_state.get('system_stats', [])
if system_stats:
    st.sidebar.divider()
    st.sidebar.subheader("⚙️ Dynamic Stat Config")
    
    def_anchor = next((s for s in system_stats if 'atk' in s.lower() or '공격' in s), system_stats[0])
    def_health = next((s for s in system_stats if 'hp' in s.lower() or '체력' in s), system_stats[0])
    def_speed = next((s for s in system_stats if 'spd' in s.lower() or '속도' in s or 'speed' in s.lower()), system_stats[0])
    
    anchor_stat = st.sidebar.selectbox("🎯 Anchor Stat (환산 기준)", system_stats, index=system_stats.index(def_anchor))
    health_stat = st.sidebar.selectbox("❤️ Health Stat (체력/생존 기준)", system_stats, index=system_stats.index(def_health))
    speed_stat = st.sidebar.selectbox("⚡ Speed Stat (턴 속도 기준)", system_stats, index=system_stats.index(def_speed))
    
    st.session_state['anchor_stat'] = anchor_stat
    st.session_state['health_stat'] = health_stat
    st.session_state['speed_stat'] = speed_stat


# --------------------------------------------------------------------------------
# 3.5 Simulation Engines
# --------------------------------------------------------------------------------
element_chart = {
    "Fire": {"strong_against": "Wood", "weak_against": "Water"},
    "Water": {"strong_against": "Fire", "weak_against": "Wood"},
    "Wood": {"strong_against": "Water", "weak_against": "Fire"},
    "Light": {"strong_against": "Dark", "weak_against": ""},
    "Dark": {"strong_against": "Light", "weak_against": ""},
    "Neutral": {"strong_against": "", "weak_against": ""}
}

def get_element_multiplier(atk_elem, def_elem):
    if element_chart.get(atk_elem, {}).get("strong_against") == def_elem: return 1.5
    if element_chart.get(atk_elem, {}).get("weak_against") == def_elem: return 0.5
    return 1.0

def run_simulation(ally_instances, enemy_instances):
    logs = []
    def add_log(msg): logs.append(msg)
    
    participants = []
    for i, inst in enumerate(ally_instances):
        if inst:
            p = inst.copy()
            p["id"] = f"A{i+1}"
            p["team"] = "Ally"
            participants.append(p)
            
    for i, inst in enumerate(enemy_instances):
        if inst:
            p = inst.copy()
            p["id"] = f"E{i+1}"
            p["team"] = "Enemy"
            participants.append(p)

    if not any(p['team'] == 'Ally' for p in participants) or not any(p['team'] == 'Enemy' for p in participants):
        return ["오류: 전투 시뮬레이션을 시작하려면 양 팀 모두 최소 한 명 이상의 캐릭터가 배치되어야 합니다."]

    add_log("⚔️ 전투가 시작됩니다!")
    turn = 1
    max_turns = 50
    
    speed_col = st.session_state.get('speed_stat')
    sys_stats = st.session_state.get('system_stats', [])

    while turn <= max_turns:
        participants.sort(key=lambda x: (-x.get(speed_col, 0) if speed_col else 0, x['id']))
        
        for active_char in participants:
            if active_char.get('current_health', 0) <= 0: continue
            
            # Dynamic Gimmick Extraction
            gimmicks = active_char.get('gimmicks', {})
            passive_col = next((c for c in gimmicks if 'passive' in c.lower()), None)
            passive_logic = gimmicks.get(passive_col, "") if passive_col else ""
            
            trigger_col = next((c for c in gimmicks if 'trigger' in c.lower()), None)
            trigger_val = gimmicks.get(trigger_col, "Active_Cast") if trigger_col else "Active_Cast"
            
            target_col = next((c for c in gimmicks if 'target' in c.lower()), None)
            target_val = gimmicks.get(target_col, "Single_Target") if target_col else "Single_Target"
            
            formula_col = next((c for c in gimmicks if 'formula' in c.lower()), None)
            local_formula = gimmicks.get(formula_col) if formula_col else None
            
            if local_formula and str(local_formula).strip() and str(local_formula).strip() != "None":
                formula_str = str(local_formula)
            else:
                formula_str = st.session_state.get('global_damage_formula', '0')
                if not formula_str: formula_str = "0"
            
            element_col = next((c for c in gimmicks if 'element' in c.lower()), None)
            atk_elem = gimmicks.get(element_col, "Neutral") if element_col else "Neutral"

            # --- [PASSIVE HOOK: On_Turn_Start] ---
            if passive_logic:
                try:
                    exec(passive_logic, {}, {"character": active_char, "trigger": "On_Turn_Start"})
                except Exception as e:
                    add_log(f"  -> ⚠️ 패시브 오류 ({active_char['id']}): {e}")
            
            if trigger_val in ["Active_Cast", "On_Turn_Start"]:
                opponents = [p for p in participants if p['team'] != active_char['team'] and p.get('current_health', 0) > 0]
                if not opponents:
                    add_log(f"🏆 {active_char['team']} 진영 궤멸!")
                    return logs

                targets = []
                if target_val == "Single_Target": targets = [opponents[0]]
                elif target_val in ["AoE_All", "AoE_FrontRow"]: targets = opponents
                elif target_val == "Lowest_HP": targets = [min(opponents, key=lambda x: x.get('current_health', 0))]
                elif target_val == "Attacker": targets = [opponents[0]]
                else: targets = [opponents[0]]
                
                if targets:
                    add_log(f"[Turn {turn}] {active_char['id']} ({active_char['name']}) 스킬 사용! 타겟: {', '.join([t['id'] for t in targets])}")
                    for t in targets:
                        # --- [PASSIVE HOOK: On_Attack] ---
                        if passive_logic:
                            try:
                                exec(passive_logic, {}, {"character": active_char, "target": t, "trigger": "On_Attack"})
                            except: pass
                            
                        try:
                            # Dynamic Formula Env
                            eval_env_raw = {s: active_char.get(s, 0) for s in sys_stats}
                            eval_env_raw.update({"target_" + s: t.get(s, 0) for s in sys_stats})
                            eval_env_raw["current_health"] = active_char.get("current_health", 0)
                            eval_env_raw["max_health"] = active_char.get("max_health", 0)
                            eval_env_raw["target_current_health"] = t.get("current_health", 0)
                            eval_env_raw["target_max_health"] = t.get("max_health", 0)
                            
                            eval_env = {str(k).lower(): float(v) for k, v in eval_env_raw.items()}
                            formula_str_eval = str(formula_str).lower()
                            if not formula_str_eval: formula_str_eval = "0"
                            
                            try:
                                raw_dmg = max(0, int(float(eval(formula_str_eval, {"__builtins__": None}, eval_env))))
                            except Exception:
                                raw_dmg = 0
                            
                            # Elemental Matchup
                            t_gimmicks = t.get('gimmicks', {})
                            t_element_col = next((c for c in t_gimmicks if 'element' in c.lower()), None)
                            def_elem = t_gimmicks.get(t_element_col, "Neutral") if t_element_col else "Neutral"
                            
                            elem_mult = get_element_multiplier(atk_elem, def_elem)
                            
                            dmg = int(raw_dmg * elem_mult)
                            elem_text = f" (상성 {elem_mult}x 적용)" if elem_mult != 1.0 else ""
                            
                            t['current_health'] = max(0, t['current_health'] - dmg)
                            add_log(f"  -> {dmg}의 피해를 입혔습니다!{elem_text} {t['id']} 잔여 체력: {t['current_health']}/{t['max_health']}")
                            
                            # --- [PASSIVE HOOK: On_Hit] ---
                            t_passive_col = next((c for c in t_gimmicks if 'passive' in c.lower()), None)
                            t_passive_logic = t_gimmicks.get(t_passive_col, "") if t_passive_col else ""
                            
                            if t_passive_logic and t.get('current_health', 0) > 0:
                                try:
                                    exec(t_passive_logic, {}, {"character": t, "attacker": active_char, "trigger": "On_Hit"})
                                except: pass
                            
                            if t['current_health'] <= 0: add_log(f"  ☠️ {t['id']} 캐릭터 파괴!")
                        except Exception as e:
                            add_log(f"  -> ❌ Formula error for {active_char['id']}: {e}")
            
            alives = [p for p in participants if p.get('current_health', 0) > 0]
            teams_alive = set(p['team'] for p in alives)
            if len(teams_alive) <= 1:
                winner = list(teams_alive)[0] if teams_alive else "None"
                add_log(f"🏆 전투 종료! {turn}턴 만에 {winner} 진영이 승리했습니다!")
                return logs
        turn += 1
        
    add_log("⏱️ 최대 턴 수 초과. 무승부로 종료.")
    return logs

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
                if trigger_col and target_col:
                    if str(inst.get('gimmicks', {}).get(trigger_col)) == parts[0] and str(inst.get('gimmicks', {}).get(target_col)) == parts[1]:
                        val += weight
        else:
            for g in sys_gimmicks:
                prefix = f"{g}_"
                if feat.startswith(prefix):
                    val_cat = feat[len(prefix):]
                    if str(inst.get('gimmicks', {}).get(g)) == val_cat:
                        val += weight
    return val

def calculate_win_rate(ally_instances, enemy_instances):
    if not st.session_state.get('has_ml_data') or 'ml_coefs' not in st.session_state:
        return None
    coefs = st.session_state['ml_coefs']
    intercept = st.session_state['ml_intercept']
    
    ally_score = sum([calc_instance_score(inst, coefs) for inst in ally_instances if inst])
    enemy_score = sum([calc_instance_score(inst, coefs) for inst in enemy_instances if inst])
    
    diff = ally_score - enemy_score + intercept
    try:
        return (1.0 / (1.0 + math.exp(-diff))) * 100
    except OverflowError:
        return 100.0 if diff > 0 else 0.0

def run_monte_carlo_formula(ally_instances, enemy_instances, coefs, intercept, runs=10000):
    ally_base = sum([calc_instance_score(inst, coefs) for inst in ally_instances if inst])
    enemy_base = sum([calc_instance_score(inst, coefs) for inst in enemy_instances if inst])
    
    np.random.seed(42)
    ally_scores = np.random.normal(ally_base, max(0.01, abs(ally_base * 0.05)), runs)
    enemy_scores = np.random.normal(enemy_base, max(0.01, abs(enemy_base * 0.05)), runs)
    
    diffs = ally_scores - enemy_scores + intercept
    probs = 1.0 / (1.0 + np.exp(-diffs))
    return probs * 100

# --------------------------------------------------------------------------------
# 4. Tabs Rendering
# --------------------------------------------------------------------------------
def get_default_df(team_keys):
    data = []
    sys_stats = st.session_state.get('system_stats', [])
    sys_gimmicks = st.session_state.get('system_gimmicks', [])
    for i in range(4):
        hero_name = team_keys[i] if i < len(team_keys) else "비어 있음"
        row_dict = {"Hero": hero_name}
        if hero_name and hero_name != "비어 있음" and hero_name in st.session_state['character_library']:
            lib_char = st.session_state['character_library'][hero_name]
            stats = lib_char['stats']
            gimmicks = lib_char.get('gimmicks', {})
            for s in sys_stats:
                row_dict[s] = float(stats.get(s, 0.0))
            for g in sys_gimmicks:
                row_dict[g] = gimmicks.get(g, "None")
        else:
            for s in sys_stats:
                row_dict[s] = 0.0
            for g in sys_gimmicks:
                row_dict[g] = "None"
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
            if hero_name and hero_name != "비어 있음" and hero_name in st.session_state['character_library']:
                lib_char = st.session_state['character_library'][hero_name]
                for s in sys_stats:
                    new_df.loc[i, s] = float(lib_char['stats'].get(s, 0.0))
                for g in sys_gimmicks:
                    new_df.loc[i, g] = lib_char.get('gimmicks', {}).get(g, "None")
            elif hero_name == "비어 있음":
                for s in sys_stats:
                    new_df.loc[i, s] = 0.0
                for g in sys_gimmicks:
                    new_df.loc[i, g] = "None"
    return changed, new_df

# --------------------------------------------------------------------------------
# [TAB 1] GM Mode: In-Game Team Setup Screen
# --------------------------------------------------------------------------------
if selected_nav == "GM Mode: Team Setup":
    if not st.session_state.get('system_stats'):
        st.warning("⚠️ 좌측 사이드바에서 System Data(CSV)를 업로드하여 스탯 스키마를 초기화해주세요.")

    st.markdown("""
    <style>
        /* Sticky Right Pane - Zero Scroll Strategy */
        [data-testid="column"]:nth-child(2) {
            position: sticky;
            top: 4rem;
            height: max-content;
            max-height: calc(100vh - 5rem);
            overflow-y: auto;
            padding-left: 1rem;
            padding-right: 0.5rem;
            z-index: 10;
        }
        .stTabs { overflow: visible !important; }
    </style>
    """, unsafe_allow_html=True)
    
    df_margin = None
    sys_stats = st.session_state.get('system_stats', [])
    
    if st.session_state.get('has_ml_data') and 'ml_coefs' in st.session_state:
        coefs = st.session_state['ml_coefs']
        orig_numeric_cols = st.session_state.get('numeric_cols', [])
        base_stat_feat = st.session_state.get('anchor_stat')
        if not base_stat_feat or base_stat_feat not in coefs:
            base_stat_feat = next((f for f, c in coefs.items() if f in orig_numeric_cols), list(coefs.keys())[0] if coefs else None)
        
        if base_stat_feat:
            base_marginal = float(coefs.get(base_stat_feat, 0.0001) * 0.25 * 100)
            if base_marginal == 0: base_marginal = 0.0001
            
            m_data_base = []
            m_data_combo = []
            for feat, coef in coefs.items():
                marginal = float(coef * 0.25 * 100)
                is_cat = feat not in orig_numeric_cols
                conversion_val = marginal / base_marginal
                
                if feat == base_stat_feat:
                    conv_text = f"기준 ({base_stat_feat} 1.0 포인트 분량)"
                else:
                    conv_text = f"{base_stat_feat} {conversion_val:.1f} 포인트 분량"
                    
                row_data = {
                    "요소 이름": feat,
                    "승률 변화(%p)": f"{marginal:+.3f}%p",
                    "환산 가치": conv_text,
                    "절대 가치": abs(marginal),
                    "원시 가치": marginal
                }
                if is_cat:
                    m_data_combo.append(row_data)
                else:
                    m_data_base.append(row_data)
                    
            df_margin_base = pd.DataFrame(m_data_base).sort_values("원시 가치", ascending=False) if m_data_base else pd.DataFrame()
            df_margin_combo = pd.DataFrame(m_data_combo).sort_values("원시 가치", ascending=False) if m_data_combo else pd.DataFrame()
            
            if not df_margin_combo.empty:
                df_margin_combo["랭킹"] = [f"{i}위" for i in range(1, len(df_margin_combo) + 1)]
            
            if not df_margin_combo.empty or not df_margin_base.empty:
                df_margin = pd.concat([df_margin_combo, df_margin_base]).sort_values("원시 가치", ascending=False)
    
    col_input, col_output = st.columns([1.2, 1])
    
    sys_gimmicks = st.session_state.get('system_gimmicks', [])
    all_heroes = ["비어 있음"] + list(st.session_state['character_library'].keys())
    
    if 'ally_df' not in st.session_state:
        ally_keys = [st.session_state.get(f"Ally_slot_{i}_select", "비어 있음") for i in range(4)]
        st.session_state['ally_df'] = get_default_df(ally_keys)
    if 'enemy_df' not in st.session_state:
        enemy_keys = [st.session_state.get(f"Enemy_slot_{i}_select", "비어 있음") for i in range(4)]
        st.session_state['enemy_df'] = get_default_df(enemy_keys)
        
    with col_input:
        st.markdown("### ⚔️ 조작부: 파티 편성 및 스탯 조정")
        st.caption("표의 셀을 직접 클릭하여 스탯을 수정하면, 우측 예상 승률 게이지에 즉시 반영됩니다.")

        def calc_char_value(row, coefs, base_coef):
            if not coefs or row["Hero"] == "비어 있음" or pd.isna(row["Hero"]):
                return 0.0
            val = 0.0
            for feat, weight in coefs.items():
                if feat in sys_stats:
                    val += float(row.get(feat, 0)) * weight
                elif feat.startswith('Combo_Trigger_Target_'):
                    val_cat = feat.replace('Combo_Trigger_Target_', '')
                    parts = val_cat.split(" & ")
                    if len(parts) == 2:
                        trigger_col = next((c for c in sys_gimmicks if 'trigger' in c.lower()), None)
                        target_col = next((c for c in sys_gimmicks if 'target' in c.lower()), None)
                        if trigger_col and target_col:
                            if str(row.get(trigger_col)) == parts[0] and str(row.get(target_col)) == parts[1]:
                                val += weight
                else:
                    for g in sys_gimmicks:
                        prefix = f"{g}_"
                        if feat.startswith(prefix):
                            val_cat = feat[len(prefix):]
                            if str(row.get(g)) == val_cat:
                                val += weight
            return val / base_coef if base_coef != 0 else val

        coef_data = st.session_state.get('ml_coefs', {})
        base_stat_feat_val = st.session_state.get('anchor_stat')
        if not base_stat_feat_val or base_stat_feat_val not in coef_data:
            base_stat_feat_val = next((f for f, c in coef_data.items() if f in sys_stats), list(coef_data.keys())[0] if coef_data else None)
        base_coef_val = coef_data.get(base_stat_feat_val, 0.0001) if base_stat_feat_val else 0.0001
        
        st.session_state['ally_df']['Total_Value'] = st.session_state['ally_df'].apply(lambda r: calc_char_value(r, coef_data, base_coef_val), axis=1)
        st.session_state['enemy_df']['Total_Value'] = st.session_state['enemy_df'].apply(lambda r: calc_char_value(r, coef_data, base_coef_val), axis=1)

        ally_team_total = st.session_state['ally_df']['Total_Value'].sum()
        enemy_team_total = st.session_state['enemy_df']['Total_Value'].sum()
        team_delta = ally_team_total - enemy_team_total

        column_config = {
            "Hero": st.column_config.SelectboxColumn("Hero", options=all_heroes),
            "Total_Value": st.column_config.NumberColumn("Total_Value", format="%.2f", disabled=True)
        }
        for s in sys_stats:
            column_config[s] = st.column_config.NumberColumn(s, format="%.1f")
        for g in sys_gimmicks:
            unique_gimmicks = st.session_state.get('gimmick_uniques', {}).get(g, ["None"])
            column_config[g] = st.column_config.SelectboxColumn(g, options=unique_gimmicks)
        
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

        def df_to_instances(df):
            instances = []
            h_stat = st.session_state.get('health_stat')
            for _, row in df.iterrows():
                if row["Hero"] and row["Hero"] != "비어 있음" and not pd.isna(row["Hero"]):
                    inst = {"name": row["Hero"], "gimmicks": {}}
                    for g in sys_gimmicks:
                        inst["gimmicks"][g] = row.get(g, "None")
                    for s in sys_stats:
                        inst[s] = float(row[s])
                        
                    if h_stat and h_stat in sys_stats:
                        inst['current_health'] = inst[h_stat]
                        inst['max_health'] = inst[h_stat]
                    else:
                        inst['current_health'] = 1.0
                        inst['max_health'] = 1.0
                        
                    instances.append(inst)
            return instances
        
        ally_instances = df_to_instances(st.session_state['ally_df'])
        enemy_instances = df_to_instances(st.session_state['enemy_df'])
        
        if df_margin is not None:
            st.markdown("<br>", unsafe_allow_html=True)
            tc1, tc2 = st.columns(2)
            with tc1:
                with st.expander("💰 기본 스탯 환율표", expanded=True):
                    st.dataframe(df_margin_base[["요소 이름", "승률 변화(%p)", "환산 가치"]], use_container_width=True, hide_index=True)
            with tc2:
                with st.expander("📖 전체 기믹 시너지 사전", expanded=True):
                    st.dataframe(df_margin_combo[["랭킹", "요소 이름", "승률 변화(%p)", "환산 가치"]], use_container_width=True, hide_index=True)

    with col_output:
        st.markdown("### 📊 결과부: 승률 및 분석")
        
        if st.session_state.get('meta_stagnation_warn'):
            ratio = st.session_state.get('meta_stagnation_ratio', 0)
            st.error(f"🚨 **메타 고착화 위험 감지:** 지배적 조합 비중 {ratio*100:.1f}%", icon="⚠️")

        current_win_rate = calculate_win_rate(ally_instances, enemy_instances) if st.session_state.get('has_ml_data') else None
        
        m1, m2 = st.columns(2)
        with m1:
            if current_win_rate is not None:
                delta_val = current_win_rate - st.session_state.get('initial_win_rate', current_win_rate)
                st.session_state['initial_win_rate'] = st.session_state.get('initial_win_rate', current_win_rate)
                st.metric("🏆 실시간 예측 승률", f"{current_win_rate:.1f}%", f"{delta_val:+.2f}% vs 초기")
            else:
                st.metric("🏆 실시간 예측 승률", "N/A", "데이터 부족")
        with m2:
            mc_metric_placeholder = st.empty()
            mc_metric_placeholder.metric("🎲 Monte Carlo (1만회)", "대기 중", "시뮬레이션 필요", delta_color="off")

        if current_win_rate is not None:
            if current_win_rate >= 50:
                st.markdown(f"<p style='color: #4B9BFF; margin-bottom: 2px; font-size: 14px;'><b>🔵 Ally Advantage ({current_win_rate:.1f}%)</b></p>", unsafe_allow_html=True)
            else:
                st.markdown(f"<p style='color: #FF4B4B; margin-bottom: 2px; font-size: 14px;'><b>🔴 Enemy Advantage ({(100 - current_win_rate):.1f}%)</b></p>", unsafe_allow_html=True)
            st.progress(current_win_rate / 100.0)
        else:
            st.markdown("<div style='margin-top: 10px; color: gray;'>전투 준비중...</div>", unsafe_allow_html=True)
            
        if df_margin is not None:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### 📈 파워 기믹 & 최우선 스탯 (Top 5 요소)")
            top_m_data = df_margin.head(5)
            fig_m = go.Figure(go.Bar(
                x=top_m_data["절대 가치"],
                y=top_m_data["요소 이름"].astype(str),
                orientation='h',
                marker_color='#4B9BFF'
            ))
            fig_m.update_layout(
                template="plotly_dark",
                height=200, margin=dict(l=0, r=0, t=10, b=0),
                xaxis_title="가치 기여도(Abs)", yaxis_title=""
            )
            fig_m.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_m, use_container_width=True, config={'displayModeBar': False})

        st.divider()

        btn_col1, btn_col2 = st.columns(2)
        mc_results_placeholder = st.empty()
        
        with btn_col1:
            if st.button("⚔️ 단일 전투 (1회)", type="primary", use_container_width=True):
                with st.spinner("단일 전투 중..."):
                    battle_logs = run_simulation(ally_instances, enemy_instances)
                    with mc_results_placeholder.container():
                        st.markdown("#### 📜 1회 전투 로그")
                        log_container = st.container(height=300)
                        with log_container:
                            for log in battle_logs:
                                if "🏆" in log or "⚔️" in log: st.markdown(f"**{log}**")
                                elif "❌" in log or "☠️" in log: st.error(log)
                                elif "->" in log: st.caption(log)
                                else: st.text(log)
        with btn_col2:
            if st.button("🎲 1만회 Monte Carlo", use_container_width=True):
                if st.session_state.get('has_ml_data'):
                    with st.spinner("Executing 1만 MC runs..."):
                        probs = run_monte_carlo_formula(ally_instances, enemy_instances, st.session_state['ml_coefs'], st.session_state['ml_intercept'])
                        mean_p, std_p = np.mean(probs), np.std(probs)
                        mc_metric_placeholder.metric("🎲 Monte Carlo (1만회)", f"{mean_p:.1f}%", f"±{std_p:.2f}%", delta_color="normal")
                        with mc_results_placeholder.container():
                            st.markdown("#### 🎲 MC 승률 분포 (5% 노이즈)")
                            fig = go.Figure(data=[go.Histogram(x=probs, nbinsx=30, marker_color='#8A2BE2')])
                            fig.update_layout(
                                template="plotly_dark", height=200,
                                xaxis_title="Win Rate (%)", yaxis_title="Frequency",
                                margin=dict(l=0, r=0, t=10, b=0)
                            )
                            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# --------------------------------------------------------------------------------
# [TAB 2] System Mechanics Extraction
# --------------------------------------------------------------------------------
elif selected_nav == "System Mechanics Extraction":
    st.markdown("## 🔍 Engine Logic Reverse-Engineering")
    st.caption("실제 게임 데이터 기반으로 숨겨진 엔진 내부의 수식(Formula)과 조건부 분기(if-else)를 역추적합니다.")
    
    if uploaded_file is not None and 'df' in locals():
        target_candidates = list(df.columns.drop(char_col, errors='ignore'))
        target_col_tab2 = st.selectbox("🎯 역설계 타겟 변수 선택 (Target Variable)", target_candidates)
        
        cols_to_drop_tab2 = [char_col, target_col_tab2] + [c for c in df.columns if 'formula' in c.lower() or 'passive' in c.lower()]
        X_engine_raw = df.drop(columns=cols_to_drop_tab2, errors='ignore')
        
        trigger_col_engine = next((c for c in X_engine_raw.columns if 'trigger' in c.lower()), None)
        target_col_engine = next((c for c in X_engine_raw.columns if 'target' in c.lower()), None)
        
        if trigger_col_engine and target_col_engine:
            X_engine_raw['Combo_Trigger_Target'] = X_engine_raw[trigger_col_engine].astype(str) + " & " + X_engine_raw[target_col_engine].astype(str)
            X_engine_raw = X_engine_raw.drop(columns=[trigger_col_engine, target_col_engine])
            
        num_cols_engine = X_engine_raw.select_dtypes(include=['int64', 'float64']).columns
        X_engine_raw[num_cols_engine] = X_engine_raw[num_cols_engine].fillna(0)
        
        cat_cols_engine = X_engine_raw.select_dtypes(exclude=['int64', 'float64']).columns
        for col in cat_cols_engine:
            counts = X_engine_raw[col].value_counts(normalize=True, dropna=False)
            rare_vals = counts[counts < 0.01].index
            if len(rare_vals) > 0:
                X_engine_raw[col] = X_engine_raw[col].apply(lambda x: 'Rare_Combo' if x in rare_vals else x)
                
        X_engine = pd.get_dummies(X_engine_raw, drop_first=False).astype(float)
        y_engine = df.loc[X_engine.index, target_col_tab2].dropna()
        
        common_idx = X_engine.index.intersection(y_engine.index)
        X_engine = X_engine.loc[common_idx]
        y_engine = y_engine.loc[common_idx]
        
        if len(X_engine) > 10:
            st.divider()
            
            st.subheader("🧮 1. Algebraic Formula Extractor (데미지/결과 공식 역산)")
            lr_engine = LinearRegression()
            lr_engine.fit(X_engine, y_engine)
            
            formula_terms = []
            for feat, coef in zip(X_engine.columns, lr_engine.coef_):
                c_val = coef[0] if isinstance(coef, np.ndarray) else coef
                if abs(c_val) > 0.0001:
                    formula_terms.append(f"({feat} * {c_val:.4f})")
            
            intercept = lr_engine.intercept_
            i_val = intercept[0] if isinstance(intercept, np.ndarray) else intercept
            sign = "+" if i_val >= 0 else "-"
            
            formula_str = f"{target_col_tab2} = " + " + ".join(formula_terms).replace("+ -", "- ") + f" {sign} {abs(i_val):.4f}"
            st.code(formula_str, language="python")
            
            st.subheader("🌳 2. Decision Logic Decompiler (if-else 조건문 역추적)")
            
            is_clf = len(np.unique(y_engine)) <= 10
            if is_clf:
                dt_engine = DecisionTreeClassifier(max_depth=4, min_samples_leaf=3, random_state=42)
                y_engine = y_engine.astype(int)
            else:
                dt_engine = DecisionTreeRegressor(max_depth=4, min_samples_leaf=3, random_state=42)
            
            dt_engine.fit(X_engine, y_engine)
            tree_text = export_text(dt_engine, feature_names=list(X_engine.columns))
            
            def parse_tree_to_python(tree_str):
                py_code = []
                last_depth_seen = {}
                lines = tree_str.strip().split('\n')
                for line in lines:
                    if '---' not in line: continue
                    depth = line.count('|') - 1
                    indent = '    ' * depth
                    content = line.split('--- ')[1].strip()
                    
                    if content.startswith('class:') or content.startswith('value:'):
                        val = content.split(': ')[1].strip().strip("[]")
                        try:
                            v = float(val)
                            if v.is_integer(): val = str(int(v))
                            else: val = f"{v:.3f}"
                        except: pass
                        
                        if is_clf and val in ['0', '1']:
                            val = '"Victory (Prob: High)"' if val == '1' else '"Defeat"'
                            
                        py_code.append(f"{indent}    return {val}")
                    else:
                        feat = content.split()[0]
                        if last_depth_seen.get(depth) == feat:
                            py_code.append(f"{indent}elif ({content}):")
                        else:
                            py_code.append(f"{indent}if ({content}):")
                            last_depth_seen[depth] = feat
                return "\n".join(py_code)
            
            decompiled_code = parse_tree_to_python(tree_text)
            st.code(f"def evaluate_logic({', '.join(X_engine.columns)}):\n{decompiled_code}", language="python")
            
            st.divider()
            st.subheader("⚠️ 수동 검토 필요: 비선형 기믹/스킬 이상치 로그")
            st.caption("랜덤 포레스트 예측 확률과 실제 전투 결과의 오차(잔차)가 가장 큰 상위 5% 데이터입니다. 판이 뒤집힌 경기일 가능성이 높습니다.")
            if 'anomaly_df' in st.session_state:
                st.dataframe(st.session_state['anomaly_df'], use_container_width=True)
            
        else:
            st.warning("분석을 위한 데이터 샘플이 부족합니다. (최소 10개 이상)")
    else:
        st.info("⚠️ 데이터 로딩 대기 중. (사이드바에서 CSV를 업로드해주세요)")

# --------------------------------------------------------------------------------
# [TAB 3] Global Character Builder
# --------------------------------------------------------------------------------
elif selected_nav == "Global Character Builder":
    st.markdown("## 🛠️ Global Character Builder")
    
    # --- Data-Driven Target Optimizer Logic ---
    st.markdown("### 👑 Data-Driven Target Optimizer (타겟팅 스탯 자동 분배)")
    st.caption("데이터 기반 제약 조건 하에서, 사용자가 설정한 '희망 승률'에 가장 근접하는 스탯 분배를 탐색합니다.")
    
    sys_stats = st.session_state.get('system_stats', [])
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        target_win_rate = st.slider("🎯 희망 승률 (Target Win Rate, %)", min_value=0.0, max_value=100.0, value=50.0, step=0.1)
    with col_t2:
        target_team = st.radio("🤝 합류할 진영 선택 (Target Team)", ["Ally", "Enemy"], horizontal=True, help="Ally 선택 시 아군 1번 슬롯, Enemy 선택 시 적군 1번 슬롯의 캐릭터를 대체한다고 가정합니다.")
    
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        opt_budget = st.number_input("💰 목표 총합 체급 예산 (Target Stat Budget)", min_value=10.0, max_value=50000.0, value=1500.0, step=50.0)
    with col_opt2:
        std_n = st.slider("📏 탐색 범위 (Standard Deviation Multiplier, N)", min_value=0.1, max_value=5.0, value=1.0, step=0.1, help="원본 데이터의 스탯별 표준편차에 N을 곱하여 상하한 탐색 범위를 결정합니다. 값이 작을수록 평균 비율을 강하게 유지합니다.")
    
    if st.button("🚀 데이터 기반 스탯 최적화 (Optimize)", use_container_width=True):
        if not st.session_state.get('has_ml_data'):
            st.warning("데이터가 부족하거나 승패(Win/Loss) 타겟 변수가 없습니다.")
        elif not sys_stats:
            st.warning("시스템 스탯 스키마가 로드되지 않았습니다.")
        elif 'df' not in locals():
            st.warning("원본 데이터프레임이 로드되지 않았습니다. (데이터를 먼저 업로드해주세요)")
        else:
            with st.spinner("최적화 연산 중... (SLSQP)"):
                coefs = st.session_state['ml_coefs']
                intercept = st.session_state['ml_intercept']
                
                # 원본 데이터 통계 계산 (결측치 제외)
                means = df[sys_stats].mean().fillna(0).values
                stds = df[sys_stats].std().fillna(1).values
                sum_means = np.sum(means) if np.sum(means) > 0 else 1.0
                
                # 예산 비율에 맞춘 스케일링
                scale_ratio = opt_budget / sum_means
                scaled_means = means * scale_ratio
                scaled_stds = stds * scale_ratio
                
                bounds = []
                for m, s in zip(scaled_means, scaled_stds):
                    lower = max(0, m - s * std_n)
                    upper = max(lower + 0.1, m + s * std_n)
                    bounds.append((lower, upper))
                    
                x0 = scaled_means.copy()
                
                # 적군 스코어 (Enemy 합류 시 1번 슬롯 제외)
                enemy_const_score = 0.0
                if 'enemy_df' in st.session_state:
                    for idx, row in st.session_state['enemy_df'].iterrows():
                        if (target_team != "Enemy" or idx > 0) and row["Hero"] and row["Hero"] != "비어 있음" and not pd.isna(row["Hero"]):
                            inst = {"gimmicks": {g: row.get(g, "None") for g in st.session_state.get('system_gimmicks', [])}}
                            for s in sys_stats: inst[s] = float(row.get(s, 0.0))
                            enemy_const_score += calc_instance_score(inst, coefs)
                
                # 아군 스코어 (Ally 합류 시 1번 슬롯 제외)
                ally_const_score = 0.0
                if 'ally_df' in st.session_state:
                    for idx, row in st.session_state['ally_df'].iterrows():
                        if (target_team != "Ally" or idx > 0) and row["Hero"] and row["Hero"] != "비어 있음" and not pd.isna(row["Hero"]):
                            inst = {"gimmicks": {g: row.get(g, "None") for g in st.session_state.get('system_gimmicks', [])}}
                            for s in sys_stats: inst[s] = float(row.get(s, 0.0))
                            ally_const_score += calc_instance_score(inst, coefs)
                            
                # 현재 설정된 캐릭터 기본 기믹 스코어
                cur_gimmicks = {g: st.session_state.get(f'builder_gimmick_{g}', "None") for g in st.session_state.get('system_gimmicks', [])}
                
                cat_score = calc_instance_score({
                    "gimmicks": cur_gimmicks
                }, coefs)

                def objective(x):
                    stat_score = 0.0
                    for stat_name, stat_val in zip(sys_stats, x):
                        stat_score += stat_val * coefs.get(stat_name, 0.0)
                    
                    if target_team == "Ally":
                        ally_total = ally_const_score + cat_score + stat_score
                        diff = ally_total - enemy_const_score + intercept
                    else:
                        enemy_total = enemy_const_score + cat_score + stat_score
                        diff = ally_const_score - enemy_total + intercept
                        
                    try:
                        prob = 1.0 / (1.0 + math.exp(-diff))
                    except OverflowError:
                        prob = 1.0 if diff > 0 else 0.0
                        
                    return abs(prob * 100.0 - target_win_rate)

                # 제약조건: 총합 = 목표 예산
                constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - opt_budget})
                
                result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints)
                
                if result.success:
                    # 정교한 prob 다시 계산
                    best_stat_score = 0.0
                    for stat_name, stat_val in zip(sys_stats, result.x):
                        best_stat_score += stat_val * coefs.get(stat_name, 0.0)
                    if target_team == "Ally":
                        best_diff = (ally_const_score + cat_score + best_stat_score) - enemy_const_score + intercept
                    else:
                        best_diff = ally_const_score - (enemy_const_score + cat_score + best_stat_score) + intercept
                    try:
                        best_prob = 1.0 / (1.0 + math.exp(-best_diff)) * 100.0
                    except OverflowError:
                        best_prob = 100.0 if best_diff > 0 else 0.0

                    st.success(f"최적화 완료! 목표 승률 {target_win_rate}% 대비 예측 승률 {best_prob:.2f}% (오차 {abs(best_prob - target_win_rate):.2f}%p)")
                    for i, stat in enumerate(sys_stats):
                        st.session_state[f'builder_stat_input_{stat}'] = float(result.x[i])
                else:
                    st.error("최적화에 실패했습니다. (탐색 범위를 넓히거나 예산을 조정해보세요)")

    st.divider()

    with st.expander("Create Custom Character Database Entry", expanded=True):
        char_name = st.text_input("Character Name", "New Hero Template")
        
        sys_gimmicks = st.session_state.get('system_gimmicks', [])
        if sys_gimmicks:
            g_cols = st.columns(min(4, len(sys_gimmicks)))
            for i, g in enumerate(sys_gimmicks):
                opts = st.session_state.get('gimmick_uniques', {}).get(g, ["None"])
                with g_cols[i % len(g_cols)]:
                    st.session_state[f'builder_gimmick_{g}'] = st.selectbox(f"Global {g}", opts, key=f'opt_g_{g}')
        
        b_stats = {}
        if sys_stats:
            cols = st.columns(min(5, len(sys_stats)))
            for i, stat in enumerate(sys_stats):
                if f'builder_stat_input_{stat}' not in st.session_state:
                    st.session_state[f'builder_stat_input_{stat}'] = 100.0
                with cols[i % len(cols)]:
                    b_stats[stat] = st.number_input(f"Global {stat}", key=f'builder_stat_input_{stat}')
        else:
            st.info("⚠️ CSV Data를 업로드하면 스탯 설정 창이 확장됩니다.")
            
        if st.button("Save to Global Library", type="primary"):
            lib = st.session_state.get('character_library', {})
            final_stats = {s: st.session_state.get(f'builder_stat_input_{s}', 100.0) for s in sys_stats}
            final_gimmicks = {g: st.session_state.get(f'builder_gimmick_{g}', "None") for g in sys_gimmicks}
            
            lib[char_name] = {
                "stats": final_stats, 
                "gimmicks": final_gimmicks
            }
            st.session_state['character_library'] = lib
            st.success(f"'{char_name}' 템플릿 신규 저장 완료! (로스터로 자동 동기화됨)")
            st.rerun()

else:
    # Empty State (Onboarding) UI
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.title("⚔️ Combat Balance Analytics")
    st.info("👋 **환영합니다!** 좌측 사이드바에서 전투 로그(CSV)를 업로드하여 분석을 시작하세요.")
    st.markdown('''
    ### 🚀 퀵 스타트 가이드
    1. **데이터 준비**: 영웅 ID와 스탯 변수, 전투 결과가 포함된 CSV 파일을 준비합니다.
    2. **업로드**: 좌측 사이드바의 `Upload Combat Logs`를 통해 파일을 업로드합니다.
    3. **자동화된 분석**: 데이터가 업로드되면 시스템이 메커니즘을 자동 역산하고 승률 기반 최적 분배를 시작합니다.
    ''')
