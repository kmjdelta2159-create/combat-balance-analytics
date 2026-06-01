# Phase 9b — 엔진-인-더-루프 최적화 멀티코어 병렬 핫픽스

## 목표

Phase 9 엔진-인-더-루프 최적화가 실제 게임에서 **수 분간 멈춘 듯 보이는** 문제를 잡는다.

원인 두 가지:
1. **연산량 과다** — `361 평가 × 300 시뮬 = 약 108,000 전투`를 **단일 코어**로 순차 실행.
   샌드박스 프로토타입(24초)은 가벼운 전투 기준이었고, 실제 게임은 전투당 턴 수·무브풀
   때문에 훨씬 무겁다.
2. **진행바 갱신이 세대 단위** — 1세대(약 3,900 전투)가 끝나야 바가 처음 움직여서,
   그 전까지 0%에 멈춰 "행(hang)"처럼 보인다.

핫픽스 내용:
- **멀티코어 병렬화** — 엔진의 검증된 워커 `_worker_simulate_match`를 재사용해, 최적화
  전체에 걸쳐 `ProcessPoolExecutor`를 **한 번만** 띄우고 모든 내부 시뮬레이션을 전 코어로
  분산한다. (풀 1회 생성 → 평가마다 재사용. 평가마다 풀을 띄우지 않는다.)
- **연산량 축소** — 평가 65회 × 내부 50시뮬 = 3,250 + 최종검증 1,000 ≈ 4,250 전투.
- **내부 전투 턴 상한** — 탐색용 시뮬은 최대 60턴으로 캡(`_OPT_MAX_TURNS`). 최종 검증
  재평가만 풀 턴 수를 쓴다.
- **평가 단위 진행바** — `objective` 호출마다(총 65회) 진행바·경과시간을 갱신해 항상
  살아있게 한다.
- **엔진 에러 가시화** — 워커가 에러를 반환하면 건수와 첫 메시지를 표시한다.

이 변경은 **Phase 9 엔진 경로 블록 하나만** 통째 교체한다. `optimizer.py`,
step6의 import, 레거시 SLSQP 경로는 전혀 건드리지 않는다.

## 대상 파일

**`modules/step6_dashboard.py`** 단 하나. `Global Character Builder` 탭의
`Data-Driven Target Optimizer` 버튼 핸들러 안, `elif _use_engine_opt:` 블록 전체를 교체한다.

---

## 변경 1 — `elif _use_engine_opt:` 엔진 블록 통째 교체

아래 **찾기** 블록(현재 Phase 9 엔진 경로 전체 + 다음 `elif` 앵커 1줄)을 찾아
**바꾸기** 블록으로 통째 교체하라. 마지막 줄 `elif not st.session_state.get('has_ml_data'):`
은 앵커이므로 바꾸기 블록에도 그대로 포함돼 있다 — 그 아래 SLSQP 경로는 불변이다.

**찾기:**
```python
            elif _use_engine_opt:
                # ═══ Phase 9 — 실제 전투 엔진 MC 승률 목적함수 최적화 ═══
                _OPT_ITERATIONS = 30
                _OPT_POPULATION = 12
                _OPT_ELITE = 4
                _OPT_INNER_MC = 300
                _OPT_FINAL_MC = 2000

                stat_weights = st.session_state.get('stat_weights', {})
                opt_weights = [float(stat_weights.get(s, 1.0)) for s in sys_stats]

                # x0 / bounds — 원본 로그 평균을 예산으로 스케일 (SLSQP 경로와 동일 로직)
                try:
                    _means = df[sys_stats].mean().fillna(0).values.astype(float)
                    _stds = df[sys_stats].std().fillna(1).values.astype(float)
                except Exception:
                    _uniform = float(opt_budget) / max(len(sys_stats), 1)
                    _means = np.array([_uniform] * len(sys_stats), dtype=float)
                    _stds = np.array([1.0] * len(sys_stats), dtype=float)
                _wsum = sum(_means[i] * opt_weights[i] for i in range(len(_means)))
                if _wsum <= 0:
                    _wsum = 1.0
                _scale = float(opt_budget) / _wsum
                _scaled_means = [float(m * _scale) for m in _means]
                _scaled_stds = [float(s * _scale) for s in _stds]
                opt_bounds = [
                    (max(0.0, m - s * std_n),
                     max(max(0.0, m - s * std_n) + 0.1, m + s * std_n))
                    for m, s in zip(_scaled_means, _scaled_stds)
                ]

                # 엔진 환경 — session_state에서 자체 추출 (베이스라인 전투: 공간/덱 미사용)
                _cf = st.session_state.get('combat_flow', DEFAULT_COMBAT_FLOW)
                _spd = st.session_state.get('speed_stat')
                _gf = st.session_state.get('global_damage_formula', '0')
                _gc = st.session_state.get('game_config')
                _max_turns = int(st.session_state.get('sim_max_turns', 100))
                _res_mod = ResourceModule(
                    st.session_state.get('resource_config') or None,
                    damage_type_map=st.session_state.get('damage_type_map') or None
                )
                _move_lib = st.session_state.get('move_library')
                _resource_config = st.session_state.get('resource_config') or {
                    "HP": {"role": "vital",
                           "stat": st.session_state.get('health_stat'), "regen": 0.0}
                }
                cur_gimmicks = {
                    g: st.session_state.get(f'builder_gimmick_{g}', "None")
                    for g in sys_gimmicks
                }

                def _opt_coerce(v):
                    try:
                        v = float(v)
                    except (TypeError, ValueError):
                        return 0.0
                    return v if v == v else 0.0

                def _opt_build_inst(name, stat_dict, gimmick_dict):
                    inst = {"name": str(name), "gimmicks": dict(gimmick_dict)}
                    for s in sys_stats:
                        inst[s] = _opt_coerce(stat_dict.get(s, 0.0))
                    inst['resources'] = {}
                    for rname, rspec in _resource_config.items():
                        rstat = rspec.get('stat')
                        rval = float(inst[rstat]) if (rstat and rstat in inst) else 1.0
                        inst['resources'][rname] = {"current": rval, "max": rval}
                    if _move_lib:
                        inst['movepool'] = _move_lib
                    return inst

                def _opt_team_from_df(team_df):
                    insts = []
                    if team_df is None:
                        return insts
                    for _, row in team_df.iterrows():
                        h = row.get("Hero")
                        if h and h != "비어 있음" and not pd.isna(h):
                            sd = {s: row.get(s, 0.0) for s in sys_stats}
                            gd = {g: row.get(g, "None") for g in sys_gimmicks}
                            insts.append(_opt_build_inst(h, sd, gd))
                    return insts

                _ally_df = st.session_state.get('ally_df')
                _enemy_df = st.session_state.get('enemy_df')
                if target_team == "Ally":
                    _mate_team = _opt_team_from_df(
                        _ally_df.iloc[1:] if _ally_df is not None else None)
                    _opp_team = _opt_team_from_df(_enemy_df)
                else:
                    _mate_team = _opt_team_from_df(
                        _enemy_df.iloc[1:] if _enemy_df is not None else None)
                    _opp_team = _opt_team_from_df(_ally_df)

                if not _opp_team:
                    st.warning("⚠️ 상대 진영에 캐릭터가 없습니다. "
                               "조작부(GM Mode: Team Setup)에서 상대 팀을 먼저 편성해주세요.")
                else:
                    # 축소 MC — run_simulation ×N, 고정 시드(0..N-1) = 공통난수로 노이즈 저감
                    def _reduced_win_rate(ally_team, enemy_team):
                        wins = 0
                        for _j in range(_OPT_INNER_MC):
                            _w, _, _ = run_simulation(
                                ally_team, enemy_team, max_turns=_max_turns,
                                combat_flow=_cf, speed_stat=_spd, sys_stats=sys_stats,
                                global_damage_formula=_gf, silent=True,
                                stochasticity=default_stochasticity_factory(_j),
                                resource_module=_res_mod, game_config=_gc
                            )
                            if _w == "Ally":
                                wins += 1
                        return wins / float(_OPT_INNER_MC) * 100.0

                    def objective(x):
                        cand_stats = {s: x[i] for i, s in enumerate(sys_stats)}
                        cand = _opt_build_inst("OPT_CANDIDATE", cand_stats, cur_gimmicks)
                        full_team = [cand] + _mate_team
                        if target_team == "Ally":
                            ally_wr = _reduced_win_rate(full_team, _opp_team)
                            wr_interest = ally_wr
                        else:
                            ally_wr = _reduced_win_rate(_opp_team, full_team)
                            wr_interest = 100.0 - ally_wr
                        return -abs(wr_interest - target_win_rate)

                    _prog_bar = st.progress(0.0)
                    _prog_txt = st.empty()

                    def _opt_progress(done, total):
                        _prog_bar.progress(min(1.0, done / float(total)))
                        _prog_txt.text(f"엔진 인-더-루프 최적화: 세대 {done}/{total}")

                    with st.spinner("실제 전투 엔진 인-더-루프 최적화 연산 중..."):
                        opt_res = optimize_allocation(
                            objective, _scaled_means, float(opt_budget),
                            weights=opt_weights, bounds=opt_bounds,
                            iterations=_OPT_ITERATIONS, population=_OPT_POPULATION,
                            elite=_OPT_ELITE, seed=0, progress=_opt_progress
                        )
                        best_x = list(opt_res["best_x"])

                        # 최종 검증 — best_x를 풀 횟수 run_monte_carlo로 1회 재평가
                        _final_cand = _opt_build_inst(
                            "OPT_CANDIDATE",
                            {s: best_x[i] for i, s in enumerate(sys_stats)},
                            cur_gimmicks
                        )
                        _final_team = [_final_cand] + _mate_team
                        if target_team == "Ally":
                            _fa, _fe = _final_team, _opp_team
                        else:
                            _fa, _fe = _opp_team, _final_team
                        _mc = run_monte_carlo(
                            _fa, _fe, _cf, _spd, sys_stats, _gf,
                            num_simulations=_OPT_FINAL_MC, max_turns=_max_turns,
                            stochasticity_factory=default_stochasticity_factory,
                            resource_module=_res_mod, game_config=_gc
                        )

                    _prog_bar.progress(1.0)
                    if isinstance(_mc, dict) and _mc.get("status") == "error":
                        st.error("🚨 최종 검증 Monte Carlo 중 에러가 발생했습니다.")
                        st.code(_mc.get("message", ""), language="python")
                    else:
                        _final_ally_wr = (_mc.get("win_rate", 0.0)
                                          if isinstance(_mc, dict) else 0.0)
                        _final_interest = (_final_ally_wr if target_team == "Ally"
                                           else 100.0 - _final_ally_wr)
                        st.success(
                            f"✅ 엔진 최적화 완료! 목표 승률 {target_win_rate}% 대비 "
                            f"검증 승률 {_final_interest:.2f}% "
                            f"(오차 {abs(_final_interest - target_win_rate):.2f}%p · "
                            f"{opt_res['evals']} evals · 검증 MC {_OPT_FINAL_MC}회)"
                        )
                        for i, stat in enumerate(sys_stats):
                            st.session_state[f'builder_stat_input_{stat}'] = float(best_x[i])
            elif not st.session_state.get('has_ml_data'):
```
**바꾸기:**
```python
            elif _use_engine_opt:
                # ═══ Phase 9 — 실제 전투 엔진 MC 승률 목적함수 최적화 (멀티코어 병렬) ═══
                from modules.engine import _worker_simulate_match

                _OPT_ITERATIONS = 8
                _OPT_POPULATION = 8
                _OPT_ELITE = 3
                _OPT_INNER_MC = 50
                _OPT_FINAL_MC = 1000

                stat_weights = st.session_state.get('stat_weights', {})
                opt_weights = [float(stat_weights.get(s, 1.0)) for s in sys_stats]

                # x0 / bounds — 원본 로그 평균을 예산으로 스케일 (SLSQP 경로와 동일 로직)
                try:
                    _means = df[sys_stats].mean().fillna(0).values.astype(float)
                    _stds = df[sys_stats].std().fillna(1).values.astype(float)
                except Exception:
                    _uniform = float(opt_budget) / max(len(sys_stats), 1)
                    _means = np.array([_uniform] * len(sys_stats), dtype=float)
                    _stds = np.array([1.0] * len(sys_stats), dtype=float)
                _wsum = sum(_means[i] * opt_weights[i] for i in range(len(_means)))
                if _wsum <= 0:
                    _wsum = 1.0
                _scale = float(opt_budget) / _wsum
                _scaled_means = [float(m * _scale) for m in _means]
                _scaled_stds = [float(s * _scale) for s in _stds]
                opt_bounds = [
                    (max(0.0, m - s * std_n),
                     max(max(0.0, m - s * std_n) + 0.1, m + s * std_n))
                    for m, s in zip(_scaled_means, _scaled_stds)
                ]

                # 엔진 환경 — session_state에서 자체 추출 (베이스라인 전투: 공간/덱 미사용)
                _cf = st.session_state.get('combat_flow', DEFAULT_COMBAT_FLOW)
                _spd = st.session_state.get('speed_stat')
                _gf = st.session_state.get('global_damage_formula', '0')
                _gc = st.session_state.get('game_config')
                _max_turns = int(st.session_state.get('sim_max_turns', 100))
                _OPT_MAX_TURNS = min(_max_turns, 60)   # 탐색용 내부 전투 턴 상한
                _res_mod = ResourceModule(
                    st.session_state.get('resource_config') or None,
                    damage_type_map=st.session_state.get('damage_type_map') or None
                )
                _move_lib = st.session_state.get('move_library')
                _resource_config = st.session_state.get('resource_config') or {
                    "HP": {"role": "vital",
                           "stat": st.session_state.get('health_stat'), "regen": 0.0}
                }
                cur_gimmicks = {
                    g: st.session_state.get(f'builder_gimmick_{g}', "None")
                    for g in sys_gimmicks
                }

                def _opt_coerce(v):
                    try:
                        v = float(v)
                    except (TypeError, ValueError):
                        return 0.0
                    return v if v == v else 0.0

                def _opt_build_inst(name, stat_dict, gimmick_dict):
                    inst = {"name": str(name), "gimmicks": dict(gimmick_dict)}
                    for s in sys_stats:
                        inst[s] = _opt_coerce(stat_dict.get(s, 0.0))
                    inst['resources'] = {}
                    for rname, rspec in _resource_config.items():
                        rstat = rspec.get('stat')
                        rval = float(inst[rstat]) if (rstat and rstat in inst) else 1.0
                        inst['resources'][rname] = {"current": rval, "max": rval}
                    if _move_lib:
                        inst['movepool'] = _move_lib
                    return inst

                def _opt_team_from_df(team_df):
                    insts = []
                    if team_df is None:
                        return insts
                    for _, row in team_df.iterrows():
                        h = row.get("Hero")
                        if h and h != "비어 있음" and not pd.isna(h):
                            sd = {s: row.get(s, 0.0) for s in sys_stats}
                            gd = {g: row.get(g, "None") for g in sys_gimmicks}
                            insts.append(_opt_build_inst(h, sd, gd))
                    return insts

                _ally_df = st.session_state.get('ally_df')
                _enemy_df = st.session_state.get('enemy_df')
                if target_team == "Ally":
                    _mate_team = _opt_team_from_df(
                        _ally_df.iloc[1:] if _ally_df is not None else None)
                    _opp_team = _opt_team_from_df(_enemy_df)
                else:
                    _mate_team = _opt_team_from_df(
                        _enemy_df.iloc[1:] if _enemy_df is not None else None)
                    _opp_team = _opt_team_from_df(_ally_df)

                if not _opp_team:
                    st.warning("⚠️ 상대 진영에 캐릭터가 없습니다. "
                               "조작부(GM Mode: Team Setup)에서 상대 팀을 먼저 편성해주세요.")
                else:
                    _total_evals = 1 + _OPT_ITERATIONS * _OPT_POPULATION
                    _eval_count = [0]
                    _opt_err = {"n": 0, "msg": ""}
                    _prog_bar = st.progress(0.0)
                    _prog_txt = st.empty()
                    _t_start = time.time()
                    _max_workers = os.cpu_count() or 4

                    with st.spinner("실제 전투 엔진 인-더-루프 최적화 연산 중... (멀티코어 병렬)"):
                        with concurrent.futures.ProcessPoolExecutor(
                                max_workers=_max_workers) as _pool:

                            def _reduced_win_rate(ally_team, enemy_team, n_sims, max_turns):
                                _tasks = [
                                    (ally_team, enemy_team, _cf, _spd, sys_stats, _gf,
                                     max_turns, default_stochasticity_factory, _res_mod,
                                     None, None, None, None, _gc, _j)
                                    for _j in range(n_sims)
                                ]
                                wins = 0
                                done = 0
                                for _r in _pool.map(_worker_simulate_match, _tasks,
                                                    chunksize=4):
                                    if isinstance(_r, str):
                                        _opt_err["n"] += 1
                                        if not _opt_err["msg"]:
                                            _opt_err["msg"] = _r
                                    else:
                                        wins += _r[0]
                                    done += 1
                                return (wins / float(done) * 100.0) if done else 0.0

                            def objective(x):
                                cand_stats = {s: x[i] for i, s in enumerate(sys_stats)}
                                cand = _opt_build_inst("OPT_CANDIDATE", cand_stats,
                                                       cur_gimmicks)
                                full_team = [cand] + _mate_team
                                if target_team == "Ally":
                                    ally_wr = _reduced_win_rate(
                                        full_team, _opp_team, _OPT_INNER_MC, _OPT_MAX_TURNS)
                                    wr_interest = ally_wr
                                else:
                                    ally_wr = _reduced_win_rate(
                                        _opp_team, full_team, _OPT_INNER_MC, _OPT_MAX_TURNS)
                                    wr_interest = 100.0 - ally_wr
                                _eval_count[0] += 1
                                _prog_bar.progress(
                                    min(1.0, _eval_count[0] / float(_total_evals)))
                                _prog_txt.text(
                                    f"엔진 최적화: 평가 {_eval_count[0]}/{_total_evals} "
                                    f"· 경과 {time.time() - _t_start:.0f}초"
                                )
                                return -abs(wr_interest - target_win_rate)

                            opt_res = optimize_allocation(
                                objective, _scaled_means, float(opt_budget),
                                weights=opt_weights, bounds=opt_bounds,
                                iterations=_OPT_ITERATIONS, population=_OPT_POPULATION,
                                elite=_OPT_ELITE, seed=0
                            )
                            best_x = list(opt_res["best_x"])

                            # 최종 검증 — best_x를 풀 턴·풀 횟수로 1회 재평가
                            _final_cand = _opt_build_inst(
                                "OPT_CANDIDATE",
                                {s: best_x[i] for i, s in enumerate(sys_stats)},
                                cur_gimmicks
                            )
                            _final_team = [_final_cand] + _mate_team
                            if target_team == "Ally":
                                _fa, _fe = _final_team, _opp_team
                            else:
                                _fa, _fe = _opp_team, _final_team
                            _final_ally_wr = _reduced_win_rate(
                                _fa, _fe, _OPT_FINAL_MC, _max_turns)

                    _prog_bar.progress(1.0)
                    if _opt_err["n"]:
                        st.warning(f"⚠️ 시뮬레이션 {_opt_err['n']}건이 엔진 에러로 "
                                   f"제외됐습니다 (결과 신뢰도 저하 가능).")
                        with st.expander("엔진 에러 메시지 (첫 건)"):
                            st.code(_opt_err["msg"], language="python")
                    _final_interest = (_final_ally_wr if target_team == "Ally"
                                       else 100.0 - _final_ally_wr)
                    st.success(
                        f"✅ 엔진 최적화 완료! 목표 승률 {target_win_rate}% 대비 "
                        f"검증 승률 {_final_interest:.2f}% "
                        f"(오차 {abs(_final_interest - target_win_rate):.2f}%p · "
                        f"{opt_res['evals']} evals · 검증 MC {_OPT_FINAL_MC}회 · "
                        f"총 {time.time() - _t_start:.0f}초)"
                    )
                    for i, stat in enumerate(sys_stats):
                        st.session_state[f'builder_stat_input_{stat}'] = float(best_x[i])
            elif not st.session_state.get('has_ml_data'):
```

---

## 설계 노트

- **영속 풀(persistent pool)** — `with ProcessPoolExecutor(...) as _pool:`가 최적화
  루프 전체를 감싼다. 풀 생성 비용(특히 Windows spawn)은 1회만 지불한다. 평가마다
  `run_monte_carlo`를 부르면 풀을 65회 새로 띄워 오히려 더 느려지므로 그렇게 하지 않는다.
- **엔진 워커 재사용** — `from modules.engine import _worker_simulate_match`. 이 워커는
  `run_monte_carlo`가 쓰는 것과 동일하며 picklable이 검증돼 있다. task 튜플 15개 인자
  순서도 엔진 정의와 일치한다. `spatial_module`/`range_stat`/`move_stat`/`deck_module`은
  `None`(베이스라인 전투) — 기존 Phase 9 설계와 동일.
- **연산량 상수** — `_OPT_ITERATIONS=8`, `_OPT_POPULATION=8`, `_OPT_INNER_MC=50`,
  `_OPT_FINAL_MC=1000`, `_OPT_MAX_TURNS=min(_max_turns,60)`. 너무 느리면 `_OPT_INNER_MC`·
  `_OPT_ITERATIONS`를 더 낮추고, 정밀도를 높이려면 올린다.
- **고정 시드 유지** — `_worker_simulate_match`에 `worker_seed=_j`(0..N-1). 모든 평가가
  같은 RNG 스트림을 공유(공통난수) → 후보 비교 노이즈 저감.
- **최종 검증** — `best_x`를 풀 턴 수·`_OPT_FINAL_MC`회로 같은 풀에서 1회 재평가한다
  (별도 `run_monte_carlo` 호출·별도 풀 생성 없음).

## 검증 체크리스트 (적용 후 직접 확인하라)

- [ ] `modules/step6_dashboard.py`만 수정됐다 (다른 파일 불변).
- [ ] `python -m py_compile modules/step6_dashboard.py` 통과.
- [ ] `elif _use_engine_opt:` 블록 안에 `from modules.engine import _worker_simulate_match`,
      `concurrent.futures.ProcessPoolExecutor`, `_pool.map(_worker_simulate_match, ...)`,
      `_OPT_MAX_TURNS` 가 존재한다.
- [ ] objective가 평가마다 `_prog_bar.progress(...)` 로 진행바를 갱신한다.
- [ ] 찾기 블록의 마지막 줄 `elif not st.session_state.get('has_ml_data'):` 아래
      **SLSQP 경로(`with st.spinner("Scipy SLSQP ...")` ~ `else: st.error(...)`)가
      한 글자도 안 바뀌었다.**
- [ ] `from modules.optimizer import optimize_allocation` import 줄은 그대로다.

## 회귀 불변 조건

이 핫픽스는 Phase 9 **엔진 경로 블록 하나만** 교체한다. 디스패치 조건(`_use_engine_opt`),
레거시 SLSQP 경로, `optimizer.py`, import 문은 모두 불변이다. `game_config`/`move_library`가
없는 프로젝트는 여전히 SLSQP 경로로 빠지며 기존과 100% 동일하게 동작한다.
