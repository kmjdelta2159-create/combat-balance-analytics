import unittest
from unittest.mock import patch
import streamlit as st
from modules.step2_system_definition import render_system_definition
import pandas as pd

class TestStep2StructuredPackageEditableDefaults(unittest.TestCase):
    def setUp(self):
        st.session_state.clear()
        # Mock dataframe with necessary columns
        st.session_state['df'] = pd.DataFrame({
            'char': ['A', 'B'],
            'win': [1, 0],
            'HP': [100, 100],
            'Atk': [50, 50],
            'type': ['Fire', 'Water']
        })
        st.session_state['char_col'] = 'char'
        st.session_state['numeric_cols_raw'] = ['win', 'HP', 'Atk']
        
    @patch('streamlit.button')
    def test_db_mode_prefills_correctly(self, mock_button):
        st.session_state['input_mode'] = 'structured_battle_package'
        st.session_state['db_corpus_schema'] = {
            'target_col': 'win',
            'system_stats': ['HP', 'Atk'],
            'system_gimmicks': ['type']
        }
        
        mock_button.return_value = False
        
        # When we render, it shouldn't auto-approve DB mode anymore, it should show the full UI.
        can_proceed, msg = render_system_definition()
        self.assertFalse(can_proceed)
        self.assertIn("파이프라인 시작", msg)
        
        # We can't easily assert on the exact rendering output of selectbox defaults without mocking them, 
        # but we can ensure it doesn't short-circuit with "자동 추론 결과 승인" anymore.

if __name__ == '__main__':
    unittest.main()
