"""
modules/detection.py
Phase 6 — Auto Game-Type Detection.

Step 2 스키마 매핑 직후, 매핑된 컬럼을 분석해 활성 모듈(자원/공간/확률/덱)을 제안한다.
순수 분석 모듈 — streamlit 의존 0. UI는 이 모듈의 출력을 '제안'으로만 사용한다.

설계 원칙:
- 탐지는 '제안'이다. 구조적 강신호(confidence='high')일 때만 detected=True.
- 약신호(컬럼명 패턴 매칭)는 detected를 켜지 않고 hints로만 보고한다.
- 덱/확률은 평면 전투로그에서 신뢰 탐지가 불가능 → detected 항상 False, hints만.
- detect_modules는 정상 입력에서 예외를 던지지 않는다(개별 연산 방어). 단, df 자체가
  비정상이면 예외가 호출부로 전파되어 호출부가 폴백(전체 표시)을 택한다.
"""

import pandas as pd

# ── 모듈 키 ──
MODULE_KEYS = ("resource", "spatial", "stochasticity", "deck")
# Step 6에 게이팅 대상 UI가 존재하는 모듈
GATED_MODULES = ("resource", "spatial", "deck")

# ── 컬럼명 패턴 사전 (소문자 부분 일치) ──
_DAMAGE_TYPE_HINTS = ("damage_type", "dmg_type", "dmgtype", "damagetype",
                      "element_type", "elem_type")
_RESOURCE_NAME_HINTS = ("mana", "shield", "stamina", "barrier", "energy", "rage")
_STOCH_HINTS = ("crit", "critical", "hit_chance", "hit_rate",
                "accuracy", "evasion", "dodge")
_DECK_HINTS = ("card", "deck", "hand_size", "mana_cost")


def _empty():
    return {"detected": False, "confidence": "none", "evidence": [], "hints": []}


def _find_coord_pair(columns):
    """좌표 컬럼 쌍 [x_col, y_col]을 찾는다. 못 찾으면 []."""
    low = {c: str(c).lower() for c in columns}
    x_cands = [c for c in columns
               if low[c] == "x" or low[c].endswith("_x")
               or "pos_x" in low[c] or "coord_x" in low[c] or "tile_x" in low[c]]
    y_cands = [c for c in columns
               if low[c] == "y" or low[c].endswith("_y")
               or "pos_y" in low[c] or "coord_y" in low[c] or "tile_y" in low[c]]
    if not x_cands or not y_cands:
        return []

    def _prefix(name, axis):
        for suf in ("_" + axis, axis):
            if name.endswith(suf):
                return name[: -len(suf)]
        return name

    for xc in x_cands:
        for yc in y_cands:
            if _prefix(low[xc], "x") == _prefix(low[yc], "y"):
                return [xc, yc]
    return [x_cands[0], y_cands[0]]


def detect_modules(df, stat_cols=None, gimmick_cols=None, target_col=None):
    """
    매핑된 컬럼을 분석해 활성 모듈을 제안한다.

    df          : Step 2 매핑 후 pandas DataFrame
    stat_cols   : 숫자형 스탯 컬럼 리스트 (system_stats) — 현재 분석엔 미사용, 확장용
    gimmick_cols: 카테고리/기믹 컬럼 리스트 (system_gimmicks) — 현재 분석엔 미사용
    target_col  : 타겟 변수 컬럼명 — 분석 대상에서 제외

    반환: { module_key: {'detected': bool, 'confidence': str,
                          'evidence': [근거 컬럼...], 'hints': [관련 가능 컬럼...]} }
    """
    result = {m: _empty() for m in MODULE_KEYS}

    all_cols = [c for c in list(df.columns) if c != target_col]
    low = {c: str(c).lower() for c in all_cols}

    # ── 공간 ── 좌표 컬럼 쌍(숫자형) = 구조적 강신호
    pair = _find_coord_pair(all_cols)
    if pair:
        numeric_ok = True
        for c in pair:
            try:
                if not pd.api.types.is_numeric_dtype(df[c]):
                    numeric_ok = False
            except Exception:
                numeric_ok = False
        if numeric_ok:
            result["spatial"] = {"detected": True, "confidence": "high",
                                 "evidence": list(pair), "hints": []}
        else:
            result["spatial"]["hints"] = list(pair)

    # ── 자원 ── damage_type 컬럼(저카디널리티 범주형) = 구조적 강신호
    dt_hit = None
    for c in all_cols:
        if any(h in low[c] for h in _DAMAGE_TYPE_HINTS):
            try:
                nuniq = int(df[c].dropna().nunique())
            except Exception:
                nuniq = 0
            if 2 <= nuniq <= 12:
                dt_hit = c
                break
    res_hints = [c for c in all_cols
                 if any(h in low[c] for h in _RESOURCE_NAME_HINTS)]
    if dt_hit:
        result["resource"] = {"detected": True, "confidence": "high",
                              "evidence": [dt_hit], "hints": res_hints}
    else:
        result["resource"]["hints"] = res_hints

    # ── 확률 ── 구조적 신호 없음 → 이름 약신호를 hints로만 (detected=False 고정)
    result["stochasticity"]["hints"] = [
        c for c in all_cols if any(h in low[c] for h in _STOCH_HINTS)]

    # ── 덱 ── 평면 로그에서 신뢰 탐지 불가 → detected=False 고정, hints만
    result["deck"]["hints"] = [
        c for c in all_cols if any(h in low[c] for h in _DECK_HINTS)]

    return result


def module_active(game_profile, module_key):
    """
    게임 프로파일 기준 모듈 활성 여부.
    game_profile이 None/불완전이면 True를 돌려준다 — 탐지 실패 시 전체 표시(현행 동작) 폴백.
    """
    if not game_profile or not isinstance(game_profile, dict):
        return True
    overrides = game_profile.get("overrides") or {}
    ov = overrides.get(module_key, "auto")
    if ov == "on":
        return True
    if ov == "off":
        return False
    detection = game_profile.get("detection") or {}
    entry = detection.get(module_key) or {}
    return bool(entry.get("detected", False))
