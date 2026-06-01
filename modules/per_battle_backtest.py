# -*- coding: utf-8 -*-
"""
per_battle_backtest.py — Phase 8c-α.

전투 로그의 각 전투를 엔진으로 재시뮬해 예측 승자 vs 실제 승자 일치율을 측정한다.
검증 패널의 기존 "승률"(1매치업↔로그평균 비교)이 구조적으로 부서져 있어 의미 없는
점수를 내는 문제를 해결한다 — Pokemon 클린룸 harness가 외부에서 한 일을 앱 안에서
직접 한다.

순수 모듈 — pandas + 표준 라이브러리만 의존. Streamlit/engine 직접 import 없음.
엔진 호출은 호출부(step6)에서 ProcessPoolExecutor + _worker_simulate_match로 한다.
"""
import pandas as pd


def _safe_float(v):
    """str/int/float/NaN → float (NaN/실패 → 0.0)."""
    try:
        v = float(v)
        return v if v == v else 0.0
    except (TypeError, ValueError):
        return 0.0


def _is_win_signal(v):
    """target_col 값을 'ally가 이김'으로 해석할지 판정.
    숫자형(0/1, True/False)과 흔한 문자열(Win/Victory/Ally)을 모두 처리."""
    if v is None:
        return False
    try:
        if pd.isna(v):
            return False
    except (TypeError, ValueError):
        pass
    s = str(v).strip().lower()
    _truthy = {"1", "1.0", "true", "yes", "y", "win", "victory", "victorious",
               "ally", "won", "winner"}
    _falsy = {"0", "0.0", "false", "no", "n", "lose", "loss", "defeat",
              "defeated", "enemy", "lost", "loser"}
    if s in _truthy:
        return True
    if s in _falsy:
        return False
    try:
        return float(s) > 0
    except (TypeError, ValueError):
        return False


def _row_to_inst(row, system_stats, system_gimmicks, health_stat,
                 move_library=None, resource_config=None):
    """로그의 한 행을 엔진 인스턴스 dict로 변환."""
    inst = {"name": "log_row", "gimmicks": {}}
    for g in system_gimmicks:
        inst["gimmicks"][g] = row.get(g, "None")
    for s in system_stats:
        inst[s] = _safe_float(row.get(s, 0.0))
    rc = resource_config or (
        {"HP": {"role": "vital", "stat": health_stat, "regen": 0.0}}
        if health_stat else
        {"HP": {"role": "vital", "stat": None, "regen": 0.0}}
    )
    inst["resources"] = {}
    for rname, rspec in rc.items():
        rstat = rspec.get("stat")
        rval = float(inst[rstat]) if (rstat and rstat in inst) else 1.0
        inst["resources"][rname] = {"current": rval, "max": rval}
    if move_library:
        inst["movepool"] = move_library
    return inst


def build_battles(df, battle_size, target_col, system_stats, system_gimmicks,
                  health_stat, move_library=None, resource_config=None,
                  max_battles=None):
    """df를 battle_size 행씩 그룹화해 1전투씩 추출.

    한 전투의 행 N개를 절반으로 잘라 앞쪽 N/2 = Ally, 뒤쪽 N/2 = Enemy로 본다.
    실제 ally_wins = (ally 측 target_col 합 > enemy 측 합).

    반환: [(ally_team_insts, enemy_team_insts, ally_wins_bool), ...]
    """
    battles = []
    if battle_size < 2 or battle_size % 2 != 0:
        return battles
    n_per_team = battle_size // 2
    total_battles = len(df) // battle_size
    if max_battles is not None:
        total_battles = min(total_battles, int(max_battles))
    for b in range(total_battles):
        rows = [df.iloc[b * battle_size + k] for k in range(battle_size)]
        ally_rows = rows[:n_per_team]
        enemy_rows = rows[n_per_team:]
        ally_signal = sum(1 if _is_win_signal(r.get(target_col)) else 0 for r in ally_rows)
        enemy_signal = sum(1 if _is_win_signal(r.get(target_col)) else 0 for r in enemy_rows)
        ally_wins = ally_signal > enemy_signal
        ally_team = [_row_to_inst(r, system_stats, system_gimmicks, health_stat,
                                  move_library, resource_config)
                     for r in ally_rows]
        enemy_team = [_row_to_inst(r, system_stats, system_gimmicks, health_stat,
                                   move_library, resource_config)
                      for r in enemy_rows]
        battles.append((ally_team, enemy_team, ally_wins))
    return battles


def score_predictions(predicted_ally_wins, actual_ally_wins):
    """예측 ally-win 여부 vs 실제 ally-win 여부 이진 비교."""
    total = len(predicted_ally_wins)
    if total == 0 or len(actual_ally_wins) != total:
        return {"accuracy": 0.0, "total": 0, "correct": 0,
                "ally_wins_actual": 0, "ally_wins_recall": 0.0,
                "not_ally_actual": 0, "not_ally_recall": 0.0}
    correct = sum(1 for p, a in zip(predicted_ally_wins, actual_ally_wins) if p == a)
    ally_actual = sum(1 for a in actual_ally_wins if a)
    not_ally_actual = total - ally_actual
    ally_hit = sum(1 for p, a in zip(predicted_ally_wins, actual_ally_wins) if a and p)
    not_ally_hit = sum(1 for p, a in zip(predicted_ally_wins, actual_ally_wins)
                       if (not a) and (not p))
    return {
        "accuracy": correct / total,
        "total": total,
        "correct": correct,
        "ally_wins_actual": ally_actual,
        "ally_wins_recall": (ally_hit / ally_actual) if ally_actual else 0.0,
        "not_ally_actual": not_ally_actual,
        "not_ally_recall": (not_ally_hit / not_ally_actual) if not_ally_actual else 0.0,
    }
