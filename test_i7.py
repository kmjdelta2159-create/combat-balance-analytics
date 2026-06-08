import ast
from pathlib import Path
import pandas as pd

print('--- Test 1: AST Check ---')
for p in ['modules/per_battle_backtest.py', 'modules/step6_dashboard.py']:
    ast.parse(Path(p).read_text(encoding='utf-8'))
    print(p, 'AST OK')

print('\n--- Test 2: faint incoming builder ---')
from modules.per_battle_backtest import build_faint_incoming_trace_from_group

df = pd.DataFrame([
    {'turn': 1, 'side': 'Ally', 'outgoing': 'A1', 'incoming': 'A3', 'action': 'replace'},
    {'turn': 1, 'side': 'Enemy', 'outgoing': 'E1', 'incoming': 'E2', 'action': 'move'},
])
schema = {
    'trace_faint_incoming_enabled': True,
    'faint_turn_col': 'turn',
    'faint_side_col': 'side',
    'faint_outgoing_id_col': 'outgoing',
    'faint_incoming_id_col': 'incoming',
    'faint_action_col': 'action',
    'faint_action_values': ['replace'],
}
entries = build_faint_incoming_trace_from_group(df, schema)
print(entries)
assert entries == [{'turn': 1, 'side': 'Ally', 'outgoing': 'A1', 'incoming': 'A3'}]
print('faint incoming builder OK')

print('\n--- Test 3: participant ID filter ---')
from modules.per_battle_backtest import _filter_faint_incoming_for_participants

entries3 = [
    {'turn': 1, 'side': 'Ally', 'outgoing': 'A1', 'incoming': 'A3'},
    {'turn': 1, 'side': 'Enemy', 'outgoing': 'E1', 'incoming': 'missing'},
]
filtered = _filter_faint_incoming_for_participants(entries3, {'A1', 'A3', 'E1'})
print(filtered)
assert filtered == [{'turn': 1, 'side': 'Ally', 'outgoing': 'A1', 'incoming': 'A3'}]
print('faint incoming participant filter OK')

print('\n--- Test 4: faint-only trace build_battles ---')
from modules.per_battle_backtest import build_battles

df4 = pd.DataFrame([
    {'battle_id': 1, 'side': 'Ally', 'unit_id': 'A1', 'result': 'win', 'HP': 100, 'SPD': 10,
     'turn': 1, 'outgoing': 'A1', 'incoming': 'A3', 'action': 'replace'},
    {'battle_id': 1, 'side': 'Ally', 'unit_id': 'A2', 'result': 'win', 'HP': 100, 'SPD': 20,
     'turn': '', 'outgoing': '', 'incoming': '', 'action': ''},
    {'battle_id': 1, 'side': 'Ally', 'unit_id': 'A3', 'result': 'win', 'HP': 100, 'SPD': 30,
     'turn': '', 'outgoing': '', 'incoming': '', 'action': ''},
    {'battle_id': 1, 'side': 'Enemy', 'unit_id': 'E1', 'result': 'lose', 'HP': 100, 'SPD': 40,
     'turn': '', 'outgoing': '', 'incoming': '', 'action': ''},
])
schema4 = {
    'battle_id_col': 'battle_id',
    'team_col': 'side',
    'entity_id_col': 'unit_id',
    'result_mode': 'battle_level',
    'trace_faint_incoming_enabled': True,
    'faint_turn_col': 'turn',
    'faint_side_col': 'side',
    'faint_outgoing_id_col': 'outgoing',
    'faint_incoming_id_col': 'incoming',
    'faint_action_col': 'action',
    'faint_action_values': ['replace'],
}
battles = build_battles(df4, 2, 'result', ['HP', 'SPD'], [], 'HP',
                        max_battles=10, game_config={}, log_schema=schema4)
print('battle_count', len(battles), 'tuple_len', len(battles[0]) if battles else None)
assert len(battles) == 1 and len(battles[0]) == 4
gc = battles[0][3]
assert gc['trace_faint_incoming'] == [{'turn': 1, 'side': 'Ally', 'outgoing': 'A1', 'incoming': 'A3'}]
assert gc['on_active_faint'] == 'replace_from_reserve'
assert gc['preserve_ids'] is True
print('build_battles faint-only trace OK')

print('\n--- Test 5: engine connection ---')
from modules.engine import run_simulation

ally = [
    {'id': 'A1', 'name': 'Lead', 'HP': 100, 'SPD': 10,
     'resources': {'HP': {'current': 100, 'max': 100}}},
    {'id': 'A2', 'name': 'Bench2', 'HP': 100, 'SPD': 20,
     'resources': {'HP': {'current': 100, 'max': 100}}},
    {'id': 'A3', 'name': 'Bench3', 'HP': 100, 'SPD': 30,
     'resources': {'HP': {'current': 100, 'max': 100}}},
]
enemy = [
    {'id': 'E1', 'name': 'Enemy', 'HP': 100, 'SPD': 999,
     'resources': {'HP': {'current': 100, 'max': 100}}},
]
gc = {
    'preserve_ids': True,
    'active_count': 1,
    'on_active_faint': 'replace_from_reserve',
    'trace_faint_incoming': [
        {'turn': 1, 'side': 'Ally', 'outgoing': 'A1', 'incoming': 'A3'},
    ],
}
winner, logs, metrics = run_simulation(
    ally, enemy, max_turns=1,
    speed_stat='SPD',
    sys_stats=['HP', 'SPD'],
    global_damage_formula='999',
    game_config=gc,
    silent=False,
)
joined = '\n'.join(logs)
for line in logs:
    if 'A1' in line or 'A2' in line or 'A3' in line:
        print(line.encode('unicode_escape').decode())
assert 'A3' in joined
assert 'A2' not in joined or joined.find('A3') < joined.find('A2')
print('engine faint incoming trace OK')

print('\nALL TESTS PASSED')
