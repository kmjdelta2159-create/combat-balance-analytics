# -*- coding: utf-8 -*-
"""
pkmn_ref.py — Pokemon-style 1v1 battle reference simulator.

검증 마일스톤용 known-answer 참조 구현. Gen6+ 정식 전투 규칙을 충실히 구현한다:
- 정식 데미지 공식 (Level/Power/A/D/+2 · STAB 1.5 · 18타입 상성 · 크리 1.5 · 난수 0.85~1.0)
- 정식 스탯 공식 (Base/IV/Nature, Lv50, EV=0)
- Physical/Special 분리 (Attack/Defense vs SpAtk/SpDef 라우팅)
- 속도 턴순 · HP 0 = 패배 (1v1) · 그리디 AI

종족값 전사 오류 회피 + 스탯공간 커버리지를 위해 오리지널 크리처(랜덤 종족값) + 포켓몬
메커니즘을 쓴다. 실험 타당성은 메커니즘의 충실도에 달려 있고 그건 정식 규칙 그대로다.

실행하면 두 로그를 생성한다:
- pkmn_battle_log.csv  : 크리처-per-전투 (스탯 + 승패)  → ML 파이프라인용
- pkmn_attack_log.csv  : per-attack (공·방 스탯 + 무브 + damage) → Phase 7 SR용
"""
import csv
import random

TYPES = ["Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting",
         "Poison", "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost",
         "Dragon", "Dark", "Steel", "Fairy"]

# ── 타입 상성 (Gen6+) — 공격타입 기준 ──
_SUPER = {
    "Normal": [], "Fire": ["Grass", "Ice", "Bug", "Steel"],
    "Water": ["Fire", "Ground", "Rock"], "Electric": ["Water", "Flying"],
    "Grass": ["Water", "Ground", "Rock"],
    "Ice": ["Grass", "Ground", "Flying", "Dragon"],
    "Fighting": ["Normal", "Ice", "Rock", "Dark", "Steel"],
    "Poison": ["Grass", "Fairy"],
    "Ground": ["Fire", "Electric", "Poison", "Rock", "Steel"],
    "Flying": ["Grass", "Fighting", "Bug"], "Psychic": ["Fighting", "Poison"],
    "Bug": ["Grass", "Psychic", "Dark"], "Rock": ["Fire", "Ice", "Flying", "Bug"],
    "Ghost": ["Psychic", "Ghost"], "Dragon": ["Dragon"],
    "Dark": ["Psychic", "Ghost"], "Steel": ["Ice", "Rock", "Fairy"],
    "Fairy": ["Fighting", "Dragon", "Dark"],
}
_NOTVERY = {
    "Normal": ["Rock", "Steel"], "Fire": ["Fire", "Water", "Rock", "Dragon"],
    "Water": ["Water", "Grass", "Dragon"],
    "Electric": ["Electric", "Grass", "Dragon"],
    "Grass": ["Fire", "Grass", "Poison", "Flying", "Bug", "Dragon", "Steel"],
    "Ice": ["Fire", "Water", "Ice", "Steel"],
    "Fighting": ["Poison", "Flying", "Psychic", "Bug", "Fairy"],
    "Poison": ["Poison", "Ground", "Rock", "Ghost"],
    "Ground": ["Grass", "Bug"], "Flying": ["Electric", "Rock", "Steel"],
    "Psychic": ["Psychic", "Steel"],
    "Bug": ["Fire", "Fighting", "Poison", "Flying", "Ghost", "Steel", "Fairy"],
    "Rock": ["Fighting", "Ground", "Steel"], "Ghost": ["Dark"],
    "Dragon": ["Steel"], "Dark": ["Fighting", "Dark", "Fairy"],
    "Steel": ["Fire", "Water", "Electric", "Steel"],
    "Fairy": ["Fire", "Poison", "Steel"],
}
_IMMUNE = {
    "Normal": ["Ghost"], "Fighting": ["Ghost"], "Poison": ["Steel"],
    "Ground": ["Flying"], "Psychic": ["Dark"], "Ghost": ["Normal"],
    "Electric": ["Ground"], "Dragon": ["Fairy"],
}


def type_mult(atk_type, def_type):
    """단일 방어타입에 대한 상성 배율."""
    if def_type is None or def_type == "Mono":
        return 1.0
    if def_type in _IMMUNE.get(atk_type, []):
        return 0.0
    if def_type in _SUPER.get(atk_type, []):
        return 2.0
    if def_type in _NOTVERY.get(atk_type, []):
        return 0.5
    return 1.0


def type_effectiveness(atk_type, def_t1, def_t2):
    """1~2개 방어타입 종합 배율 (곱)."""
    return type_mult(atk_type, def_t1) * type_mult(atk_type, def_t2)


# ── 무브풀 (name: type, category, power) — 18타입 × Physical/Special ──
MOVES = {
    "Tackle": ("Normal", "Physical", 40), "Body_Slam": ("Normal", "Physical", 85),
    "Hyper_Voice": ("Normal", "Special", 90),
    "Fire_Punch": ("Fire", "Physical", 75), "Flamethrower": ("Fire", "Special", 90),
    "Aqua_Tail": ("Water", "Physical", 90), "Surf": ("Water", "Special", 90),
    "Thunder_Punch": ("Electric", "Physical", 75),
    "Thunderbolt": ("Electric", "Special", 90),
    "Leaf_Blade": ("Grass", "Physical", 90), "Energy_Ball": ("Grass", "Special", 90),
    "Ice_Punch": ("Ice", "Physical", 75), "Ice_Beam": ("Ice", "Special", 90),
    "Close_Combat": ("Fighting", "Physical", 120),
    "Aura_Sphere": ("Fighting", "Special", 80),
    "Poison_Jab": ("Poison", "Physical", 80),
    "Sludge_Bomb": ("Poison", "Special", 90),
    "Earthquake": ("Ground", "Physical", 100),
    "Earth_Power": ("Ground", "Special", 90),
    "Brave_Bird": ("Flying", "Physical", 120), "Air_Slash": ("Flying", "Special", 75),
    "Zen_Headbutt": ("Psychic", "Physical", 80), "Psychic": ("Psychic", "Special", 90),
    "X_Scissor": ("Bug", "Physical", 80), "Bug_Buzz": ("Bug", "Special", 90),
    "Rock_Slide": ("Rock", "Physical", 75), "Power_Gem": ("Rock", "Special", 80),
    "Shadow_Claw": ("Ghost", "Physical", 70), "Shadow_Ball": ("Ghost", "Special", 80),
    "Dragon_Claw": ("Dragon", "Physical", 80),
    "Dragon_Pulse": ("Dragon", "Special", 85),
    "Crunch": ("Dark", "Physical", 80), "Dark_Pulse": ("Dark", "Special", 80),
    "Iron_Head": ("Steel", "Physical", 80), "Flash_Cannon": ("Steel", "Special", 80),
    "Play_Rough": ("Fairy", "Physical", 90), "Moonblast": ("Fairy", "Special", 95),
}
_MOVES_BY_TYPE = {}
for _mn, (_mt, _mc, _mp) in MOVES.items():
    _MOVES_BY_TYPE.setdefault(_mt, []).append(_mn)

LEVEL = 50


def calc_stat(base, iv, nature_mult, is_hp):
    """정식 스탯 공식 (Lv50, EV=0)."""
    inner = ((2 * base + iv) * LEVEL) // 100
    if is_hp:
        return inner + LEVEL + 10
    return int((inner + 5) * nature_mult)


def make_creature(rng):
    """오리지널 크리처 1개 생성 — 랜덤 종족값/타입/IV/Nature/무브풀."""
    base = {
        "hp": rng.randint(40, 130), "atk": rng.randint(35, 145),
        "def": rng.randint(35, 145), "spa": rng.randint(35, 145),
        "spd": rng.randint(35, 145), "spe": rng.randint(35, 145),
    }
    t1 = rng.choice(TYPES)
    t2 = rng.choice([t for t in TYPES if t != t1]) if rng.random() < 0.35 else None
    # 스탯: IV 0~31, Nature ±10% (한 스탯 ↑, 한 스탯 ↓)
    natures = {k: 1.0 for k in ["atk", "def", "spa", "spd", "spe"]}
    up, down = rng.sample(list(natures), 2)
    natures[up], natures[down] = 1.1, 0.9
    stats = {"hp": calc_stat(base["hp"], rng.randint(0, 31), 1.0, True)}
    for k in ["atk", "def", "spa", "spd", "spe"]:
        stats[k] = calc_stat(base[k], rng.randint(0, 31), natures[k], False)
    # 무브풀 4개: STAB 가능 2개 + 임의 2개
    own = list(_MOVES_BY_TYPE.get(t1, []))
    if t2:
        own += list(_MOVES_BY_TYPE.get(t2, []))
    moveset = []
    if own:
        moveset += rng.sample(own, min(2, len(own)))
    pool = [m for m in MOVES if m not in moveset]
    moveset += rng.sample(pool, 4 - len(moveset))
    return {"type1": t1, "type2": t2, "moves": moveset, **stats}


def calc_damage(atk, dfn, move_name, rng, expected=False):
    """정식 데미지 공식. expected=True면 크리/난수 평균값으로 기대 데미지."""
    mtype, mcat, power = MOVES[move_name]
    A = atk["atk"] if mcat == "Physical" else atk["spa"]
    D = dfn["def"] if mcat == "Physical" else dfn["spd"]
    base = (((2 * LEVEL / 5 + 2) * power * A / D) / 50) + 2
    base = int(base)  # floor
    stab = 1.5 if mtype in (atk["type1"], atk["type2"]) else 1.0
    eff = type_effectiveness(mtype, dfn["type1"], dfn["type2"])
    if expected:
        crit, rnd = 1.0, 0.925
    else:
        crit = 1.5 if rng.random() < (1.0 / 24.0) else 1.0
        rnd = rng.randint(85, 100) / 100.0
    dmg = int(base * stab * eff * crit * rnd)
    if eff == 0.0:
        return 0, {"stab": stab, "eff": eff, "crit": crit, "rand": rnd}
    return max(1, dmg), {"stab": stab, "eff": eff, "crit": crit, "rand": rnd}


def choose_move(atk, dfn):
    """그리디 AI — 기대 데미지 최대 무브."""
    best, best_dmg = atk["moves"][0], -1.0
    for mv in atk["moves"]:
        d, _ = calc_damage(atk, dfn, mv, None, expected=True)
        if d > best_dmg:
            best, best_dmg = mv, d
    return best


def run_battle(c1, c2, rng):
    """1v1 전투. 반환: (winner_idx 0/1, attack_records)."""
    s = [dict(c1, current_hp=c1["hp"]), dict(c2, current_hp=c2["hp"])]
    records = []
    for _turn in range(50):
        order = [0, 1] if s[0]["spe"] > s[1]["spe"] else (
            [1, 0] if s[1]["spe"] > s[0]["spe"] else rng.sample([0, 1], 2))
        for ai in order:
            di = 1 - ai
            if s[ai]["current_hp"] <= 0 or s[di]["current_hp"] <= 0:
                continue
            mv = choose_move(s[ai], s[di])
            dmg, info = calc_damage(s[ai], s[di], mv, rng)
            s[di]["current_hp"] -= dmg
            mtype, mcat, power = MOVES[mv]
            records.append({
                "Atk_Attack": s[ai]["atk"], "Atk_SpAtk": s[ai]["spa"],
                "Atk_Type1": s[ai]["type1"], "Atk_Type2": s[ai]["type2"] or "Mono",
                "Def_Defense": s[di]["def"], "Def_SpDef": s[di]["spd"],
                "Def_Type1": s[di]["type1"], "Def_Type2": s[di]["type2"] or "Mono",
                "Move_Power": power, "Move_Type": mtype, "Move_Category": mcat,
                "Damage": dmg,
            })
        if s[0]["current_hp"] <= 0 or s[1]["current_hp"] <= 0:
            break
    if s[0]["current_hp"] <= 0 and s[1]["current_hp"] > 0:
        return 1, records
    if s[1]["current_hp"] <= 0 and s[0]["current_hp"] > 0:
        return 0, records
    # 턴 제한 도달 — HP% 높은 쪽 승
    h0 = s[0]["current_hp"] / s[0]["hp"]
    h1 = s[1]["current_hp"] / s[1]["hp"]
    return (0 if h0 >= h1 else 1), records


def main():
    rng = random.Random(20260522)
    roster = [make_creature(rng) for _ in range(80)]
    battle_rows, attack_rows = [], []
    N = 2500
    for _ in range(N):
        i, j = rng.sample(range(len(roster)), 2)
        c1, c2 = roster[i], roster[j]
        winner, recs = run_battle(c1, c2, rng)
        for idx, c in enumerate((c1, c2)):
            battle_rows.append({
                "HP": c["hp"], "Attack": c["atk"], "Defense": c["def"],
                "SpAtk": c["spa"], "SpDef": c["spd"], "Speed": c["spe"],
                "Type1": c["type1"], "Type2": c["type2"] or "Mono",
                "Is_Victorious": 1 if winner == idx else 0,
            })
        attack_rows.extend(recs)

    rng.shuffle(attack_rows)
    attack_rows = attack_rows[:8000]

    with open("pkmn_battle_log.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(battle_rows[0].keys()))
        w.writeheader()
        w.writerows(battle_rows)
    with open("pkmn_attack_log.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(attack_rows[0].keys()))
        w.writeheader()
        w.writerows(attack_rows)

    print("battle_log rows:", len(battle_rows))
    print("attack_log rows:", len(attack_rows))
    dmgs = [r["Damage"] for r in attack_rows]
    print("damage min/mean/max: %d / %.1f / %d"
          % (min(dmgs), sum(dmgs) / len(dmgs), max(dmgs)))
    wins = sum(r["Is_Victorious"] for r in battle_rows)
    print("battle_log win rate: %.3f (기대 0.5)" % (wins / len(battle_rows)))


if __name__ == "__main__":
    main()
