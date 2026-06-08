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
    st.session_state['ally_team'] = []
if 'enemy_team' not in st.session_state:
    st.session_state['enemy_team'] = []
if 'system_stats' not in st.session_state:
    st.session_state['system_stats'] = []

st.markdown("""
<style>
    /* Semantic color tokens */
    :root {
        --app-bg: #0e1117;
        --sidebar-bg: #161a22;
        --panel-bg: #111827;
        --surface-light: #f8fafc;
        
        --text-on-dark: #f8fafc;
        --text-secondary-on-dark: #d1d5db;
        --text-muted-on-dark: #b8c0cc;
        --text-disabled-on-dark: #a7b0be;
        
        --text-on-light: #111827;
        --text-muted-on-light: #4b5563;
        --border-subtle: #30363d;
    }

    /* Core backgrounds and primary text */
    [data-testid="stAppViewContainer"] { background-color: var(--app-bg); color: var(--text-on-dark); }
    [data-testid="stSidebar"] { background-color: var(--sidebar-bg); border-color: var(--border-subtle); }
    
    /* 1. 어두운 앱 배경 위 텍스트 */
    h1, h2, h3, h4, h5, h6 { color: var(--text-on-dark) !important; }
    .stMarkdown p, .stMarkdown ul, .stMarkdown ol, [data-testid="stText"] p { color: var(--text-on-dark) !important; }
    [data-testid="stAppViewContainer"] label { color: var(--text-on-dark) !important; }
    
    small, 
    [data-testid="stCaptionContainer"] p, 
    [data-testid="stSidebar"] p, 
    [data-testid="stMarkdownContainer"] small,
    [data-testid="stTab"] p { 
        color: var(--text-secondary-on-dark) !important; 
    }

    [data-testid="stExpander"] summary p,
    [data-testid="stToggle"] label p,
    [data-testid="stCheckbox"] label p,
    [data-testid="stRadio"] label p { 
        color: var(--text-on-dark); 
    }

    [data-testid="stTab"][aria-selected="true"] p {
        color: var(--text-on-dark);
    }

    [data-testid="stMetricValue"] { color: var(--text-on-dark); }
    [data-testid="stMetricValue"] > div { color: var(--text-on-dark); }
    [data-testid="stMetricLabel"] { color: var(--text-secondary-on-dark); }
    [data-testid="stMetricLabel"] > div > div > p { color: var(--text-secondary-on-dark); }

    /* 2. 밝은 form surface 위 텍스트 (텍스트 색만 변경) */
    input, 
    textarea, 
    [data-baseweb="input"] input, 
    [data-baseweb="textarea"] textarea, 
    [data-baseweb="base-input"] input,
    [data-baseweb="base-input"] textarea,
    [data-testid="stSelectbox"] input, 
    [data-testid="stTextInput"] input, 
    [data-testid="stTextArea"] textarea, 
    [data-testid="stNumberInput"] input, 
    [data-testid="stFileUploader"] button {
        color: var(--text-on-light) !important;
        caret-color: var(--text-on-light) !important;
    }
    
    input::placeholder, 
    textarea::placeholder {
        color: var(--text-muted-on-light) !important;
    }
    
    /* Selectbox 내부 값 및 multiselect tag (chip), 그리고 pills */
    [data-baseweb="select"] div[aria-selected="true"],
    [data-baseweb="select"] span[title],
    [data-baseweb="tag"] span,
    [data-testid="stPills"] button,
    [data-testid="stPills"] span,
    [data-testid="stPills"] p,
    [data-baseweb="pill"] span {
        color: var(--text-on-light) !important;
    }

    /* 3. disabled 상태 (opacity 제외, 텍스트가 읽히도록 유지) */
    /* Formula variable chips: Streamlit may render pills as buttons, labels, or radio wrappers. */
    [data-testid="stPills"] button,
    [data-testid="stPills"] label,
    [data-testid="stPills"] [role="button"],
    [data-testid="stPills"] [role="radio"],
    [data-testid="stPills"] [data-baseweb="radio"],
    [class*="formula_chip_selector"] button,
    [class*="formula_chip_selector"] label,
    [class*="formula_chip_selector"] [role="button"],
    [class*="formula_chip_selector"] [role="radio"],
    [class*="formula_chip_selector"] [data-baseweb="radio"] {
        background-color: #f8fafc !important;
        border: 1px solid #94a3b8 !important;
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
        opacity: 1 !important;
        text-shadow: none !important;
        filter: none !important;
        mix-blend-mode: normal !important;
    }
    [data-testid="stPills"] *,
    [class*="formula_chip_selector"] * {
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
        opacity: 1 !important;
        text-shadow: none !important;
        filter: none !important;
        mix-blend-mode: normal !important;
    }
    [data-testid="stPills"] button[aria-selected="true"],
    [data-testid="stPills"] button[aria-pressed="true"],
    [data-testid="stPills"] [role="button"][aria-selected="true"],
    [data-testid="stPills"] [role="radio"][aria-checked="true"],
    [data-testid="stPills"] label:has(input:checked),
    [class*="formula_chip_selector"] button[aria-selected="true"],
    [class*="formula_chip_selector"] button[aria-pressed="true"],
    [class*="formula_chip_selector"] [role="button"][aria-selected="true"],
    [class*="formula_chip_selector"] [role="radio"][aria-checked="true"],
    [class*="formula_chip_selector"] label:has(input:checked) {
        background-color: #2563eb !important;
        border-color: #60a5fa !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    [data-testid="stPills"] button[aria-selected="true"] *,
    [data-testid="stPills"] button[aria-pressed="true"] *,
    [data-testid="stPills"] [role="button"][aria-selected="true"] *,
    [data-testid="stPills"] [role="radio"][aria-checked="true"] *,
    [data-testid="stPills"] label:has(input:checked) *,
    [class*="formula_chip_selector"] button[aria-selected="true"] *,
    [class*="formula_chip_selector"] button[aria-pressed="true"] *,
    [class*="formula_chip_selector"] [role="button"][aria-selected="true"] *,
    [class*="formula_chip_selector"] [role="radio"][aria-checked="true"] *,
    [class*="formula_chip_selector"] label:has(input:checked) * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }

    button:disabled,
    [data-testid="stButton"] button:disabled,
    [data-testid="stFormSubmitButton"] button:disabled,
    [aria-disabled="true"],
    [data-disabled="true"],
    input:disabled,
    textarea:disabled { 
        color: var(--text-disabled-on-dark) !important;
        border-color: var(--border-subtle) !important;
    }
    
    [data-testid="stCheckbox"] input:disabled ~ div, 
    [data-testid="stToggle"] input:disabled ~ div { 
        color: var(--text-disabled-on-dark) !important; 
    }
    
    /* Dataframe and Tables */
    [data-testid="stDataFrame"] th { color: var(--text-secondary-on-dark) !important; }
    [data-testid="stDataFrame"] td { color: var(--text-on-light) !important; }

    /* Buttons */
    [data-testid="stButton"] button { color: var(--text-on-light) !important; }

    /* File uploader visibility */
    [data-testid="stFileUploader"] small { color: var(--text-muted-on-dark) !important; }
    
    /* Alerts and hints */
    .stAlert p, .stAlert span, .stAlert div[data-testid="stMarkdownContainer"] p { color: var(--text-on-dark) !important; }
    
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
