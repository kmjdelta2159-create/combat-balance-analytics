import streamlit as st
import os
import json
import pandas as pd
from modules.ui_db_corpus_helper import process_db_corpus_upload
from modules.step6_dashboard import render_dashboard

def main():
    # Mock session state setup
    st.set_page_config(layout="wide")

    if "db_corpus_adapter_report" not in st.session_state:
        db_path = ".codex_tmp/adapt8_multi_battle_replay/pokemon_showdown_multi.db"
        with open(db_path, "rb") as f:
            file_bytes = f.read()
        
        df, report, schema = process_db_corpus_upload(file_bytes, os.path.basename(db_path))
        
        st.session_state["df"] = df
        st.session_state["current_file_name"] = os.path.basename(db_path)
        st.session_state["db_corpus_adapter_report"] = report
        st.session_state["db_corpus_schema"] = schema
        st.session_state["bb_last_corpus_schema"] = schema
        st.session_state["bb_last_log_schema"] = schema["log_schema"]
        
        st.session_state["target_col"] = schema.get("target_col", "result")
        st.session_state["system_stats"] = schema.get("system_stats", ["HP"])
        st.session_state["system_gimmicks"] = schema.get("system_gimmicks", [])
        st.session_state["health_stat"] = schema.get("health_stat", "HP")
        st.session_state["mapping_approved"] = True
        st.session_state["db_corpus_last_backtest_has_run"] = False
        
        # Run backtest to populate summary
        from modules.ui_db_corpus_helper import run_db_corpus_backtest_from_session
        summary, mm_rows = run_db_corpus_backtest_from_session(st.session_state)
        st.session_state["db_corpus_last_backtest_summary"] = summary
        st.session_state["db_corpus_last_mismatch_rows"] = mm_rows
        st.session_state["db_corpus_last_backtest_has_run"] = True

    render_dashboard()

if __name__ == "__main__":
    main()
