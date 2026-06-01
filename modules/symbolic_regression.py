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
