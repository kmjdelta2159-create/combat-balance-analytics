# Phase 7 — Damage Formula Symbolic Regression (데미지 공식 자동 추측)

## 배경

지금은 사용자가 Step 2의 Live Formula Validator에 데미지 공식을 **수동 입력**한다
(`phys_power - target_armor_class` 같은 eval 식). Phase 7은 전투로그에 **데미지(연속
숫자) 컬럼이 있을 때**, gplearn 기호 회귀(Symbolic Regression)로 `damage ≈ f(스탯)`
공식을 자동 추측해 후보로 제시한다. 사용자가 후보를 골라 공식 입력창에 채울 수 있다.

하이브리드 설계: 데미지 컬럼이 탐지되면 SR 활성, 없으면 비활성(수동 입력 안내).
탐색공간(후보 변수)은 Phase 6의 `game_profile`로 조정된다.

## 변경 파일 (3개)

- **`modules/symbolic_regression.py`** — 신규. 순수 분석 모듈 (gplearn + pandas,
  streamlit/엔진 의존 0).
- **`modules/step2_system_definition.py`** — SR UI (자동 추측 버튼 + 후보 표시).
- **`requirements.txt`** — `gplearn` 의존성 추가.

**엔진(`engine.py`) · `run_simulation` · Phase 6 파일(`detection.py`) · 기타 모듈
일절 수정 금지.** Phase 7은 순수 추가 기능이다.

## 설계 원칙 — 순수 추가, 기존 경로 불변

- `symbolic_regression.py`는 신규 파일 — 신규 step2 코드 외 아무도 import하지 않는다.
- step2 변경은 `with col2:` 블록 끝에 UI를 **추가**할 뿐, 기존 매핑/공식 검증/ML
  로직을 변경하지 않는다.
- SR 버튼을 누르지 않으면 동작은 현행과 100% 동일. 엔진·시뮬레이션 경로는 무관.
- function_set는 `add/sub/mul/div`로 한정 → 산출 공식이 엔진 eval(순수 산술 infix)과
  호환된다. **로직 개선 금지 — 제공 코드 그대로.**

---

## 1. 신규 파일 — `modules/symbolic_regression.py`

아래 코드를 **그대로** 새 파일로 생성한다. 실행 로직은 클린룸 회귀 21/21 통과로
검증 완료(gplearn 비의존 로직 + prefix→infix 변환기) — **실행 코드 한 줄도 변경 금지.**

```python
"""
modules/symbolic_regression.py
Phase 7 — Damage Formula Symbolic Regression.

전투로그에 데미지(연속 숫자) 컬럼이 있으면, gplearn 기호 회귀로
damage ≈ f(스탯) 공식을 자동 추측한다.

순수 분석 모듈 — streamlit/엔진 의존 0. UI는 산출 공식을 '제안'으로만 쓴다.

설계:
- function_set는 add/sub/mul/div로 한정 → 산출 공식이 엔진 eval(순수 산술 infix)과 호환.
- gplearn 산출물(prefix 트리)을 infix 파이썬 식으로 변환, 변수명은 매핑 스탯 소문자명.
- gplearn protected div ≠ 엔진 plain '/' → 각 후보를 표본 행에 eval해 eval_safe 플래그.
- 유전 알고리즘이라 시드 고정 + 다중 시드로 Top-N 후보 제시.
"""

import numpy as np
import pandas as pd

from modules.detection import module_active

# ── 컬럼명 패턴 사전 ──
_DAMAGE_COL_HINTS = ("damage", "dmg", "피해", "데미지", "harm")
_SPATIAL_COL_HINTS = ("range", "reach", "사거리", "move", "movement", "이동",
                      "distance", "pos_x", "pos_y", "coord")

# 엔진 eval은 순수 산술 infix만 지원 → function_set를 4칙연산으로 한정
_BINOP = {"add": "+", "sub": "-", "mul": "*", "div": "/"}
_FUNCTION_SET = ("add", "sub", "mul", "div")


def gplearn_available():
    """gplearn 설치 여부. UI가 정확한 안내 메시지를 내기 위함."""
    try:
        import gplearn  # noqa: F401
        return True
    except Exception:
        return False


def detect_damage_column(df, stat_cols=None, target_col=None):
    """
    로그에서 데미지(연속 숫자) 컬럼을 탐지한다. 없으면 None.
    damage_type 같은 범주형/이진 컬럼은 제외한다.
    """
    for c in df.columns:
        if c == target_col:
            continue
        low = str(c).lower()
        if "type" in low:                       # damage_type 등 범주형 제외
            continue
        if any(h in low for h in _DAMAGE_COL_HINTS):
            try:
                if pd.api.types.is_numeric_dtype(df[c]) and \
                        int(df[c].dropna().nunique()) > 2:   # 연속값(이진 아님)
                    return c
            except Exception:
                continue
    return None


def select_feature_cols(stat_cols, damage_col, game_profile=None):
    """
    SR 후보 변수 = 매핑 스탯 − 데미지 컬럼.
    game_profile이 주어지고 공간 모듈이 비활성이면 공간 관련 컬럼을 제외한다.
    """
    feats = [c for c in (stat_cols or []) if c != damage_col]
    if game_profile is not None and not module_active(game_profile, "spatial"):
        feats = [c for c in feats
                 if not any(h in str(c).lower() for h in _SPATIAL_COL_HINTS)]
    return feats


def _program_to_infix(program, feature_names):
    """gplearn _Program(prefix 트리)을 infix 파이썬 식 문자열로 변환한다."""
    nodes = list(program.program)
    pos = [0]

    def walk():
        node = nodes[pos[0]]
        pos[0] += 1
        # 터미널: 정수 = 피처 인덱스
        if isinstance(node, (int, np.integer)) and not isinstance(node, bool):
            return str(feature_names[int(node)])
        # 터미널: 실수 = 상수
        if isinstance(node, (float, np.floating)):
            return repr(round(float(node), 6))
        # _Function 노드
        name = getattr(node, "name", None)
        arity = int(getattr(node, "arity", 0))
        args = [walk() for _ in range(arity)]
        if name in _BINOP and arity == 2:
            return "(" + args[0] + " " + _BINOP[name] + " " + args[1] + ")"
        return str(name) + "(" + ", ".join(args) + ")"

    return walk()


def _r2score(y_true, y_pred):
    """결정계수 R². 비정상 예측은 0으로 보정."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if not np.all(np.isfinite(y_pred)):
        y_pred = np.nan_to_num(y_pred, nan=0.0, posinf=0.0, neginf=0.0)
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot <= 0 or not np.isfinite(ss_res):
        return 0.0
    return 1.0 - ss_res / ss_tot


def _eval_safe(formula, work_df, lc_names, real_cols, sample=200):
    """
    formula를 엔진 방식 eval({"__builtins__": None})로 표본 행에 적용한다.
    전부 예외 없이 계산되면 True (0除算 등 위험 없음).
    """
    sub = work_df[real_cols].head(sample)
    try:
        for _, row in sub.iterrows():
            env = {lc: float(row[rc]) for lc, rc in zip(lc_names, real_cols)}
            eval(formula, {"__builtins__": None}, env)
        return True
    except Exception:
        return False


def infer_formula(df, damage_col, feature_cols, n_candidates=3,
                  population_size=1000, generations=15,
                  parsimony_coefficient=0.01, random_state=42):
    """
    gplearn 기호 회귀로 damage_col ≈ f(feature_cols)를 적합한다.

    반환: [{'formula': str, 'r2': float, 'complexity': int, 'eval_safe': bool}, ...]
          — r2 내림차순, 최대 n_candidates개. 전제 미충족 시 [].
    formula는 매핑 스탯 소문자명을 쓴 infix 파이썬 식 → 엔진 공식 입력창에 그대로 사용 가능.
    """
    try:
        from gplearn.genetic import SymbolicRegressor
    except Exception:
        return []

    feature_cols = list(feature_cols or [])
    if not feature_cols or damage_col is None:
        return []

    work = df[feature_cols + [damage_col]].apply(
        pd.to_numeric, errors="coerce").dropna()
    if len(work) < 20:
        return []

    X = work[feature_cols].astype(float).values
    y = work[damage_col].astype(float).values
    lc_names = [str(c).lower() for c in feature_cols]

    results = []
    seen = set()
    for k in range(max(1, int(n_candidates))):
        try:
            est = SymbolicRegressor(
                population_size=population_size,
                generations=generations,
                function_set=_FUNCTION_SET,
                metric="rmse",
                parsimony_coefficient=parsimony_coefficient,
                const_range=(-5.0, 5.0),
                random_state=random_state + k,
                n_jobs=1,
                verbose=0,
            )
            est.fit(X, y)
            prog = est._program
            formula = _program_to_infix(prog, lc_names)
            if formula in seen:
                continue
            seen.add(formula)
            pred = prog.execute(X)
            results.append({
                "formula": formula,
                "r2": round(_r2score(y, pred), 4),
                "complexity": int(getattr(prog, "length_", 0)),
                "eval_safe": _eval_safe(formula, work, lc_names, feature_cols),
            })
        except Exception:
            continue

    results.sort(key=lambda d: d["r2"], reverse=True)
    return results
```

`n_jobs=1`은 의도적이다 — Step 2 UI 스레드에서 단일 실행하며 멀티프로세싱/피클링
경로를 타지 않는다. **이 값을 바꾸지 말 것.**

---

## 2. `requirements.txt` — gplearn 추가

현재 `requirements.txt` 마지막 줄(`streamlit-sortables`) 다음에 한 줄 추가:
```
gplearn
```

---

## 3. `modules/step2_system_definition.py` 수정

### 3-1. import 추가

현재 13행 `from modules.detection import detect_modules` 다음 줄에:
```python
from modules.symbolic_regression import (
    detect_damage_column, select_feature_cols, infer_formula, gplearn_available,
)
```

### 3-2. SR UI 블록 추가 (`with col2:` 끝)

`render_system_definition()`의 `if not mapping_approved:` 분기 안, `with col2:` 블록
**맨 끝**에 추가한다. 구체적으로 — Live Formula Validator의 eval 검증 블록 마지막 줄
`st.warning("⚠️ 데미지 공식을 입력해주세요.")`(현재 235행, 16칸 들여쓰기) **다음**,
그리고 `# ═══...Tag Normalization` 주석(현재 237행, 8칸) **앞**에 삽입한다.
들여쓰기는 **12칸** (`with col2:` 본문 레벨):

```python
            # ── Phase 7: 데미지 공식 자동 추측 (Symbolic Regression) ──
            st.markdown("##### 🔮 데미지 공식 자동 추측 (Symbolic Regression)")

            def _sr_apply(_formula):
                # 위젯 키는 콜백에서만 안전하게 수정 가능 (on_chip_click과 동일 패턴)
                st.session_state['formula_input_ui'] = _formula
                st.session_state.pop('sr_candidates', None)

            _sr_dmg_col = detect_damage_column(df, base_stats, selected_target)
            if not gplearn_available():
                st.caption("⚠️ gplearn 미설치 — requirements.txt의 gplearn 설치 후 사용 가능합니다.")
            elif _sr_dmg_col is None:
                st.caption("로그에 데미지(연속 숫자) 컬럼이 없어 자동 추측 불가 — 공식을 직접 입력하세요.")
            else:
                st.caption(f"데미지 컬럼 `{_sr_dmg_col}` 감지 — 기호 회귀로 공식 후보를 추측합니다.")
                if st.button("🔮 공식 자동 추측 실행", use_container_width=True,
                             key="sr_run_btn"):
                    with st.spinner("gplearn 기호 회귀 연산 중... (수십 초 소요될 수 있음)"):
                        _sr_feats = select_feature_cols(
                            base_stats, _sr_dmg_col,
                            st.session_state.get('game_profile'))
                        st.session_state['sr_candidates'] = infer_formula(
                            df, _sr_dmg_col, _sr_feats)
                _sr_cands = st.session_state.get('sr_candidates')
                if _sr_cands:
                    st.caption("후보 (R² 내림차순) — '이 공식 사용' 시 위 입력창에 채워집니다:")
                    for _i, _cand in enumerate(_sr_cands):
                        _cc1, _cc2 = st.columns([4, 1])
                        with _cc1:
                            st.code(_cand['formula'], language="python")
                            _w = "" if _cand['eval_safe'] else " · ⚠️ 0除算 위험"
                            st.caption(f"R² {_cand['r2']:.3f} · 복잡도 {_cand['complexity']}{_w}")
                        with _cc2:
                            st.button("이 공식 사용", key=f"sr_use_{_i}",
                                      on_click=_sr_apply, args=(_cand['formula'],))
                elif _sr_cands == []:
                    st.info("공식 후보를 찾지 못했습니다 (데이터 부족 또는 적합 실패).")
```

설계 메모:
- 공식 적용은 `_sr_apply` **콜백**으로 한다 — `st.text_input(key="formula_input_ui")`가
  이미 렌더된 뒤 본문에서 그 키를 직접 대입하면 Streamlit이 예외를 던진다. 콜백은
  안전하다 (기존 `on_chip_click`과 동일 패턴).
- SR은 버튼 클릭 시에만 실행되고 결과는 `sr_candidates`에 저장된다.
  `detect_damage_column`만 매 렌더 호출되며 컬럼명 스캔이라 가볍다.
- 산출 공식은 매핑 스탯 소문자명을 쓰므로 `formula_input_ui` → eval 검증기 → 엔진
  `global_damage_formula`로 그대로 흐른다.

---

## 제약 / 주의

- 변경 파일 3개 한정. 엔진 · `detection.py` · 기타 모듈 수정 금지.
- **로직 개선 금지, 사양대로만.** `symbolic_regression.py`는 제공 코드 그대로 —
  실행 코드 한 줄도 변경 금지. function_set·n_jobs·패턴 사전 임의 변경 금지.
- `symbolic_regression.py`는 streamlit을 import하지 않는다.
- SR UI는 `with col2:` 블록 **안**(12칸 들여쓰기)에 들어가야 한다. 기존 eval 검증
  블록(`if formula_str_eval / else`)은 한 줄도 바꾸지 말 것 — 그 뒤에 추가만.

## 동작 동일성 — 회귀 검증

- `symbolic_regression.py`는 신규 파일 — 신규 step2 코드 외 아무도 import하지 않음.
- step2 변경은 import 1건 + `with col2:` 끝에 UI 추가뿐. 기존 매핑/공식검증/ML/
  파이프라인 로직 무변경.
- SR 버튼을 누르지 않으면 동작은 현행과 100% 동일. 엔진·시뮬레이션 경로는 무관 →
  `universal_test_log.csv` 단일 전투 NoVariance 1v1 lopsided **620.0** / near-even
  **1026.0** 불변. (test CSV엔 데미지 컬럼이 없어 SR 버튼 자체가 비활성.)

## 완료 기준 체크리스트

- [ ] `modules/symbolic_regression.py` 신규 생성 — 제공 코드의 실행 로직 그대로
- [ ] `symbolic_regression.py`: streamlit import 없음, `n_jobs=1` 유지
- [ ] `symbolic_regression.py`가 `detect_damage_column`/`select_feature_cols`/
      `infer_formula`/`gplearn_available` 노출
- [ ] `requirements.txt`에 `gplearn` 줄 추가
- [ ] step2: `from modules.symbolic_regression import ...` import 추가
- [ ] step2: `with col2:` 블록 끝에 SR UI 블록 추가 (12칸 들여쓰기)
- [ ] step2: 공식 적용은 `_sr_apply` 콜백(`on_click`)으로 — 본문 직접 대입 금지
- [ ] step2: 기존 Live Formula Validator / eval 검증 블록 0줄 변경
- [ ] 변경 파일 3개 외 수정 없음
- [ ] 회귀: SR 미사용 시 `universal_test_log.csv` 단일 전투 620.0 / 1026.0 불변
