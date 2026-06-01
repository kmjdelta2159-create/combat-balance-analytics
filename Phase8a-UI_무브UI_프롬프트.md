# Phase 8a-UI — 무브 시스템 UI 통합 (Step 2 추출·검수 + Step 6 연결)

## 목표

Phase 8a 엔진(이미 적용 완료 — `engine.py`의 `MOVE_SELECT`/`movepool`/`game_config`)을
**UI에 연결**한다. Step 2에서 전투로그의 무브 컬럼을 자동 추출해 사용자가 검수·수정하고,
카테고리별 공격/방어 스탯 라우팅을 지정한다. Step 6에서 그 무브풀을 시뮬레이션
인스턴스에 부착하고 `game_config`를 엔진에 전달한다.

이 변경도 **순수 가산적**이다 — 로그에 무브 컬럼이 없으면 무브 패널은 비활성으로
표시되고 기존 단일 공식 동작이 100% 유지된다.

## 대상 — 3개 파일

1. **신규 생성**: `modules/move_extraction.py` (아래 Part A 전체를 그대로)
2. **수정**: `modules/step2_system_definition.py` (Part B — 4개 변경)
3. **수정**: `modules/step6_dashboard.py` (Part C — 3개 변경)

`engine.py`는 **건드리지 마라** (Phase 8a 엔진에서 이미 완료됨).

## 데이터 흐름

Step 2 → `st.session_state['move_library']` (무브 dict 리스트) + `st.session_state['game_config']`
(`{"categories": {카테고리: {"offense": 스탯, "defense": 스탯}}}`) 저장 → Step 6의
`df_to_instances`가 각 인스턴스에 `movepool` 부착 + `run_simulation`/`run_monte_carlo`에
`game_config` 전달.

---

## Part A — 신규 파일 `modules/move_extraction.py`

아래 내용으로 **새 파일**을 생성하라. 클린룸 검증 완료된 코드다 (수정 금지, 그대로).

```python
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
    return {"power": power, "type": type_, "category": category, "name": name}


def has_move_data(df):
    """무브 추출 가능 여부 — 최소한 위력 컬럼이 탐지되면 True."""
    return detect_move_columns(df)["power"] is not None


def extract_moves(df, power_col, type_col=None, category_col=None, name_col=None):
    """distinct 무브 추출. 반환: [{'name','power','type','category','count'}, ...] (count 내림차순).

    name_col 미지정 시 type/category/power로 이름 합성 — 사용자가 검수 단계에서 수정한다.
    """
    if power_col is None or power_col not in df.columns:
        return []
    keys = [c for c in (name_col, type_col, category_col, power_col)
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
        moves.append({"name": name, "power": power, "type": mtype,
                      "category": category, "count": int(len(sub))})
    moves.sort(key=lambda m: -m["count"])
    return moves
```

---

## Part B — `modules/step2_system_definition.py` (4개 변경)

### 변경 B1 — `move_extraction` import 추가

**찾기:**
```python
from modules.symbolic_regression import (
    detect_damage_column, select_feature_cols, infer_formula, gplearn_available,
)
```
**바꾸기:**
```python
from modules.symbolic_regression import (
    detect_damage_column, select_feature_cols, infer_formula, gplearn_available,
)
from modules.move_extraction import detect_move_columns, extract_moves, has_move_data
```

### 변경 B2 — Live Formula Validator에 무브 변수 샘플값 주입

무브 공식(`move_power`/`offense`/`defense` 참조)을 검증창에서 테스트할 수 있게 한다.

**찾기:**
```python
            eval_env = {str(k).lower(): float(v) if pd.notnull(v) and isinstance(v, (int, float)) else v for k, v in eval_env_raw.items()}
```
**바꾸기:**
```python
            # ── Phase 8a: 무브 공식 검증용 샘플 변수 ──
            _mv_cols = detect_move_columns(df)
            if _mv_cols.get("power") and _mv_cols["power"] in df.columns:
                _pw = pd.to_numeric(df[_mv_cols["power"]], errors="coerce").dropna()
                eval_env_raw["move_power"] = float(_pw.mean()) if len(_pw) else 0.0
                _ss = base_stats[0] if base_stats else None
                _sv = float(row1.get(_ss, 1) or 1) if _ss else 1.0
                eval_env_raw["offense"] = _sv
                eval_env_raw["defense"] = _sv

            eval_env = {str(k).lower(): float(v) if pd.notnull(v) and isinstance(v, (int, float)) else v for k, v in eval_env_raw.items()}
```

### 변경 B3 — Move System 패널 추가 (Tag Normalization 섹션 바로 앞에 삽입)

**찾기:**
```python
        # ═══════════════════════════════════════════════════════════════════
        # Tag Normalization — 카테고리 태그 → 엔진 표준 태그 매핑 UI
        # ═══════════════════════════════════════════════════════════════════
```
**바꾸기:**
```python
        # ═══════════════════════════════════════════════════════════════════
        # Phase 8a — Move System (무브/어빌리티 자동 추출 + 검수)
        # ═══════════════════════════════════════════════════════════════════
        st.divider()
        st.markdown("## 🎯 Move System (무브/어빌리티)")
        move_library_edited = None
        move_categories_cfg = {}
        if has_move_data(df):
            st.info("💡 로그에서 무브 위력/타입/카테고리 컬럼을 감지했습니다. "
                    "추출된 무브를 표에서 검수·수정하세요.")
            _mv_detect = detect_move_columns(df)
            _opts = ["(없음)"] + list(df.columns)
            def _opt_idx(v):
                return _opts.index(v) if v in _opts else 0
            _mcc = st.columns(4)
            with _mcc[0]:
                _pcol = st.selectbox("위력 컬럼", _opts, index=_opt_idx(_mv_detect.get("power")), key="ui_move_power_col")
            with _mcc[1]:
                _tcol = st.selectbox("타입 컬럼", _opts, index=_opt_idx(_mv_detect.get("type")), key="ui_move_type_col")
            with _mcc[2]:
                _ccol = st.selectbox("카테고리 컬럼", _opts, index=_opt_idx(_mv_detect.get("category")), key="ui_move_cat_col")
            with _mcc[3]:
                _ncol = st.selectbox("이름 컬럼", _opts, index=_opt_idx(_mv_detect.get("name")), key="ui_move_name_col")
            _moves = extract_moves(
                df,
                _pcol if _pcol != "(없음)" else None,
                _tcol if _tcol != "(없음)" else None,
                _ccol if _ccol != "(없음)" else None,
                _ncol if _ncol != "(없음)" else None,
            )
            if _moves:
                st.caption(f"✅ {len(_moves)}개 무브 추출됨 — 표에서 직접 수정 가능:")
                move_library_edited = st.data_editor(
                    pd.DataFrame(_moves), use_container_width=True,
                    num_rows="dynamic", key="ui_move_library_editor")
                _cats = sorted({str(m.get("category", "")) for m in _moves
                                if str(m.get("category", "")).strip()})
                if _cats and base_stats:
                    st.markdown("#### 카테고리별 공격/방어 스탯 라우팅")
                    st.caption("각 무브 카테고리가 어떤 스탯으로 공격/방어 판정을 하는지 지정합니다.")
                    for _cat in _cats:
                        _rc = st.columns(2)
                        with _rc[0]:
                            _off = st.selectbox(f"`{_cat}` 공격 스탯", base_stats, key=f"ui_movecat_off_{_cat}")
                        with _rc[1]:
                            _def = st.selectbox(f"`{_cat}` 방어 스탯", base_stats, key=f"ui_movecat_def_{_cat}")
                        move_categories_cfg[_cat] = {"offense": _off, "defense": _def}
                elif not base_stats:
                    st.warning("⚠️ 카테고리 라우팅 설정 전에 Base Stats를 먼저 선택하세요.")
            else:
                st.caption("추출된 무브가 없습니다 — 무브 컬럼 선택을 확인하세요.")
        else:
            st.caption("로그에 무브 컬럼(위력/타입/카테고리)이 없습니다 — 무브 시스템 비활성. "
                       "단일 데미지 공식으로 동작합니다.")

        # ═══════════════════════════════════════════════════════════════════
        # Tag Normalization — 카테고리 태그 → 엔진 표준 태그 매핑 UI
        # ═══════════════════════════════════════════════════════════════════
```

### 변경 B4 — 파이프라인 시작 버튼: `move_library`·`game_config` 저장

**찾기:**
```python
                st.session_state['system_stats'] = base_stats
                st.session_state['system_gimmicks'] = gimmicks
```
**바꾸기:**
```python
                st.session_state['system_stats'] = base_stats
                st.session_state['system_gimmicks'] = gimmicks
                # ── Phase 8a: 무브 시스템 → game_config / move_library ──
                if move_library_edited is not None and len(move_library_edited) > 0:
                    st.session_state['move_library'] = move_library_edited.to_dict('records')
                    st.session_state['game_config'] = {"categories": move_categories_cfg}
                else:
                    st.session_state.pop('move_library', None)
                    st.session_state.pop('game_config', None)
```

---

## Part C — `modules/step6_dashboard.py` (3개 변경)

### 변경 C1 — `df_to_instances`: 인스턴스에 `movepool` 부착

**찾기:**
```python
                            inst['resources'][rname] = {"current": val, "max": val}
                            # 격자 좌표 부착 (공간 OFF면 char_positions가 비어 있어 미부착)
```
**바꾸기:**
```python
                            inst['resources'][rname] = {"current": val, "max": val}
                            # ── Phase 8a: 무브풀 부착 (글로벌 무브 라이브러리) ──
                            _move_lib = st.session_state.get('move_library')
                            if _move_lib:
                                inst['movepool'] = _move_lib
                            # 격자 좌표 부착 (공간 OFF면 char_positions가 비어 있어 미부착)
```

### 변경 C2 — 단일 전투 `run_simulation` 호출에 `game_config` 전달

**찾기:**
```python
                            winner, battle_logs, sim_metrics = run_simulation(
                                ally_instances, enemy_instances, max_turns=sim_max_turns,
                                combat_flow=combat_flow_val, speed_stat=speed_stat_val,
                                sys_stats=sys_stats_val, global_damage_formula=global_formula_val,
                                resource_module=ResourceModule(
                                    st.session_state.get('resource_config') or None,
                                    damage_type_map=st.session_state.get('damage_type_map') or None
                                ),
                                spatial_module=spatial_module_val,
                                range_stat=range_stat_val,
                                move_stat=move_stat_val,
                                deck_module=deck_module_val
                            )
```
**바꾸기:**
```python
                            winner, battle_logs, sim_metrics = run_simulation(
                                ally_instances, enemy_instances, max_turns=sim_max_turns,
                                combat_flow=combat_flow_val, speed_stat=speed_stat_val,
                                sys_stats=sys_stats_val, global_damage_formula=global_formula_val,
                                resource_module=ResourceModule(
                                    st.session_state.get('resource_config') or None,
                                    damage_type_map=st.session_state.get('damage_type_map') or None
                                ),
                                spatial_module=spatial_module_val,
                                range_stat=range_stat_val,
                                move_stat=move_stat_val,
                                deck_module=deck_module_val,
                                game_config=st.session_state.get('game_config')
                            )
```

### 변경 C3 — Monte Carlo `run_monte_carlo` 호출에 `game_config` 전달

**찾기:**
```python
                            mc_result = run_monte_carlo(
                                ally_instances, enemy_instances, combat_flow_val,
                                speed_stat_val, sys_stats_val, global_formula_val,
                                num_simulations=10000, max_turns=sim_max_turns,
                                progress_callback=progress_cb,
                                stochasticity_factory=default_stochasticity_factory,
                                resource_module=ResourceModule(
                                    st.session_state.get('resource_config') or None,
                                    damage_type_map=st.session_state.get('damage_type_map') or None
                                ),
                                spatial_module=spatial_module_val,
                                range_stat=range_stat_val,
                                move_stat=move_stat_val,
                                deck_module=deck_module_val
                            )
```
**바꾸기:**
```python
                            mc_result = run_monte_carlo(
                                ally_instances, enemy_instances, combat_flow_val,
                                speed_stat_val, sys_stats_val, global_formula_val,
                                num_simulations=10000, max_turns=sim_max_turns,
                                progress_callback=progress_cb,
                                stochasticity_factory=default_stochasticity_factory,
                                resource_module=ResourceModule(
                                    st.session_state.get('resource_config') or None,
                                    damage_type_map=st.session_state.get('damage_type_map') or None
                                ),
                                spatial_module=spatial_module_val,
                                range_stat=range_stat_val,
                                move_stat=move_stat_val,
                                deck_module=deck_module_val,
                                game_config=st.session_state.get('game_config')
                            )
```

---

## 검증 체크리스트 (적용 후 직접 확인하라)

- [ ] `modules/move_extraction.py` 가 새로 생성됐다 (Part A 그대로).
- [ ] `modules/step2_system_definition.py` 만, `modules/step6_dashboard.py` 만 수정됐다. `engine.py` 등 다른 파일은 그대로다.
- [ ] `python -m py_compile modules/move_extraction.py modules/step2_system_definition.py modules/step6_dashboard.py` 가 에러 없이 통과한다.
- [ ] step2 변경 4개(B1~B4), step6 변경 3개(C1~C3)가 **전부** 적용됐다.
- [ ] step2에 `## 🎯 Move System` 마크다운과 `st.data_editor(... key="ui_move_library_editor")` 가 존재한다.
- [ ] step6의 `run_simulation`·`run_monte_carlo` 호출 **양쪽 모두** `game_config=...` 인자를 가진다.

## 회귀 불변 조건

로그에 무브 컬럼이 없으면 — `has_move_data(df)` 가 False → `move_library`/`game_config` 가
session_state에 저장되지 않음 → `df_to_instances` 가 `movepool` 을 부착하지 않음 →
엔진은 단일 `global_damage_formula` 경로로 현행과 100% 동일하게 동작한다.
