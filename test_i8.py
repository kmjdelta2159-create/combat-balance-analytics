import ast
from pathlib import Path

print('--- Test 1: AST Check ---')
for p in ['modules/engine.py', 'modules/per_battle_backtest.py', 'modules/step6_dashboard.py']:
    ast.parse(Path(p).read_text(encoding='utf-8'))
    print(p, 'AST OK')

print('\n--- Test 2: Engine preserve_initial_on_field ---')
from modules.engine import run_simulation
ally = [
    {'id': 'A1', 'name': 'Bench1', 'HP': 100, 'SPD': 1, 'on_field': False,
     'resources': {'HP': {'current': 100, 'max': 100}}},
    {'id': 'A2', 'name': 'Lead2', 'HP': 100, 'SPD': 2, 'on_field': True,
     'resources': {'HP': {'current': 100, 'max': 100}}},
]
enemy = [
    {'id': 'E1', 'name': 'Enemy', 'HP': 100, 'SPD': 999, 'on_field': True,
     'resources': {'HP': {'current': 100, 'max': 100}}},
]
winner, logs, metrics = run_simulation(
    ally, enemy, max_turns=1,
    speed_stat='SPD',
    sys_stats=['HP', 'SPD'],
    global_damage_formula='0',
    game_config={'preserve_ids': True, 'active_count': 1, 'preserve_initial_on_field': True},
    silent=False,
)
joined = '\n'.join(logs)
for line in logs:
    if '[Turn 1]' in line:
        print(line.encode('unicode_escape').decode())
assert '[Turn 1] A2' in joined
assert '[Turn 1] A1' not in joined
print('engine preserve_initial_on_field OK')

print('\n--- Test 3: active_count fallback regression ---')
ally = [
    {'id': 'A1', 'name': 'First', 'HP': 100, 'SPD': 1, 'on_field': False,
     'resources': {'HP': {'current': 100, 'max': 100}}},
    {'id': 'A2', 'name': 'Second', 'HP': 100, 'SPD': 2, 'on_field': True,
     'resources': {'HP': {'current': 100, 'max': 100}}},
]
enemy = [
    {'id': 'E1', 'name': 'Enemy', 'HP': 100, 'SPD': 999,
     'resources': {'HP': {'current': 100, 'max': 100}}},
]
winner, logs, metrics = run_simulation(
    ally, enemy, max_turns=1,
    speed_stat='SPD',
    sys_stats=['HP', 'SPD'],
    global_damage_formula='0',
    game_config={'preserve_ids': True, 'active_count': 1},
    silent=False,
)
joined = '\n'.join(logs)
for line in logs:
    if '[Turn 1]' in line:
        print(line.encode('unicode_escape').decode())
assert '[Turn 1] A1' in joined
assert '[Turn 1] A2' not in joined
print('active_count fallback regression OK')

print('\n--- Test 4: build_battles initial-only ---')
import pandas as pd
from modules.per_battle_backtest import build_battles
df = pd.DataFrame([
    {'battle_id': 1, 'side': 'Ally', 'unit_id': 'A1', 'result': 'win', 'HP': 100, 'SPD': 10, 'lead': 0, 'slot': 1},
    {'battle_id': 1, 'side': 'Ally', 'unit_id': 'A2', 'result': 'win', 'HP': 100, 'SPD': 20, 'lead': 1, 'slot': 2},
    {'battle_id': 1, 'side': 'Enemy', 'unit_id': 'E1', 'result': 'lose', 'HP': 100, 'SPD': 30, 'lead': 1, 'slot': 1},
    {'battle_id': 1, 'side': 'Enemy', 'unit_id': 'E2', 'result': 'lose', 'HP': 100, 'SPD': 40, 'lead': 0, 'slot': 2},
])
schema = {
    'battle_id_col': 'battle_id',
    'team_col': 'side',
    'entity_id_col': 'unit_id',
    'result_mode': 'battle_level',
    'initial_on_field_enabled': True,
    'initial_on_field_col': 'lead',
    'initial_on_field_values': ['1', 'true', 'lead'],
    'initial_order_col': 'slot',
}
battles = build_battles(df, 2, 'result', ['HP', 'SPD'], [], 'HP',
                        max_battles=10, game_config={}, log_schema=schema)
print('battle_count', len(battles), 'tuple_len', len(battles[0]) if battles else None)
assert len(battles) == 1 and len(battles[0]) == 4
ally, enemy, ally_wins, gc = battles[0]
print([(u['id'], u.get('on_field')) for u in ally], [(u['id'], u.get('on_field')) for u in enemy], gc)
assert [u['id'] for u in ally] == ['A1', 'A2']
assert ally[0]['on_field'] is False and ally[1]['on_field'] is True
assert enemy[0]['on_field'] is True and enemy[1]['on_field'] is False
assert gc['preserve_initial_on_field'] is True
print('build_battles initial on-field OK')

print('\n--- Test 5: DB -> engine trace check ---')
df = pd.DataFrame([
    {'battle_id': 1, 'side': 'Ally', 'unit_id': 'A1', 'result': 'win', 'HP': 100, 'SPD': 10, 'lead': 0},
    {'battle_id': 1, 'side': 'Ally', 'unit_id': 'A2', 'result': 'win', 'HP': 100, 'SPD': 20, 'lead': 1},
    {'battle_id': 1, 'side': 'Enemy', 'unit_id': 'E1', 'result': 'lose', 'HP': 100, 'SPD': 999, 'lead': 1},
])
schema = {
    'battle_id_col': 'battle_id',
    'team_col': 'side',
    'entity_id_col': 'unit_id',
    'result_mode': 'battle_level',
    'initial_on_field_enabled': True,
    'initial_on_field_col': 'lead',
    'initial_on_field_values': ['1'],
}
battles = build_battles(df, 2, 'result', ['HP', 'SPD'], [], 'HP',
                        max_battles=10, game_config={}, log_schema=schema)
ally, enemy, ally_wins, gc = battles[0]
winner, logs, metrics = run_simulation(
    ally, enemy, max_turns=1,
    speed_stat='SPD',
    sys_stats=['HP', 'SPD'],
    global_damage_formula='0',
    game_config=gc,
    silent=False,
)
joined = '\n'.join(logs)
for line in logs:
    if '[Turn 1]' in line:
        print(line.encode('unicode_escape').decode())
assert '[Turn 1] A2' in joined
assert '[Turn 1] A1' not in joined
print('DB initial on-field -> engine OK')

print('\nALL TESTS PASSED')
