import unittest
from unittest.mock import patch
import streamlit as st
from modules.step2_system_definition import render_system_definition
import pandas as pd

class TestStep2StructuredPackageReview(unittest.TestCase):
    def setUp(self):
        st.session_state.clear()
        st.session_state['df'] = pd.DataFrame({'a': [1, 2], 'target': [1, 0]})

    @patch('streamlit.button')
    def test_db_package_mode_needs_approval(self, mock_button):
        st.session_state['input_mode'] = 'structured_battle_package'
        mock_button.return_value = False
        
        can_proceed, msg = render_system_definition()
        self.assertFalse(can_proceed)
        self.assertIn("자동 추론 결과를 확인하고 승인해주세요", msg)
        
    @patch('streamlit.rerun')
    @patch('streamlit.button')
    def test_db_package_mode_approve(self, mock_button, mock_rerun):
        st.session_state['input_mode'] = 'structured_battle_package'
        mock_button.return_value = True
        
        # Normally it throws RerunException, but mock_rerun just intercepts it
        can_proceed, msg = render_system_definition()
        self.assertTrue(st.session_state.get('mapping_approved'))

    def test_db_package_mode_already_approved(self):
        st.session_state['input_mode'] = 'structured_battle_package'
        st.session_state['mapping_approved'] = True
        
        can_proceed, msg = render_system_definition()
        self.assertTrue(can_proceed)
        self.assertEqual(msg, "")

if __name__ == '__main__':
    unittest.main()
