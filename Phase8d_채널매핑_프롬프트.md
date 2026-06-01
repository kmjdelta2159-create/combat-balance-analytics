# Phase 8d — 기믹 채널 명시 매핑 (엔진 이름 추측 → game_config 채널)

## 목표

엔진이 기믹 채널(`passive`·`trigger`·`target`·`formula`·`element`·`damage_type`)을
**컬럼명에 영어 키워드가 들어있는지로** 자동 탐지한다 (engine.py 다중 사이트). 사용자가
한국어 또는 다른 언어/명명규칙으로 컬럼을 만들면 엔진이 그 채널을 **조용히 누락**하고
사용자는 알아채지 못한다 — 패시브 안 발동, 공식 폴백, 속성 1.0 배율 등.

해결: `game_config["channels"]` dict에 명시 매핑을 받고, 엔진은 그것을 우선 사용,
없으면 기존 이름 추측 폴백. Step 2에 채널 매핑 UI 섹션 추가.

회귀 불변: `channels` 키가 없으면 100% 기존 동작.

## 대상 파일

1. **`modules/engine.py`** — 헬퍼 함수 추가 + 2개 사이트 수정
2. **`modules/step2_system_definition.py`** — Channel Mapping UI 섹션 추가 + game_config 조립 수정

---

## 변경 1 — `modules/engine.py`에 `_channel_col` 헬퍼 추가

`get_element_multiplier` 함수 직후에 신규 헬퍼를 삽입한다.

**찾기:**
```python
def get_element_multiplier(atk_elem, def_elem):
    if element_chart.get(atk_elem, {}).get("strong_against") == def_elem: return 1.5
    if element_chart.get(atk_elem, {}).get("weak_against") == def_elem: return 0.5
    return 1.0
```
**바꾸기:**
```python
def get_element_multiplier(atk_elem, def_elem):
    if element_chart.get(atk_elem, {}).get("strong_against") == def_elem: return 1.5
    if element_chart.get(atk_elem, {}).get("weak_against") == def_elem: return 0.5
    return 1.0


def _channel_col(gimmicks, channels, role, fallback_keywords):    """Phase 8d — 기믹 채널 명시 매핑 우선, 미설정 시 컬럼명 키워드 추측 폴백.

    channels: game_config['channels'] dict — {"passive": col_name, "trigger": ..., ...}.
    각 role의 값이 컬럼명을 가리키면 그걸 반환. 명시 None이면 None(채널 비활성).
    role이 channels에 없으면 fallback_keywords로 컬럼명 부분일치 검색(기존 동작).
    """
    if channels and role in channels:
        mapped = channels[role]
        if mapped is None:
            return None
        if mapped in gimmicks:
            return mapped
    if isinstance(fallback_keywords, (tuple, list)):
        return next((c for c in gimmicks
                     if any(k in str(c).lower() for k in fallback_keywords)), None)
    return next((c for c in gimmicks
                 if str(fallback_keywords) in str(c).lower()), None)
```

---

## 변경 2 — `_act_on_hit`의 t_passive_col 부분 교체

**찾기:**
```python
    t_gimmicks = t.get('gimmicks', {})
    t_passive_col = next((c for c in t_gimmicks if 'passive' in c.lower()), None)
    t_passive_logic = t_gimmicks.get(t_passive_col, "") if t_passive_col else ""
```
**바꾸기:**
```python
    t_gimmicks = t.get('gimmicks', {})
    _ch = ((ctx.get("game_config") or {}).get("channels") or {})
    t_passive_col = _channel_col(t_gimmicks, _ch, "passive", "passive")
    t_passive_logic = t_gimmicks.get(t_passive_col, "") if t_passive_col else ""
```

---

## 변경 3 — `build_ctx`의 채널 탐지 블록 통째 교체

`run_simulation` 함수 안의 `build_ctx` 클로저에서 6개 채널을 모두 명시 매핑 우선으로
바꾼다.

**찾기:**
```python
    def build_ctx(active_char, turn, participants_list):
        gimmicks = active_char.get('gimmicks', {})
        passive_col = next((c for c in gimmicks if 'passive' in c.lower()), None)
        passive_logic = gimmicks.get(passive_col, "") if passive_col else ""

        trigger_col = next((c for c in gimmicks if 'trigger' in c.lower()), None)
        trigger_val = gimmicks.get(trigger_col, "Active_Cast") if trigger_col else "Active_Cast"

        target_col_g = next((c for c in gimmicks if 'target' in c.lower()), None)
        target_val = gimmicks.get(target_col_g, "Single_Target") if target_col_g else "Single_Target"

        formula_col = next((c for c in gimmicks if 'formula' in c.lower()), None)
        local_formula = gimmicks.get(formula_col) if formula_col else None
        formula_str = (str(local_formula)
                       if local_formula and str(local_formula).strip()
                       and str(local_formula).strip() != "None"
                       else global_damage_formula)

        element_col = next((c for c in gimmicks if 'element' in c.lower()), None)
        atk_elem = gimmicks.get(element_col, "Neutral") if element_col else "Neutral"
        damage_type_col = next((c for c in gimmicks if 'damage_type' in c.lower() or 'dmg_type' in c.lower()), None)
        damage_type = gimmicks.get(damage_type_col) if damage_type_col else None
```
**바꾸기:**
```python
    def build_ctx(active_char, turn, participants_list):
        gimmicks = active_char.get('gimmicks', {})
        _ch = (game_config or {}).get("channels") or {}

        passive_col = _channel_col(gimmicks, _ch, "passive", "passive")
        passive_logic = gimmicks.get(passive_col, "") if passive_col else ""

        trigger_col = _channel_col(gimmicks, _ch, "trigger", "trigger")
        trigger_val = gimmicks.get(trigger_col, "Active_Cast") if trigger_col else "Active_Cast"

        target_col_g = _channel_col(gimmicks, _ch, "target", "target")
        target_val = gimmicks.get(target_col_g, "Single_Target") if target_col_g else "Single_Target"

        formula_col = _channel_col(gimmicks, _ch, "formula", "formula")
        local_formula = gimmicks.get(formula_col) if formula_col else None
        formula_str = (str(local_formula)
                       if local_formula and str(local_formula).strip()
                       and str(local_formula).strip() != "None"
                       else global_damage_formula)

        element_col = _channel_col(gimmicks, _ch, "element", "element")
        atk_elem = gimmicks.get(element_col, "Neutral") if element_col else "Neutral"
        damage_type_col = _channel_col(gimmicks, _ch, "damage_type",
                                       ("damage_type", "dmg_type"))
        damage_type = gimmicks.get(damage_type_col) if damage_type_col else None
```

---

## 변경 4 — `modules/step2_system_definition.py`에 Channel Mapping UI 섹션 추가

`c_btn, c_json = st.columns(2)` 직전, divider 사이에 새 expander를 삽입한다.

**찾기:**
```python
        st.divider()

        c_btn, c_json = st.columns(2)
```
**바꾸기:**
```python
        st.divider()

        # ── Phase 8d: 기믹 채널 명시 매핑 ──
        with st.expander("🧩 기믹 채널 매핑 (Channel Mapping) — 권장", expanded=False):
            st.caption(
                "엔진이 어떤 기믹 컬럼을 어느 역할로 읽을지 명시합니다. "
                "기본 '(자동 감지)'는 영어 키워드(passive·trigger·target 등) 부분일치로 폴백합니다 — "
                "한국어/다국어 같은 비-영어 명명을 쓰는 게임은 명시 매핑이 필수입니다 "
                "(그렇지 않으면 엔진이 해당 채널을 조용히 누락)."
            )
            _channel_roles = [
                ("passive",     "🔁 패시브 로직"),
                ("trigger",     "⏱ 발동 트리거"),
                ("target",      "🎯 타겟 규칙"),
                ("formula",     "🧮 데미지 공식"),
                ("element",     "🌀 속성 타입"),
                ("damage_type", "💥 데미지 타입"),
            ]
            _ch_cols = st.columns(3)
            _channel_choices = {}
            for _i, (_role, _label) in enumerate(_channel_roles):
                with _ch_cols[_i % 3]:
                    _options = ["(자동 감지)", "(없음)"] + list(gimmicks)
                    _key = f"ui_channel_{_role}"
                    _channel_choices[_role] = st.selectbox(
                        _label, _options, index=0, key=_key,
                        help=f"이 기믹 컬럼을 {_label} 채널로 사용. "
                             "'(자동 감지)'는 컬럼명에 영어 키워드가 있을 때만 작동, "
                             "'(없음)'은 이 채널을 명시적으로 비활성."
                    )

        st.divider()

        c_btn, c_json = st.columns(2)
```

---

## 변경 5 — `step2`의 game_config 조립 수정

기존 무브 시스템 전용 game_config 조립을 채널 매핑까지 포함하도록 확장한다. 채널만 있고
무브가 없는 경우, 무브만 있는 경우, 둘 다 있는 경우 모두 정상 작동하도록.

**찾기:**
```python
                # ── Phase 8a/8b: 무브 시스템 → game_config / move_library ──
                if move_library_edited is not None and len(move_library_edited) > 0:
                    st.session_state['move_library'] = move_library_edited.to_dict('records')
                    _gc = {"categories": move_categories_cfg}
                    if move_type_table_edited is not None and move_type_columns:
                        _gc["type_table"] = {
                            str(_atk): {str(_d): float(move_type_table_edited.loc[_atk, _d])
                                        for _d in move_type_table_edited.columns}
                            for _atk in move_type_table_edited.index}
                        _gc["type_columns"] = list(move_type_columns)
                        _gc["stab_factor"] = float(move_stab_factor)
                    st.session_state['game_config'] = _gc
                else:
                    st.session_state.pop('move_library', None)
                    st.session_state.pop('game_config', None)
```
**바꾸기:**
```python
                # ── Phase 8a/8b/8d: 무브 시스템 + 채널 매핑 → game_config / move_library ──
                _gc = {}
                # Phase 8d — 채널 매핑 수집
                _ch = {}
                for _role, _ in _channel_roles:
                    _val = _channel_choices.get(_role, "(자동 감지)")
                    if _val == "(없음)":
                        _ch[_role] = None
                    elif _val and _val != "(자동 감지)":
                        _ch[_role] = _val
                if _ch:
                    _gc["channels"] = _ch
                # Phase 8a/8b — 무브 시스템
                if move_library_edited is not None and len(move_library_edited) > 0:
                    st.session_state['move_library'] = move_library_edited.to_dict('records')
                    _gc["categories"] = move_categories_cfg
                    if move_type_table_edited is not None and move_type_columns:
                        _gc["type_table"] = {
                            str(_atk): {str(_d): float(move_type_table_edited.loc[_atk, _d])
                                        for _d in move_type_table_edited.columns}
                            for _atk in move_type_table_edited.index}
                        _gc["type_columns"] = list(move_type_columns)
                        _gc["stab_factor"] = float(move_stab_factor)
                else:
                    st.session_state.pop('move_library', None)
                if _gc:
                    st.session_state['game_config'] = _gc
                else:
                    st.session_state.pop('game_config', None)
```

---

## 검증 체크리스트 (적용 후 직접 확인하라)

- [ ] `python -m py_compile modules/engine.py modules/step2_system_definition.py` 통과.
- [ ] `engine.py`에 `def _channel_col(gimmicks, channels, role, fallback_keywords):` 신규 함수 존재.
- [ ] `_act_on_hit`이 `_channel_col(t_gimmicks, _ch, "passive", "passive")`를 호출한다.
- [ ] `build_ctx`가 6개 채널 모두 `_channel_col(...)` 호출로 바뀌었다.
- [ ] `step2_system_definition.py`에 `🧩 기믹 채널 매핑` expander가 `c_btn` 컬럼 직전에 존재.
- [ ] `_channel_choices` dict가 6개 키(passive/trigger/target/formula/element/damage_type)를 가진다.
- [ ] `game_config` 조립이 `_ch` 수집을 먼저 하고 `_gc["channels"]`로 합친다.
- [ ] **기존 코드 외 곁가지 수정 0건.** Phase 9b 영역, Phase 8c-α backtest 섹션, optimizer.py 모두 불변.

## 회귀 불변 조건

`game_config["channels"]`가 비어 있거나 미설정이면 `_channel_col`은 `fallback_keywords`로
폴백 → 기존 `next((c for c in gimmicks if 'X' in c.lower()))` 동작과 100% 동일. 따라서:
- Phase 8d 미사용 프로젝트는 기존 그대로 동작.
- 사용자가 Step 2 UI에서 모든 채널을 `(자동 감지)`로 두면 `_ch` dict가 비어 game_config에
  `channels` 키가 안 들어가 → 회귀 불변.
- 사용자가 일부 채널만 명시 매핑하면 그것만 명시 사용, 나머지는 폴백.
