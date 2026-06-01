# Phase 8b-UI — 타입 상성표 UI + STAB (Step 2)

## 목표

Phase 8b 엔진(이미 적용 — `engine.py`의 `type_table`/`type_columns`/`stab_factor` 소비)을
**UI에 연결**한다. Step 2의 Move System 패널에 타입 상성표 편집 그리드 + STAB 배율 입력 +
타입 컬럼 지정을 추가하고, 그 값들을 `game_config`에 채워 넣는다.

타입 상성표는 게임의 핵심 데이터이며 로그에서 자동 도출이 불가능하다(전투로그 역설계
검증에서 확인됨 — 범주형 배율은 회귀로 복원 안 됨). 따라서 도구는 감지된 타입들로
**N×N 그리드를 1.0(무영향)으로 초기화**해 제시하고, 전문가가 효과적/반감/무효 배율을
직접 입력한다.

## 대상 파일

**`modules/step2_system_definition.py` 단 하나.** `step6`는 8a-UI에서 이미 `game_config`를
엔진에 전달하므로 수정 불필요. `engine.py`도 건드리지 마라.

## 데이터 계약

8a-UI가 만든 `st.session_state['game_config']`(`categories`)에 3개 키를 추가한다:

```python
game_config = {
    "categories":   {...},                          # 8a-UI (기존)
    "type_table":   {atk_type: {def_type: float}},   # 8b-UI — N×N 상성표
    "type_columns": [gimmick_col, ...],              # 8b-UI — 캐릭터 타입 기믹 컬럼
    "stab_factor":  float,                           # 8b-UI — STAB 배율
}
```

---

## 변경 사항 — 3개를 빠짐없이 적용하라. 들여쓰기를 정확히 지켜라.

### 변경 1 — Move System 패널 상단에 8b 변수 초기화 추가

**찾기:**
```python
        move_library_edited = None
        move_categories_cfg = {}
```
**바꾸기:**
```python
        move_library_edited = None
        move_categories_cfg = {}
        move_type_table_edited = None
        move_type_columns = []
        move_stab_factor = 1.0
```

### 변경 2 — Move System 패널에 타입 상성표 그리드 + STAB 추가

무브 카테고리 라우팅 블록과 "추출된 무브가 없습니다" 분기 **사이**에 타입 상성표
섹션을 삽입한다. 삽입되는 블록은 `if _moves:` 내부이므로 **16칸 들여쓰기**다.

**찾기:**
```python
                elif not base_stats:
                    st.warning("⚠️ 카테고리 라우팅 설정 전에 Base Stats를 먼저 선택하세요.")
            else:
                st.caption("추출된 무브가 없습니다 — 무브 컬럼 선택을 확인하세요.")
```
**바꾸기:**
```python
                elif not base_stats:
                    st.warning("⚠️ 카테고리 라우팅 설정 전에 Base Stats를 먼저 선택하세요.")

                # ── Phase 8b: 타입 상성표 + STAB ──
                st.markdown("#### 🔯 타입 상성표 (Type Effectiveness)")
                _type_col_default = [g for g in gimmicks
                                     if 'type' in g.lower() or '타입' in g or '속성' in g]
                move_type_columns = st.multiselect(
                    "캐릭터 타입이 든 기믹 컬럼 (방어 상성·STAB 판정에 사용)",
                    gimmicks, default=_type_col_default, key="ui_move_type_columns")
                _move_types = {str(m.get("type", "")) for m in _moves
                               if str(m.get("type", "")).strip()}
                _gimmick_types = {str(v) for c in move_type_columns
                                  for v in df[c].dropna().astype(str).unique()}
                _type_roster = sorted(_move_types | _gimmick_types)
                if _type_roster:
                    st.caption(f"{len(_type_roster)}개 타입 — 공격(행) × 방어(열) 배율표. "
                               f"기본 1.0(무영향) · 효과적 2.0 · 반감 0.5 · 무효 0.0. "
                               f"게임의 상성표는 전문가가 직접 입력합니다.")
                    _tt_init = pd.DataFrame(1.0, index=_type_roster, columns=_type_roster)
                    move_type_table_edited = st.data_editor(
                        _tt_init, use_container_width=True, key="ui_type_table_editor")
                    move_stab_factor = st.number_input(
                        "STAB 배율 (무브 타입 == 공격자 타입 시 추가 배율, 1.0 = STAB 없음)",
                        min_value=1.0, max_value=3.0, value=1.0, step=0.1, key="ui_stab_factor")
                else:
                    st.caption("타입 정보가 없어 상성표를 만들 수 없습니다.")
            else:
                st.caption("추출된 무브가 없습니다 — 무브 컬럼 선택을 확인하세요.")
```

> ⚠️ 들여쓰기 주의: 새 블록 본문은 **16칸**(`if _moves:` 내부). 그 안의
> `if _type_roster:` 본문은 20칸, `else:`(if _type_roster의 else)는 16칸.
> 마지막 `else:`(if _moves의 else)는 **12칸**, 그 `st.caption`은 16칸 — 원본 그대로 유지.
> 이 문맥 구조는 py_compile로 사전 검증됨.

### 변경 3 — 파이프라인 시작 버튼: `game_config`에 8b 키 채우기

**찾기:**
```python
                # ── Phase 8a: 무브 시스템 → game_config / move_library ──
                if move_library_edited is not None and len(move_library_edited) > 0:
                    st.session_state['move_library'] = move_library_edited.to_dict('records')
                    st.session_state['game_config'] = {"categories": move_categories_cfg}
                else:
                    st.session_state.pop('move_library', None)
                    st.session_state.pop('game_config', None)
```
**바꾸기:**
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

---

## 검증 체크리스트 (적용 후 직접 확인하라)

- [ ] `modules/step2_system_definition.py` **단 하나만** 수정됐다.
- [ ] `python -m py_compile modules/step2_system_definition.py` 가 통과한다.
- [ ] Move System 패널에 `#### 🔯 타입 상성표` 와 `st.data_editor(... key="ui_type_table_editor")` 가 존재한다.
- [ ] `st.number_input(... key="ui_stab_factor")` 가 존재한다.
- [ ] 파이프라인 시작 시 `_gc["type_table"]`·`_gc["type_columns"]`·`_gc["stab_factor"]` 가 채워진다.
- [ ] 변경 3개가 **전부** 적용됐다. 변경 2의 `else:` 분기 2개가 각각 16칸/12칸으로 정확히 존재한다.

## 회귀 불변 조건

타입 컬럼을 지정하지 않거나 상성표를 전부 1.0으로 두면 — `game_config`에 `type_table`이
없거나(엔진이 레거시 `element_chart` 경로) 모든 배율이 1.0이라 — Phase 8a 동작과 동일하다.
로그에 무브 컬럼이 없으면 Move System 패널 자체가 비활성 → 그 이전 동작과 100% 동일.
