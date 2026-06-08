import unittest
from unittest.mock import patch
import streamlit as st
from modules.step5_discrepancy import render_discrepancy
import pandas as pd

class TestStep3StructuredPackageValidation(unittest.TestCase):
    def setUp(self):
        st.session_state.clear()
        st.session_state['df'] = pd.DataFrame({'a': [1, 2], 'target': [1, 0]})
        st.session_state['mapping_approved'] = True

    @patch('streamlit.button')
    def test_validation_not_run(self, mock_button):
        st.session_state['input_mode'] = 'structured_battle_package'
        st.session_state['db_corpus_adapter_report'] = {'battle_count': 100}
        mock_button.return_value = False
        
        can_proceed, msg = render_discrepancy()
        self.assertFalse(can_proceed)
        self.assertIn("리플레이 검증을 실행", msg)

    @patch('modules.step5_discrepancy.run_db_corpus_backtest_from_session')
    @patch('streamlit.spinner')
    @patch('streamlit.button')
    def test_validation_run(self, mock_button, mock_spinner, mock_backtest):
        st.session_state['input_mode'] = 'structured_battle_package'
        
        mock_button.side_effect = [True, True]
        
        mock_backtest.return_value = (
            {"battles": 10, "state_checks": 100, "mismatches": 0, "accuracy": 100.0},
            []
        )
        
        class MockSpinnerContextManager:
            def __enter__(self): pass
            def __exit__(self, exc_type, exc_value, traceback): pass
        mock_spinner.return_value = MockSpinnerContextManager()
        
        can_proceed, msg = render_discrepancy()
        self.assertTrue(can_proceed)

if __name__ == '__main__':
    unittest.main()
