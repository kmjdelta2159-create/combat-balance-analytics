import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

def render_profiling():
    # 상단 공통 타이틀/설명글 삭제 (수직 공간 압축)
    
    if 'df' not in st.session_state or not st.session_state.get('mapping_approved', False):
        return False, "⚠️ 2단계(System Definition)에서 매핑 파이프라인을 완료해야 분석이 가능합니다."
        
    df = st.session_state["df"]
    
    with st.spinner("데이터 구조를 파악하고 있습니다..."):
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        if not numeric_cols:
            st.error("❌ 데이터에 숫자형 컬럼이 없어 분석을 진행할 수 없습니다.")
            return False, "숫자형 컬럼이 부족합니다."

        target_candidates = ['is_victorious', 'win', 'result', 'target', 'victory', 'is_win']
        target_col = None

        for col in numeric_cols:
            if col.lower() in target_candidates:
                target_col = col
                break

        if target_col is None:
            target_col = numeric_cols[-1]
            st.info(f"💡 명시적인 승패(Win/Loss) 컬럼을 찾지 못해, 마지막 숫자형 컬럼인 `{target_col}`을(를) Target으로 임시 할당했습니다.")

        feature_cols = [col for col in numeric_cols if col != target_col]

        if not feature_cols:
            st.error("❌ 분석에 사용할 Feature(스탯) 컬럼이 부족합니다.")
            return False, "Feature 컬럼이 부족합니다."

        X = df[feature_cols].fillna(df[feature_cols].mean())
        y = df[target_col].fillna(0)

        if len(y.unique()) > 2:
            median_val = y.median()
            y = (y > median_val).astype(int)
            st.warning(f"⚠️ Target 컬럼(`{target_col}`)이 이진 형태(0/1)가 아니므로, 중앙값({median_val:.2f}) 기준으로 임시 이진화 처리했습니다.")

    with st.spinner("🤖 기계학습 엔진이 가설을 추출하고 있습니다..."):
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        rf_model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
        rf_model.fit(X_scaled, y)
        importances = rf_model.feature_importances_ * 100

        importance_df = pd.DataFrame({
            'Feature': feature_cols,
            'Importance': importances
        }).sort_values(by='Importance', ascending=False)

        lr_model = LogisticRegression(max_iter=1000, random_state=42, n_jobs=-1)
        try:
            lr_model.fit(X, y)
            coef_dict = dict(zip(feature_cols, lr_model.coef_[0]))
        except Exception:
            coef_dict = {}

    # --------------------------------------------------------------------------------
    # Top Banner (AI 추론 결과)
    # --------------------------------------------------------------------------------
    st.subheader("💡 AI 시스템 추론 결과")
    banner_cols = st.columns(2)
    with banner_cols[0]:
        if not importance_df.empty:
            top_feature = importance_df.iloc[0]['Feature']
            top_importance = importance_df.iloc[0]['Importance']
            st.success(f"**가설 1:** 가장 핵심 스탯은 `{top_feature}` (기여도 {top_importance:.1f}%)로 추정됩니다.")
    with banner_cols[1]:
        if len(importance_df) > 1:
            second_feature = importance_df.iloc[1]['Feature']
            second_importance = importance_df.iloc[1]['Importance']
            if second_feature in coef_dict:
                coef = coef_dict[second_feature]
                prob_change = coef * 0.25 * 100
                trend = "상승" if prob_change > 0 else "하락"
                st.info(f"**가설 2:** `{second_feature}` 1 단위당 승률 약 {abs(prob_change):.2f}% {trend} (선형 패턴 관찰).")

    st.divider()

    # --------------------------------------------------------------------------------
    # Middle Section (시각화 차트)
    # --------------------------------------------------------------------------------
    tab1, tab2 = st.tabs(["📊 스탯별 승률 기여도 분포", "🕸️ 변수 간 상관관계 히트맵"])
    
    with tab1:
        fig = px.bar(
            importance_df, x='Importance', y='Feature', orientation='h',
            title="승패에 미치는 특성 중요도 (Feature Importances)",
            labels={'Importance': '승률 기여도 (%)', 'Feature': '분석된 스탯'},
            color='Importance', color_continuous_scale=px.colors.sequential.Plasma
        )
        fig.update_layout(yaxis={'categoryorder':'total ascending'}, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=500)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        try:
            corr_df = X.copy()
            corr_df[target_col] = y
            corr_matrix = corr_df.corr()
            fig_corr = px.imshow(
                corr_matrix, 
                text_auto=".2f", 
                aspect="auto",
                color_continuous_scale="RdBu_r",
                title="스탯 및 타겟 간 상관관계"
            )
            fig_corr.update_layout(template="plotly_dark", height=500)
            st.plotly_chart(fig_corr, use_container_width=True)
        except Exception as e:
            st.warning(f"상관관계 히트맵 렌더링 중 오류가 발생했습니다: {e}")

    # --------------------------------------------------------------------------------
    # Bottom Section (데이터 표)
    # --------------------------------------------------------------------------------
    st.divider()
    with st.expander("원본 데이터 및 전처리 결과 확인", expanded=False):
        col_config = {}
        for c in X.columns:
            if pd.api.types.is_numeric_dtype(X[c]):
                col_config[c] = st.column_config.NumberColumn(
                    c,
                    help=f"{c} (Numeric)",
                    format="%.1f"
                )
            else:
                col_config[c] = st.column_config.TextColumn(
                    c,
                    help=f"{c} (Categorical)"
                )
        
        st.dataframe(X.head(100), use_container_width=True, height=400, column_config=col_config)

    return True, ""
