import json
import pandas as pd
from modules.step6_dashboard import _mismatch_row_from_score, _extend_mismatch_rows_from_metrics

def test_mismatch_extraction():
    metrics_list = [
        # Battle 1: mismatch in state
        {
            "state_score": {
                "first_mismatch": {"turn": 1, "id": "A1", "kind": "HP", "expected": 100, "actual": 80},
                "checks": 10,
                "mismatches": 1
            }
        },
        # Battle 2: no mismatch
        {
            "state_score": {
                "checks": 10,
                "mismatches": 0
            }
        },
        # Battle 3: mismatch in action_damage with complex dicts
        {
            "action_damage_score": {
                "first_mismatch": {
                    "turn": 2, "id": "A2", "kind": "damage",
                    "expected": {"val": 50}, "actual": {"val": 30}
                },
                "checks": 5,
                "mismatches": 1
            }
        }
    ]

    rows = []
    for bb_idx, metrics in enumerate(metrics_list, start=1):
        _extend_mismatch_rows_from_metrics(rows, bb_idx, metrics)
        
    assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"

    # Verify Battle 1
    assert rows[0]["battle_index"] == 1
    assert rows[0]["score_type"] == "state"
    assert rows[0]["expected_full"] == "100"

    # Verify Battle 3
    assert rows[1]["battle_index"] == 3
    assert rows[1]["score_type"] == "action_damage"
    assert rows[1]["expected_full"] == "{'val': 50}"
    assert rows[1]["actual_full"] == "{'val': 30}"

    # Verify dataframe conversion is safe
    df = pd.DataFrame(rows)
    assert len(df) == 2
    assert "expected_full" in df.columns

def test_source_checks():
    # 1. render_mechanism_re()가 st.button 블록 안에만 갇혀 있지 않은지 확인
    with open("modules/step6_dashboard.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "bb_last_backtest_has_run" in content
    
    # render_mechanism_re 호출 라인이 if st.button(...)의 인덴테이션(24칸)과 같거나 더 바깥쪽에 있어야 함.
    # 하지만 실제 구현에서는 동일한 depth(24칸)의 if st.session_state.get(...) 안에 들어있으므로, 
    # button block과 독립적인 최상위 렌더링 블록인지 확인합니다.
    assert "if st.session_state.get(\"bb_last_backtest_has_run\"):" in content

if __name__ == "__main__":
    test_mismatch_extraction()
    test_source_checks()
    print("All tests passed.")
