# DB코퍼스 PR-UI4c globalContrastReadability 프롬프트

## 역할

너는 이 저장소의 UI/UX 구현을 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수와 프롬프트 작성만 담당한다. 아래 요구사항에 따라 Streamlit 전역 테마/컴포넌트 가시성 문제를 수정하고, 실제 화면 검수 증거를 남겨라.

## 사용자 제보

사용자가 실제 Streamlit 화면에서 다음 문제를 추가 제보했다.

- Step과 관계없이 텍스트 색이 배경과 맞지 않아 가시성이 떨어지는 요소가 있다.
- 예시: Dashboard의 Ally 총합 체급 값 `2167.00`, Enemy 총합 체급 값 `1903.70`, 예측 승률 `95.1%`, Monte Carlo `대기 중` 같은 큰 숫자/상태 텍스트가 어두운 배경 위에서 너무 흐리게 보인다.
- 기존 Step2 입력창/셀렉트/버튼의 흰 배경-흰 글자 문제도 같은 계열의 전역 대비 문제로 취급해야 한다.

이번 PR은 특정 Step 하나가 아니라 **Step1~Step5 전체의 텍스트/배경 대비와 컴포넌트 readable state를 통일하는 작업**이다.

## 목표

전역 UI에서 hover 없이 읽을 수 없는 텍스트를 제거한다. 특히 metric 숫자, caption, disabled text, selectbox/multiselect/input 내부 텍스트, uploader 내부 텍스트, table/chart label, sidebar 상태 텍스트가 모두 배경 대비 충분히 읽히도록 한다.

## 우선순위

### P0. 전역 텍스트 대비 토큰 정리

현재 `main.py`의 전역 CSS는 일부 텍스트만 직접 색을 지정하고 있어 Streamlit 내부 컴포넌트와 충돌한다. 단순히 모든 `span`을 흰색으로 덮어쓰는 방식은 흰 배경 컴포넌트에서 다시 문제가 생긴다.

필수 수정:

- `main.py` 전역 CSS에 semantic color token을 정의하라.
  - app background
  - panel/card background
  - input background
  - table/chart light surface background
  - primary text
  - secondary text
  - muted text
  - disabled text
  - positive/negative/accent text
- 배경이 어두운 영역의 primary metric/text는 명확한 밝은 색으로 표시하라.
- 배경이 밝은 영역의 table/chart/input 내부 텍스트는 명확한 어두운 색으로 표시하라.
- 전역 `span`, `p`, `label` 전체를 무차별로 같은 색으로 덮어쓰는 방식은 피하고, 컴포넌트별 selector로 적용하라.

수용 기준:

- 어두운 배경 위 큰 숫자(metric)가 회색으로 묻히지 않는다.
- 밝은 입력창/테이블 위 텍스트가 흰색으로 묻히지 않는다.
- hover해야만 보이는 텍스트가 없다.

### P0. Dashboard metric/readability 보정

사용자 스크린샷 기준 Dashboard에서 다음 요소가 흐리게 보인다.

- Ally 총합 체급 값 `2167.00`
- Enemy 총합 체급 값 `1903.70`
- 예측 승률 `95.1%`
- Monte Carlo 상태 `대기 중`
- sidebar의 caption/status 일부
- expander header 및 toggle label

필수 수정:

- `st.metric` 또는 custom metric 영역의 value 색을 어두운 배경 대비 충분히 밝게 하라.
- metric label과 delta는 primary/secondary/positive/negative 색을 명확히 분리하라.
- inactive/waiting 상태 텍스트는 너무 어둡게 두지 말고 muted text라도 읽을 수 있게 하라.
- Dashboard의 Plotly/차트 영역은 둘 중 하나로 통일하라.
  - 밝은 차트 패널을 유지하면 axis/label/bar label은 어두운 색, 패널 경계는 명확하게.
  - 어두운 차트 패널로 바꾸면 axis/label/grid/bar contrast를 dark theme에 맞게.
- 테이블은 밝은 표면이면 셀 텍스트를 어두운 색으로 유지하고, 바깥 dark UI와 경계를 명확히 하라.

수용 기준:

- 사용자 스크린샷과 같은 Dashboard 상태에서 `2167.00`, `1903.70`, `95.1%`, `대기 중`이 한눈에 읽힌다.
- chart axis label과 category label이 배경과 충돌하지 않는다.
- sidebar status/caption이 흐리게 사라지지 않는다.

### P0. Streamlit 입력 컴포넌트 대비 보정

Step2만이 아니라 전체 Step에서 다음 컴포넌트의 normal/hover/focus/disabled 상태를 점검하고 보정하라.

- `st.text_input`
- `st.text_area`
- `st.number_input`
- `st.selectbox`
- `st.multiselect`
- multiselect tag/pill
- `st.file_uploader`
- `st.button`
- disabled button/input
- `st.tabs`
- `st.expander`
- `st.checkbox`, `st.toggle`, `st.radio`
- `st.dataframe`

필수 selector 계열:

- `input`
- `textarea`
- `[data-baseweb="input"]`
- `[data-baseweb="textarea"]`
- `[data-baseweb="select"]`
- `[data-baseweb="tag"]`
- `[data-testid="stTextInput"]`
- `[data-testid="stTextArea"]`
- `[data-testid="stNumberInput"]`
- `[data-testid="stSelectbox"]`
- `[data-testid="stMultiSelect"]`
- `[data-testid="stFileUploader"]`
- `[data-testid="stButton"]`
- `[data-testid="stMetric"]`
- `[data-testid="stExpander"]`
- `[data-testid="stSidebar"]`

수용 기준:

- Step1 uploader 내부 파일명/도움말/버튼이 hover 없이 읽힌다.
- Step2 formula 후보, 버튼, selectbox, number input, mechanism attach 영역이 hover 없이 읽힌다.
- Step5/Dashboard의 metric, chart, table, sidebar가 hover 없이 읽힌다.
- disabled 상태도 최소한 상태를 인지할 수 있을 만큼 읽힌다.

### P1. 인코딩 깨짐/문구 깨짐 확인

현재 일부 파일/출력에서 한글이 깨져 보이는 흔적이 있다. UI에 실제로 깨진 텍스트가 노출되는지 확인하라.

필수 수정:

- 화면에 깨진 한글이 노출되면 해당 문구를 정상 한국어 또는 명확한 영어로 고쳐라.
- 코드 파일 인코딩은 UTF-8로 유지하라.
- 불필요한 대량 문구 리라이트는 하지 말고, 실제 화면에 보이는 깨진 텍스트만 고쳐라.

수용 기준:

- 주요 화면 Step1~Step5에서 깨진 문자열이 보이지 않는다.

## 검수 요구사항

실제 Streamlit 앱을 실행하고 브라우저 화면으로 검수하라. HTTP 200만으로 검수를 끝내지 마라.

권장 실행:

```powershell
streamlit run main.py
```

필수 viewport:

- desktop: 1366x768 이상
- narrow/mobile: 390x844 또는 430x932

필수 화면:

- Step1 일반 업로드
- Step1 DB 코퍼스 업로드
- Step2 필수 매핑 상단
- Step2 공식 검증/후보 공식 영역
- Step2 선택 규칙 또는 Mechanism Attach 하단 영역
- Step3 Discrepancy
- Step5 Dashboard, 특히 metric 숫자와 chart가 보이는 화면

필수 스크린샷 산출:

- `.codex_tmp/ui4c_global_contrast/step1_upload_desktop.png`
- `.codex_tmp/ui4c_global_contrast/step2_mapping_desktop.png`
- `.codex_tmp/ui4c_global_contrast/step2_formula_desktop.png`
- `.codex_tmp/ui4c_global_contrast/step3_discrepancy_desktop.png`
- `.codex_tmp/ui4c_global_contrast/step5_dashboard_metrics_desktop.png`
- `.codex_tmp/ui4c_global_contrast/mobile_step2.png`
- `.codex_tmp/ui4c_global_contrast/mobile_dashboard.png`

브라우저 자동화가 불가능하면:

- 불가능한 이유를 검수요약에 명확히 적어라.
- 대신 수동 검수 체크리스트와 최소한 Streamlit 실행 로그/HTTP 200/코드 selector 대조 결과를 남겨라.
- 단, 가능하면 스크린샷 검수를 우선하라.

## 테스트 요구사항

기존 회귀 테스트를 유지하라. 이번 PR은 UI 대비 수정이 주목적이므로 DB adapter/replay stack 로직을 건드리지 마라.

필수 실행:

```powershell
python -m py_compile main.py modules/step1_upload.py modules/step2_system_definition.py modules/step5_discrepancy.py modules/step6_dashboard.py modules/ui_db_corpus_helper.py
python test_db_corpus_ui_state.py
python test_db_corpus_scale_validation.py
python test_step1_db_corpus_upload_adapter.py
python test_step6_db_corpus_auto_schema.py
python test_step6_db_corpus_oneclick_backtest.py
python test_showdown_db_extract_adapter.py
python test_db_corpus_backtest_report.py
python test_i15_integration_smoke.py
```

가능하면 다음도 실행하라.

```powershell
python test_step3_target_flow.py
```

만약 `test_step3_target_flow.py`가 `matplotlib` 미설치 때문에 실패하면, 다음 중 더 적절한 방식으로 보정하라.

- `requirements.txt`에 필요한 의존성을 추가한다.
- 또는 `step5_discrepancy.py`에서 `background_gradient`가 matplotlib 없이도 안전하게 fallback되도록 한다.

단, 이 보정은 Step3 테스트를 깨지 않기 위한 최소 수정이어야 하며, DB replay/backtest 로직을 변경하지 마라.

## 검수요약 문서

루트에 아래 문서를 작성하라.

- `DB코퍼스_UI4c_globalContrastReadability_검수요약.md`

포함 내용:

- 수정한 파일명
- 전역 CSS/테마 보정 요약
- Dashboard metric `2167.00` 계열 가시성 보정 내용
- 입력 컴포넌트 normal/hover/focus/disabled 대비 확인 결과
- Step1~Step5 화면별 확인 결과
- 스크린샷 파일 경로
- 실행한 테스트 명령과 결과
- `Skipping` 발생 여부
- 남은 이슈

## 금지/주의

- 새 기능을 추가하지 마라.
- DB adapter, replay stack, backtest 계산 로직을 불필요하게 변경하지 마라.
- 단순히 모든 텍스트를 흰색으로 만드는 전역 CSS를 쓰지 마라.
- 밝은 배경 컴포넌트의 텍스트를 흰색으로 만들지 마라.
- disabled 상태를 완전히 안 보이게 만들지 마라.
- landing page나 별도 디자인 페이지를 만들지 마라.
- pycache, 대용량 임시 산출물, 무관한 데이터 파일을 커밋 대상으로 만들지 마라.

## 완료 보고 형식

완료 후 아래 형식으로 보고하라.

```text
UI4c 완료 보고

1. 수정 파일
- ...

2. 가시성 보정 요약
- ...

3. 스크린샷
- ...

4. 테스트 결과
- ...

5. 남은 이슈
- ...
```
