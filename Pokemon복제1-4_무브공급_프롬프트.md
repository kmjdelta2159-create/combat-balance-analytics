# Pokemon 복제 1/4 · 2단계 — 무브 데이터 공급 인프라 (attack_log 진입)

## 목표

`modules/step2_system_definition.py`의 Move System 섹션(L289~L370)에 attack_log 업로드
진입 경로를 추가한다. 메인 로그(battle_log)가 entity-per-row 형식이라 무브 컬럼이 없는
게임(Pokemon 등)에서, 사용자가 attack-per-row 형식의 보조 로그를 별도로 업로드하면
거기서 무브 풀을 추출할 수 있게 한다.

기믹 채널 매핑·타입 상성표·STAB 분기 안의 `df[c]` 참조는 **메인 df 그대로** 유지한다
(entity 컬럼은 메인 로그가 진실의 출처).

## 변경 사이트 — 단 2곳

- **Change A**: L294~L299 변수 초기화 직후 → Sec A 신규 + Sec B 가드 치환 (`if has_move_data(df):` → `if df_for_moves is not None:`)
- **Change B**: L302~L321 분기 본문 → `df` 3곳을 `df_for_moves`로 치환

곁가지 수정 0건. L322 이후 (`_moves`, `_cats`, 타입 상성표, STAB 등)는 건드리지 않는다.
L351의 `df[c]` 기믹 추출도 건드리지 않는다.

## 라인 수 산술

- Change A: 기존 6줄 → 신규 27줄 (+21)
- Change B: 기존 20줄 → 신규 20줄 (+0)
- **총 변경: +21줄**

## 새 import — 없음

`from modules.move_extraction import detect_move_columns, extract_moves, has_move_data`는
이미 L17에 있다. `pandas as pd`도 이미 L2. 추가 import 0건.

## 새 session_state key

- `attack_log_df` (선택) — 업로드된 attack-per-row DataFrame을 영속화

기존 `move_library`, `mapping_approved` 등과 같은 패턴.

---

## Change A — L294~L299 (Sec A 신규 + Sec B 가드 치환)

### Find (6줄, 정확 일치)

```python
        move_library_edited = None
        move_categories_cfg = {}
        move_type_table_edited = None
        move_type_columns = []
        move_stab_factor = 1.0
        if has_move_data(df):
```

### Replace (27줄)

```python
        move_library_edited = None
        move_categories_cfg = {}
        move_type_table_edited = None
        move_type_columns = []
        move_stab_factor = 1.0

        # ── attack_log 진입 경로 — 메인 df에 무브 컬럼이 없을 때 보강 ──
        attack_log_df = st.session_state.get("attack_log_df")
        with st.expander("📎 Attack Log 업로드 (선택) — 메인 로그에 무브 컬럼이 없을 때", expanded=False):
            _uploaded_attack = st.file_uploader(
                "attack-per-row CSV", type=["csv"], key="ui_attack_log_upload")
            if _uploaded_attack is not None:
                attack_log_df = pd.read_csv(_uploaded_attack)
                st.session_state["attack_log_df"] = attack_log_df
                st.caption(f"✅ {len(attack_log_df)}행 로드됨")
            elif attack_log_df is not None:
                st.caption(f"📦 세션에 저장된 attack_log ({len(attack_log_df)}행) 사용 중")

        # ── 무브 추출 데이터 출처 결정 ──
        if has_move_data(df):
            df_for_moves = df
        elif attack_log_df is not None and has_move_data(attack_log_df):
            df_for_moves = attack_log_df
            st.info("📎 메인 로그에 무브 컬럼이 없어 attack_log에서 추출합니다.")
        else:
            df_for_moves = None
        if df_for_moves is not None:
```

---

## Change B — L302~L321 (df → df_for_moves 3곳)

### Find (20줄, 정확 일치)

```python
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
```

### Replace (20줄 — `df` 3곳만 `df_for_moves`로 치환, 그 외 0 변경)

```python
            _mv_detect = detect_move_columns(df_for_moves)
            _opts = ["(없음)"] + list(df_for_moves.columns)
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
                df_for_moves,
                _pcol if _pcol != "(없음)" else None,
                _tcol if _tcol != "(없음)" else None,
                _ccol if _ccol != "(없음)" else None,
                _ncol if _ncol != "(없음)" else None,
            )
```

---

## 검증 단서 (납품 후 사용자가 확인)

1. **라인 수 산술**: 변경 후 `step2_system_definition.py` 라인 수 = 변경 전 + 21
2. **마커 grep 양성** (있어야 함):
   - `attack_log_df = st.session_state.get`
   - `key="ui_attack_log_upload"`
   - `df_for_moves = df` (메인 우선 분기)
   - `elif attack_log_df is not None and has_move_data`
   - `if df_for_moves is not None:`
3. **마커 grep 음성** (옛 코드가 남으면 안 됨):
   - `if has_move_data(df):` 가 분기 가드 자리에 남아 있으면 안 됨 (Change A가 가드를 `if df_for_moves is not None:`로 치환). Change A의 새 코드 안쪽에는 `if has_move_data(df):` 라인 1개가 정상적으로 존재한다(우선순위 로직). 즉 grep 결과는 1건이어야 한다.
   - `detect_move_columns(df)` (괄호 안이 `df` 단독) → 0건이어야 함
   - `list(df.columns)` → 0건이어야 함 (Move System 분기 안 한정)
4. **동작 테스트**:
   - `python -m py_compile modules/step2_system_definition.py` 통과
   - Streamlit 재시작 (`Ctrl+C` → `streamlit run main.py`) — 모듈 캐시 때문에 reload 필수
   - Step 1에서 `검증_포켓몬/pkmn_battle_log.csv` 업로드
   - Step 2 진입 후 Move System 섹션 끝까지 스크롤 → 새 expander "📎 Attack Log 업로드 (선택)" 보임
   - expander 열고 `검증_포켓몬/pkmn_attack_log.csv` 업로드
   - "📎 메인 로그에 무브 컬럼이 없어 attack_log에서 추출합니다" 안내 노출
   - 무브 37개 추출 + 카테고리(Physical/Special) 라우팅 + 18 타입 상성표 UI 모두 활성

## 제약

- **곁가지 수정 0건**: 본 프롬프트의 Change A/B 외 라인은 절대 건드리지 않는다.
- **들여쓰기**: Change A는 8 스페이스, Change B는 12 스페이스. 탭 사용 금지.
- **import 추가 금지**: 모든 의존성은 이미 임포트되어 있다.
- **다른 게임 영향 0**: FF7는 `Move_Element`를 type으로 인식 못 하지만 그건 별도 PR이고 본 PR은 손대지 않는다.
- **session_state 키 충돌 금지**: `attack_log_df`, `ui_attack_log_upload`는 코드베이스에 부재(`grep -r "attack_log_df" modules/`으로 확인 후 작업).
