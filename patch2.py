import sys

with open('modules/step2_system_definition.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if "if not st.session_state.get('library_parsed', False):" in line:
        start_idx = i
    if "if 'enemy_df' in st.session_state: del st.session_state['enemy_df']" in line:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    new_lines = lines[:start_idx]
    
    code = """                if not st.session_state.get('library_parsed', False):
                    parsed_dict = {}
                    is_db_mode = st.session_state.get("input_mode") == "structured_battle_package"
                    
                    if is_db_mode and "db_corpus_raw_tables" in st.session_state and "battle_roster_pokemon" in st.session_state["db_corpus_raw_tables"]:
                        roster_df = st.session_state["db_corpus_raw_tables"]["battle_roster_pokemon"]
                        for idx, row in roster_df.iterrows():
                            import pandas as pd
                            char_key = str(row.get("species", row.get("name", f"Unknown_{idx}")))
                            if char_key == "nan" or pd.isna(char_key):
                                continue
                            if char_key not in parsed_dict:
                                parsed_dict[char_key] = {
                                    "stats": {f: float(row[f]) for f in numeric_cols if f in row and pd.notnull(row[f])},
                                    "gimmicks": {g: str(row[g]) for g in gimmick_cols if g in row and pd.notnull(row[g])}
                                }
                    else:
                        for idx, row in df.iterrows():
                            import pandas as pd
                            char_key = str(row[char_col])
                            if pd.isna(char_key): continue
                            parsed_dict[char_key] = {
                                "stats": {f: float(row[f]) for f in numeric_cols if f in row and pd.notnull(row[f])},
                                "gimmicks": {g: str(row[g]) for g in gimmick_cols if g in row and pd.notnull(row[g])}
                            }
                    
                    st.session_state['character_library'] = parsed_dict
                    st.session_state['library_parsed'] = True
                    
                    if 'ally_df' in st.session_state: del st.session_state['ally_df']
                    if 'enemy_df' in st.session_state: del st.session_state['enemy_df']
"""
    new_lines.append(code)
    new_lines.extend(lines[end_idx + 1:])
    
    with open('modules/step2_system_definition.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print('Patched successfully')
else:
    print('Failed to find indices', start_idx, end_idx)
