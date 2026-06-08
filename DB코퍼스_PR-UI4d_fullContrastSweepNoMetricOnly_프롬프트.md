# DB코퍼스 PR-UI4d fullContrastSweepNoMetricOnly 프롬프트

## 역할

너는 이 저장소의 UI/UX 구현을 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수와 프롬프트 작성만 담당한다. 이번 작업은 이전 UI4c 결과의 부분 수정 실패를 바로잡는 후속 PR이다.

## 실패 판정

UI4c 반영 결과, Dashboard의 대표 metric 숫자 일부만 개선되었다. 사용자가 확인한 결과는 다음과 같다.

- `2167.00` 같은 큰 숫자는 개선되었다.
- 그러나 Step과 관계없는 전역 텍스트 대비 문제는 여전히 남아 있다.
- 작은 label/caption/help text/disabled text/secondary text가 어두운 배경과 거의 섞인다.
- 즉, metric value 하나만 고친 것이고, 전체 UI 대비 감사가 수행되지 않았다.

이번 PR은 **개별 숫자 핫픽스 금지**다. 반드시 전체 Streamlit 앱의 텍스트 계층과 컴포넌트 상태를 한 번에 정리하라.

## 사용자 스크린샷 기준 아직 흐린 요소

Dashboard 화면에서 다음 계열이 여전히 가시성이 낮다.

- `총합 체급 (Ally)`, `총합 체급 (Enemy)` 같은 metric label
- `예측 승률 (Logistic Regression)`, `Monte Carlo (1만회)` 같은 metric label
- `버튼을 눌러 실행` 같은 비활성/힌트 텍스트
- `Global Character Builder` 같은 비활성 탭/보조 텍스트
- `뷰어 전체화면` toggle label
- 상단 expander header 주변 보조 텍스트
- sidebar의 `File: ...`, `Target: ...`, `Stats: ...`, `Gimmicks: ...` 같은 caption
- 탭/차트/테이블 주변 작은 label
- Step1~Step5 전역의 caption/help/disabled/secondary 텍스트

## 목표

앱 전체에서 hover 없이 읽기 어려운 텍스트를 없앤다. 큰 숫자만 밝게 만드는 방식은 실패로 간주한다.

최소 목표:

- normal text: 배경 대비 충분히 선명해야 한다.
- secondary/caption text: primary보다 약하되 읽을 수 있어야 한다.
- muted/disabled text: 비활성임을 알 수 있으면서도 상태를 읽을 수 있어야 한다.
- dark background 위 text는 밝은 계열이어야 한다.
- light table/chart/input surface 위 text는 어두운 계열이어야 한다.

가능하면 WCAG 기준을 목표로 삼아라.

- 일반 텍스트: contrast ratio 4.5:1 이상
- 큰 텍스트/metric: contrast ratio 3:1 이상, 가능하면 4.5:1 근접
- disabled text도 2.5~3:1 미만으로 떨어뜨리지 말 것

## 필수 구현 지침

### P0. 전역 색상 토큰을 정리하라

`main.py` 또는 앱 공통 스타일 위치에 CSS color token을 명확히 정의하라.

예시 토큰:

- `--app-bg`
- `--sidebar-bg`
- `--panel-bg`
- `--surface-bg`
- `--surface-light-bg`
- `--text-primary`
- `--text-secondary`
- `--text-muted`
- `--text-disabled`
- `--text-on-light`
- `--border-subtle`
- `--accent`
- `--positive`
- `--negative`

주의:

- 모든 `span`, `p`, `label`을 무조건 흰색으로 만드는 방식은 금지한다.
- 흰색/밝은 테이블, file uploader, input 내부 텍스트는 `--text-on-light`로 처리하라.
- 어두운 배경 위 caption/secondary/disabled 텍스트는 너무 어둡게 만들지 마라.

### P0. 텍스트 계층 selector를 전역 보정하라

다음 계열을 직접 확인하고 보정하라.

- heading
- markdown paragraph
- caption
- small text
- label
- expander header
- tab label
- sidebar caption
- metric label/value/delta
- toggle/checkbox/radio label
- disabled button text
- disabled input text
- help text
- alert/info/warning 내부 텍스트

필수 selector 후보:

```css
[data-testid="stMarkdownContainer"]
[data-testid="stCaptionContainer"]
[data-testid="stSidebar"]
[data-testid="stMetric"]
[data-testid="stMetricLabel"]
[data-testid="stMetricValue"]
[data-testid="stMetricDelta"]
[data-testid="stExpander"]
[data-testid="stTabs"]
[data-testid="stCheckbox"]
[data-testid="stRadio"]
[data-testid="stToggle"]
[data-testid="stButton"]
button:disabled
[aria-disabled="true"]
```

Streamlit 버전에 따라 selector가 다르면 실제 DOM을 보고 맞는 selector를 사용하라.

### P0. 입력/선택 컴포넌트 대비를 별도로 보정하라

이전 문제였던 흰 배경/흰 글자도 아직 같은 범위다. 아래 컴포넌트의 normal/hover/focus/disabled 상태를 확인하라.

- file uploader
- text input
- text area
- number input
- selectbox
- multiselect
- multiselect tag/pill
- button
- disabled button
- dataframe/table

필수 selector 후보:

```css
input
textarea
[data-baseweb="input"]
[data-baseweb="textarea"]
[data-baseweb="select"]
[data-baseweb="tag"]
[data-testid="stTextInput"]
[data-testid="stTextArea"]
[data-testid="stNumberInput"]
[data-testid="stSelectbox"]
[data-testid="stMultiSelect"]
[data-testid="stFileUploader"]
[data-testid="stDataFrame"]
```

주의:

- input/select/uploader가 밝은 배경이면 내부 텍스트는 어두운 색이어야 한다.
- dark theme에 맞춰 input 자체를 어둡게 바꾸는 것도 가능하지만, 이 경우 placeholder/disabled/value/focus border까지 모두 같이 처리하라.
- disabled button 텍스트가 배경과 섞이지 않게 하라.

### P0. Dashboard를 실제 기준 화면으로 고쳐라

사용자 스크린샷과 같은 Dashboard 화면에서 아래 요소가 모두 읽혀야 한다.

- `2167.00`
- `1903.70`
- `95.1%`
- `대기 중`
- `총합 체급 (Ally)`
- `총합 체급 (Enemy)`
- `예측 승률 (Logistic Regression)`
- `Monte Carlo (1만회)`
- `버튼을 눌러 실행`
- `Global Character Builder`
- `뷰어 전체화면`
- sidebar의 File/Target/Stats/Gimmicks caption

수정은 [modules/step6_dashboard.py]와 공통 CSS를 함께 보되, 계산 로직은 건드리지 마라.

### P1. 차트/테이블 가시성 확인

Plotly/차트와 dataframe은 밝은 surface와 어두운 app background가 혼재한다.

필수 확인:

- 차트 title/axis/category label이 읽히는가
- dataframe header/cell text가 읽히는가
- table border와 dark background 경계가 충분한가
- chart surface를 밝게 유지할지 dark로 통일할지 결정하고 label 색을 맞췄는가

## 검수 요구사항

실제 Streamlit 앱을 실행하고 브라우저로 검수하라. HTTP 200만으로 완료하지 마라.

필수 화면:

- Step1 일반 업로드
- Step1 DB 코퍼스 업로드
- Step2 필수 매핑
- Step2 공식 검증/후보 공식
- Step2 선택 규칙/Mechanism 영역
- Step3 Discrepancy
- Step5 Dashboard

필수 viewport:

- desktop 1366x768 이상
- mobile/narrow 390x844 또는 430x932

필수 스크린샷:

- `.codex_tmp/ui4d_full_contrast/step1_upload_desktop.png`
- `.codex_tmp/ui4d_full_contrast/step2_mapping_desktop.png`
- `.codex_tmp/ui4d_full_contrast/step2_formula_desktop.png`
- `.codex_tmp/ui4d_full_contrast/step3_discrepancy_desktop.png`
- `.codex_tmp/ui4d_full_contrast/step5_dashboard_desktop.png`
- `.codex_tmp/ui4d_full_contrast/mobile_step2.png`
- `.codex_tmp/ui4d_full_contrast/mobile_dashboard.png`

스크린샷 검수 시 다음을 체크리스트로 표시하라.

- 큰 metric value만이 아니라 label/caption도 읽히는가
- disabled text도 의미 파악이 가능한가
- sidebar caption이 묻히지 않는가
- chart/table 내부 text가 배경과 충돌하지 않는가
- hover 없이 읽히지 않는 요소가 없는가

## 테스트 요구사항

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

가능하면 실행:

```powershell
python test_step3_target_flow.py
```

`test_step3_target_flow.py`가 `matplotlib` 미설치로 실패하면 최소 수정으로 해결하라.

- `requirements.txt`에 `matplotlib` 추가 또는
- `background_gradient` 사용부에 fallback 추가

## 검수요약 문서

루트에 아래 파일을 작성하라.

- `DB코퍼스_UI4d_fullContrastSweepNoMetricOnly_검수요약.md`

포함 내용:

- 수정 파일
- 전역 색상 토큰/selector 보정 요약
- Dashboard 스크린샷 기준 남아 있던 흐린 요소별 해결 여부
- Step1~Step5 화면별 가시성 확인 결과
- 입력/선택/disabled 컴포넌트 상태별 확인 결과
- 스크린샷 경로
- 테스트 명령과 결과
- `Skipping` 발생 여부
- 남은 이슈

## 금지

- `2167.00` 같은 특정 metric value만 고치는 패치 금지
- 특정 화면 하나만 고치고 완료 처리 금지
- 모든 텍스트를 흰색으로 만드는 전역 덮어쓰기 금지
- 밝은 배경 위 텍스트를 흰색으로 만드는 selector 금지
- DB adapter/replay/backtest 계산 로직 변경 금지
- 새 기능 추가 금지
- pycache, 대용량 임시 파일, 무관한 데이터 파일 커밋 금지

## 완료 보고 형식

```text
UI4d 완료 보고

1. 수정 파일
- ...

2. 전역 대비 보정
- ...

3. 사용자 스크린샷 기준 해결 여부
- 2167.00:
- 1903.70:
- metric label:
- disabled/caption:
- sidebar caption:
- chart/table:

4. 스크린샷
- ...

5. 테스트 결과
- ...

6. 남은 이슈
- ...
```
