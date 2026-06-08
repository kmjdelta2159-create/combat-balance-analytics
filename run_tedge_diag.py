"""
턴엔드 누락 엣지 진단 2 — 상대 교체 턴(T7)에 Hippowdon 턴엔드 회복이 왜 누락되는지 정밀.

1차 진단으로 확인: Hippowdon은 T7에 행동(actor=Hippowdon)하지만 자기 HP가 안 변함(324 고정).
T6는 정상(324→350). 차이는 상대 교체뿐. 이번엔 각 행동 유닛 턴엔드에서:
- active_char의 id / item / ability / status / tox_stage / resources.HP(직접)
- 같은 시점 participants 리스트의 Hippowdon HP (객체 동일성/이중객체 점검)
를 찍는다. Hippowdon 차례에 item이 'Leftovers'인지, active_char HP와 participants HP가 같은지.

프로젝트 루트에서:  python run_tedge_diag.py   (출력 전체를 붙여주세요)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
REPLAY = os.path.join(HERE, "Gen5OU-2015-05-11-reymedy-leftiez.html")
LO, HI = 6, 7


def main():
    from modules.showdown_trace import parse_replay
    from modules.fullbattle_run import setup_for_engine, build_onfield_timeline, _make_resync
    from modules.fullbattle_diff import build_snapshots
    from modules.engine import run_simulation
    from modules.resource import get_current
    import modules.reference_gen5 as r5

    with open(REPLAY, encoding="utf-8") as f:
        trace = parse_replay(f.read())

    ally, enemy, gc, spec = setup_for_engine(trace, r5)
    log_snaps = build_snapshots(trace)
    onfield_tl = build_onfield_timeline(trace)

    # effects 스키마 확인 (디스패처가 보는 것)
    effs = ((gc.get("mechanisms") or {}).get("effects")) or {}
    print("game_config effects 키:", sorted(effs.keys()))
    print("Leftovers spec:", effs.get("Leftovers"))

    rows = []
    base_resync = _make_resync(log_snaps, onfield_tl)

    def resync_hook(turn, participants):
        base_resync(turn, participants)
        if LO <= turn <= HI:
            h = next((p for p in participants if p.get("id") == "Hippowdon"), None)
            rows.append((turn, "RESYNC", "-", None, None, None, None,
                         (h.get("resources") or {}).get("HP", {}).get("current") if h else None,
                         h.get("on_field") if h else None))

    def te_hook(ctx):
        t = ctx.get("turn")
        if t is None or not (LO <= t <= HI):
            return
        ac = ctx.get("active_char") or {}
        ac_hp = (ac.get("resources") or {}).get("HP", {}).get("current")
        ph = next((p for p in ctx["participants"] if p.get("id") == "Hippowdon"), None)
        ph_hp = (ph.get("resources") or {}).get("HP", {}).get("current") if ph else None
        rows.append((t, "TURN_END", ac.get("id"), ac.get("item"), ac.get("ability"),
                     ac.get("status"), ac.get("tox_stage"), ac_hp,
                     ph_hp))   # 마지막=participants Hippowdon HP

    run_simulation(
        ally, enemy, max_turns=100,
        sys_stats=["atk", "df", "spa", "spd", "spe"], speed_stat="spe",
        global_damage_formula=gc.get("formula"), game_config=gc, silent=True,
        on_turn_end=te_hook, on_round_start=resync_hook,
    )

    print(f"\n{'T':>2} {'phase':9} {'actor':10} {'item':12} {'status':5} {'tox':>3} "
          f"{'actorHP':>7} {'partHippHP':>10}")
    for r in rows:
        t, ph, aid, item, abil, status, tox, achp, phhp = r
        print(f"{t:>2} {ph:9} {str(aid):10} {str(item):12} {str(status):5} {str(tox):>3} "
              f"{str(achp):>7} {str(phhp):>10}")

    print("\n해석:")
    print(" - T7 actor=Hippowdon 줄의 item이 'Leftovers'가 아니면 → 교체가 Hippowdon item 오염.")
    print(" - item='Leftovers'인데 actorHP=324(미회복)면 → 디스패처가 안 돌았거나 effects 미스.")
    print(" - actorHP != partHippHP 면 → active_char와 participants가 다른 객체(preserve_ids 이중객체).")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        print("=== 실행 에러 (트레이스백 전체를 붙여주세요) ===")
        traceback.print_exc()
        sys.exit(1)
