import unittest
from unittest.mock import patch
import streamlit as st
from modules.step2_system_definition import render_system_definition
import pandas as pd

class TestStep2SingleClassTargetGuard(unittest.TestCase):
    def setUp(self):
        st.session_state.clear()
        st.session_state['df'] = pd.DataFrame({
            'char': ['A', 'B', 'C'],
            'win': [1, 1, 1], # Single class target
            'HP': [100, 100, 100],
            'Atk': [50, 50, 50],
            'type': ['Fire', 'Water', 'Grass']
        })
        st.session_state['char_col'] = 'char'
        st.session_state['numeric_cols_raw'] = ['win', 'HP', 'Atk']
        st.session_state['mapping_approved'] = True
        st.session_state['has_ml_data'] = True
        st.session_state['target_col'] = 'win'
        st.session_state['system_stats'] = ['HP', 'Atk']
        st.session_state['system_gimmicks'] = ['type']
        st.session_state['character_library'] = {}
        
    @patch('streamlit.info')
    def test_single_class_skips_ml(self, mock_info):
        st.session_state['input_mode'] = 'structured_battle_package'
        
        with patch('modules.step2_system_definition._render_game_profile_panel'):
            can_proceed, msg = render_system_definition()
            
        self.assertTrue(can_proceed)
        self.assertEqual(msg, "")
        
        called_args = [call_args[0][0] for call_args in mock_info.call_args_list]
        found = any("단일 클래스라 승률 예측 모델 학습은 건너뜁니다" in arg for arg in called_args)
        self.assertTrue(found)
        
        self.assertNotIn('ml_coefs', st.session_state)

if __name__ == '__main__':
    unittest.main()
