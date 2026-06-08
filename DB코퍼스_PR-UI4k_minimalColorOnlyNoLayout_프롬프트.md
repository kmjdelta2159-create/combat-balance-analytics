# DB코퍼스 PR-UI4k minimalColorOnlyNoLayout 프롬프트

## 역할

너는 이 저장소의 UI/UX 구현을 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수와 프롬프트 작성만 담당한다.

이전 UI4 계열 가시성 수정은 화면을 더 망가뜨렸고 롤백되었다. 이번 작업은 **색상만 최소 수정**하는 복구형 PR이다. 레이아웃, 크기, padding, overflow, line-height를 건드리면 실패다.

## 현재 전제

- 가시성 개선을 시도했다가 문제가 더 심해져 롤백했다.
- 원인은 텍스트 색과 배경색의 대비 문제인데, 이전 시도에서 너무 넓은 selector와 내부 구조 수정이 들어가 chip/text clipping이 발생했다.
- 이번에는 "텍스트 색을 배경색과 다르게 지정"하는 데만 집중한다.

## 핵심 목표

배경과 텍스트가 같거나 너무 비슷한 요소만 고친다.

- 어두운 앱 배경 위 텍스트는 밝게.
- 흰색/밝은 input/select/uploader/table 내부 텍스트는 어둡게.
- disabled/placeholder/help text는 흐리되 읽히게.
- multiselect chip/tag는 글자가 잘리지 않게 유지.

## 절대 금지

다음 CSS 속성은 이번 PR에서 수정하지 마라.

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
top
left
right
bottom
transform
font-size
letter-spacing
```

다음 방식도 금지한다.

- 모든 `span`, `p`, `label`을 무조건 흰색으로 만드는 전역 selector
- `[data-baseweb="select"] *`처럼 내부 전체를 무차별로 덮는 selector
- multiselect chip/tag의 크기, padding, overflow 조정
- 파란 highlight 또는 텍스트 배경색 덧칠로 억지로 보이게 만들기
- 특정 문구에 inline style 직접 삽입
- 새 UI 구조 변경
- 새 기능 추가

## 허용 CSS 속성

이번 PR에서는 원칙적으로 아래만 사용하라.

```css
color
background-color
border-color
caret-color
```

필요할 경우 `box-shadow`는 focus ring 보정에만 최소 사용한다.  
`opacity`는 텍스트를 더 흐리게 만들 수 있으므로 사용하지 마라.

## 색상 기준

권장 색상:

```css
--text-on-dark: #F8FAFC;
--text-secondary-on-dark: #D1D5DB;
--text-muted-on-dark: #B8C0CC;
--text-disabled-on-dark: #A7B0BE;
--text-on-light: #111827;
--text-muted-on-light: #4B5563;
--surface-light: #F8FAFC;
--surface-dark: #0E1117;
--border-subtle: #30363D;
```

실제 앱 톤에 맞게 조정해도 되지만, 텍스트가 배경과 섞이면 실패다.

## 수정 대상

### 1. 어두운 앱 배경 위 텍스트

다음은 밝은 텍스트 계열이어야 한다.

- heading
- section title
- 일반 label
- caption/help text
- sidebar caption
- step indicator text
- tab text
- expander header
- warning/info/success 내부 텍스트

단, 전역 `label` 전체에 무리하게 `!important`를 남발하지 말고, 앱 dark 영역에서만 필요한 범위로 제한하라.

### 2. 밝은 form surface 위 텍스트

다음 컴포넌트는 밝은 배경을 유지한다면 내부 텍스트가 반드시 어두워야 한다.

- selectbox selected value
- selectbox placeholder
- multiselect value/tag text
- text input value/placeholder
- number input value/placeholder
- textarea value/placeholder
- file uploader internal text
- dataframe header/cell text

핵심 selector 후보:

```css
input
textarea
input::placeholder
textarea::placeholder
[data-baseweb="input"] input
[data-baseweb="textarea"] textarea
[data-baseweb="select"]
[data-testid="stSelectbox"] input
[data-testid="stTextInput"] input
[data-testid="stTextArea"] textarea
[data-testid="stNumberInput"] input
[data-testid="stFileUploader"] button
```

주의:

- chip/tag 내부는 크기 관련 속성을 건드리지 말고 텍스트 색만 조정하라.
- `HP`, `Attack`, `Type1` 같은 tag 텍스트가 잘리면 실패다.

### 3. disabled 상태

disabled 버튼/입력은 비활성처럼 보여야 하지만 텍스트는 읽혀야 한다.

대상:

```css
button:disabled
[aria-disabled="true"]
input:disabled
textarea:disabled
```

비활성 텍스트를 흰 배경 위 거의 흰색으로 두지 마라.

## Step1 문구 유지 조건

사용자-facing 화면에는 내부 용어를 노출하지 마라.

금지:

- `Pokemon Showdown`
- `DB 코퍼스`
- `코퍼스 파일`

허용:

- 확장자 안내의 `DB`, `ZIP`

권장:

- `전투 데이터 파일`
- `지원 형식: CSV, Excel, JSON, TSV, TXT, Parquet, DB, ZIP`

Step1은 다음 세 입력이 inline으로 보여야 한다.

- 전투 데이터 파일
- 무브 로그 파일 (선택)
- 매핑 프리셋 JSON (선택)

탭/expander를 다시 만들지 마라.

## 필수 검수 화면

실제 브라우저로 확인하라. HTTP 200만으로 완료하지 마라.

필수 확인:

- Step1 upload 화면
- Step2 필수 매핑 화면
- Step2 공식 검증 화면
- Dashboard 화면

특히 Step2에서 아래를 확인하라.

- `Is_Victorious`가 selectbox 안에서 보이는가
- `HP`, `Attack`, `Defense`, `SpAtk`, `SpDef`, `Speed` chip이 잘리지 않는가
- `Type1`, `Type2` chip이 잘리지 않는가
- formula input 값/placeholder가 보이는가
- 이전/다음 disabled 버튼 텍스트가 읽히는가

## 필수 스크린샷

아래에 저장하라.

- `.codex_tmp/ui4k_minimal_color_only/step1_desktop.png`
- `.codex_tmp/ui4k_minimal_color_only/step2_mapping_desktop.png`
- `.codex_tmp/ui4k_minimal_color_only/step2_formula_desktop.png`
- `.codex_tmp/ui4k_minimal_color_only/dashboard_desktop.png`

## 실패 조건

아래 중 하나라도 있으면 완료 보고하지 마라.

- 흰 배경 위 흰/옅은 텍스트
- 어두운 배경 위 검은/짙은 회색 텍스트
- chip/tag 텍스트 잘림
- 파란 highlight 땜질
- form 컴포넌트 크기/배치 변경
- Step1 내부 용어 노출
- 스크린샷 미제출

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

가능하면 기존 DB 코퍼스 회귀 테스트도 실행하라.

## 검수요약 문서

루트에 아래 파일을 작성하라.

- `DB코퍼스_UI4k_minimalColorOnlyNoLayout_검수요약.md`

포함:

- 수정 파일
- 수정한 CSS selector 목록
- 사용한 CSS 속성 목록
- 금지 속성을 쓰지 않았다는 확인
- Step1/Step2/Dashboard 가시성 확인 결과
- chip/tag 잘림 없음 확인
- 스크린샷 경로
- 테스트 결과
- 남은 이슈

## 완료 보고 형식

```text
UI4k 완료 보고

1. 수정 파일
- ...

2. CSS 최소 수정
- selector:
- 속성:
- 금지 속성 미사용:

3. 가시성 확인
- Step1:
- Step2 selectbox:
- Step2 chip/tag:
- Step2 formula input:
- Dashboard:

4. 스크린샷
- ...

5. 테스트 결과
- ...

6. 남은 이슈
- ...
```
