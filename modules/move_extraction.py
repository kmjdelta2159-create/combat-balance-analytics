"""
move_extraction.py — 전투로그에서 무브/어빌리티 정의를 자동 추출 (Phase 8a).

순수 모듈: pandas만 의존. streamlit/엔진 비의존 (detection.py·symbolic_regression.py 동일 패턴).
attack-per-row 로그에 무브 위력/타입/카테고리 컬럼이 있으면 distinct 무브 집합을 추출해
사용자 검수용으로 제시한다. 무브 이름 컬럼이 없으면 type/category/power로 이름을 합성한다.
"""

_POWER_HINTS = ("move_power", "skill_power", "power", "위력")
_TYPE_HINTS = ("move_type", "skill_type", "movetype", "무브타입", "스킬타입", "속성")
_CATEGORY_HINTS = ("move_category", "move_class", "category", "카테고리", "분류")
_NAME_HINTS = ("move_name", "skill_name", "ability_name", "무브이름", "스킬이름")
_NAME_EXACT = ("move", "skill", "ability", "무브", "스킬")
_PRIORITY_HINTS = ("move_priority", "priority", "우선도", "우선순위")


def _find(cols, hints, exclude=()):
    for c in cols:
        if c in exclude:
            continue
        if any(h in str(c).lower() for h in hints):
            return c
    return None


def detect_move_columns(df):
    """무브 관련 컬럼을 추정. 반환: {'power','type','category','name'} — 각 값은 컬럼명 또는 None."""
    cols = list(df.columns)
    power = _find(cols, _POWER_HINTS)
    category = _find(cols, _CATEGORY_HINTS)
    name = _find(cols, _NAME_HINTS)
    if name is None:
        name = next((c for c in cols if str(c).lower() in _NAME_EXACT), None)
    type_ = _find(cols, _TYPE_HINTS, exclude={power, category, name})
    priority = _find(cols, _PRIORITY_HINTS, exclude={power, category, name, type_})
    return {"power": power, "type": type_, "category": category, "name": name, "priority": priority}


def has_move_data(df):
    """무브 추출 가능 여부 — 최소한 위력 컬럼이 탐지되면 True."""
    return detect_move_columns(df)["power"] is not None


def extract_moves(df, power_col, type_col=None, category_col=None, name_col=None, priority_col=None):
    """distinct 무브 추출. 반환: [{'name','power','type','category','count'}, ...] (count 내림차순).

    name_col 미지정 시 type/category/power로 이름 합성 — 사용자가 검수 단계에서 수정한다.
    """
    if power_col is None or power_col not in df.columns:
        return []
    keys = [c for c in (name_col, type_col, category_col, power_col, priority_col)
            if c and c in df.columns]
    moves = []
    for vals, sub in df.groupby(keys, dropna=False):
        if not isinstance(vals, tuple):
            vals = (vals,)
        rec = dict(zip(keys, vals))
        try:
            power = float(rec.get(power_col) or 0)
        except (TypeError, ValueError):
            power = 0.0
        mtype = str(rec.get(type_col)) if type_col and rec.get(type_col) is not None else ""
        category = str(rec.get(category_col)) if category_col and rec.get(category_col) is not None else ""
        raw_name = rec.get(name_col) if name_col else None
        if raw_name is not None and str(raw_name).strip():
            name = str(raw_name).strip()
        else:
            parts = [p for p in (mtype, category, (f"{power:g}" if power else "")) if p]
            name = "_".join(parts) if parts else "Move"
        try:
            prio = int(float(rec.get(priority_col))) if (priority_col and rec.get(priority_col) is not None) else 0
        except (TypeError, ValueError):
            prio = 0
        moves.append({"name": name, "power": power, "type": mtype,
                      "category": category, "priority": prio, "count": int(len(sub))})
    moves.sort(key=lambda m: -m["count"])
    return moves
