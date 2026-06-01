import streamlit as st
import pandas as pd
import json

def render_upload():
    # 상단 공통 타이틀/설명글 삭제 (수직 공간 압축)
    
    can_proceed = False
    warning_msg = "⚠️ 다음 단계로 이동하려면 CSV 파일을 업로드해야 합니다."
    
    st.subheader("새로운 전투 로그(CSV) 업로드")
    uploaded_file = st.file_uploader("Upload Combat Logs (CSV)", type=["csv"])
    
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            st.session_state['df'] = df
            
            # Schema-Agnostic 초기 정보 저장
            st.session_state['char_col'] = df.columns[0]
            st.session_state['numeric_cols_raw'] = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
            
            if st.session_state.get('current_file_name') != uploaded_file.name:
                st.session_state['current_file_name'] = uploaded_file.name
                st.session_state['mapping_approved'] = False
                st.session_state['formula_input_ui'] = ""
                if 'combat_flow' in st.session_state:
                    del st.session_state['combat_flow']
            
            st.success(f"✅ 데이터가 성공적으로 파싱되었습니다! (총 {len(df)}행)")
            
            with st.expander("원본 데이터 미리보기", expanded=False):
                col_config = {}
                for c in df.columns:
                    if pd.api.types.is_numeric_dtype(df[c]):
                        col_config[c] = st.column_config.NumberColumn(c, format="%.1f")
                    else:
                        col_config[c] = st.column_config.TextColumn(c)
                st.dataframe(df.head(100), use_container_width=True, height=400, column_config=col_config)
                
            can_proceed = True
            warning_msg = ""
        except Exception as e:
            st.error(f"❌ CSV 파싱 중 오류가 발생했습니다: {e}")
            return False, "올바르지 않은 CSV 파일입니다."
            
    st.markdown("---")
    st.subheader("또는 이전 맵핑 프리셋(JSON) 불러오기")
    preset_file = st.file_uploader("Upload Mapping Preset (JSON)", type=["json"], help="저장된 매핑 설정을 불러와 즉시 복원합니다.")
    
    if preset_file and 'df' in st.session_state:
        try:
            preset_data = json.load(preset_file)
            st.session_state['mapping_approved'] = True
            st.session_state['global_damage_formula'] = preset_data.get('global_damage_formula', '')
            st.session_state['target_col'] = preset_data.get('target_col')
            st.session_state['system_stats'] = preset_data.get('base_stats_list', [])
            st.session_state['system_gimmicks'] = preset_data.get('gimmick_list', [])
            st.session_state['has_ml_data'] = True if preset_data.get('target_col') and preset_data.get('target_col') != "None" else False
            st.session_state['formula_input_ui'] = preset_data.get('global_damage_formula', '')
            st.success("✅ JSON 매핑 프리셋이 성공적으로 로드되었습니다!")
        except Exception as e:
            st.error(f"❌ JSON 파싱 중 오류가 발생했습니다: {e}")
            
    return can_proceed, warning_msg
