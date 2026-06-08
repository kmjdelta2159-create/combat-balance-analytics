import sqlite3
import pandas as pd
import os
import shutil

src_db = 'C:/Users/kmjde/Downloads/pokemon_showdown_production_style.db'
out_dir = '.codex_tmp/adapt8_multi_battle_replay'
os.makedirs(out_dir, exist_ok=True)
dest_db = os.path.join(out_dir, 'pokemon_showdown_multi.db')

if os.path.exists(dest_db):
    os.remove(dest_db)

conn_src = sqlite3.connect(src_db)
conn_dest = sqlite3.connect(dest_db)

tables = ['battles', 'battle_players', 'battle_rules', 'battle_roster_pokemon', 'battle_events']

for t in tables:
    df = pd.read_sql_query(f'SELECT * FROM {t}', conn_src)
    df_copy = df.copy()
    if 'battle_id' in df_copy.columns:
        df_copy['battle_id'] = df_copy['battle_id'].astype(str) + '_copy'
    # For battle_events, we don't need to change event_id because SQLite can auto-increment or we just generate new ones
    if 'event_id' in df_copy.columns:
        df_copy['event_id'] = df_copy['event_id'].max() + df_copy['event_id']
    if 'roster_id' in df_copy.columns:
        df_copy['roster_id'] = df_copy['roster_id'].max() + df_copy['roster_id']
    
    df_combined = pd.concat([df, df_copy], ignore_index=True)
    df_combined.to_sql(t, conn_dest, index=False)

conn_src.close()
conn_dest.close()
print("Created multi-battle fixture at", dest_db)
