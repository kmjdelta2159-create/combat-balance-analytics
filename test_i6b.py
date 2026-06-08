import ast
from pathlib import Path
for p in ['modules/step6_dashboard.py']:
    ast.parse(Path(p).read_text(encoding='utf-8'))
    print(p, 'AST OK')

print('--- Test 2: Indentation sanity check ---')
lines = Path('modules/step6_dashboard.py').read_text(encoding='utf-8').splitlines()
trace_exp_line = 0
ts_use_line = 0
schema_if_line = 0
for i, line in enumerate(lines, 1):
    if 'with st.expander("행동 trace 연결' in line:
        trace_exp_line = i
        print('trace_expander', i, len(line) - len(line.lstrip()))
    if '_ts_use = st.checkbox("switch trace 사용"' in line:
        ts_use_line = i
        print('ts_use', i, len(line) - len(line.lstrip()))
    if 'if _bb_id_col != "(없음)" and _bb_team_col != "(없음)":' in line:
        schema_if_line = i
        print('schema_if', i, len(line) - len(line.lstrip()))

assert trace_exp_line < ts_use_line
assert ts_use_line < schema_if_line

print('--- Test 3: Regression Test ---')
import pandas as pd
from modules.per_battle_backtest import build_battles

df = pd.DataFrame([
    {'battle_id': 1, 'side': 'Ally', 'unit_id': 'A1', 'result': 'win', 'HP': 100, 'SPD': 10,
     'turn': 1, 'actor': 'A1', 'incoming': 'A2', 'action': 'switch'},
    {'battle_id': 1, 'side': 'Ally', 'unit_id': 'A2', 'result': 'win', 'HP': 100, 'SPD': 20,
     'turn': '', 'actor': '', 'incoming': '', 'action': ''},
    {'battle_id': 1, 'side': 'Enemy', 'unit_id': 'E1', 'result': 'lose', 'HP': 100, 'SPD': 30,
     'turn': '', 'actor': '', 'incoming': '', 'action': ''},
])
schema = {
    'battle_id_col': 'battle_id',
    'team_col': 'side',
    'entity_id_col': 'unit_id',
    'result_mode': 'battle_level',
    'trace_switches_enabled': True,
    'switch_turn_col': 'turn',
    'switch_outgoing_id_col': 'actor',
    'switch_incoming_id_col': 'incoming',
    'switch_action_col': 'action',
    'switch_action_values': ['switch'],
}
battles = build_battles(df, 2, 'result', ['HP', 'SPD'], [], 'HP',
                        max_battles=10, game_config={}, log_schema=schema)
assert len(battles) == 1 and len(battles[0]) == 4
assert battles[0][3]['trace_actions']['switch'] == {(1, 'A1'): 'A2'}
print('switch trace regression OK')
