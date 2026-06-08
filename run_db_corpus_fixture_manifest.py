import os
import sys
import json
import argparse
import subprocess
import pandas as pd

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    manifest_path = os.path.abspath(args.manifest)
    manifest_dir = os.path.dirname(manifest_path)
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    cases = manifest.get("cases", [])
    if not cases:
        print("No cases found in manifest.")
        return

    os.makedirs(args.out_dir, exist_ok=True)
    
    all_passed = True
    
    for case in cases:
        name = case["name"]
        schema_path = os.path.join(manifest_dir, case["schema"])
        log_paths = [os.path.join(manifest_dir, lp) for lp in case["logs"]]
        expected = case.get("expected", {})
        
        case_out_dir = os.path.join(args.out_dir, name)
        os.makedirs(case_out_dir, exist_ok=True)
        
        print(f"Running fixture case: {name}")
        cmd = [
            sys.executable, "-X", "utf8", "run_db_corpus_backtest.py",
            "--schema", schema_path,
            "--out-dir", case_out_dir
        ] + log_paths
        
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if res.returncode != 0:
            print(f"[{name}] CLI failed. Stderr: {res.stderr}")
            all_passed = False
            continue
            
        summary_csv = os.path.join(case_out_dir, "db_corpus_backtest_summary.csv")
        if not os.path.exists(summary_csv):
            print(f"[{name}] summary CSV not found at {summary_csv}")
            all_passed = False
            continue
            
        df = pd.read_csv(summary_csv)
        if len(df) != 1:
            print(f"[{name}] expected 1 row in summary, got {len(df)}")
            all_passed = False
            continue
            
        row = df.iloc[0]
        
        for k, expected_v in expected.items():
            if k not in row:
                print(f"[{name}] Key {k} missing in summary")
                all_passed = False
                continue
                
            actual_v = row[k]
            if isinstance(expected_v, str) and expected_v.startswith(">"):
                try:
                    threshold = float(expected_v[1:])
                    actual_val = float(actual_v)
                    if not (actual_val > threshold):
                        print(f"[{name}] Assertion failed for {k}: expected >{threshold}, got {actual_v}")
                        all_passed = False
                except ValueError:
                    if str(actual_v) != str(expected_v):
                        print(f"[{name}] Assertion failed for {k}: expected {expected_v}, got {actual_v}")
                        all_passed = False
            else:
                if str(actual_v) != str(expected_v):
                    print(f"[{name}] Assertion failed for {k}: expected {expected_v}, got {actual_v}")
                    all_passed = False
                    
    if not all_passed:
        print("Some fixture cases failed.")
        sys.exit(1)
    else:
        print("All fixture cases passed.")

if __name__ == "__main__":
    main()
