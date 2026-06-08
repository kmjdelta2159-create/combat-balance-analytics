import ast
from pathlib import Path

print('--- Test 1: AST Check ---')
for p in ['modules/engine.py', 'modules/per_battle_backtest.py', 'modules/step6_dashboard.py']:
    ast.parse(Path(p).read_text(encoding='utf-8'))
    print(p, 'AST OK')

print('\n--- Test 2: DB snapshot builder ---')
import pandas as pd
from modules.per_battle_backtest import build_state_snapshots_from_group
df = pd.DataFrame([
    {'turn': 1, 'unit': 'A1', 'hp_after': 80, 'status': 'poison', 'dead': 0},
    {'turn': 1, 'unit': 'E1', 'hp_after': 0, 'status': '', 'dead': 1},
    {'turn': 2, 'unit': 'A1', 'hp_after': 60, 'status': 'poison', 'dead': 0},
])
schema = {
    'state_trace_enabled': True,
    'state_turn_col': 'turn',
    'state_entity_id_col': 'unit',
    'state_hp_col': 'hp_after',
    'state_status_col': 'status',
    'state_fainted_col': 'dead',
}
snaps = build_state_snapshots_from_group(df, schema)
print(snaps)
assert snaps[1]['A1']['hp'] == 80.0
assert snaps[1]['A1']['status'] == 'poison'
assert snaps[1]['A1']['fainted'] is False
assert snaps[1]['E1']['fainted'] is True
assert snaps[2]['A1']['hp'] == 60.0
print('state snapshot builder OK')

print('\n--- Test 3: build_battles state-only 4-tuple ---')
from modules.per_battle_backtest import build_battles
df = pd.DataFrame([
    {'battle_id': 1, 'side': 'Ally', 'unit_id': 'A1', 'result': 'win', 'HP': 100, 'SPD': 10, 'turn': 1, 'hp_after': 100, 'dead': 0},
    {'battle_id': 1, 'side': 'Enemy', 'unit_id': 'E1', 'result': 'lose', 'HP': 100, 'SPD': 20, 'turn': 1, 'hp_after': 100, 'dead': 0},
])
schema = {
    'battle_id_col': 'battle_id',
    'team_col': 'side',
    'entity_id_col': 'unit_id',
    'result_mode': 'battle_level',
    'state_trace_enabled': True,
    'state_turn_col': 'turn',
    'state_entity_id_col': 'unit_id',
    'state_hp_col': 'hp_after',
    'state_fainted_col': 'dead',
    'state_hp_mode': 'absolute',
    'state_hp_tolerance': 0,
}
battles = build_battles(df, 2, 'result', ['HP', 'SPD'], [], 'HP',
                        max_battles=10, game_config={}, log_schema=schema)
print('battle_count', len(battles), 'tuple_len', len(battles[0]) if battles else None)
assert len(battles) == 1 and len(battles[0]) == 4
gc = battles[0][3]
assert '_expected_state_snapshots' in gc
assert gc['_expected_state_snapshots'][1]['A1']['hp'] == 100.0
assert gc['_state_score_config']['hp_mode'] == 'absolute'
print('build_battles state-only OK')

print('\n--- Test 4: worker state_score perfect match ---')
from modules.engine import _worker_simulate_match
ally = [{'id': 'A1', 'name': 'A1', 'HP': 100, 'SPD': 1, 'resources': {'HP': {'current': 100, 'max': 100}}}]
enemy = [{'id': 'E1', 'name': 'E1', 'HP': 100, 'SPD': 2, 'resources': {'HP': {'current': 100, 'max': 100}}}]
gc = {
    'preserve_ids': True,
    '_expected_state_snapshots': {
        1: {
            'A1': {'hp': 100.0, 'fainted': False},
            'E1': {'hp': 100.0, 'fainted': False},
        }
    },
    '_state_score_config': {'hp_mode': 'absolute', 'hp_tol': 0.0},
}
res = _worker_simulate_match((
    ally, enemy, None, 'SPD', ['HP', 'SPD'], '0',
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]['state_score']
assert score['checks'] >= 4
assert score['mismatches'] == 0
assert score['accuracy'] == 1.0
print('worker state_score perfect OK')

print('\n--- Test 5: worker state_score mismatch ---')
gc['_expected_state_snapshots'][1]['A1']['hp'] = 50.0
res = _worker_simulate_match((
    ally, enemy, None, 'SPD', ['HP', 'SPD'], '0',
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]['state_score']
assert score['hp_mismatches'] >= 1
assert score['mismatches'] >= 1
print('worker state_score mismatch OK')

print('\nALL TESTS PASSED')
