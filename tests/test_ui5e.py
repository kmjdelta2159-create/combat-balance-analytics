import pytest
import pandas as pd
import streamlit as st

def test_structured_package_dashboard_roster():
    from modules.step6_dashboard import get_default_df
    
    st.session_state.clear()
    st.session_state["system_stats"] = ["HP"]
    st.session_state["system_gimmicks"] = ["species"]
    st.session_state["structured_package_mode"] = True
    
    # Mock character library as if it was populated from roster
    st.session_state["character_library"] = {
        "Pikachu": {"stats": {"HP": 100}, "gimmicks": {"species": "Pikachu"}},
        "Bulbasaur": {"stats": {"HP": 120}, "gimmicks": {"species": "Bulbasaur"}}
    }
    
    # Simulate DB mode dashboard init
    rosters_df = pd.DataFrame({
        "battle_id": ["b1", "b1", "b1", "b1"],
        "player": ["p1", "p1", "p2", "p2"],
        "species": ["Pikachu", "Unknown", "Bulbasaur", "Unknown"]
    })
    
    st.session_state["db_corpus_raw_tables"] = {"battle_roster_pokemon": rosters_df}
    
    # The dashboard logic parses the roster to generate keys
    players = rosters_df['player'].dropna().unique()
    ally_sample = rosters_df[rosters_df['player'] == players[0]]
    enemy_sample = rosters_df[rosters_df['player'] == players[1]]
    
    ally_keys = [ally_sample.iloc[i].get("species", "비어 있음") if i < len(ally_sample) else "비어 있음" for i in range(4)]
    enemy_keys = [enemy_sample.iloc[i].get("species", "비어 있음") if i < len(enemy_sample) else "비어 있음" for i in range(4)]
    
    ally_df = get_default_df(ally_keys)
    enemy_df = get_default_df(enemy_keys)
    
    assert ally_df.iloc[0]["Hero"] == "Pikachu"
    assert ally_df.iloc[0]["HP"] == 100
    assert enemy_df.iloc[0]["Hero"] == "Bulbasaur"
    assert enemy_df.iloc[0]["HP"] == 120
    assert ally_df.iloc[1]["Hero"] == "Unknown"
    assert ally_df.iloc[1]["HP"] == 0.0
