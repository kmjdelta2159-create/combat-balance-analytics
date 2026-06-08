import streamlit as st
import pandas as pd
from modules.step5_discrepancy import render_discrepancy

def test_step3_target_resolution():
    # Mock data
    df = pd.DataFrame({"dummy_stat": [10, 20], "result": [1, 0], "other_col": [0, 1]})
    
    # 1. Test with target_col only
    st.session_state.clear()
    st.session_state['df'] = df
    st.session_state['mapping_approved'] = True
    st.session_state['damage_formula'] = "dummy_stat * 2"
    st.session_state['target_col'] = "result"
    
    # Should succeed
    can_proceed, msg = render_discrepancy()
    assert can_proceed is True, f"Failed with target_col: {msg}"
    
    # 2. Test with target_variable only (fallback)
    st.session_state.clear()
    st.session_state['df'] = df
    st.session_state['mapping_approved'] = True
    st.session_state['damage_formula'] = "dummy_stat * 2"
    st.session_state['target_variable'] = "result"
    
    # Should succeed
    can_proceed, msg = render_discrepancy()
    assert can_proceed is True, f"Failed with target_variable: {msg}"
    
    # 3. Test with no target
    st.session_state.clear()
    st.session_state['df'] = df
    st.session_state['mapping_approved'] = True
    st.session_state['damage_formula'] = "dummy_stat * 2"
    
    # Should fail
    can_proceed, msg = render_discrepancy()
    assert can_proceed is False, "Should fail when no target is set"
    assert msg == "타겟 변수 오류", f"Wrong error message: {msg}"
    
    # 4. Test with invalid target (not in df)
    st.session_state.clear()
    st.session_state['df'] = df
    st.session_state['mapping_approved'] = True
    st.session_state['damage_formula'] = "dummy_stat * 2"
    st.session_state['target_col'] = "nonexistent_target"
    
    # Should fail
    can_proceed, msg = render_discrepancy()
    assert can_proceed is False, "Should fail when target is not in df"
    assert msg == "타겟 변수 오류", f"Wrong error message: {msg}"

if __name__ == "__main__":
    test_step3_target_resolution()
    print("test_step3_target_flow OK")
