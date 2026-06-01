# -*- coding: utf-8 -*-
"""hs_ref.py - Hearthstone 1v1 reference simulator (극단 단순화).

미니언/스펠/힐 카드만, 키워드 전면 deferred, 카드 텍스트 효과 전면 deferred.
영웅 HP=30 고정, mana = min(turn, 10), 보드 한도 7, 시작 핸드 4, 매 턴 드로우 1.
양방향 트레이드 (A 공격→B 데미지 = A.Attack, A 데미지 = B.Attack).
AI: 그리디 (ManaCost 큰 카드부터, ManaCost 큰 미니언부터 공격).
출력: hs_battle_log.csv + hs_attack_log.csv
"""
import csv
import math
import random

# === 카드 풀 (80장: 60 미니언 + 15 데미지 스펠 + 5 힐) ===
# 미니언: (cost, atk, hp). vanilla curve atk+hp ≈ 2*cost+1
# 일부는 sub-vanilla(약체), 일부는 over-vanilla(강체) — archetype별 선호 차이용
MINIONS = [
    # cost 1
    ("M1a", 1, 1, 1), ("M1b", 1, 2, 1), ("M1c", 1, 1, 2),
    ("M1d", 1, 2, 2), ("M1e", 1, 3, 1), ("M1f", 1, 1, 3),
    # cost 2
    ("M2a", 2, 2, 3), ("M2b", 2, 3, 2), ("M2c", 2, 2, 2),
    ("M2d", 2, 3, 3), ("M2e", 2, 4, 2), ("M2f", 2, 1, 4),
    ("M2g", 2, 4, 1),
    # cost 3
    ("M3a", 3, 3, 4), ("M3b", 3, 4, 3), ("M3c", 3, 3, 3),
    ("M3d", 3, 5, 2), ("M3e", 3, 2, 5), ("M3f", 3, 4, 4),
    ("M3g", 3, 5, 3),
    # cost 4
    ("M4a", 4, 4, 5), ("M4b", 4, 5, 4), ("M4c", 4, 4, 4),
    ("M4d", 4, 6, 3), ("M4e", 4, 3, 6), ("M4f", 4, 5, 5),
    ("M4g", 4, 6, 4),
    # cost 5
    ("M5a", 5, 5, 6), ("M5b", 5, 6, 5), ("M5c", 5, 4, 7),
    ("M5d", 5, 7, 4), ("M5e", 5, 5, 5), ("M5f", 5, 6, 6),
    # cost 6
    ("M6a", 6, 6, 7), ("M6b", 6, 7, 6), ("M6c", 6, 5, 8),
    ("M6d", 6, 8, 5), ("M6e", 6, 6, 6), ("M6f", 6, 7, 7),
    # cost 7
    ("M7a", 7, 7, 8), ("M7b", 7, 8, 7), ("M7c", 7, 6, 9),
    ("M7d", 7, 9, 6), ("M7e", 7, 7, 7), ("M7f", 7, 8, 8),
    # cost 8
    ("M8a", 8, 8, 9), ("M8b", 8, 9, 8), ("M8c", 8, 7, 10),
    ("M8d", 8, 10, 7), ("M8e", 8, 8, 8),
    # cost 9
    ("M9a", 9, 9, 10), ("M9b", 9, 10, 9), ("M9c", 9, 8, 11),
    ("M9d", 9, 11, 8),
    # cost 10
    ("M10a", 10, 10, 10), ("M10b", 10, 12, 9), ("M10c", 10, 9, 12),
    ("M10d", 10, 11, 11), ("M10e", 10, 8, 12), ("M10f", 10, 12, 12),
]
# 데미지 스펠: (id, cost, damage). vanilla: damage ≈ cost + 1
DAMAGE_SPELLS = [
    ("D1a", 1, 2), ("D1b", 1, 1),
    ("D2a", 2, 3), ("D2b", 2, 3), ("D2c", 2, 4),
    ("D3a", 3, 4), ("D3b", 3, 5),
    ("D4a", 4, 5), ("D4b", 4, 6),
    ("D5a", 5, 6), ("D5b", 5, 7),
    ("D6a", 6, 8),
    ("D7a", 7, 9),
    ("D8a", 8, 10), ("D8b", 8, 10),
]
# 힐 스펠: (id, cost, heal). vanilla: heal ≈ 2*cost
HEAL_SPELLS = [
    ("H1a", 1, 2), ("H2a", 2, 4), ("H3a", 3, 6),
    ("H5a", 5, 8), ("H6a", 6, 10),
]

ARCHETYPES = ("Aggro", "Midrange", "Control")
HERO_HP = 30
BOARD_CAP = 7
START_HAND = 4
MAX_TURNS = 50


def _card_dict(c, kind):
    """미니언 또는 스펠 튜플을 dict로 변환."""
    if kind == "Minion":
        cid, cost, atk, hp = c
        return {"id": cid, "kind": "Minion", "cost": cost,
                "atk": atk, "hp": hp, "max_hp": hp}
    elif kind == "Damage":
        cid, cost, dmg = c
        return {"id": cid, "kind": "Damage", "cost": cost, "value": dmg}
    else:  # Heal
        cid, cost, heal = c
        return {"id": cid, "kind": "Heal", "cost": cost, "value": heal}


def _gauss_weight(cost, peak, sigma):
    """가우시안 가중치. cost가 peak에 가까울수록 높음."""
    return math.exp(-((cost - peak) ** 2) / (2 * sigma ** 2))


def build_deck(archetype, rng):
    """archetype별 30장 덱 구성. mana curve가 archetype마다 다르되,
    Control도 저코스트 일부 보유해서 초반 마나에 묶이지 않게 평탄화."""
    if archetype == "Aggro":
        # 67% minion (저코스트 peak), 20% damage, 13% heal
        # heal을 약간 늘려 Aggro의 face damage 누적이 self-sustain 안되게
        n_minion, n_damage, n_heal = 20, 6, 4
        minion_weights = [_gauss_weight(m[1], peak=3, sigma=2.5) for m in MINIONS]
    elif archetype == "Midrange":
        # 60% minion (중코스트 peak), 25% damage, 15% heal
        n_minion, n_damage, n_heal = 18, 8, 4
        minion_weights = [_gauss_weight(m[1], peak=4, sigma=2.5) for m in MINIONS]
    else:  # Control
        # 57% minion (mid-high cost peak 평탄화), 20% damage, 23% heal
        # 저코스트 강한 가중치 + 미니언 수 ↑로 초반 mana lockout 완화
        n_minion, n_damage, n_heal = 17, 6, 7
        minion_weights = [_gauss_weight(m[1], peak=5, sigma=4.0) for m in MINIONS]

    deck = []
    chosen_m = rng.choices(MINIONS, weights=minion_weights, k=n_minion)
    deck.extend(_card_dict(m, "Minion") for m in chosen_m)
    chosen_d = rng.choices(DAMAGE_SPELLS, k=n_damage)
    deck.extend(_card_dict(d, "Damage") for d in chosen_d)
    chosen_h = rng.choices(HEAL_SPELLS, k=n_heal)
    deck.extend(_card_dict(h, "Heal") for h in chosen_h)
    rng.shuffle(deck)
    return deck


def deck_profile(deck, archetype):
    """battle_log 한 행이 될 덱 집계 통계."""
    minions = [c for c in deck if c["kind"] == "Minion"]
    n_minion = len(minions)
    n_damage = sum(1 for c in deck if c["kind"] == "Damage")
    n_heal = sum(1 for c in deck if c["kind"] == "Heal")
    avg_atk = sum(c["atk"] for c in minions) / max(1, n_minion)
    avg_hp = sum(c["max_hp"] for c in minions) / max(1, n_minion)
    total_power = sum(c["atk"] + c["max_hp"] for c in minions)
    avg_cost = sum(c["cost"] for c in deck) / len(deck)
    tempo = 10.0 / max(0.5, avg_cost)
    return {
        "HeroHP":             HERO_HP,
        "DeckAvgAttack":      round(avg_atk, 2),
        "DeckAvgHP":          round(avg_hp, 2),
        "DeckAvgManaCost":    round(avg_cost, 2),
        "DeckMinionCount":    n_minion,
        "DeckSpellCount":     n_damage,
        "DeckHealCount":      n_heal,
        "DeckTotalStatPower": total_power,
        "DeckTempo":          round(tempo, 2),
        "StartHandSize":      START_HAND,
        "Archetype":          archetype,
    }


def _play_one_card(state, opp, records, rng):
    """한 카드 플레이. 가능한 가장 비싼 카드 선택. True if played."""
    affordable = [(i, c) for i, c in enumerate(state["hand"])
                  if c["cost"] <= state["mana"]]
    if not affordable:
        return False
    # 최고 cost 카드 선택, 동률은 랜덤
    affordable.sort(key=lambda x: (-x[1]["cost"], rng.random()))
    idx, card = affordable[0]
    if card["kind"] == "Minion":
        if len(state["board"]) >= BOARD_CAP:
            # 보드 가득 — 이 카드는 못 냄. 다음 affordable에서 비-미니언 시도
            for i2, c2 in affordable[1:]:
                if c2["kind"] != "Minion":
                    idx, card = i2, c2
                    break
            else:
                return False
    state["hand"].pop(idx)
    state["mana"] -= card["cost"]
    if card["kind"] == "Minion":
        state["board"].append(dict(card))
    elif card["kind"] == "Damage":
        # 적 미니언 중 가장 비싼 것 우선, 없으면 영웅
        if opp["board"]:
            opp["board"].sort(key=lambda m: -m["cost"])
            target = opp["board"][0]
            target["hp"] -= card["value"]
            records.append({
                "Atk_Attack":     card["value"],
                "Atk_HP":         0,
                "Atk_ManaCost":   card["cost"],
                "Def_Attack":     target["atk"],
                "Def_HP":         target["max_hp"],
                "Def_ManaCost":   target["cost"],
                "Card_Category":  "Spell",
                "Damage":         card["value"],
            })
            if target["hp"] <= 0:
                opp["board"].remove(target)
        else:
            opp["hero_hp"] -= card["value"]
            records.append({
                "Atk_Attack":     card["value"],
                "Atk_HP":         0,
                "Atk_ManaCost":   card["cost"],
                "Def_Attack":     0,
                "Def_HP":         HERO_HP,
                "Def_ManaCost":   0,
                "Card_Category":  "Spell",
                "Damage":         card["value"],
            })
    else:  # Heal
        state["hero_hp"] = min(HERO_HP, state["hero_hp"] + card["value"])
    return True


def _attack_phase(state, opp, records, rng):
    """보드 미니언이 공격. 비싼 미니언부터, 적 미니언 우선."""
    attackers = sorted(state["board"], key=lambda m: -m["cost"])
    for m in attackers:
        if m["hp"] <= 0 or m not in state["board"]:
            continue
        if opp["board"]:
            opp["board"].sort(key=lambda t: -t["cost"])
            target = opp["board"][0]
            # 양방향 트레이드
            damage_to_target = m["atk"]
            damage_to_attacker = target["atk"]
            records.append({
                "Atk_Attack":     m["atk"],
                "Atk_HP":         m["max_hp"],
                "Atk_ManaCost":   m["cost"],
                "Def_Attack":     target["atk"],
                "Def_HP":         target["max_hp"],
                "Def_ManaCost":   target["cost"],
                "Card_Category":  "Minion",
                "Damage":         m["atk"],
            })
            target["hp"] -= damage_to_target
            m["hp"] -= damage_to_attacker
            if target["hp"] <= 0:
                opp["board"].remove(target)
            if m["hp"] <= 0:
                if m in state["board"]:
                    state["board"].remove(m)
        else:
            opp["hero_hp"] -= m["atk"]
            records.append({
                "Atk_Attack":     m["atk"],
                "Atk_HP":         m["max_hp"],
                "Atk_ManaCost":   m["cost"],
                "Def_Attack":     0,
                "Def_HP":         HERO_HP,
                "Def_ManaCost":   0,
                "Card_Category":  "Minion",
                "Damage":         m["atk"],
            })
            if opp["hero_hp"] <= 0:
                return


def _draw(state, n=1):
    for _ in range(n):
        if state["deck"]:
            state["hand"].append(state["deck"].pop())


def run_battle(deck1, deck2, rng):
    """한 게임 시뮬레이션. (winner_idx, attack_records) 반환."""
    s = [
        {"deck": list(deck1), "hand": [], "board": [],
         "hero_hp": HERO_HP, "mana": 0},
        {"deck": list(deck2), "hand": [], "board": [],
         "hero_hp": HERO_HP, "mana": 0},
    ]
    for side in s:
        _draw(side, START_HAND)
    records = []
    # 선공 랜덤
    first = rng.randint(0, 1)
    for turn in range(1, MAX_TURNS + 1):
        for offset in (0, 1):
            ai = (first + offset) % 2
            di = 1 - ai
            if s[ai]["hero_hp"] <= 0 or s[di]["hero_hp"] <= 0:
                continue
            s[ai]["mana"] = min(turn, 10)
            _draw(s[ai], 1)
            # 플레이 단계: 가능한 한 많이
            for _ in range(10):
                if not _play_one_card(s[ai], s[di], records, rng):
                    break
                if s[di]["hero_hp"] <= 0:
                    break
            if s[di]["hero_hp"] <= 0:
                continue
            # 공격 단계
            _attack_phase(s[ai], s[di], records, rng)
        if s[0]["hero_hp"] <= 0 or s[1]["hero_hp"] <= 0:
            break
    if s[0]["hero_hp"] <= 0 and s[1]["hero_hp"] > 0:
        return 1, records
    if s[1]["hero_hp"] <= 0 and s[0]["hero_hp"] > 0:
        return 0, records
    # 50턴 초과: HP% 비교 (둘 다 살아있거나 둘 다 0 이하)
    h0 = max(0, s[0]["hero_hp"]) / HERO_HP
    h1 = max(0, s[1]["hero_hp"]) / HERO_HP
    return (0 if h0 >= h1 else 1), records


def main():
    rng = random.Random(20260528)
    battle_rows, attack_rows = [], []
    N = 2500
    for _ in range(N):
        a1 = rng.choice(ARCHETYPES)
        a2 = rng.choice(ARCHETYPES)
        d1 = build_deck(a1, rng)
        d2 = build_deck(a2, rng)
        p1 = deck_profile(d1, a1)
        p2 = deck_profile(d2, a2)
        winner, recs = run_battle(d1, d2, rng)
        for idx, prof in enumerate((p1, p2)):
            row = dict(prof)
            row["Is_Victorious"] = 1 if winner == idx else 0
            battle_rows.append(row)
        attack_rows.extend(recs)
    rng.shuffle(attack_rows)
    attack_rows = attack_rows[:8000]
    with open("hs_battle_log.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(battle_rows[0].keys()))
        w.writeheader()
        w.writerows(battle_rows)
    with open("hs_attack_log.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(attack_rows[0].keys()))
        w.writeheader()
        w.writerows(attack_rows)
    print("battle_log rows:", len(battle_rows))
    print("attack_log rows:", len(attack_rows))
    dmgs = [r["Damage"] for r in attack_rows]
    print("damage min/mean/max:", min(dmgs), "/",
          round(sum(dmgs) / len(dmgs), 1), "/", max(dmgs))
    wins = sum(r["Is_Victorious"] for r in battle_rows)
    print("battle_log win rate:", round(wins / len(battle_rows), 3))
    arch_count = {a: 0 for a in ARCHETYPES}
    arch_wins = {a: 0 for a in ARCHETYPES}
    for r in battle_rows:
        arch_count[r["Archetype"]] += 1
        arch_wins[r["Archetype"]] += r["Is_Victorious"]
    for a in ARCHETYPES:
        c = arch_count[a]
        wr = round(arch_wins[a] / max(1, c), 3)
        print(f"  {a}: count={c}, winrate={wr}")
    matches = sum(1 for r in attack_rows if r["Damage"] == r["Atk_Attack"])
    pct = round(100 * matches / len(attack_rows), 1)
    print(f"Damage == Atk_Attack: {matches}/{len(attack_rows)} ({pct}%)")


if __name__ == "__main__":
    main()
