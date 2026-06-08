# DB코퍼스 PR-UI4i computedContrastGate 프롬프트

## 역할

너는 이 저장소의 UI/UX 구현을 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수와 프롬프트 작성만 담당한다.

이번 작업은 반복 실패한 텍스트 가시성 문제를 **computed style 기반 대비 검사로 차단**하는 후속 PR이다. 스크린샷만 보고 일부 요소를 고치는 방식은 실패했다. 이번에는 실제 DOM의 color/background를 검사하고, 대비 실패가 남아 있으면 완료 보고하지 마라.

## 현재 실패 판정

사용자 스크린샷 기준:

- selectbox/multiselect/text input이 흰 배경인데 내부 텍스트도 흰색 또는 너무 옅은 색이라 보이지 않는다.
- 예: Step2 `Is_Victorious`, formula input의 `move_power * attack / defense`, selectbox placeholder/value, multiselect 선택값 주변 영역.
- chip/pill 일부도 밝은 배경 위 흐린 텍스트 또는 어색한 대비로 보인다.
- disabled `이전 단계` 버튼도 거의 읽히지 않는다.
- 이전 PR에서 일부 label에 파란 highlight를 붙이는 식의 임시 처리가 생겼는데, 이는 해결이 아니라 디자인 실패다.

이 문제의 핵심은 “어두운 앱 배경”과 “밝은 Streamlit/BaseWeb form surface”가 섞여 있는데, text color role이 surface별로 분리되지 않은 것이다.

## 최종 목표

앱 전체에서 다음이 성립해야 한다.

- 어두운 배경 위 텍스트는 밝고 읽힌다.
- 밝은 form/table/uploader surface 위 텍스트는 어두운 색으로 읽힌다.
- placeholder, selected value, disabled text도 읽힌다.
- 파란 highlight/inline 땜질 없이 자연스러운 theme로 해결한다.
- Step1/Step2/Step3/Dashboard의 visible text 대비 검사를 통과한다.

## P0. 흰 배경/흰 글씨 문제를 우선 해결

반드시 아래 컴포넌트의 내부 텍스트 색을 고쳐라.

- `st.selectbox`
- `st.multiselect`
- multiselect selected tag/pill
- `st.text_input`
- `st.text_area`
- `st.number_input`
- `st.file_uploader`
- disabled button/input

### 필수 원칙

밝은 surface를 유지한다면:

- 배경: 밝은 색 가능
- 내부 value/placeholder/help text: 어두운 색이어야 함
- caret/icon/clear icon도 식별 가능해야 함

dark surface로 통일한다면:

- 배경: dark panel 색
- 내부 value/placeholder/help text: 밝은 색이어야 함
- border/focus/disabled 상태를 모두 맞춰야 함

둘 중 하나를 선택하되, 한 컴포넌트 안에서 “흰 배경 + 흰 글씨”가 절대 남으면 안 된다.

## P0. 정확히 확인해야 할 selector

실제 DOM을 inspector 또는 브라우저 자동화로 확인하고 selector를 맞춰라. Streamlit/BaseWeb은 내부 구조가 복잡하므로 겉 selector만 고치면 실패한다.

필수 후보:

```css
input
textarea
input::placeholder
textarea::placeholder
[data-baseweb="input"]
[data-baseweb="input"] input
[data-baseweb="textarea"]
[data-baseweb="textarea"] textarea
[data-baseweb="select"]
[data-baseweb="select"] *
[data-baseweb="tag"]
[data-baseweb="tag"] *
[data-testid="stSelectbox"]
[data-testid="stSelectbox"] *
[data-testid="stMultiSelect"]
[data-testid="stMultiSelect"] *
[data-testid="stTextInput"]
[data-testid="stTextInput"] *
[data-testid="stTextArea"]
[data-testid="stTextArea"] *
[data-testid="stNumberInput"]
[data-testid="stNumberInput"] *
[data-testid="stFileUploader"]
[data-testid="stFileUploader"] *
[data-testid="stButton"]
button:disabled
[aria-disabled="true"]
```

주의:

- `*` selector를 쓰더라도 범위를 해당 컴포넌트 내부로 한정하라.
- 모든 전역 `span`, `p`, `label`에 같은 색을 주지 마라.
- 밝은 surface 내부 아이콘/placeholder도 확인하라.

## P0. 사용자-facing 문구 정리 유지

Step1 사용자-facing 화면에는 내부 용어를 노출하지 마라.

금지 문구:

- `Pokemon Showdown`
- `DB 코퍼스`
- `코퍼스 파일`

권장 문구:

- `전투 데이터 파일`
- `지원 형식: CSV, Excel, JSON, TSV, TXT, Parquet, DB, ZIP`

`.db`, `.zip` 지원과 내부 DB 분기 로직은 유지한다.

## P0. 파란 highlight/임시 강조 제거

이전 결과처럼 label이나 텍스트 뒤에 파란 배경을 붙여서 가시성을 만드는 방식은 금지한다.

제거 대상:

- label 텍스트에 붙은 강한 blue background
- 선택된 것도 아닌데 파란 박스처럼 보이는 제목/label
- 불필요한 inline style highlight

텍스트 대비는 color token과 surface token으로 해결하라.

## P0. Computed Contrast Gate 추가

이번 PR은 스크린샷만으로 완료하지 마라. 브라우저에서 실제 computed style을 읽어 대비 실패를 찾는 검사를 추가/실행하라.

### 산출물

아래 파일을 생성하라.

- `.codex_tmp/ui4i_computed_contrast/contrast_audit_step1.json`
- `.codex_tmp/ui4i_computed_contrast/contrast_audit_step2_mapping.json`
- `.codex_tmp/ui4i_computed_contrast/contrast_audit_step2_formula.json`
- `.codex_tmp/ui4i_computed_contrast/contrast_audit_dashboard.json`
- `.codex_tmp/ui4i_computed_contrast/contrast_audit_summary.md`

### 감사 방식

브라우저 자동화로 각 화면의 visible text element를 순회하라.

검사 대상:

- visible text node가 있는 element
- input/textarea value
- input/textarea placeholder
- button text
- selected option/value text
- tag/pill text
- caption/help text
- disabled text

각 항목에 대해:

- selector 또는 element path
- text sample
- computed `color`
- effective background color
- contrast ratio
- pass/fail
- screenshot reference

를 기록하라.

### 최소 기준

- 일반 텍스트: contrast ratio 4.5 이상
- 큰 텍스트/metric: 3.0 이상
- disabled/placeholder/help text: 3.0 이상 권장, 최소 2.5 미만이면 실패
- input value/selected value는 일반 텍스트 기준으로 보고 4.5 이상을 목표로 하라.

완벽한 자동 계산이 어렵다면:

- 밝은 배경 위 거의 흰 텍스트는 반드시 fail로 수동 표기하라.
- 자동 검사 한계와 수동 확인 결과를 summary에 적어라.

### 완료 조건

`contrast_audit_summary.md`에 fail 항목이 0이어야 완료 보고할 수 있다.

단, decorative icon이나 의미 없는 빈 텍스트는 제외 가능하다. 제외한 항목은 사유를 적어라.

## P0. 실제 화면 스크린샷

필수:

- `.codex_tmp/ui4i_computed_contrast/step1_desktop.png`
- `.codex_tmp/ui4i_computed_contrast/step2_mapping_desktop.png`
- `.codex_tmp/ui4i_computed_contrast/step2_formula_desktop.png`
- `.codex_tmp/ui4i_computed_contrast/dashboard_desktop.png`
- `.codex_tmp/ui4i_computed_contrast/mobile_step1.png`
- `.codex_tmp/ui4i_computed_contrast/mobile_step2.png`

스크린샷에서 반드시 확인:

- selectbox 값이 보이는가
- formula input 값/placeholder가 보이는가
- multiselect tags가 보이는가
- uploader help text가 보이는가
- disabled 이전/다음 버튼이 읽히는가
- 파란 highlight 땜질이 사라졌는가

## P1. Step1 구조 유지

Step1은 다음 세 입력이 inline으로 보여야 한다.

- 전투 데이터 파일
- 무브 로그 파일 (선택)
- 매핑 프리셋 JSON (선택)

탭/expander/내부 DB 코퍼스 섹션은 만들지 마라.

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

추가:

- 사용자-facing Step1 문자열에 `Pokemon Showdown`, `DB 코퍼스`, `코퍼스 파일`이 남지 않았는지 확인하라.
- `.db`/`.zip` 자동 분기가 유지되는지 확인하라.

## 검수요약 문서

루트에 아래 파일을 작성하라.

- `DB코퍼스_UI4i_computedContrastGate_검수요약.md`

포함:

- 수정 파일
- 흰 배경/흰 글씨 문제 해결 방식
- form component selector 보정 요약
- 제거한 파란 highlight/임시 스타일
- 사용자-facing 문구 정리 결과
- contrast audit summary
  - 검사 화면 수
  - 검사 항목 수
  - fail 항목 수
  - 제외 항목 및 사유
- 스크린샷 경로
- 테스트 결과
- 남은 이슈

## 완료 보고 형식

```text
UI4i 완료 보고

1. 수정 파일
- ...

2. 핵심 해결
- 흰 배경/흰 글씨:
- form component 대비:
- 파란 highlight 제거:
- 사용자-facing 문구:

3. Contrast Audit
- 검사 화면:
- 검사 항목:
- fail:
- summary:

4. 스크린샷
- ...

5. 테스트 결과
- ...

6. 남은 이슈
- ...
```
