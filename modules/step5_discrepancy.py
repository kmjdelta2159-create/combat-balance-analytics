import streamlit as st
import pandas as pd
from modules.move_extraction import detect_move_columns, has_move_data

def render_discrepancy():
    # 상단 공통 타이틀/설명글 삭제 (수직 공간 압축)
    
    if 'df' not in st.session_state or not st.session_state.get('mapping_approved', False):
        return False, "⚠️ 2단계(System Definition)에서 전투 공식 맵핑을 완료해야 오차 분석이 가능합니다."

    df = st.session_state['df'].copy()
    formula = st.session_state['damage_formula']

    st.info(f"**현재 검증 중인 사용자 정의 공식 (White-Box):** `{formula}`")

    target_col = st.session_state.get('target_variable')

    if not target_col or target_col not in df.columns:
        st.error("❌ 2단계에서 설정한 Target Variable(결과값)을 찾을 수 없습니다. 다시 맵핑해주세요.")
        return False, "타겟 변수 오류"

    with st.spinner("사용자 공식 기반 오차 연산 및 데이터 처리 중..."):
        try:
            eval_df = df.copy()
            eval_df.columns = [str(c).lower() for c in eval_df.columns]
            
            original_cols = list(eval_df.columns)
            for c in original_cols:
                eval_df[f"target_{c}"] = eval_df[c]
                
            # ── Phase 8a: 무브 변수 broadcast (attack_log 보조 진입) ──
            _atk_log_df = st.session_state.get("attack_log_df")
            _mv_src = df if has_move_data(df) else (_atk_log_df if _atk_log_df is not None and has_move_data(_atk_log_df) else None)
            if _mv_src is not None:
                _mv_cols = detect_move_columns(_mv_src)
                _pwr_col = _mv_cols.get("power")
                if _pwr_col and _pwr_col in _mv_src.columns:
                    _pw = pd.to_numeric(_mv_src[_pwr_col], errors="coerce").dropna()
                    _mp = float(_pw.mean()) if len(_pw) else 0.0
                    eval_df["move_power"] = _mp
                    eval_df["target_move_power"] = _mp
                    _bs = st.session_state.get("system_stats", [])
                    if _bs and _bs[0].lower() in eval_df.columns:
                        eval_df["offense"] = eval_df[_bs[0].lower()]
                        eval_df["defense"] = eval_df[_bs[0].lower()]

            eval_formula = formula.lower()
            
            predicted_values = eval_df.eval(eval_formula)
            
            df['Predicted_Value'] = predicted_values
            df['Calculated_Error'] = abs(df['Predicted_Value'] - df[target_col])
            
        except Exception as e:
            st.error(f"❌ 수식 연산 중 오류가 발생했습니다. 공식 문법을 확인해주세요.\n\n**오류 내용:** `{str(e)}`")
            return False, "수식 오류"

    st.error("🚨 **이상치 감지 (Anomaly Detected):** 사용자의 예측 공식과 실제 결과값이 가장 크게 빗나가는 상위 20개 데이터입니다. 숨겨진 조건부 로직이나 누락된 변수가 있는지 검토하십시오.")

    anomaly_df = df.nlargest(20, 'Calculated_Error')
    cols = ['Calculated_Error', 'Predicted_Value', target_col] + [c for c in anomaly_df.columns if c not in ['Calculated_Error', 'Predicted_Value', target_col]]
    anomaly_df = anomaly_df[cols]

    # 제 1원칙: 동적 컬러맵 (vmin, vmax) 복구 및 NumberColumn 적용
    min_err = float(anomaly_df['Calculated_Error'].min()) if not anomaly_df.empty else 0.0
    max_err = float(anomaly_df['Calculated_Error'].max()) if not anomaly_df.empty else 1.0
    
    col_config = {}
    for c in anomaly_df.columns:
        if pd.api.types.is_numeric_dtype(anomaly_df[c]):
            col_config[c] = st.column_config.NumberColumn(c, format="%.1f")
        else:
            col_config[c] = st.column_config.TextColumn(c)

    styled_df = anomaly_df.style.background_gradient(
        subset=['Calculated_Error'], 
        cmap='Reds', 
        vmin=min_err, 
        vmax=max_err
    )

    st.dataframe(styled_df, use_container_width=True, height=500, column_config=col_config)

    with st.expander("💡 이상치(Anomaly) 분석 가이드"):
        st.markdown("""
        - **오차가 유독 높은 행이 있나요?** 
          - 원본 데이터에 기획자가 인지하지 못한 예외 로직(예: 특정 직업군 데미지 반감, 상성 버그)이 적용되어 있을 확률이 높습니다.
        """)

    return True, ""
