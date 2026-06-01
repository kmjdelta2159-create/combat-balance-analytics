import json
from modules.engine import run_simulation
from modules.spatial import SpatialModule

# Baseline 1v1
ally = [{
    'name': 'A', 'team': 'Ally', 'id': 'A1',
    'Vit': 500, 'Phys': 100, 'Arm': 30, 'Spd': 50,
    'resources': {'HP': {'current': 500, 'max': 500}},
    'gimmicks': {}
}]
enemy = [{
    'name': 'E', 'team': 'Enemy', 'id': 'E1',
    'Vit': 400, 'Phys': 70, 'Arm': 30, 'Spd': 40,
    'resources': {'HP': {'current': 400, 'max': 400}},
    'gimmicks': {}
}]

# Test 1: No spatial data -> identical behavior
winner, logs, sim_metrics = run_simulation(
    ally, enemy, global_damage_formula="phys - target_arm",
    sys_stats=["Vit", "Phys", "Arm", "Spd"], speed_stat="Spd"
)
print("Test 1 Winner:", winner, "Total Damage:", sim_metrics.get("total_damage"))

# Test 2: Spatial data, out of range
ally[0]['position'] = {'x': 0, 'y': 0}
enemy[0]['position'] = {'x': 5, 'y': 5}
spatial_mod = SpatialModule(distance_metric="manhattan")

winner, logs, sim_metrics = run_simulation(
    ally, enemy, global_damage_formula="phys - target_arm",
    sys_stats=["Vit", "Phys", "Arm", "Spd"], speed_stat="Spd",
    spatial_module=spatial_mod, range_stat="Range"
)
print("Test 2 (Out of range) Winner:", winner, "Total Damage:", sim_metrics.get("total_damage"))

# Test 3: Spatial data, in range
ally[0]['Range'] = 10  # Manhattan distance is 10, so it's in range
enemy[0]['Range'] = 10
winner, logs, sim_metrics = run_simulation(
    ally, enemy, global_damage_formula="phys - target_arm",
    sys_stats=["Vit", "Phys", "Arm", "Spd"], speed_stat="Spd",
    spatial_module=spatial_mod, range_stat="Range"
)
print("Test 3 (In range) Winner:", winner, "Total Damage:", sim_metrics.get("total_damage"))
