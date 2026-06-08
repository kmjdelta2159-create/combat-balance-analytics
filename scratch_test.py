import pandas as pd
import json
from run_db_corpus_backtest import load_db_file
from modules.per_battle_backtest import build_battles
from modules.engine import _worker_simulate_match
from modules.engine import default_stochasticity_factory

df = load_db_file('.codex_tmp/adapt6_switch_trace/battle_log.csv')
with open('.codex_tmp/adapt6_switch_trace/schema.json') as f:
    schema = json.load(f)

battles = build_battles(
    df, 2, 'result', 
    schema['system_stats'], schema['system_gimmicks'], schema['health_stat'], 
    log_schema=schema['log_schema']
)
a, e, w, gc = battles[0]

res = _worker_simulate_match((
    a, e, schema.get('combat_flow'), schema.get('speed_stat'), schema['system_stats'], 
    schema.get('global_damage_formula', '0'), 100, default_stochasticity_factory, 
    None, None, None, None, None, gc, 0
))

metrics = res[1]
actual_state = metrics.get('_actual_state', {})
# The actual state is not returned in metrics directly! Wait, _worker_simulate_match only returns metrics.
print("Metrics keys:", metrics.keys())
print("Expected keys:", gc['_expected_state_snapshots'][16].keys())
