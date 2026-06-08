# DB코퍼스 PR-UI4l formulaTabContrastCoverage 프롬프트

## 역할

너는 이 저장소의 UI/UX 구현을 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수와 프롬프트 작성만 담당한다.

이전 UI4k 적용 후에도 Step2 `공식 검증` 탭의 가시성 문제가 그대로 남았다. 이번 작업은 **공식 검증 탭 미적용 영역을 색상만으로 고치는 보완 PR**이다.

## 실패 판정

사용자 스크린샷 기준 다음은 아직 실패다.

- `변수 칩` 영역의 pill 텍스트가 흰 배경 위에서 거의 안 보인다.
  - `HP`
  - `Attack`
  - `Defense`
  - `SpAtk`
  - `SpDef`
  - `Speed`
  - `Type1`
  - `Type2`
- `전투 데미지 공식 (Damage Formula)` 입력창/textarea가 흰 배경인데 내부 값 또는 placeholder가 거의 안 보인다.
- disabled `다음 단계로` 버튼 텍스트가 어두운 배경과 섞여 읽기 어렵다.
- 하단 `이전 단계` 버튼도 밝은 버튼 위 텍스트 상태를 확인해야 한다.
- 공식 검증 탭의 보조 label/help text도 일부 약하다.

즉, UI4k는 Step2 `공식 검증` 탭까지 커버하지 못했다.

## 절대 금지

이번 PR에서도 레이아웃을 건드리지 마라.

금지 CSS 속성:

```css
height
min-height
max-height
width
min-width
max-width
padding
margin
line-height
overflow
display
position
transform
font-size
letter-spacing
```

금지 방식:

- chip/pill 크기 조정
- chip/pill padding 조정
- chip/pill overflow 조정
- 모든 `span`, `label`, `p`를 전역으로 흰색 처리
- `[data-baseweb="select"] *`, `[data-baseweb="tag"] *` 같은 무차별 내부 덮어쓰기
- 파란 highlight나 텍스트 배경색 덧칠
- 특정 문구 inline style 삽입

허용 속성:

```css
color
background-color
border-color
caret-color
```

## 필수 수정 대상

### 1. 공식 검증 변수 pill

공식 검증 탭의 변수 chip/pill은 밝은 배경을 유지한다면 텍스트가 어두워야 한다.

확인 대상:

- `HP`
- `Attack`
- `Defense`
- `SpAtk`
- `SpDef`
- `Speed`
- `Type1`
- `Type2`

수용 기준:

- 모든 chip 텍스트가 전체 단어로 보인다.
- 첫 글자가 잘리지 않는다.
- 흰 배경 위 흰/옅은 글씨가 아니다.
- chip 크기나 배치가 바뀌지 않는다.

### 2. Damage Formula 입력창

`전투 데미지 공식 (Damage Formula)` 입력창/textarea의 value와 placeholder가 보여야 한다.

수용 기준:

- 비어 있을 때 placeholder가 읽힌다.
- 값이 있을 때 `move_power * attack / defense` 같은 텍스트가 읽힌다.
- caret 색이 배경과 구분된다.
- input/textarea 크기와 배치는 바뀌지 않는다.

### 3. disabled navigation button

하단 `다음 단계로` disabled 버튼 텍스트가 읽혀야 한다.

수용 기준:

- 비활성 상태임을 알 수 있다.
- 텍스트는 읽을 수 있다.
- 버튼 크기/위치가 바뀌지 않는다.

### 4. 공식 검증 탭 label/help text

다음 텍스트는 hover 없이 읽혀야 한다.

- `변수 칩 (클릭 시 수식 입력창에 삽입됩니다):`
- `전투 데미지 공식 (Damage Formula)`
- warning/success 메시지
- Step2 setup summary
- tab labels

## selector 지침

실제 DOM을 보고 좁게 적용하라. 후보:

```css
[data-testid="stTextInput"] input
[data-testid="stTextArea"] textarea
input
textarea
input::placeholder
textarea::placeholder
[data-baseweb="tag"]
[data-baseweb="tag"] span
[data-testid="stButton"] button:disabled
button:disabled
```

주의:

- `tag` 내부 전체에 layout 관련 속성을 주지 마라.
- 필요하면 `color`만 조정하라.
- 밝은 pill/input surface의 텍스트는 `#111827` 또는 유사한 dark text를 써라.
- dark app background 위 label은 `#F8FAFC` 또는 `#D1D5DB` 계열을 써라.

## 검수 요구사항

HTTP 200만으로 완료하지 마라. 반드시 공식 검증 탭 스크린샷을 남겨라.

필수 스크린샷:

- `.codex_tmp/ui4l_formula_tab_contrast/step2_formula_empty.png`
- `.codex_tmp/ui4l_formula_tab_contrast/step2_formula_with_value.png`
- `.codex_tmp/ui4l_formula_tab_contrast/step2_mapping_regression.png`

검수 체크리스트:

- 공식 검증 변수 pill 8개가 모두 읽히는가
- formula input placeholder가 읽히는가
- formula input 값이 읽히는가
- disabled `다음 단계로` 텍스트가 읽히는가
- chip 텍스트가 잘리지 않는가
- Step2 필수 매핑 탭이 다시 깨지지 않았는가

하나라도 실패하면 완료 보고하지 마라.

## 테스트 요구사항

필수 실행:

```powershell
python -m py_compile main.py modules/step1_upload.py modules/step2_system_definition.py modules/step5_discrepancy.py modules/step6_dashboard.py modules/ui_db_corpus_helper.py
python test_db_corpus_ui_state.py
python test_step1_db_corpus_upload_adapter.py
python test_step6_db_corpus_auto_schema.py
python test_step6_db_corpus_oneclick_backtest.py
python test_i15_integration_smoke.py
```

## 검수요약 문서

루트에 아래 파일을 작성하라.

- `DB코퍼스_UI4l_formulaTabContrastCoverage_검수요약.md`

포함:

- 수정 파일
- 수정한 selector
- 사용한 CSS 속성
- 공식 검증 탭 실패 항목별 해결 여부
- Step2 필수 매핑 회귀 여부
- 스크린샷 경로
- 테스트 결과
- 남은 이슈

## 완료 보고 형식

```text
UI4l 완료 보고

1. 수정 파일
- ...

2. 공식 검증 탭 가시성
- 변수 pill:
- formula input placeholder:
- formula input value:
- disabled 다음 단계:

3. 회귀 확인
- 필수 매핑 탭:
- chip 잘림:

4. 스크린샷
- ...

5. 테스트 결과
- ...

6. 남은 이슈
- ...
```
