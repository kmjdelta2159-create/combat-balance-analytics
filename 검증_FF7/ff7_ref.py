# -*- coding: utf-8 -*-
"""ff7_ref.py - FF7 1v1 reference simulator (GameFAQs Algorithms FAQ 단순화).

Physical/Magic 데미지 분리, 9속성 (약점 2x, 흡수 -1x), Limit Break 게이지,
Dex 기반 턴 순서, Crit = Luck/64. 1v1, 순수 턴제, MP 비용 6 고정.
출력: ff7_battle_log.csv + ff7_attack_log.csv
"""
import csv
import random

ELEMENTS = ["Fire", "Ice", "Lightning", "Earth", "Water", "Wind",
            "Holy", "Poison", "Gravity"]
LEVEL = 50

MOVES = {
    "Slash":        ("Physical", None,        16),
    "Heavy_Strike": ("Physical", None,        24),
    "Cross_Slash":  ("Physical", None,        32),
    "Pierce":       ("Physical", None,        20),
    "Fire":         ("Magic",    "Fire",      14),
    "Fire2":        ("Magic",    "Fire",      30),
    "Fire3":        ("Magic",    "Fire",      60),
    "Ice":          ("Magic",    "Ice",       14),
    "Ice2":         ("Magic",    "Ice",       30),
    "Ice3":         ("Magic",    "Ice",       60),
    "Bolt":         ("Magic",    "Lightning", 14),
    "Bolt2":        ("Magic",    "Lightning", 30),
    "Bolt3":        ("Magic",    "Lightning", 60),
    "Quake":        ("Magic",    "Earth",     24),
    "Quake2":       ("Magic",    "Earth",     48),
    "Water":        ("Magic",    "Water",     24),
    "Aqualung":     ("Magic",    "Water",     50),
    "Wind_Slash":   ("Magic",    "Wind",      28),
    "Aero":         ("Magic",    "Wind",      54),
    "Holy":         ("Magic",    "Holy",      66),
    "Bio":          ("Magic",    "Poison",    26),
    "Bio2":         ("Magic",    "Poison",    46),
    "Demi":         ("Magic",    "Gravity",   28),
    "Demi2":        ("Magic",    "Gravity",   42),
    "Limit_Break":  ("Physical", None,        32),
}

_PHYS_MOVES = [m for m, (c, _, _) in MOVES.items()
               if c == "Physical" and m != "Limit_Break"]
_MAGIC_MOVES = [m for m, (c, _, _) in MOVES.items() if c == "Magic"]


def get_elem_mult(move_elem, def_resist, def_absorb):
    if move_elem is None:
        return 1.0
    if move_elem == def_absorb:
        return -1.0
    if move_elem == def_resist:
        return 2.0
    return 1.0


def make_character(rng):
    char = {
        "HP":            rng.randint(1500, 4500),
        "MP":            rng.randint(80, 280),
        "Strength":      rng.randint(20, 80),
        "Magic":         rng.randint(20, 80),
        "Vitality":      rng.randint(20, 80),
        "Spirit":        rng.randint(20, 80),
        "Dexterity":     rng.randint(20, 80),
        "Luck":          rng.randint(5, 30),
        "WeaponAttack":  rng.randint(15, 90),
        "WeaponMagic":   rng.randint(0, 50),
        "ArmorDefense":  rng.randint(10, 70),
        "ArmorSpirit":   rng.randint(0, 25),
        "ResistElement": (rng.choice(ELEMENTS) if rng.random() < 0.55 else None),
        "AbsorbElement": (rng.choice(ELEMENTS) if rng.random() < 0.15 else None),
    }
    if char["ResistElement"] == char["AbsorbElement"]:
        char["AbsorbElement"] = None
    return char


def calc_phys_damage(atk, dfn, move_name, rng, expected=False):
    _, _, power = MOVES[move_name]
    phys_atk = atk["Strength"] + atk["WeaponAttack"]
    base = (phys_atk * (phys_atk + LEVEL)) // 64
    def_total = dfn["Vitality"] + dfn["ArmorDefense"]
    def_clip = max(0, min(512, def_total))
    damage = (base * (512 - def_clip) // 512) * power // 16
    if expected:
        crit_mult = 1.0 + (atk["Luck"] / 64.0)
        rand_mult = 1.0
    else:
        crit_mult = 2.0 if rng.random() < (atk["Luck"] / 64.0) else 1.0
        rand_mult = rng.uniform(0.9375, 1.0625)
    return max(1, int(damage * crit_mult * rand_mult))


def calc_magic_damage(atk, dfn, move_name, rng, expected=False):
    _, elem, power = MOVES[move_name]
    mag_atk = atk["Magic"] + atk["WeaponMagic"]
    base = (mag_atk * (mag_atk + LEVEL)) // 64
    spr_total = dfn["Spirit"] + dfn["ArmorSpirit"]
    spr_clip = max(0, min(512, spr_total))
    damage = (base * (512 - spr_clip) // 512) * power // 16
    elem_mult = get_elem_mult(elem, dfn.get("ResistElement"),
                              dfn.get("AbsorbElement"))
    rand_mult = 1.0 if expected else rng.uniform(0.9375, 1.0625)
    final = int(damage * elem_mult * rand_mult)
    if elem_mult < 0:
        return final
    return max(1, final) if elem_mult > 0 else 0


def choose_action(atk, dfn, mp_remaining, limit_ready, rng=None):
    if rng is not None and rng.random() < 0.05:
        pool = list(_PHYS_MOVES)
        if mp_remaining >= 6:
            pool += _MAGIC_MOVES
        if limit_ready:
            pool.append("Limit_Break")
        return rng.choice(pool)
    best, best_dmg = None, -1.0
    if limit_ready:
        d = calc_phys_damage(atk, dfn, "Limit_Break", None, expected=True)
        if d > best_dmg:
            best, best_dmg = "Limit_Break", d
    for mv in _PHYS_MOVES:
        d = calc_phys_damage(atk, dfn, mv, None, expected=True)
        if d > best_dmg:
            best, best_dmg = mv, d
    if mp_remaining >= 6:
        for mv in _MAGIC_MOVES:
            d = calc_magic_damage(atk, dfn, mv, None, expected=True)
            if d > best_dmg:
                best, best_dmg = mv, d
    return best


def run_battle(c1, c2, rng):
    s = [
        dict(c1, current_hp=c1["HP"], current_mp=c1["MP"], limit_gauge=0.0),
        dict(c2, current_hp=c2["HP"], current_mp=c2["MP"], limit_gauge=0.0),
    ]
    records = []
    for _turn in range(60):
        if s[0]["Dexterity"] > s[1]["Dexterity"]:
            order = [0, 1]
        elif s[1]["Dexterity"] > s[0]["Dexterity"]:
            order = [1, 0]
        else:
            order = rng.sample([0, 1], 2)
        for ai in order:
            di = 1 - ai
            if s[ai]["current_hp"] <= 0 or s[di]["current_hp"] <= 0:
                continue
            limit_ready = s[ai]["limit_gauge"] >= 1.0
            move = choose_action(s[ai], s[di], s[ai]["current_mp"],
                                 limit_ready, rng=rng)
            if move is None:
                continue
            cat, elem, power = MOVES[move]
            if cat == "Physical":
                dmg = calc_phys_damage(s[ai], s[di], move, rng)
            else:
                dmg = calc_magic_damage(s[ai], s[di], move, rng)
                s[ai]["current_mp"] -= 6
            if dmg < 0:
                s[di]["current_hp"] = min(s[di]["HP"], s[di]["current_hp"] - dmg)
                actual_damage = 0
            else:
                s[di]["current_hp"] -= dmg
                actual_damage = dmg
            if actual_damage > 0:
                s[di]["limit_gauge"] = min(1.0, s[di]["limit_gauge"]
                                           + actual_damage / s[di]["HP"])
            if move == "Limit_Break":
                s[ai]["limit_gauge"] = 0.0
            records.append({
                "Atk_Strength":      s[ai]["Strength"],
                "Atk_Magic":         s[ai]["Magic"],
                "Atk_WeaponAttack":  s[ai]["WeaponAttack"],
                "Atk_WeaponMagic":   s[ai]["WeaponMagic"],
                "Def_Vitality":      s[di]["Vitality"],
                "Def_Spirit":        s[di]["Spirit"],
                "Def_ArmorDefense":  s[di]["ArmorDefense"],
                "Def_ArmorSpirit":   s[di]["ArmorSpirit"],
                "Move_Power":        power,
                "Move_Category":     cat,
                "Move_Element":      elem if elem else "None",
                "Def_ResistElement": s[di]["ResistElement"] if s[di]["ResistElement"] else "None",
                "Def_AbsorbElement": s[di]["AbsorbElement"] if s[di]["AbsorbElement"] else "None",
                "Damage":            dmg,
            })
        if s[0]["current_hp"] <= 0 or s[1]["current_hp"] <= 0:
            break
    if s[0]["current_hp"] <= 0 and s[1]["current_hp"] > 0:
        return 1, records
    if s[1]["current_hp"] <= 0 and s[0]["current_hp"] > 0:
        return 0, records
    h0 = s[0]["current_hp"] / s[0]["HP"]
    h1 = s[1]["current_hp"] / s[1]["HP"]
    return (0 if h0 >= h1 else 1), records


def main():
    rng = random.Random(20260527)
    roster = [make_character(rng) for _ in range(80)]
    battle_rows, attack_rows = [], []
    N = 2500
    for _ in range(N):
        i, j = rng.sample(range(len(roster)), 2)
        c1, c2 = roster[i], roster[j]
        winner, recs = run_battle(c1, c2, rng)
        for idx, c in enumerate((c1, c2)):
            battle_rows.append({
                "HP":            c["HP"],
                "MP":            c["MP"],
                "Strength":      c["Strength"],
                "Magic":         c["Magic"],
                "Vitality":      c["Vitality"],
                "Spirit":        c["Spirit"],
                "Dexterity":     c["Dexterity"],
                "Luck":          c["Luck"],
                "WeaponAttack":  c["WeaponAttack"],
                "WeaponMagic":   c["WeaponMagic"],
                "ArmorDefense":  c["ArmorDefense"],
                "ArmorSpirit":   c["ArmorSpirit"],
                "ResistElement": c["ResistElement"] if c["ResistElement"] else "None",
                "AbsorbElement": c["AbsorbElement"] if c["AbsorbElement"] else "None",
                "Is_Victorious": 1 if winner == idx else 0,
            })
        attack_rows.extend(recs)
    rng.shuffle(attack_rows)
    attack_rows = attack_rows[:8000]
    with open("ff7_battle_log.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(battle_rows[0].keys()))
        w.writeheader()
        w.writerows(battle_rows)
    with open("ff7_attack_log.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(attack_rows[0].keys()))
        w.writeheader()
        w.writerows(attack_rows)
    print("battle_log rows:", len(battle_rows))
    print("attack_log rows:", len(attack_rows))
    dmgs = [r["Damage"] for r in attack_rows]
    print("damage min/mean/max:", min(dmgs), "/", round(sum(dmgs)/len(dmgs), 1), "/", max(dmgs))
    wins = sum(r["Is_Victorious"] for r in battle_rows)
    print("battle_log win rate:", round(wins/len(battle_rows), 3))
    abs_count = sum(1 for r in attack_rows if r["Damage"] < 0)
    print("absorb attacks:", abs_count, "(" + str(round(100*abs_count/len(attack_rows), 1)) + "%)")


if __name__ == "__main__":
    main()
