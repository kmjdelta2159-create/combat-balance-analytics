import streamlit as st

if 'formula_input_ui' not in st.session_state:
    st.session_state['formula_input_ui'] = ""

def on_pill_change():
    selected = st.session_state.pill_vars
    if selected:
        st.session_state['formula_input_ui'] += selected.lower() + " "
        st.session_state.pill_vars = None

all_vars = ["HP", "MP", "STR", "DEF"]

st.write("변수 칩 (클릭 시 수식 입력창에 삽입됩니다):")
st.pills("Chips", all_vars, key="pill_vars", on_change=on_pill_change, label_visibility="collapsed")

st.text_input("Formula", key="formula_input_ui")
