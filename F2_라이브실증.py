"""PR-F2 동적 해저드 라이브 실증.

시나리오: Ally A1이 setup_first 정책으로 첫 턴에 효과 무브 '해저드설치'를 사용 →
move_effects의 set_hazard가 ctx['field_state']['hazard']['Enemy']=0.25 를 설치.
이후 Enemy 유닛이 죽어 예비가 교체 진입할 때마다 _apply_entry_hazard가 동적 해저드를
읽어 진입 데미지를 발화해야 한다. game_config에 정적 mechanisms.hazard는 두지 않는다
→ 순수하게 '무브 설치 → 진입 데미지' 동적 경로만 검증.

기대 로그:
  - 초기 리드(A1,E1)는 진입 데미지 없음.
  - A1이 '해저드설치' 사용 시 "Enemy 진영에 해저드 설치 (0.250)".
  - Enemy 예비(E2,E3...) 진입 시 "진입 데미지 N (Hazard)" (N = max*0.25 바닥값).
  - Ally 예비 진입은 데미지 없음(Enemy 진영에만 설치).
"""
from modules.engine import run_simulation

# 효과 무브 '해저드설치'(power 0, 데미지 없음) + '강타'(딜)
movepool = [
    {"name": "해저드설치", "power": 0},
    {"name": "강타", "power": 100},
]

def ally(idx, hp):
    return {
        "name": f"A{idx}", "team": "Ally", "id": f"A{idx}",
        "Phys": 120, "Arm": 20, "Spd": 60,
        "resources": {"HP": {"current": hp, "max": hp}},
        "gimmicks": {}, "movepool": movepool, "roster_idx": idx,
    }

def enemy(idx, hp):
    return {
        "name": f"E{idx}", "team": "Enemy", "id": f"E{idx}",
        "Phys": 110, "Arm": 20, "Spd": 50,
        "resources": {"HP": {"current": hp, "max": hp}},
        "gimmicks": {}, "movepool": [{"name": "강타", "power": 100}], "roster_idx": idx,
    }

# Ally 1명 + 예비 2명, Enemy 1명 + 예비 2명
ally_party = [ally(1, 300), ally(2, 160), ally(3, 200)]
enemy_party = [enemy(1, 130), enemy(2, 200), enemy(3, 160)]

game_config = {
    "active_count": 1,                       # 진영당 1명 출전 + 나머지 예비 → 교체 진입 발생
    "move_policy": "setup_first",            # A1이 첫 턴에 효과 무브 우선
    "move_effects": {
        "해저드설치": [{"kind": "set_hazard", "team": "Enemy", "percent": 0.25}],
    },
    "on_active_faint": "replace_from_reserve",  # 사망 시 예비 교체 (진입 hook 발화)
    # 주의: 정적 mechanisms.hazard 없음 — 동적 경로만 본다.
}

winner, logs, metrics = run_simulation(
    ally_party, enemy_party,
    global_damage_formula="phys - target_arm",
    sys_stats=["Phys", "Arm", "Spd"], speed_stat="Spd",
    game_config=game_config, max_turns=60,
)

print("\n".join(logs))
print("\n=== RESULT ===")
print("Winner:", winner)

# 자동 판정
joined = "\n".join(logs)
install = [l for l in logs if "해저드 설치" in l]
entry_dmg = [l for l in logs if "진입 데미지" in l and "(Hazard)" in l]
print("해저드 설치 로그:", len(install), "건")
for l in install: print("  ", l.strip())
print("진입 데미지 로그:", len(entry_dmg), "건")
for l in entry_dmg: print("  ", l.strip())

ok = len(install) >= 1 and len(entry_dmg) >= 1
print("\nLIVE PASS" if ok else "\nLIVE FAIL — 설치 또는 진입 데미지 로그 없음")
