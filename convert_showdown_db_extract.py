import os
import argparse
import json
from modules.showdown_db_adapter import extract_from_zip_or_dir, convert_to_battle_log, generate_schema

def main():
    parser = argparse.ArgumentParser(description="Convert Pokemon Showdown DB Extract to DB Corpus format")
    parser.add_argument("--input", required=True, help="Path to SQLite .db, zip file, or extracted directory")
    parser.add_argument("--out-dir", required=True, help="Directory to save the converted files")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.out_dir):
        os.makedirs(args.out_dir)
        
    print(f"Loading data from {args.input}...")
    battles_df, events_df, rosters_df = extract_from_zip_or_dir(args.input)
    
    print("Converting to battle log format...")
    battle_log_df, report = convert_to_battle_log(battles_df, events_df, rosters_df)
    
    battle_log_path = os.path.join(args.out_dir, "battle_log.csv")
    battle_log_df.to_csv(battle_log_path, index=False)
    print(f"Wrote {os.path.basename(battle_log_path)}")
    
    schema = generate_schema()
    schema_path = os.path.join(args.out_dir, "schema.json")
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    print(f"Wrote {os.path.basename(schema_path)}")
    
    report_path = os.path.join(args.out_dir, "adapter_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Wrote {os.path.basename(report_path)}")

if __name__ == "__main__":
    main()
