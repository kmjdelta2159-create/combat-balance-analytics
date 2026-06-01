# Pokemon 복제 1/4 · Live Formula Validator 후속 보강

## 문제

직전 PR(Pokemon복제1-4_무브공급_프롬프트.md)이 Move System 섹션(L289~L370)에
attack_log_df 진입 경로를 추가해 무브 풀 37개 추출이 작동한다. 그러나 동일 파일
L228~L236의 **Live Formula Validator**는 여전히 메인 `df`만 보고 무브 변수를
주입한다. 사용자가 attack_log를 업로드해도 라이브 검증기에는 `move_power`/
`offense`/`defense` 변수가 환경에 들어오지 않아 `move_power * attack / defense`
같은 공식 입력 시 에러가 발생한다.

L504의 적용 버튼은 `disabled=not is_valid` 가드(L148/L245)로 막혀 있어 라이브
검증 통과 없이는 step3~5 진행이 불가능하다. 즉 본 보강 없이는 시연 흐름 자체가
끊긴다.

## 해결

L228~L236의 무브 변수 주입 분기에서 attack_log_df도 보게 한다. `has_move_data`로
메인 df → attack_log_df 우선순위 결정 후 `_df_for_validate`로 통합한다. 1/4 PR의
`df_for_moves` 결정 로직과 정확히 같은 패턴.

## 변경 사이트 — 단 1곳

- **Change A**: L228~L236 — 무브 변수 주입 분기 보강

`has_move_data`, `detect_move_columns`는 이미 L17에서 import됨. `pandas as pd`도
이미 있음. 추가 import 0건. 새 session_state key 0건(attack_log_df는 1/4 PR이
이미 도입).

L205~L216의 변수 칩 목록은 본 PR 범위 외. 사용자가 공식을 타이핑으로 입력하면
변수 칩 없이도 라이브 검증 통과 가능. 칩 UX 보강은 별도 결정 영역.

## 라인 수 산술

- Change A: 9줄 → 18줄 (+9)
- **총 변경: +9줄**

---

## Change A — L228~L236 (Live Formula Validator 무브 변수 주입 보강)

### Find (9줄, 정확 일치)

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
```

### Replace (18줄)

```python
            # ── Phase 8a: 무브 공식 검증용 샘플 변수 (attack_log 보조 진입) ──
            _atk_log_df = st.session_state.get("attack_log_df")
            if has_move_data(df):
                _df_for_validate = df
            elif _atk_log_df is not None and has_move_data(_atk_log_df):
                _df_for_validate = _atk_log_df
            else:
                _df_for_validate = None
            if _df_for_validate is not None:
                _mv_cols = detect_move_columns(_df_for_validate)
                _pwr_col = _mv_cols.get("power")
                if _pwr_col and _pwr_col in _df_for_validate.columns:
                    _pw = pd.to_numeric(_df_for_validate[_pwr_col], errors="coerce").dropna()
                    eval_env_raw["move_power"] = float(_pw.mean()) if len(_pw) else 0.0
                    _ss = base_stats[0] if base_stats else None
                    _sv = float(row1.get(_ss, 1) or 1) if _ss else 1.0
                    eval_env_raw["offense"] = _sv
                    eval_env_raw["defense"] = _sv
```

---

## 검증 단서 (납품 후 사용자가 확인)

1. **라인 수 산술**: 변경 후 `step2_system_definition.py` 라인 수 = 변경 전 + 9
   (직전 1/4 PR 적용 후 729줄 + 9 = 738줄)
2. **마커 grep 양성** (있어야 함):
   - `_atk_log_df = st.session_state.get("attack_log_df")`
   - `_df_for_validate = df` (메인 우선 분기)
   - `_df_for_validate = _atk_log_df`
   - `_df_for_validate = None`
   - `if _df_for_validate is not None:`
   - `_pwr_col = _mv_cols.get("power")`
3. **마커 grep 음성** (옛 코드가 분기 가드 자리에 남으면 안 됨):
   - Live Formula Validator 분기 안의 `if _mv_cols.get("power") and _mv_cols["power"] in df.columns:` → 0건. (Move System 섹션의 다른 분기에는 등장 안 함)
4. **동작 테스트** — 라이브 검증:
   - Streamlit 재시작 (Ctrl+C → `streamlit run main.py`) — 모듈 캐시 reload 필수
   - Step 1에서 `pkmn_battle_log.csv` 업로드
   - Step 2에서 Move System 섹션의 `📎 Attack Log 업로드` expander 열고 `pkmn_attack_log.csv` 업로드
   - 화면 위로 스크롤해서 Live Formula Validator 영역으로 복귀
   - 전투 데미지 공식에 `move_power * attack / defense` 입력
   - "✅ 연산 성공! 예상 데미지: ..." 노출 (NoneType 에러 사라짐)
   - 페이지 하단 "🚀 기획 의도 확립 및 파이프라인 시작" 버튼이 활성화됨

## 제약

- **곁가지 수정 0건**: 본 프롬프트의 Change A 외 라인은 절대 건드리지 않는다.
- **들여쓰기**: Change A는 12 스페이스. 탭 사용 금지.
- **import 추가 금지**: `has_move_data`/`detect_move_columns`/`pd` 모두 이미 임포트되어 있다.
- **session_state 키 신규 0**: `attack_log_df`는 1/4 PR이 이미 도입했고 본 PR은 그 키를 read-only로 사용.
- **변수 칩(L205~L216) 미수정**: 본 PR 범위 외.
