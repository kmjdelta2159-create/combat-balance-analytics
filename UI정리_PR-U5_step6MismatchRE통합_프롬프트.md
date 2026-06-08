# UI정리 PR-U5 — Step6 Mismatch Report + Mechanism RE 통합

## 목적

1차목표 종료판정에서 남은 조건은 엔진 기능 자체가 아니라 **사용자 개입 루프의 surface 연결**이다.

현재 Step 6 전투별 백테스트는 다음 score들을 이미 계산한다.

- `state_score`
- `action_damage_score`
- `action_resource_delta_score`

그리고 메커니즘 RE 도구는 별도 surface로 존재한다.

- `modules/step_mechanism_re.py::render_mechanism_re`
- `modules/mechanism_detect.py`
- `modules/mechanism_commit.py`

이번 PR은 둘을 한 흐름으로 묶는다.

**DB-log 백테스트 mismatch → 사람이 확인 가능한 Mismatch Report → Mechanism RE / EFFECTS 후보 생성 surface**

즉, 새 전투 규칙을 억지로 자동 구현하는 작업이 아니라, 최종 목표의 핵심인 “검증 결과를 보고 전문가가 개입해 복제본을 닫는 루프”를 Step 6에 연결하는 작업이다.

## 현재 확인된 상태

`modules/step6_dashboard.py` 현재 구조:

- `_bb_state_scores = []`
- `_bb_action_damage_scores = []`
- `_bb_action_resource_delta_scores = []`
- worker 결과에서 각 metrics score를 수집
- 각 score 종류별 aggregate metric 표시
- action damage/resource delta는 첫 mismatch를 `_d_first`, `_rd_first`로 표시

문제:

1. 상태 스냅샷 score 표시부에 실제 버그가 있다.

```python
if _first:
    st.caption(...)
```

현재 검색 결과상 `_first`는 정의되지 않는다.

2. mismatch가 caption 한 줄로만 표시되어서 사용자가 검수하기 어렵다.

3. mismatch display와 `render_mechanism_re()` surface가 Step 6 안에서 연결되어 있지 않다.

## 수정 대상

가능하면 아래 파일만 수정한다.

- `modules/step6_dashboard.py`

필요하면 테스트 파일 1개를 추가해도 된다.

- `test_step6_mismatch_report.py`

다음 파일은 수정하지 마라.

- `modules/engine.py`
- `modules/per_battle_backtest.py`
- `modules/mechanism_detect.py`
- `modules/mechanism_commit.py`
- `modules/step_mechanism_re.py`

`step_mechanism_re.py`는 이미 있는 surface를 import해서 호출만 한다.

## 구현 지시

### 1. `_first` 미정의 버그 수정

`state_score` 표시부에서 `_first` 대신 state score list에서 첫 `first_mismatch`를 찾아 쓰라.

예:

```python
_s_first = next((s.get("first_mismatch") for s in _bb_state_scores if s.get("first_mismatch")), None)
if _s_first:
    ...
```

이름은 달라도 되지만, undefined variable이 남으면 안 된다.

### 2. Mismatch Report row 생성

전투별 백테스트 결과 루프에서 score별 mismatch row를 수집하라.

권장 방식:

```python
_bb_mismatch_rows = []
...
_bb_idx = len(_bb_predictions) + 1
...
if _metrics.get("state_score"):
    _bb_state_scores.append(_metrics["state_score"])
    # first_mismatch가 있으면 report row 추가
```

각 row에는 가능한 한 다음 필드를 담아라.

```text
battle_index
score_type                  # state / action_damage / action_resource_delta / engine_error
turn
id
kind
resource
expected
actual
checks
mismatches
accuracy
expected_full
actual_full
```

주의:

- `first_mismatch`만 있어도 충분하다. 이번 PR에서 모든 mismatch event를 엔진에서 새로 수집할 필요는 없다.
- `expected_full` / `actual_full`은 dict/list일 수 있으므로 dataframe 표시 전에 `repr()` 또는 `json.dumps(..., ensure_ascii=False, default=str)`처럼 안전하게 문자열화하라.
- worker가 문자열 error를 반환하는 경우도 `score_type="engine_error"` row로 남기면 좋다.

### 3. Step 6에 Mismatch Report 표 표시

백테스트 완료 후 score metric들 아래 또는 바로 다음에 `Mismatch Report` 섹션을 추가하라.

요구:

- `_bb_mismatch_rows`가 있으면 `pd.DataFrame(_bb_mismatch_rows)`로 `st.dataframe(...)` 표시.
- CSV 다운로드 버튼을 제공.
- `st.session_state["bb_last_mismatch_report"]`에 dataframe 또는 row list를 저장.
- mismatch가 없으면 “현재 score mismatch 없음”에 해당하는 성공/정보 메시지를 표시해도 된다.

표는 사용자가 **어느 battle / 어느 turn / 어느 actor / 어떤 종류의 mismatch인지** 바로 볼 수 있어야 한다.

### 4. Mechanism RE surface를 Step 6 백테스트 흐름 아래에 붙이기

Mismatch Report 바로 아래에 기존 surface를 expander로 호출하라.

권장:

```python
with st.expander("메커니즘 RE / EFFECTS 후보 생성", expanded=bool(_bb_mismatch_rows)):
    try:
        from modules.step_mechanism_re import render_mechanism_re
        render_mechanism_re()
    except Exception as e:
        st.warning(f"Mechanism RE surface 로드 실패: {e}")
```

조건:

- 메커니즘 RE 로드 실패가 Step 6 전체를 죽이면 안 된다.
- 기존 `render_mechanism_re()`의 동작과 key를 바꾸지 마라.
- Step 6에 새 surface가 생겨도 기존 백테스트 실행/MC 실행/optimizer 실행 흐름은 깨지면 안 된다.

### 5. UI 문구의 의미

문구는 다음 의미를 유지하라.

- Mismatch Report는 “엔진이 틀렸다”가 아니라 “복제본과 관측 로그가 갈라진 첫 지점”이다.
- Mechanism RE는 자동 완성 마법이 아니라 전문가가 EFFECTS 후보를 확정하는 surface다.
- DB-log 기반 검증 루프와 Showdown trace 기반 RE surface가 현재 1차 포켓몬 실증에서 나란히 쓰이는 구조임을 암시하되, 장황한 설명은 피하라.

## 테스트 / 검증

최소 실행:

```bash
python -X utf8 -m py_compile modules/step6_dashboard.py modules/step_mechanism_re.py
python -X utf8 test_i15_integration_smoke.py
python -X utf8 test_mechanism_detect_aliases.py
python -X utf8 test_mechanism_commit_canonical.py
```

가능하면 새 helper를 테스트하는 `test_step6_mismatch_report.py`를 추가하라.

테스트 포인트:

- state/action_damage/action_resource_delta score dict에서 `first_mismatch` row가 생성된다.
- `expected_full` / `actual_full` 같은 dict 필드가 dataframe-safe 문자열로 변환된다.
- mismatch가 없는 score는 row를 만들지 않는다.
- `_first` 미정의 NameError가 더 이상 발생하지 않는다.

## 금지

- 엔진 score 의미 변경 금지.
- worker metrics schema 변경 금지.
- `mechanism_detect` / `mechanism_commit` 로직 변경 금지.
- 포켓몬 전용 하드코딩 금지.
- Step 6 전체 레이아웃 대개편 금지.

## 완료 조건

- `modules/step6_dashboard.py`에 `_first` undefined 문제가 남아 있지 않다.
- 백테스트 완료 후 mismatch를 표로 볼 수 있다.
- mismatch report를 CSV로 받을 수 있다.
- 같은 영역에서 Mechanism RE surface를 열 수 있다.
- 기존 I15 및 mechanism detect/commit 테스트가 통과한다.
