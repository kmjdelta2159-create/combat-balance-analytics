import unittest
from unittest.mock import patch
import streamlit as st
from modules.step5_discrepancy import render_discrepancy
import pandas as pd

class TestStep3DBPackageMode(unittest.TestCase):
    def setUp(self):
        st.session_state.clear()
        st.session_state['df'] = pd.DataFrame({'a': [1, 2], 'target': [1, 0]})
        st.session_state['mapping_approved'] = True
        st.session_state['target_col'] = 'target'

    @patch('streamlit.button')
    @patch('streamlit.info')
    @patch('streamlit.markdown')
    @patch('streamlit.columns')
    def test_db_package_mode_no_formula(self, mock_cols, mock_markdown, mock_info, mock_button):
        # DB 패키지 모드 + damage_formula 없음
        st.session_state['input_mode'] = 'structured_battle_package'
        st.session_state['db_corpus_adapter_report'] = {'battle_count': 100, 'event_count': 500, 'participant_count': 200}
        
        # mock st.columns
        class MockMetric:
            def metric(self, label, value):
                pass
        mock_cols.return_value = (MockMetric(), MockMetric(), MockMetric())
        mock_button.return_value = False
        
        can_proceed, msg = render_discrepancy()
        
        self.assertFalse(can_proceed)
        self.assertIn("리플레이 검증을 실행하여 복제 결과를 확인하세요", msg)
        mock_info.assert_called_with("📦 **수식 오차 분석 대신, 실제 전투 이벤트를 복제본이 얼마나 재현하는지 검증합니다.**")

    def test_normal_log_mode_no_formula(self):
        # 일반 로그 모드 + damage_formula 없음
        can_proceed, msg = render_discrepancy()
        
        self.assertFalse(can_proceed)
        self.assertIn("Step2에서 데미지 공식을 입력하고 파이프라인을 시작해야", msg)

    @patch('streamlit.info')
    @patch('streamlit.spinner')
    @patch('streamlit.error')
    @patch('streamlit.dataframe')
    def test_normal_log_mode_with_formula(self, mock_df, mock_err, mock_spinner, mock_info):
        # 일반 로그 모드 + damage_formula 있음
        st.session_state['damage_formula'] = 'a * 2'
        
        # We need to mock spinner context manager
        class MockSpinnerContextManager:
            def __enter__(self): pass
            def __exit__(self, exc_type, exc_value, traceback): pass
        mock_spinner.return_value = MockSpinnerContextManager()
        
        can_proceed, msg = render_discrepancy()
        
        self.assertTrue(can_proceed)
        self.assertEqual(msg, "")
        mock_info.assert_called_with("**현재 검증 중인 사용자 정의 공식 (White-Box):** `a * 2`")

if __name__ == '__main__':
    unittest.main()
