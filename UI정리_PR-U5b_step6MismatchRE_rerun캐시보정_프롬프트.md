# UI정리 PR-U5b — Step6 Mismatch/RE rerun 캐시 보정

## 목적

PR-U5 적용 결과 핵심 기능은 들어갔다.

- `_first` 미정의 버그가 `_s_first`로 수정됨.
- `_bb_mismatch_rows` 수집이 추가됨.
- Mismatch Report dataframe/CSV 다운로드가 추가됨.
- `render_mechanism_re()` expander가 Step 6 백테스트 결과 아래에 연결됨.
- `test_step6_mismatch_report.py`, I15, mechanism detect/commit 테스트 통과.

하지만 실제 Streamlit 사용 흐름 기준으로 남은 결함이 있다.

현재 Mismatch Report와 Mechanism RE surface가 모두 `if st.button("🔬 백테스트 실행", ...)` 블록 **안에서만 렌더링**된다.

문제:

- 백테스트 직후 한 번은 화면에 보인다.
- 하지만 사용자가 Mechanism RE expander 안의 file uploader에 HTML을 업로드하면 Streamlit rerun이 발생한다.
- rerun 시 button 값은 `False`가 되므로, `render_mechanism_re()` 호출 블록 자체가 사라진다.
- 즉 surface가 “붙은 것처럼 보이지만 실제 상호작용 루프에서는 끊긴다.”

이번 PR은 이 rerun 문제를 고친다.

## 수정 대상

가능하면 아래 파일만 수정한다.

- `modules/step6_dashboard.py`
- `test_step6_mismatch_report.py`

수정 금지:

- `modules/engine.py`
- `modules/per_battle_backtest.py`
- `modules/mechanism_detect.py`
- `modules/mechanism_commit.py`
- `modules/step_mechanism_re.py`

## 현재 코드 위치 참고

`modules/step6_dashboard.py` 기준:

```text
1413: if st.button("🔬 백테스트 실행", ...)
...
1692:     st.divider()
1693:     st.markdown("### 📋 Mismatch Report")
...
1708:     with st.expander("메커니즘 RE / EFFECTS 후보 생성", expanded=bool(_bb_mismatch_rows)):
1710:         from modules.step_mechanism_re import render_mechanism_re
1711:         render_mechanism_re()
1715: with tab2:
```

라인 번호는 달라질 수 있지만, 핵심은 `Mismatch Report`와 `render_mechanism_re()`가 button block 안에 있다는 점이다.

## 구현 지시

### 1. Mismatch rows 생성 helper를 분리

현재 `_bb_mismatch_rows.append({...})` 로직이 state/action_damage/action_resource_delta에 중복되어 있다.

가능하면 top-level helper를 추가하라.

예:

```python
def _safe_report_cell(value):
    ...

def _mismatch_row_from_score(battle_index, score_type, score):
    ...

def _extend_mismatch_rows_from_metrics(rows, battle_index, metrics):
    ...
```

요구:

- `first_mismatch`가 없으면 row를 만들지 않는다.
- `expected_full` / `actual_full`은 dataframe/CSV safe 문자열이어야 한다.
- `expected_full`은 `_fm.get("expected_full", _fm.get("expected"))`를 우선 사용하라.
- `actual_full`은 `_fm.get("actual_full", _fm.get("actual"))`를 우선 사용하라.
- `accuracy`는 가능하면 score dict의 `accuracy` 값을 사용하고, 없을 때만 계산한다.
- 기존 metrics schema는 바꾸지 않는다.

### 2. 백테스트 실행 결과를 session_state에 캐시

button block 내부에서 백테스트가 끝나면 다음 정보를 저장하라.

권장 key:

```python
st.session_state["bb_last_backtest_has_run"] = True
st.session_state["bb_last_mismatch_rows"] = list(_bb_mismatch_rows)
```

가능하면 score summary도 저장하면 좋다.

```python
st.session_state["bb_last_backtest_summary"] = {
    "total": _bb_sc["total"],
    "correct": _bb_sc["correct"],
    "accuracy_pct": _bb_acc_pct,
    "elapsed": _bb_elapsed,
    "errors": _bb_errors,
}
```

주의:

- mismatch가 0건이어도 `bb_last_backtest_has_run=True`와 `bb_last_mismatch_rows=[]`를 유지하라.
- mismatch가 없다고 `pop("bb_last_mismatch_report")` 식으로 surface 상태를 지우지 마라.

### 3. Mismatch Report + Mechanism RE 렌더링을 button block 밖으로 이동

button block 안에서는 실행/계산/캐시 저장까지만 하라.

그 아래, 같은 backtest expander/tab 영역 안에서 다음처럼 렌더하라.

```python
if st.session_state.get("bb_last_backtest_has_run"):
    _cached_rows = st.session_state.get("bb_last_mismatch_rows", [])
    # Mismatch Report 표시
    # Mechanism RE expander 표시
```

조건:

- 이 렌더 블록은 `if st.button(...)`의 indentation보다 밖에 있어야 한다.
- 그러나 Step 6의 전투별 백테스트 UI 영역 안에는 남아 있어야 한다.
- 사용자가 file uploader, download button, expander, checkbox 등을 조작해 rerun이 발생해도 Mismatch Report와 Mechanism RE expander가 계속 보이게 하라.
- `render_mechanism_re()` 실패는 `st.warning(...)`으로만 처리하고 Step 6 전체를 죽이지 마라.

### 4. 기존 즉시 렌더링 유지

button을 누른 바로 그 run에서도 결과가 보이게 해야 한다.

가장 단순한 방법:

- button block 끝에서 session_state에 저장한다.
- button block 바깥의 공통 렌더 블록이 같은 run에서 session_state를 읽어 표시한다.

### 5. `bb_last_mismatch_report` key 정리

PR-U5에서 추가한 `bb_last_mismatch_report`가 있다면 다음 중 하나로 통일하라.

- 기존 key를 계속 쓰되, `bb_last_backtest_has_run`과 함께 유지
- 또는 `bb_last_mismatch_rows`로 이름을 바꾸고 모든 참조를 맞춤

중요:

- mismatch 0건이어도 캐시가 유지되어야 한다.
- 다운로드용 dataframe은 캐시된 rows에서 매번 만들면 된다.

## 테스트 보강

`test_step6_mismatch_report.py`를 보강하라.

최소:

1. helper가 state/action_damage/action_resource_delta first_mismatch를 row로 만든다.
2. helper가 mismatch 없는 score는 row를 만들지 않는다.
3. dict/list 값이 `expected_full` / `actual_full`에서 문자열화된다.
4. source check:
   - `render_mechanism_re()` 호출이 `if st.button("🔬 백테스트 실행"` 블록 안에만 갇혀 있지 않은지 확인한다.
   - 단순 source test여도 된다. 예: button line indent보다 render line indent가 더 작거나 같은 렌더 호출이 하나 이상 존재.
5. source check:
   - `bb_last_backtest_has_run` 또는 동등한 session_state cache flag가 존재한다.

## 실행 검증

다음은 반드시 통과해야 한다.

```bash
python -X utf8 -m py_compile modules/step6_dashboard.py modules/step_mechanism_re.py test_step6_mismatch_report.py
python -X utf8 test_step6_mismatch_report.py
python -X utf8 test_i15_integration_smoke.py
python -X utf8 test_mechanism_detect_aliases.py
python -X utf8 test_mechanism_commit_canonical.py
```

## 금지

- 엔진/worker/score schema 의미 변경 금지.
- `render_mechanism_re()` 내부 key 변경 금지.
- Step 6 대형 레이아웃 재작성 금지.
- 포켓몬 전용 분기 금지.

## 완료 조건

- 백테스트 실행 직후 Mismatch Report가 보인다.
- Streamlit rerun 이후에도 마지막 Mismatch Report와 Mechanism RE expander가 유지된다.
- Mechanism RE file uploader를 사용할 수 있는 구조가 된다.
- mismatch 0건이어도 “최근 백테스트 결과 있음” 상태가 유지된다.
- 기존 테스트와 새 mismatch report 테스트가 통과한다.
