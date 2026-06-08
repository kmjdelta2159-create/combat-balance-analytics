import pandas as pd
from modules.step6_dashboard import (
    resolve_db_corpus_log_schema,
    has_db_corpus_schema,
    default_backtest_method_index,
    schema_col_default,
    schema_sort_cols_default,
    merge_db_corpus_log_schema
)

def test_resolve_and_index():
    state1 = {}
    assert resolve_db_corpus_log_schema(state1) is None
    assert has_db_corpus_schema(state1) is False
    assert default_backtest_method_index(state1) == 0
    
    state2 = {"bb_last_log_schema": {"state_trace_enabled": True}}
    assert resolve_db_corpus_log_schema(state2) is not None
    assert has_db_corpus_schema(state2) is True
    assert default_backtest_method_index(state2) == 1

def test_schema_col_default():
    cols = ["battle_id", "my_turn", "actor", "target"]
    log_schema = {"battle_id_col": "battle_id"}
    
    # Exists in schema
    assert schema_col_default(log_schema, cols, "battle_id_col") == "battle_id"
    # Not in schema, hint matched
    assert schema_col_default(log_schema, cols, "turn_col", ["turn"]) == "my_turn"
    # Not in schema, hint unmatched
    assert schema_col_default(log_schema, cols, "team_col", ["side"]) == "(없음)"

def test_schema_sort_cols_default():
    cols = ["turn", "order", "seq"]
    log_schema1 = {"sort_cols": ["turn"]}
    assert schema_sort_cols_default(log_schema1, cols) == ["turn"]
    
    log_schema2 = {"sort_cols": ["nonexistent"]}
    # fallbacks to hints
    assert schema_sort_cols_default(log_schema2, cols) == ["turn"]

def test_apply_defaults():
    db_schema = {
        "observed_hp_trace_enabled": True,
        "observed_status_trace_enabled": True,
        "observed_switch_trace_enabled": True,
        "state_trace_enabled": True
    }
    
    # If state trace is enabled by UI
    res = merge_db_corpus_log_schema(
        {"some_base": 1}, 
        db_schema, 
        {"state_trace_enabled": True}
    )
    assert res["state_trace_enabled"] is True
    assert res["observed_hp_trace_enabled"] is True
    assert res["observed_switch_trace_enabled"] is True
    
    # If state trace is disabled by UI
    res2 = merge_db_corpus_log_schema(
        {"some_base": 1}, 
        db_schema, 
        {"state_trace_enabled": False}
    )
    assert res2["state_trace_enabled"] is False
    assert res2["observed_hp_trace_enabled"] is False
    assert res2["observed_switch_trace_enabled"] is False

if __name__ == "__main__":
    test_resolve_and_index()
    test_schema_col_default()
    test_schema_sort_cols_default()
    test_apply_defaults()
    print("test_step6_db_corpus_auto_schema OK")
