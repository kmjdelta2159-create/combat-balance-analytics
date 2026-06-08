import os
import shutil
import subprocess
import json
import zipfile
import pandas as pd

base_dir = ".codex_tmp/adapt8_multi_battle_replay"
src_db = os.path.join(base_dir, "pokemon_showdown_multi.db")

# 1. Create Folder format with CSVs
folder_path = os.path.join(base_dir, "input_folder")
os.makedirs(folder_path, exist_ok=True)

import sqlite3
conn = sqlite3.connect(src_db)
for t in ["battles", "battle_events", "battle_roster_pokemon"]:
    df = pd.read_sql_query(f"SELECT * FROM {t}", conn)
    df.to_csv(os.path.join(folder_path, f"{t}.csv"), index=False)
conn.close()

# 2. Create Zip format
zip_path = os.path.join(base_dir, "input_zip.zip")
with zipfile.ZipFile(zip_path, 'w') as zf:
    for f in os.listdir(folder_path):
        zf.write(os.path.join(folder_path, f), f)

formats = {
    "db": src_db,
    "folder": folder_path,
    "zip": zip_path
}

py_exe = 'C:/Users/kmjde/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'

results = {}

for fmt_name, path in formats.items():
    out_dir = os.path.join(base_dir, f"out_{fmt_name}")
    os.makedirs(out_dir, exist_ok=True)
    
    # Run convert
    subprocess.run([py_exe, "-X", "utf8", "convert_showdown_db_extract.py", "--input", path, "--out-dir", out_dir], check=True)
    
    # Run backtest
    subprocess.run([py_exe, "-X", "utf8", "run_db_corpus_backtest.py", 
                    "--schema", os.path.join(out_dir, "schema.json"), 
                    "--out-dir", os.path.join(out_dir, "backtest"), 
                    "--max-battles", "10", 
                    os.path.join(out_dir, "battle_log.csv")], check=True)
    
    # Read reports
    with open(os.path.join(out_dir, "adapter_report.json"), "r", encoding="utf-8") as f:
        report = json.load(f)
        
    df = pd.read_csv(os.path.join(out_dir, "backtest", "db_corpus_backtest_summary.csv"))
    backtest = df.iloc[0].to_dict()
    
    results[fmt_name] = {
        "battle_count": report.get("battle_count"),
        "participant_count": report.get("participant_count"),
        "state_event_count": report.get("state_event_count"),
        "damage_event_count": report.get("damage_event_count"),
        "winner_sides": report.get("winner_sides"),
        "roster_only_entities": report.get("roster_only_entities"),
        "backtest": {
            "actual_count": backtest.get("actual_count"),
            "predicted_count": backtest.get("predicted_count"),
            "accuracy_pct": backtest.get("accuracy_pct"),
            "outcome_mismatches": backtest.get("outcome_mismatches"),
            "state_mismatches": backtest.get("state_mismatches")
        }
    }

# Check parity
is_parity = True
ref = results["db"]
for fmt_name, res in results.items():
    if res != ref:
        is_parity = False
        print(f"Mismatch in {fmt_name}: {res}")

output = {
    "is_parity": is_parity,
    "formats_compared": list(formats.keys()),
    "reference_values": ref
}

with open(os.path.join(base_dir, "input_parity_report.json"), "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"Parity report generated. Parity={is_parity}")
