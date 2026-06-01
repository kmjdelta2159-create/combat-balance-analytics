"""
Combat Balance Analytics - Master Balance Engine (SPA Wizard)
main.py - 단일 진입점 및 라우터 모듈
"""
import streamlit as st
import pandas as pd

# 모듈 임포트 (지연 로딩 방식 또는 상단 임포트)
from modules.step1_upload import render_upload
from modules.step2_system_definition import render_system_definition
from modules.step5_discrepancy import render_discrepancy
from modules.step2_profiling import render_profiling
from modules.step6_dashboard import render_dashboard

# --------------------------------------------------------------------------------
# 1. Page Config & Session State Initialization
# --------------------------------------------------------------------------------
st.set_page_config(page_title="Combat Balance Analytics", page_icon="⚔️", layout="wide")

if 'current_step' not in st.session_state:
    st.session_state.current_step = 1

if 'character_library' not in st.session_state:
    st.session_state['character_library'] = {}
if 'ally_team' not in st.session_state:
    st.session_state['ally_team'] = [None] * 4
if 'enemy_team' not in st.session_state:
    st.session_state['enemy_team'] = [None] * 4
if 'system_stats' not in st.session_state:
    st.session_state['system_stats'] = []

st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background-color: #0E1117; }
    [data-testid="stSidebar"] { background-color: #161A22; border-right: 1px solid #2D333B; }
    h1, h2, h3, h4, h5, h6, span, p, label { color: #E6EDF3 !important; font-family: 'Inter', sans-serif; }
    .stDataFrame { border-radius: 8px; overflow: hidden; border: 1px solid #30363D; }
    /* Hide Streamlit default sidebar nav if it somehow appears */
    [data-testid="stSidebarNav"] { display: none !important; }
    
    /* 제 2원칙: 스마트 스크롤 억제용 커스텀 CSS & 기본 헤더 은닉 */
    [data-testid="stHeader"] { display: none !important; }
    .block-container {
        padding-top: 3.5rem !important;
        padding-bottom: 1rem !important;
        max-width: 100% !important;
    }
    
    /* 뷰어 전체화면용 제어판 숨김 클래스 */
    .hide-controls [data-testid="stSidebar"], .hide-controls .step-indicator, .hide-controls .bottom-nav {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------------
# 2. Sidebar Status Board (읽기 전용 전광판)
# --------------------------------------------------------------------------------
with st.sidebar:
    st.title("📋 Status Board")
    st.divider()
    
    # 데이터 로드 상태
    if 'df' in st.session_state:
        st.success(f"✅ Data Loaded: {len(st.session_state['df'])} rows")
        if 'current_file_name' in st.session_state:
            st.caption(f"File: {st.session_state['current_file_name']}")
    else:
        st.error("❌ Data Not Loaded")
        
    st.divider()
    
    # 맵핑 상태
    if st.session_state.get('mapping_approved'):
        st.success("✅ Schema Mapped")
        st.caption(f"Target: {st.session_state.get('target_col', 'N/A')}")
        st.caption(f"Stats: {len(st.session_state.get('system_stats', []))} mapped")
        st.caption(f"Gimmicks: {len(st.session_state.get('system_gimmicks', []))} mapped")
    else:
        st.error("❌ Schema Unmapped")
        
    st.divider()
    
    # 로스터 상태
    lib_size = len(st.session_state.get('character_library', {}))
    if lib_size > 0:
        st.success(f"✅ Roster Parsed: {lib_size} Heroes")
    else:
        st.warning("⚠️ Roster Empty")
        
    st.divider()
    st.info("💡 사이드바는 상태 확인 전용입니다. 화면 하단의 버튼을 통해 단계를 이동하세요.")

# --------------------------------------------------------------------------------
# 3. Step Indicator & Header (Sticky Custom Header)
# --------------------------------------------------------------------------------

TOTAL_STEPS = 5
step_names = [
    "1. Data Upload", 
    "2. System Definition", 
    "3. Discrepancy", 
    "4. System Profiling", 
    "5. Dashboard"
]

progress_val = st.session_state.current_step / TOTAL_STEPS

html_str = f"""
<div style='position: fixed; top: 0; left: 0; width: 100%; z-index: 9999; background: #0E1117; padding-top: 15px; border-bottom: 1px solid #30363D;'>
    <div style='display: flex; justify-content: space-around; max-width: 100%; padding: 0 2rem; margin: 0 auto; color: white; font-family: Inter, sans-serif; font-size: 14px;'>
"""

for i in range(TOTAL_STEPS):
    step_num = i + 1
    if step_num < st.session_state.current_step:
        status, color, weight = "✅", "gray", "normal"
    elif step_num == st.session_state.current_step:
        status, color, weight = "🟢", "white", "bold"
    else:
        status, color, weight = "🔒", "gray", "normal"
    
    html_str += f"<div style='font-weight: {weight}; color: {color};'>{status} {step_names[i]}</div>"

html_str += f"""
    </div>
    <div style='height: 4px; width: 100%; background: #30363D; margin-top: 15px;'>
        <div style='height: 4px; width: {progress_val*100}%; background: #4B9BFF; transition: width 0.3s ease-in-out;'></div>
    </div>
</div>
"""
st.markdown(html_str, unsafe_allow_html=True)

# --------------------------------------------------------------------------------
# 4. Routing & View Rendering
# --------------------------------------------------------------------------------
can_proceed = False
warning_msg = ""

if st.session_state.current_step == 1:
    can_proceed, warning_msg = render_upload()
elif st.session_state.current_step == 2:
    can_proceed, warning_msg = render_system_definition()
elif st.session_state.current_step == 3:
    can_proceed, warning_msg = render_discrepancy()
elif st.session_state.current_step == 4:
    can_proceed, warning_msg = render_profiling()
elif st.session_state.current_step == 5:
    can_proceed, warning_msg = render_dashboard()

st.divider()

# --------------------------------------------------------------------------------
# 5. Bottom Navigation (단방향 흐름 강제)
# --------------------------------------------------------------------------------
st.markdown('<div class="bottom-nav">', unsafe_allow_html=True)

def go_next():
    if st.session_state.current_step < TOTAL_STEPS:
        st.session_state.current_step += 1

def go_prev():
    if st.session_state.current_step > 1:
        st.session_state.current_step -= 1

if not can_proceed and warning_msg:
    st.warning(warning_msg)

nav_col1, nav_col2, nav_col3 = st.columns([1, 8, 1])
with nav_col1:
    if st.session_state.current_step > 1:
        st.button("⬅️ 이전 단계", on_click=go_prev, use_container_width=True)

with nav_col3:
    if st.session_state.current_step < TOTAL_STEPS:
        st.button("다음 단계로 ➡️", on_click=go_next, disabled=not can_proceed, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)
