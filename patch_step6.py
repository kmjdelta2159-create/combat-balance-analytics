import sys

with open('modules/step6_dashboard.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if "if 'ally_df' not in st.session_state:" in line:
        start_idx = i
    if "if 'enemy_df' not in st.session_state:" in line:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    new_lines = lines[:start_idx]
    
    code = """        if 'ally_df' not in st.session_state or 'enemy_df' not in st.session_state:
            ally_keys = [st.session_state.get(f"Ally_slot_{i}_select", "비어 있음") for i in range(4)]
            enemy_keys = [st.session_state.get(f"Enemy_slot_{i}_select", "비어 있음") for i in range(4)]
            
            if st.session_state.get("structured_package_mode") and "db_corpus_raw_tables" in st.session_state:
                rosters_df = st.session_state["db_corpus_raw_tables"].get("battle_roster_pokemon")
                if rosters_df is not None and not rosters_df.empty:
                    b_id = rosters_df['battle_id'].iloc[0] if 'battle_id' in rosters_df.columns else None
                    if b_id:
                        sample_roster = rosters_df[rosters_df['battle_id'] == b_id]
                    else:
                        sample_roster = rosters_df
                        
                    players = sample_roster['player'].dropna().unique() if 'player' in sample_roster.columns else []
                    if len(players) >= 2:
                        ally_sample = sample_roster[sample_roster['player'] == players[0]]
                        enemy_sample = sample_roster[sample_roster['player'] == players[1]]
                    else:
                        ally_sample = sample_roster.head(min(4, len(sample_roster)))
                        enemy_sample = sample_roster.iloc[len(ally_sample):len(ally_sample)+4]
                        
                    def get_key(row):
                        k = row.get("species", row.get("name", "비어 있음"))
                        if pd.isna(k) or k == "nan": return "비어 있음"
                        return str(k)
                        
                    ally_keys = [get_key(ally_sample.iloc[i]) if i < len(ally_sample) else "비어 있음" for i in range(4)]
                    enemy_keys = [get_key(enemy_sample.iloc[i]) if i < len(enemy_sample) else "비어 있음" for i in range(4)]
                    
            st.session_state['ally_df'] = get_default_df(ally_keys)
            st.session_state['enemy_df'] = get_default_df(enemy_keys)
"""
    new_lines.append(code)
    new_lines.extend(lines[end_idx + 1:])
    
    with open('modules/step6_dashboard.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print('Patched step6 successfully')
else:
    print('Failed to find indices in step6', start_idx, end_idx)
