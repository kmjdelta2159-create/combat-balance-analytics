# Phase 8c-α — Per-Battle Backtest (전투별 백테스트 검증 모드)

## 목표

`modules/validation.py`의 "승률" 검증이 **구조적으로 의미 없는 비교**를 한다 — 사용자의
GM Mode 1개 매치업의 MC 승률을, 업로드 로그 전체의 target 컬럼 평균과 빼서 점수를 매긴다.
이 비교는 시뮬레이터가 아무리 정확해도 매치업이 균형이 아니면 자동으로 0~3%로 떨어진다.
사용자가 본 "승률 3% ❌"가 이 결함의 결과다 — **엔진 부정확이 아니라 검증 로직 자체의
오작동**.

Pokemon known-answer harness가 외부 클린룸 도구로 존재한 이유도 같다 — 앱 안에서
per-battle backtest를 못 하기 때문에 외부 harness로 92.6% 충실도를 측정했다. 이 갭이
**두 잔여 갭의 공통 뿌리**다.

이 변경은 그 인프라를 앱 안으로 가져온다 — 로그의 각 전투를 엔진으로 재시뮬하고 예측
승자를 실제 승자와 1대1로 비교한다. 결과:
- 사용자가 보는 점수가 **의미 있는 충실도 지표**가 된다 (3% misleading 종결).
- 향후 엔진 개선의 캐노니컬 측정 기반이 앱 안에 존재한다 (외부 harness 의존 종결).

## 대상 파일

1. **신규 파일** `modules/per_battle_backtest.py` — 순수 모듈(pandas+stdlib만 의존,
   streamlit·engine import 없음).
2. **`modules/step6_dashboard.py`** — `시뮬레이션 로그` 탭(`chart_tabs[2]`) 끝에
   백테스트 섹션 1개 삽입. **단일 위치 삽입, 기존 코드 한 줄도 안 바뀜.**

다른 파일은 건드리지 마라. Phase 9b 변경 영역(`elif _use_engine_opt:` 블록), 레거시
SLSQP 경로, optimizer.py, MC 버튼, validation.py — 모두 불변.

---

## 변경 1 — 신규 파일 `modules/per_battle_backtest.py` 생성

아래 내용 그대로 `modules/per_battle_backtest.py`를 새로 만든다 (순수 모듈,
실제 Pokemon 로그 5000행으로 build_battles → 2500전투 정확 추출 / Ally 승률 49.9% /
완벽 예측 100% / 동전 던지기 51.6% 단위 검증 완료).

```python
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
```

---

## 변경 2 — `modules/step6_dashboard.py`에 백테스트 섹션 삽입

`시뮬레이션 로그` 탭(`chart_tabs[2]`)의 기존 MC 검증 패널 끝, `with tab2:` 직전에
새 백테스트 섹션을 삽입한다.

**찾기 블록 (2줄):**
```python
                            st.rerun()
    with tab2:
```
**바꾸기 블록:**
```python
                            st.rerun()

                # ══════════════════════════════════════════════════════════════
                # Phase 8c-α — Per-Battle Backtest (전투별 백테스트)
                # ══════════════════════════════════════════════════════════════
                st.markdown("---")
                with st.container(border=True):
                    st.markdown("#### 🔬 전투별 백테스트 (Per-Battle Backtest)")
                    st.caption(
                        "로그의 각 전투를 엔진으로 재시뮬해 **예측 승자 vs 실제 승자 일치율**을 측정합니다. "
                        "기존 검증의 \"승률\"(1매치업↔로그평균 비교)과 달리, 이건 *로그 안의 모든 전투*를 "
                        "1대1로 검사합니다. 의미 있는 시뮬레이터 충실도 지표."
                    )

                    _bb_df = st.session_state.get("df")
                    _bb_target = (st.session_state.get("target_col")
                                  or st.session_state.get("target_variable"))
                    _bb_health = st.session_state.get("health_stat")
                    _bb_ready = (_bb_df is not None and _bb_target
                                 and _bb_target in _bb_df.columns
                                 and bool(sys_stats))

                    if not _bb_ready:
                        st.info(
                            "ℹ️ 백테스트를 실행하려면 Step 2에서 **target_col**(전투 결과 컬럼)과 "
                            "**system_stats**(전투에 쓰는 스탯)가 매핑돼 있어야 합니다."
                        )
                    else:
                        _bb_n_rows = len(_bb_df)
                        _bb_c1, _bb_c2 = st.columns(2)
                        with _bb_c1:
                            _bb_size = st.number_input(
                                "전투당 행 수 (1v1=2 · 2v2=4 · 4v4=8 — 로그가 캐릭터-per-행 패턴일 때)",
                                min_value=2, max_value=20, value=2, step=2,
                                key="ui_backtest_size",
                                help="로그가 캐릭터당 한 행이라면, 한 전투의 모든 참가자가 연속해서 행으로 들어 있다고 가정합니다. "
                                     "앞쪽 절반 = Ally, 뒤쪽 절반 = Enemy."
                            )
                        with _bb_c2:
                            _bb_max_cap = max(10, _bb_n_rows // max(int(_bb_size), 2))
                            _bb_max_default = min(500, _bb_max_cap)
                            _bb_max = st.number_input(
                                f"최대 전투 수 (로그 전체 = {_bb_max_cap})",
                                min_value=10, max_value=max(_bb_max_cap, 10),
                                value=_bb_max_default, step=50,
                                key="ui_backtest_max",
                                help="성능 한계 — 500전투 ≈ 수십 초. 전수 검사하려면 최대치로."
                            )

                        if st.button("🔬 백테스트 실행", use_container_width=True, key="run_backtest"):
                            from modules.per_battle_backtest import build_battles, score_predictions
                            from modules.engine import _worker_simulate_match

                            _battles = build_battles(
                                _bb_df, int(_bb_size), _bb_target,
                                sys_stats, sys_gimmicks, _bb_health,
                                move_library=st.session_state.get("move_library"),
                                resource_config=st.session_state.get("resource_config"),
                                max_battles=int(_bb_max),
                            )

                            if not _battles:
                                st.warning("⚠️ 전투를 구성할 수 없습니다 — 행 수 또는 전투당 행 수 설정을 확인하세요.")
                            else:
                                _bb_cf = st.session_state.get("combat_flow", DEFAULT_COMBAT_FLOW)
                                _bb_spd = st.session_state.get("speed_stat")
                                _bb_gf = st.session_state.get("global_damage_formula", "0")
                                _bb_gc = st.session_state.get("game_config")
                                _bb_mt = int(st.session_state.get("sim_max_turns", 100))
                                _bb_rm = ResourceModule(
                                    st.session_state.get("resource_config") or None,
                                    damage_type_map=st.session_state.get("damage_type_map") or None,
                                )

                                _bb_tasks = []
                                _bb_actuals = []
                                for _bb_i, (_a_team, _e_team, _ally_wins) in enumerate(_battles):
                                    _bb_tasks.append((
                                        _a_team, _e_team, _bb_cf, _bb_spd, sys_stats, _bb_gf,
                                        _bb_mt, default_stochasticity_factory, _bb_rm,
                                        None, None, None, None, _bb_gc, _bb_i,
                                    ))
                                    _bb_actuals.append(_ally_wins)

                                _bb_total = len(_bb_tasks)
                                _bb_prog = st.progress(0.0)
                                _bb_status = st.empty()
                                _bb_t0 = time.time()
                                _bb_predictions = []
                                _bb_errors = 0
                                _bb_workers = os.cpu_count() or 4

                                with st.spinner(f"백테스트 실행 중... ({_bb_total}전투, 멀티코어 병렬)"):
                                    with concurrent.futures.ProcessPoolExecutor(
                                            max_workers=_bb_workers) as _bb_pool:
                                        _bb_step = max(1, _bb_total // 50)
                                        for _bb_r in _bb_pool.map(
                                                _worker_simulate_match, _bb_tasks, chunksize=4):
                                            if isinstance(_bb_r, str):
                                                _bb_errors += 1
                                                _bb_predictions.append(False)
                                            else:
                                                _bb_predictions.append(_bb_r[0] == 1)
                                            _bb_done = len(_bb_predictions)
                                            if _bb_done % _bb_step == 0 or _bb_done == _bb_total:
                                                _bb_prog.progress(min(1.0, _bb_done / float(_bb_total)))
                                                _bb_status.text(
                                                    f"백테스트: {_bb_done}/{_bb_total} · "
                                                    f"경과 {time.time() - _bb_t0:.0f}초"
                                                )

                                _bb_prog.progress(1.0)
                                _bb_sc = score_predictions(_bb_predictions, _bb_actuals)
                                _bb_elapsed = time.time() - _bb_t0
                                _bb_acc_pct = _bb_sc["accuracy"] * 100.0

                                if _bb_acc_pct >= 90:
                                    _bb_grade = "🟢 우수 (완벽 메커니즘 권역)"
                                elif _bb_acc_pct >= 70:
                                    _bb_grade = "🟡 양호 (typeless 천장 권역)"
                                elif _bb_acc_pct >= 50:
                                    _bb_grade = "🟠 미흡 (동전 던지기 이상이지만 보정 필요)"
                                else:
                                    _bb_grade = "🔴 매핑·공식 점검 필요 (동전 던지기 이하)"

                                st.success(
                                    f"🎯 백테스트 완료! **전체 일치율 {_bb_acc_pct:.1f}%** — {_bb_grade} "
                                    f"({_bb_sc['correct']}/{_bb_sc['total']} 전투 · {_bb_elapsed:.0f}초)"
                                )

                                _bbm1, _bbm2, _bbm3 = st.columns(3)
                                with _bbm1:
                                    st.metric("전체 일치율", f"{_bb_acc_pct:.1f}%",
                                              f"{_bb_sc['correct']}/{_bb_sc['total']}")
                                with _bbm2:
                                    _bb_ar = _bb_sc["ally_wins_recall"] * 100.0
                                    st.metric("Ally 승 정확도",
                                              f"{_bb_ar:.1f}%",
                                              f"실제 Ally 승 {_bb_sc['ally_wins_actual']}건 중 적중")
                                with _bbm3:
                                    _bb_nr = _bb_sc["not_ally_recall"] * 100.0
                                    st.metric("Enemy/무승부 정확도",
                                              f"{_bb_nr:.1f}%",
                                              f"실제 비-Ally 승 {_bb_sc['not_ally_actual']}건 중 적중")

                                if _bb_errors:
                                    st.warning(f"⚠️ {_bb_errors}전투가 엔진 에러로 제외됐습니다 "
                                               f"(결과는 그 외 전투 기준).")

                                st.caption(
                                    "**해석 가이드** — 100%는 결정론적 완벽 시뮬, 95.8%는 Pokemon 기준 "
                                    "이론적 천장(난수 4.2%), 71.6%는 무브/타입 도입 전 Pokemon best-effort, "
                                    "50%는 동전 던지기. 50%대면 매핑/공식부터 점검하세요."
                                )

    with tab2:
```

---

## 설계 노트

- **모듈 분리** — 데이터 빌더(`build_battles`, `score_predictions`)는 순수 모듈에 두고,
  엔진 호출(병렬 풀 + `_worker_simulate_match`)은 step6에 둔다. Phase 9b의 영속 풀 패턴
  그대로 재사용 — 검증된 워커, 검증된 task 튜플 15원소.
- **전투당 행 수 (`battle_size`)** — 로그가 캐릭터-per-행 패턴이라 가정하고, 한 전투의
  모든 참가자가 *연속해서* 행으로 들어 있다고 본다. 앞 절반=Ally, 뒤 절반=Enemy.
  1v1=2, 2v2=4, 4v4=8. Pokemon 로그(2)로 검증됨.
- **실제 승자 판정** — 한 전투의 Ally 측 행들의 `target_col` 합 vs Enemy 측 합. 큰 쪽 승.
  `_is_win_signal`이 숫자(0/1, True/False, 0.5 등)와 문자열("Win"/"Victory"/"Ally" 등)을
  모두 처리.
- **이진 정확도** — 엔진 워커 `_worker_simulate_match`는 `(1 if winner=="Ally" else 0,
  metrics)`를 돌려준다. 그래서 backtest도 ally-win 여부의 이진 비교(Pokemon harness와
  동일 방식). Draw는 not-ally-win에 흡수됨.
- **성능** — Phase 9b 측정 기준 약 70 sims/sec(병렬). 500전투 × max_turns=100 ≈
  20~60초. 사용자가 `최대 전투 수`로 조절.
- **결과 해석 가이드** — UI에 그레이드 4단계 표시: 🟢 ≥90% (완벽 메커니즘 권역) /
  🟡 ≥70% (typeless 천장 권역) / 🟠 ≥50% (보정 필요) / 🔴 <50% (매핑·공식 점검).
  Pokemon 기준 95.8%(천장) / 71.6%(typeless best-effort) / 50%(동전).

## 검증 체크리스트 (적용 후 직접 확인하라)

- [ ] `modules/per_battle_backtest.py`가 새로 생성됐다 (`build_battles`,
      `score_predictions`, `_row_to_inst`, `_is_win_signal` 함수 포함).
- [ ] `modules/step6_dashboard.py`만 수정됐고, 단일 위치 1회 삽입만 일어났다.
- [ ] `python -m py_compile modules/per_battle_backtest.py modules/step6_dashboard.py` 통과.
- [ ] step6의 `🔬 전투별 백테스트` 섹션이 `chart_tabs[2]` 안, MC 검증 패널 다음,
      `with tab2:` 직전에 위치한다.
- [ ] 백테스트 task tuple이 `_worker_simulate_match` 15-인자 시그니처와 정확히 맞는다
      (ally_team, enemy_team, combat_flow, speed_stat, sys_stats, global_formula,
      max_turns, stochasticity_factory, resource_module, spatial=None, range_stat=None,
      move_stat=None, deck_module=None, game_config, worker_seed).
- [ ] Phase 9b 변경 영역(원본 step6의 `elif _use_engine_opt:` 블록, 약 913~1107줄)은
      **한 글자도 안 바뀌었다.**
- [ ] 레거시 SLSQP 경로, MC 버튼(`1만회 Monte Carlo 실행`), `calculate_validation_score`
      호출, `modules/validation.py`, `modules/optimizer.py` — 전부 불변.

## 회귀 불변 조건

이 변경은 **순수 가산적**이다:
- 신규 모듈 1개 추가.
- step6에 신규 섹션 1개 삽입(다른 코드는 건드리지 않음).
백테스트 버튼을 누르지 않으면 기존 동작과 100% 동일하다. `target_col`이 매핑되지 않은
프로젝트에선 안내 메시지만 뜨고 버튼이 노출되지 않는다 (`_bb_ready` 가드).
