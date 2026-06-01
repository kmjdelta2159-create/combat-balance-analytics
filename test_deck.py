import json
from modules.engine import run_simulation
from modules.deck import DeckModule

deck_mod = DeckModule(hand_size=2, energy_per_turn=2)

ally = [{
    'name': 'A', 'team': 'Ally', 'id': 'A1',
    'Vit': 500, 'Phys': 100, 'Arm': 30, 'Spd': 50,
    'resources': {'HP': {'current': 500, 'max': 500}},
    'gimmicks': {},
    'deck': [
        {"name": "Strike", "cost": 1, "gimmicks": {"Target_Logic": "Single_Target", "Formula": "phys"}},
        {"name": "Defend", "cost": 1, "gimmicks": {"Formula": "0", "Trigger": "On_Hit"}}
    ]
}]
enemy = [{
    'name': 'E', 'team': 'Enemy', 'id': 'E1',
    'Vit': 400, 'Phys': 70, 'Arm': 30, 'Spd': 40,
    'resources': {'HP': {'current': 400, 'max': 400}},
    'gimmicks': {},
    'deck': [
        {"name": "Strike", "cost": 1, "gimmicks": {"Target_Logic": "Single_Target", "Formula": "phys"}}
    ]
}]

winner, logs, sim_metrics = run_simulation(
    ally, enemy, global_damage_formula="phys - target_arm",
    sys_stats=["Vit", "Phys", "Arm", "Spd"], speed_stat="Spd",
    deck_module=deck_mod, max_turns=5
)

print("Winner:", winner)
for log in logs:
    if "Strike" in log or "Defend" in log or "드로우" in log or "버림" in log or "전투" in log:
        print(log)
print("Total Damage:", sim_metrics.get("total_damage"))
