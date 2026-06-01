import json
from modules.engine import run_simulation
from modules.spatial import SpatialModule

# Unit Test step_toward
sm_manhattan = SpatialModule(distance_metric="manhattan")
pos = sm_manhattan.step_toward({'x': 0, 'y': 0}, {'x': 10, 'y': 0}, 3)
assert pos['x'] == 3 and pos['y'] == 0, f"Manhattan fail: {pos}"
sm_chebyshev = SpatialModule(distance_metric="chebyshev")
pos = sm_chebyshev.step_toward({'x': 0, 'y': 0}, {'x': 10, 'y': 10}, 3)
assert pos['x'] == 3 and pos['y'] == 3, f"Chebyshev fail: {pos}"
print("step_toward unit tests passed!")

# Integration Test
ally = [{
    'name': 'A', 'team': 'Ally', 'id': 'A1',
    'Vit': 500, 'Phys': 100, 'Arm': 30, 'Spd': 50,
    'resources': {'HP': {'current': 500, 'max': 500}},
    'gimmicks': {},
    'position': {'x': 0, 'y': 0},
    'Range': 1,
    'Move': 1
}]
enemy = [{
    'name': 'E', 'team': 'Enemy', 'id': 'E1',
    'Vit': 400, 'Phys': 70, 'Arm': 30, 'Spd': 40,
    'resources': {'HP': {'current': 400, 'max': 400}},
    'gimmicks': {},
    'position': {'x': 10, 'y': 0},
    'Range': 1,
    'Move': 1
}]

winner, logs, sim_metrics = run_simulation(
    ally, enemy, global_damage_formula="phys - target_arm",
    sys_stats=["Vit", "Phys", "Arm", "Spd"], speed_stat="Spd",
    spatial_module=sm_manhattan, range_stat="Range", move_stat="Move"
)
print("Winner:", winner)
print("Total Damage:", sim_metrics.get("total_damage"))
