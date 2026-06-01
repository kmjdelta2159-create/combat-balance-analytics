# 대화창 이동 핸드오프 — Combat Balance Analytics / Phase 9 진입 직전

> 새 대화창에 이 문서를 그대로 붙여넣어라. 아래 컨텍스트를 숙지하고, 곧바로 **즉시 다음 스텝**부터 이어서 진행한다.

---

## 0. 너의 역할 (불변 제약 — 절대 어기지 마라)

너는 프로젝트 **"Combat Balance Analytics"** 의 보조자다. 프로젝트 리드는 사용자(김민재)다.

- 너는 **프로젝트 코드 파일을 직접 수정하지 않는다.** 너의 산출물은 코드 생성기 **"Antigravity"** 에게 넘길 **markdown 프롬프트**다. 사용자가 그 프롬프트를 Antigravity에 전달하고, Antigravity가 실제 파일을 고친다.
- **예외:** 검증용 테스트 하니스, 레퍼런스 구현(reference implementation)은 너가 직접 작성해도 된다. 이것들은 프로젝트 코드가 아니라 검증 도구다. 샌드박스(`~/...`)에서 작업한다.
- **검증 의무:** Antigravity 산출물은 **절대 설명만 믿지 마라.** 항상 코드를 직접 읽어 검증한다 — grep으로 마커 확인 → 변경 구역 정독 → 클린룸 회귀 테스트. Antigravity는 불완전·하드코딩 납품 전력이 있다.
- 프롬프트 스타일: **앵커 기반 통째 블록 find/replace** (찾기 블록 / 바꾸기 블록). `Phase8b_상성표STAB_프롬프트.md` 등 기존 프롬프트가 모범 양식이다.

---

## 1. 프로젝트 개요 — 최종 목표

Python 3 / Streamlit / Pandas / Scikit-learn / gplearn 기반 **턴제 전투 시뮬레이터**.

**최종 목표 (3단계):**
1. 전투 로그를 **역설계**한다.
2. 전문가(사용자) **개입**을 받아 게임의 전투 시스템을 **복제**한다.
3. 복제본을 **밸런스 분석용으로 최적화**한다.

**핵심 원리 — 연속 슬라이더:** 대상은 턴제 구조 게임. *대중적인 형태일수록* 시뮬레이터의 **역설계 비중이 높고**, *비대중적일수록* **사용자 개입 비중이 높다.** 역설계와 개입은 독립된 두 기둥이 아니라 **하나의 연속 슬라이더의 양 끝**이다. 흔치 않은 메커닉에서 자동 역설계가 약한 것은 결함이 아니라 슬라이더가 정상 작동하는 것이다.

정직한 스코프: 스탯 기반 턴제 게임 (JRPG / 가챠 / SRPG / 덱빌더).

---

## 2. 아키텍처 핵심

- Streamlit SPA 위저드: Step 1 업로드 → Step 2 시스템 정의 → Step 5 불일치 → Step 2 프로파일링 → Step 6 대시보드.
- 전투 엔진 `modules/engine.py` — UI 독립, 순수 Python. 액션 파이프라인:
  `PASSIVE_START → STAT_CALC → MOVE_SELECT → TARGET_SELECT → DAMAGE_CALC → ELEMENT_MULT → CRIT_CALC → APPLY_DAMAGE → ON_HIT → DEATH_CHECK`
- 3-Layer 설계: L1 Universal Core(~80%), L2 Pluggable Modules(~82%), L3 Game Plugins(~15%, 대부분 부재).
- `game_config` dict = L3의 "데이터 척추". Phase 8에서 도입: `{categories, type_table, type_columns, stab_factor}`.

---

## 3. 현재 진행 상황

### Phase 8 — 완료·검증 끝
- **8a (무브 시스템):** `engine.py`에 MOVE_SELECT 단계·`_act_move_select`·무브 주입(`move_power`/`offense`/`defense`)·`game_config` 파라미터 추가. 신규 순수 모듈 `modules/move_extraction.py`(71줄). UI는 `step2_system_definition.py`에 무브 패널 + `game_config` 조립.
- **8b (N-type 상성표 + STAB):** `engine.py`에 `_move_type_multiplier`·`_move_stab_multiplier`·무브 인지 `_act_element_mult`·타입 인지 그리디. UI는 `step2_system_definition.py`에 타입 상성표 그리드(`st.data_editor` key `ui_type_table_editor`) + STAB `number_input`(key `ui_stab_factor`).
- 8a/8b 엔진·UI **4건 모두 Antigravity 납품 완료**, 직접 Read로 검증 끝 — 사전 검증 패치와 바이트 동일.
- `engine.py` 851 → 890줄.

### 검증 결과 (포켓몬 known-answer 하니스, 클린룸)
- known-answer 충실도: **71.6%(베이스) → 74.3%(8a) → 92.6%(8b)**, 천장 95.8%.
- 잔여 갭: move-power/routing 3.7pp + 환원 불가 RNG 4.2pp.

### Phase 9 — 진행 중 (현재 위치)
**목표:** Step 6 대시보드의 스탯 배분 최적화를 **엔진-인-더-루프**로 교체.
- 현재 step6는 SLSQP로 **LR 대리모델**(`calc_instance_score`/`ml_coefs`)을 최적화한다 → 모델의 모델을 최적화하는 셈.
- Phase 9는 이것을 **실제 엔진 MC 승률 목적함수**로 교체한다. 엔진은 충분히 빠르다(아래 프로토타입 참조).

---

## 4. 핵심 방법론 주의사항 (반드시 지켜라)

**bash 마운트 truncation (재발성·치명적):** bash로 큰 워크스페이스 파일(engine.py 890줄, step2 ~627줄, step6 ~956줄)을 `cp`/`cat`하면 **조용히 잘린다.** `wc`/`py_compile`/`diff`가 거짓 에러를 낸다.
- → 워크스페이스 파일은 **반드시 Read/Grep 파일 도구로** 읽어라. bash 금지.
- 검증은 Grep 마커 + 변경 구역 Read 정독으로 한다.
- 샌드박스 자체 파일(`~/pkmn_regen/...`)은 bash로 다뤄도 안전하다.

기타 함정:
- `run_simulation`은 **3-튜플** 반환 → `wa, _, _ = E.run_simulation(...)`.
- `run_simulation`/`run_monte_carlo`는 이제 `game_config` 파라미터를 받는다.
- 샌드박스 `/tmp`는 권한 문제 있음 → `~/pkmn_regen` (HOME, 소유권 OK) 사용.

---

## 5. 검증 끝난 자산 — `optimizer.py` (Phase 9 신규 모듈의 원본)

샌드박스 `~/pkmn_regen/optimizer.py`에 작성·검증 완료. 미분 없는 노이즈 내성 (μ,λ)-진화 전략 + 예산 제약 초평면 투영. Phase 9에서 이걸 **`modules/optimizer.py`로 그대로(verbatim)** 넣는다.

검증: 합성 무노이즈 L1 오차 0.02 / 노이즈(σ=800) 수렴 / 임계 테스트 speed-tier 정확히 120 검출.

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

**엔진-인-더-루프 프로토타입 검증 결과:** 빌드 스탯을 reduced-MC(`run_simulation` ×300, `DamageVariance(variance_pct=0.1)`) 승률 목적함수로 최적화 → 361 evals, 23.8초, 승률 77.3% → 100%, 예산 정확히 595 유지.

---

## 6. 다음 작업 — Task 20: Phase 9 Antigravity 프롬프트 작성

산출물 = `Phase9_엔진최적화_프롬프트.md` (워크스페이스에 저장). 내용:

**(A) 신규 파일 `modules/optimizer.py`** — 위 §5 코드 verbatim.

**(B) `modules/step6_dashboard.py` 결합 변경** — 현재 SLSQP 최적화 블록(약 895–945줄)을 교체:
- 제거: `scipy.optimize` SLSQP가 LR 대리모델(`calc_instance_score`/`coefs`/`ml_coefs`)을 최적화하는 부분.
- 도입: `optimizer.optimize_allocation(objective, ...)`. `objective`는 후보 스탯 배분으로 빌드를 구성해 **축소 횟수 `run_monte_carlo`**(실제 엔진, `game_config` 전달)를 돌려 **승률**을 반환.
- `weights` = 기존 `stat_weights`, `budget` = 기존 `opt_budget`.
- Streamlit 진행바: `optimize_allocation`의 `progress` 콜백 연결.
- 최종 검증: 최적해를 **풀 횟수 MC**로 1회 재평가해 표시.
- 결과 기입: 기존과 동일하게 `st.session_state[f'builder_stat_input_{stat}']`에 쓴다.
- **회귀 불변:** `game_config`/movepool 없으면 기존과 동등하게 동작하도록 — 또는 최소한 엔진 경로가 안전하게 폴백하도록 설계.

작성 후: 프롬프트를 사전 py_compile 컨텍스트 검증(들여쓰기!) → 사용자에게 전달 → Antigravity 납품 후 Grep+Read 직접 검증 → 클린룸 회귀.

---

## 7. 즉시 다음 스텝

1. **`Read` 도구로** `C:\Users\kmjde\OneDrive\Desktop\턴제 시뮬레이션\modules\step6_dashboard.py`의 SLSQP 최적화 블록(약 895–945줄)을 정독한다. **bash 금지 — 마운트 truncation.** 정확한 변수명(`calc_instance_score`, `coefs`/`ml_coefs`, `stat_weights`, `opt_budget`, SLSQP 호출, `builder_stat_input_*` 기입)과 앵커로 쓸 통째 블록을 확정한다.
2. step6 결합 설계를 확정하고 `Phase9_엔진최적화_프롬프트.md`를 작성한다 (찾기/바꾸기 앵커 블록 양식).
3. 프롬프트의 step6 변경 블록을 py_compile 컨텍스트로 사전 검증한다.
4. 사용자에게 전달한다.

---

## 8. 파일 위치

- 워크스페이스(사용자 폴더): `C:\Users\kmjde\OneDrive\Desktop\턴제 시뮬레이션`
- 프로젝트 코드: `modules/engine.py`, `modules/move_extraction.py`, `modules/step2_system_definition.py`, `modules/step6_dashboard.py`
- 기존 Phase 프롬프트: `Phase8a_무브엔티티_프롬프트.md`, `Phase8a-UI_무브UI_프롬프트.md`, `Phase8b_상성표STAB_프롬프트.md`, `Phase8b-UI_상성표UI_프롬프트.md`
- 검증 자산: `검증_포켓몬/pkmn_ref.py`, `검증_포켓몬/검증_Run결과_채점표.md`
- 검증 끝난 `optimizer.py` 원본: 샌드박스 `~/pkmn_regen/optimizer.py` (§5에 전문 수록)

---

**상태 요약:** Phase 8 전부 완료·검증 끝. Phase 9는 방향 확정(엔진-인-더-루프) + `optimizer.py` 검증 끝. 남은 것 = Task 20 (Phase 9 프롬프트 작성). 위 §7 1번 — step6 SLSQP 블록 Read부터 시작하라.
