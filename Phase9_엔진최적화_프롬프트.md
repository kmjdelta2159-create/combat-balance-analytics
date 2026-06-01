# Phase 9 — 엔진-인-더-루프 스탯 배분 최적화 (대시보드 레이어)

## 목표

Step 6 대시보드 `Global Character Builder` 탭의 **Data-Driven Target Optimizer**를
**실제 전투 엔진 몬테카를로 승률**을 목적함수로 쓰는 최적화로 교체한다.

현재는 `scipy.optimize`의 SLSQP가 **LR 대리모델**(`calc_instance_score` / `ml_coefs`)을
최적화한다 — 즉 *모델의 모델*을 최적화한다. Phase 9는 후보 스탯 배분으로 빌드를 만들어
실제 `engine.py`를 돌리고, 그 승률을 목적함수로 삼는다.

엔진은 충분히 빠르다(프로토타입 실측: 361 evals · 약 24초). 최적화기는 미분 없는
노이즈 내성 (μ,λ)-진화 전략 + 예산 제약 초평면 투영을 쓰는 신규 순수 모듈
`modules/optimizer.py`다.

### 회귀 불변 — 디스패치 설계

이 변경은 **순수 가산적**이다. 최적화 버튼 핸들러는 다음과 같이 분기한다:

- `game_config` 또는 `move_library`가 있으면 → **Phase 9 엔진 경로** (신규).
- 둘 다 없으면 → **레거시 SLSQP 경로** (기존 코드 그대로, 한 글자도 안 바뀜).

따라서 Phase 8 시스템 정의를 하지 않은 프로젝트는 기존과 **100% 동일**하게 동작한다.
SLSQP 블록(원본 910~946줄, `coefs = ...` ~ `else: st.error(...)`)은 **건드리지 않는다** —
find 블록이 909줄 `with st.spinner("Scipy SLSQP 최적화 연산 중..."):`에서 끝나고,
그 아래 SLSQP 본문은 그대로 새 `else:` 분기의 몸통으로 재사용된다.

## 대상 파일

1. **신규 파일** `modules/optimizer.py` — 생성.
2. **`modules/step6_dashboard.py`** — import 1줄 추가 + 버튼 핸들러 앞부분 5줄 교체.

다른 파일은 건드리지 마라. `modules/engine.py`는 수정하지 않는다 (소비만 한다).

---

## 변경 1 — 신규 파일 `modules/optimizer.py` 생성

아래 내용 그대로 `modules/optimizer.py`를 새로 만든다 (표준 라이브러리만 의존하는
순수 모듈, 합성·노이즈·임계 테스트로 검증 완료).

```python
# -*- coding: utf-8 -*-
"""
optimizer.py — 예산 제약 스탯 배분 최적화 (Phase 9).
순수 모듈: 표준 라이브러리만 의존. 미분 없는 노이즈 내성 (μ,λ)-진화 전략.
"""
import random as _random

def _project_budget(x, weights, budget):
    """w·x == budget 초평면으로 직교 투영."""
    wdotx = sum(w * xi for w, xi in zip(weights, x))
    wdotw = sum(w * w for w in weights)
    if wdotw == 0:
        return list(x)
    k = (wdotx - budget) / wdotw
    return [xi - k * w for xi, w in zip(x, weights)]

def _feasible(x, weights, budget, bounds, passes=8):
    """경계 클립 + 예산 초평면 재투영 반복."""
    x = list(x)
    for _ in range(passes):
        x = _project_budget(x, weights, budget)
        hit = False
        for i, (lo, hi) in enumerate(bounds):
            if x[i] < lo:
                x[i] = lo; hit = True
            elif x[i] > hi:
                x[i] = hi; hit = True
        if not hit:
            break
    return x

def optimize_allocation(objective, x0, budget, weights=None, bounds=None,
                        iterations=40, population=14, elite=4, seed=0,
                        sigma=None, progress=None):
    n = len(x0)
    weights = list(weights) if weights else [1.0] * n
    if bounds is None:
        bounds = [(0.0, float(budget))] * n
    rng = _random.Random(seed)
    mean = _feasible(x0, weights, budget, bounds)
    if sigma is None:
        scale = sum(abs(v) for v in mean) / max(n, 1)
        sigma = max(1.0, 0.25 * scale)
    evals = [0]
    def ev(x):
        evals[0] += 1
        return objective(x)
    best_x, best_score = list(mean), ev(mean)
    history = [best_score]
    for it in range(iterations):
        cands = []
        for _ in range(population):
            c = [mean[i] + rng.gauss(0, sigma) for i in range(n)]
            c = _feasible(c, weights, budget, bounds)
            cands.append((c, ev(c)))
        cands.sort(key=lambda cs: -cs[1])
        el = cands[:elite]
        mean = _feasible([sum(e[0][i] for e in el) / elite for i in range(n)],
                         weights, budget, bounds)
        if el[0][1] > best_score:
            best_score, best_x = el[0][1], list(el[0][0])
        sigma *= 0.90
        history.append(el[0][1])
        if progress:
            progress(it + 1, iterations)
    return {"x": mean, "best_x": best_x, "score": best_score,
            "history": history, "evals": evals[0]}
```

---

## 변경 2 — `modules/step6_dashboard.py` 상단에 optimizer import 추가

**찾기:**
```python
from modules.engine import run_simulation, run_monte_carlo, default_stochasticity_factory, DEFAULT_COMBAT_FLOW
from modules.spatial import SpatialModule
```
**바꾸기:**
```python
from modules.engine import run_simulation, run_monte_carlo, default_stochasticity_factory, DEFAULT_COMBAT_FLOW
from modules.optimizer import optimize_allocation
from modules.spatial import SpatialModule
```

---

## 변경 3 — `modules/step6_dashboard.py` 최적화 버튼 핸들러 디스패치 교체

`with tab2:` 안, `Data-Driven Target Optimizer` 버튼 핸들러의 **앞부분 5줄**을 찾아
아래 블록으로 교체한다. find 블록의 마지막 줄(`with st.spinner("Scipy SLSQP ...")`)은
바꾸기 블록 끝에 **그대로 다시 포함**되어 있으므로, 그 아래 기존 SLSQP 본문
(`coefs = ...` ~ `else: st.error("❌ 최적화에 실패했습니다.")`)은 **한 줄도 수정하지 마라.**

**찾기:**
```python
        if st.button("🚀 데이터 기반 스탯 최적화 실행 (Optimize)", use_container_width=True):
            if not st.session_state.get('has_ml_data') or not sys_stats:
                st.warning("⚠️ 데이터가 부족하거나 시스템 스탯 스키마가 로드되지 않았습니다.")
            else:
                with st.spinner("Scipy SLSQP 최적화 연산 중..."):
```
**바꾸기:**
```python
        if st.button("🚀 데이터 기반 스탯 최적화 실행 (Optimize)", use_container_width=True):
            # ── Phase 9 — 엔진-인-더-루프 vs 레거시 SLSQP 디스패치 ──
            _use_engine_opt = bool(
                st.session_state.get('game_config') or st.session_state.get('move_library')
            )
            if not sys_stats:
                st.warning("⚠️ 시스템 스탯 스키마가 로드되지 않았습니다.")
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
                st.warning("⚠️ 데이터가 부족하거나 시스템 스탯 스키마가 로드되지 않았습니다.")
            else:
                with st.spinner("Scipy SLSQP 최적화 연산 중..."):
```

---

## 설계 노트 (왜 이렇게 했는가)

- **inner objective는 `run_simulation` 루프 (`run_monte_carlo` 아님).**
  `run_monte_carlo`는 호출마다 `ProcessPoolExecutor`를 새로 띄운다. objective는 약
  361회 호출되므로, objective마다 `run_monte_carlo`를 부르면 프로세스 풀 스폰
  오버헤드가 361회 누적돼 비현실적으로 느려진다 (특히 Windows `spawn`). 검증된
  프로토타입(361 evals · 24초)도 `run_simulation ×300` 루프를 썼다. 따라서
  inner objective는 `run_simulation` 루프, **최종 재평가만 `run_monte_carlo` 1회**.
- **고정 시드 0..N-1** — 모든 objective 호출이 같은 RNG 스트림을 공유한다
  (공통난수, common random numbers). 후보 간 비교 노이즈를 줄여 (μ,λ)-ES가
  깨끗하게 수렴하게 한다.
- **베이스라인 전투 스코프** — 최적화 시뮬레이션은 `resource_module`·`game_config`·
  `movepool`은 전달하되 `spatial_module`·`deck_module`은 전달하지 않는다 (`None`).
  스탯 예산 배분에는 격자 좌표·덱이 무관하고, 후보 캐릭터에는 좌표/덱이 없어
  엔진에 넘기면 위험하다. 사거리 무제한·이동 없음 = 현행 baseline 전투.
- **후보 = 대상 진영 슬롯 0.** 후보는 `target_team`의 0번 슬롯을 차지하고,
  나머지 슬롯 1~3과 상대 진영 전원은 `ally_df`/`enemy_df` 그대로 쓴다.
  (레거시 SLSQP의 `idx > 0` 상수항 로직과 동일한 의미.)
- `_OPT_INNER_MC` / `_OPT_FINAL_MC` / `_OPT_ITERATIONS` / `_OPT_POPULATION`은
  상수로 노출돼 있다. 너무 느리면 `_OPT_INNER_MC`·`_OPT_ITERATIONS`를 낮춰라.
  현재 값 = 1 + 30×12 = 361 evals (검증 프로토타입과 동일).

---

## 검증 체크리스트 (적용 후 직접 확인하라)

- [ ] `modules/optimizer.py`가 새로 생성됐다 (`optimize_allocation` 함수 포함).
- [ ] `modules/step6_dashboard.py`만 수정됐다 (optimizer.py 생성 외 다른 파일 불변).
- [ ] `python -m py_compile modules/optimizer.py modules/step6_dashboard.py`가 통과한다.
- [ ] step6 상단에 `from modules.optimizer import optimize_allocation` 한 줄이 추가됐다.
- [ ] 버튼 핸들러에 `_use_engine_opt` 분기 → `elif _use_engine_opt:` 엔진 경로가 있다.
- [ ] 엔진 경로의 objective가 `run_simulation`을 루프로 호출한다 (objective 안에서
      `run_monte_carlo`를 부르지 **않는다**).
- [ ] 최종 재평가가 `run_monte_carlo`를 **딱 1회** 호출한다.
- [ ] 최적해를 `st.session_state[f'builder_stat_input_{stat}']`에 기입한다.
- [ ] **SLSQP 블록(원본 `coefs = st.session_state['ml_coefs']` ~
      `else: st.error("❌ 최적화에 실패했습니다.")`)이 한 글자도 안 바뀌었다.**
- [ ] 변경 3개(파일 생성 + import + 디스패치)가 전부 적용됐다.

## 회귀 불변 조건

`game_config`와 `move_library`가 **둘 다 없으면** — `_use_engine_opt`가 `False` →
`elif not st.session_state.get('has_ml_data')` / `else` 분기로 진입 → 기존 SLSQP
경로가 **그대로** 실행된다. SLSQP 본문은 find/replace 대상이 아니므로 바이트 단위로
동일하다. 즉 Phase 8 시스템 정의를 하지 않은 프로젝트의 동작은 100% 불변이다.
