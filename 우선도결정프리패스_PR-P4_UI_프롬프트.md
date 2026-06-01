# PR-P4 (우선도 입력 UI) Antigravity 프롬프트

## 목적
`modules/step2_system_definition.py`에 우선도 관련 **사용자 개입 입력**을 추가한다 —
① 무브 우선도(priority) 컬럼 **명시 매핑** 셀렉트박스, ② 교체 행동 우선도 티어(switch_priority)
입력. 이로써 PR-P3a·P3b로 엔진에 들어간 우선도 정렬을 사용자가 직접 켜고 조정할 수 있다.
**회귀 0**: 우선도 컬럼 기본값은 기존 자동 탐지값과 동일, switch_priority 기본은 엔진 기본
6이라 미저장 → 현행 동작 그대로.

## 제약
- `modules/step2_system_definition.py` **한 파일만** 수정. 엔진·turn_manager·move_extraction 손대지 말 것.
- 아래 find/replace **3건만** 적용. 곁가지 수정·키 이름 변경 금지.
- Streamlit 위젯 `key`는 신규 고유값(`ui_move_priority_col`, `ui_switch_priority`) 그대로 사용.

## 적용 1 — 무브 컬럼 매핑에 우선도 컬럼 셀렉트박스 추가 (`st.columns(4)`→`5`)

다음 블록을 **정확히** 찾아서:

```python
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
                df_for_moves,
                _pcol if _pcol != "(없음)" else None,
                _tcol if _tcol != "(없음)" else None,
                _ccol if _ccol != "(없음)" else None,
                _ncol if _ncol != "(없음)" else None,
                _mv_detect.get("priority"),
            )
```

다음으로 **교체**:

```python
            _mcc = st.columns(5)
            with _mcc[0]:
                _pcol = st.selectbox("위력 컬럼", _opts, index=_opt_idx(_mv_detect.get("power")), key="ui_move_power_col")
            with _mcc[1]:
                _tcol = st.selectbox("타입 컬럼", _opts, index=_opt_idx(_mv_detect.get("type")), key="ui_move_type_col")
            with _mcc[2]:
                _ccol = st.selectbox("카테고리 컬럼", _opts, index=_opt_idx(_mv_detect.get("category")), key="ui_move_cat_col")
            with _mcc[3]:
                _ncol = st.selectbox("이름 컬럼", _opts, index=_opt_idx(_mv_detect.get("name")), key="ui_move_name_col")
            with _mcc[4]:
                _prcol = st.selectbox("우선도 컬럼", _opts, index=_opt_idx(_mv_detect.get("priority")), key="ui_move_priority_col")
            _moves = extract_moves(
                df_for_moves,
                _pcol if _pcol != "(없음)" else None,
                _tcol if _tcol != "(없음)" else None,
                _ccol if _ccol != "(없음)" else None,
                _ncol if _ncol != "(없음)" else None,
                _prcol if _prcol != "(없음)" else None,
            )
```

## 적용 2 — 교체 모델 UI에 switch_priority 입력 추가

다음 블록을 **정확히** 찾아서:

```python
            _switch_thr = st.number_input(
                "HP 임계 비율 (hp_threshold일 때 적용)",
                min_value=0.0, max_value=1.0, value=0.25, step=0.05,
                format="%.2f", key="ui_switch_threshold"
            )
```

다음으로 **교체**:

```python
            _switch_thr = st.number_input(
                "HP 임계 비율 (hp_threshold일 때 적용)",
                min_value=0.0, max_value=1.0, value=0.25, step=0.05,
                format="%.2f", key="ui_switch_threshold"
            )
            # ── 행동 순서: 교체 우선도 티어 (교체가 공격보다 먼저 해결; 무브 우선도와 결합) ──
            _switch_prio_in = st.number_input(
                "교체 행동 우선도 티어 (switch_priority — 높을수록 공격보다 먼저; 기본 6)",
                min_value=0, value=6, step=1, key="ui_switch_priority"
            )
            st.caption("ℹ️ 무브 우선도 컬럼을 매핑하면 느린 유닛도 우선도 무브로 먼저 행동합니다. "
                       "교체 우선도 티어는 교체를 무브보다 앞에 둡니다.")
```

## 적용 3 — 시작 버튼 핸들러에 switch_priority → game_config 저장

다음 블록을 **정확히** 찾아서:

```python
                if _switch_policy_sel.startswith("HP 임계"):
                    _gc["switch_policy"] = {"type": "hp_threshold",
                                            "threshold": float(_switch_thr)}
```

다음으로 **교체**:

```python
                if _switch_policy_sel.startswith("HP 임계"):
                    _gc["switch_policy"] = {"type": "hp_threshold",
                                            "threshold": float(_switch_thr)}
                # ── 교체 행동 우선도 티어 → game_config (엔진 기본 6과 다를 때만 저장 → 회귀 0) ──
                if _switch_prio_in is not None and int(_switch_prio_in) != 6:
                    _gc["switch_priority"] = int(_switch_prio_in)
```

## 적용 후 자가 점검 (보고만, 코드 변경 금지)
1. `st.columns(5)` 1회, `ui_move_priority_col` 1회, `ui_switch_priority` 1회 존재.
2. `extract_moves(...)` 의 우선도 인자가 `_prcol if _prcol != "(없음)" else None` 로 바뀜
   (기존 `_mv_detect.get("priority")` 제거).
3. 저장 핸들러에 `_gc["switch_priority"] = int(_switch_prio_in)` 가 `!= 6` 가드 아래 존재.
4. `modules/step2_system_definition.py` 구문 오류 없이 compile 됨.
5. 엔진·turn_manager·move_extraction **변경 없음**.

## 회귀 0 근거
- 우선도 컬럼 셀렉트박스 기본 인덱스 = `_opt_idx(_mv_detect.get("priority"))` → 자동 탐지값.
  미탐지 시 `(없음)` → `extract_moves`에 None 전달(현행과 동일). 보조자 하니스로 확인.
- switch_priority 기본 6 = 엔진 기본. `!= 6`일 때만 `_gc`에 저장 → 기본 사용 시 game_config
  불변 → 현행 동작. 보조자 하니스로 게이트 로직 확인.

## 라이브 확인 권장
priority/우선도 컬럼이 있는 무브 데이터로 step2에서 "우선도 컬럼"을 매핑하고, **느린 유닛이
높은 priority 무브**를 갖도록 구성한 전투를 단일 실행하면, 그 유닛이 빠른 유닛보다 먼저
행동하는 로그로 우선도 프리패스의 end-to-end 발화가 실증된다.
