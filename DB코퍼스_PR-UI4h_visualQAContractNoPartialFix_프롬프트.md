# DB코퍼스 PR-UI4h visualQAContractNoPartialFix 프롬프트

## 역할

너는 이 저장소의 UI/UX 구현을 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수와 프롬프트 작성만 담당한다.

이번 작업은 새 기능 추가가 아니라 **반복 실패한 UI 가시성/업로드 UX를 완료 판정 가능한 수준으로 끝내는 계약 작업**이다. 부분 수정 후 완료 보고하지 마라.

## 현재 실패 상황

이전 작업들은 사용자가 지적한 일부 문구/숫자만 고쳤고, 전체 UI 문제는 남았다.

사용자 불만:

- “고치라는 데만 고친 게 한두 번이 아니다.”
- “언제까지 이걸 반복해야 하냐.”
- 가시성 문제가 그대로 남아 있다.
- 내부 용어가 사용자 화면에 남아 있다.
- 일부 텍스트를 파란 배경으로 감싸는 식의 땜질이 생겼다.

현재 스크린샷 기준 실패 예:

- Step2의 `타겟 컬럼`, `숫자형 스탯 (Base Stats)`, `카테고리/기믹 (Gimmicks)` label이 여전히 작고 흐리거나, 임시 파란 배경 강조로 어색하게 처리됨.
- selectbox/multiselect의 밝은 배경과 어두운 앱 테마가 정리되지 않음.
- disabled 이전 단계 버튼 텍스트가 거의 보이지 않음.
- 공식 검증기의 chip/button 텍스트가 흐리거나 밝은 pill 위에서 묻힘.
- step tab/summary/text 계층이 일관되지 않음.
- Step1 사용자-facing 문구에 내부 용어가 남거나, uploader label/help가 여전히 흐림.

## 완료 방식 변경

이번 PR은 “요청받은 예시만 수정”하면 실패다.

반드시 다음 순서로 진행하라.

1. 실제 화면에서 전체 텍스트 가시성 실패 항목을 먼저 목록화한다.
2. 공통 CSS/theme와 컴포넌트 스타일을 근본적으로 정리한다.
3. Step1/Step2/Step3/Dashboard를 다시 찍는다.
4. 수정 전 실패 항목이 모두 해결됐는지 표로 증명한다.
5. 하나라도 남으면 완료 보고하지 말고 추가 수정한다.

## P0. 부분 수정 금지

금지:

- 사용자가 예로 든 텍스트만 밝게 만들기
- 특정 숫자만 밝게 만들기
- 특정 label만 inline style로 덮어쓰기
- 텍스트 뒤에 파란색/강한 배경 박스를 붙여 억지로 보이게 만들기
- 모든 `span`, `p`, `label`을 무조건 흰색으로 바꾸기
- 밝은 selectbox/input/table 내부 텍스트를 흰색으로 만들기
- disabled 상태를 거의 안 보이게 만들기
- HTTP 200만 확인하고 완료 보고하기

특히 현재처럼 label에 파란 highlight가 생기는 방식은 디자인 실패다. 텍스트 자체 대비와 컴포넌트 surface 대비로 해결하라.

## P0. 사용자-facing 문구 정리

Step1 사용자 화면에는 내부 구현 용어를 노출하지 마라.

사용자 화면에서 제거:

- `Pokemon Showdown`
- `DB 코퍼스`
- `코퍼스 파일`
- `Pokemon Showdown DB 코퍼스 파일`

유지:

- 지원 확장자 안내의 `DB`, `ZIP`
- 내부 함수명/변수명/테스트명
- 검수요약의 개발자용 설명

권장 문구:

- 제목: `전투 로그 업로드`
- 메인 uploader label: `전투 데이터 파일`
- 설명: `전투 데이터 파일을 업로드하면 형식에 맞춰 자동으로 처리합니다.`
- help: `지원 형식: CSV, Excel, JSON, TSV, TXT, Parquet, DB, ZIP`
- 하단 경고: `전투 데이터 파일을 업로드해야 합니다.`

## P0. Step1 입력 구조

Step1은 세 입력을 같은 흐름에서 inline으로 보여라.

- 전투 데이터 파일
- 무브 로그 파일 (선택)
- 매핑 프리셋 JSON (선택)

금지:

- 탭
- expander
- 접힌 보조 옵션
- 빈 흰색 바
- 내부 용어가 노출되는 별도 DB 코퍼스 섹션

## P0. 전역 가시성 기준

아래 모든 텍스트 role이 hover 없이 읽혀야 한다.

- heading
- section title
- body text
- label
- caption
- help text
- placeholder
- selected value
- disabled text
- tab text
- expander header
- uploader text
- button text
- chip/pill text
- metric label/value/delta
- sidebar caption
- alert/info/warning text
- table header/cell text
- chart axis/category/legend text

대비 기준:

- dark background 위 primary text는 밝고 선명해야 한다.
- dark background 위 secondary/caption text도 읽을 수 있어야 한다.
- disabled text도 의미를 읽을 수 있어야 한다.
- light input/select/table surface 위 텍스트는 어두운 색이어야 한다.
- chip/pill은 배경과 텍스트가 모두 명확해야 한다.

## P0. 컴포넌트별 필수 보정

실제 DOM을 확인해 Streamlit selector를 맞춰라.

필수 대상:

```css
[data-testid="stFileUploader"]
[data-testid="stFileUploader"] label
[data-testid="stFileUploader"] small
[data-testid="stFileUploader"] span
[data-testid="stFileUploader"] button
[data-testid="stTextInput"]
[data-testid="stTextArea"]
[data-testid="stNumberInput"]
[data-testid="stSelectbox"]
[data-testid="stMultiSelect"]
[data-testid="stButton"]
[data-testid="stMetric"]
[data-testid="stCaptionContainer"]
[data-testid="stMarkdownContainer"]
[data-testid="stSidebar"]
[data-testid="stTabs"]
[data-testid="stExpander"]
[data-baseweb="select"]
[data-baseweb="tag"]
[data-baseweb="input"]
input
textarea
button:disabled
[aria-disabled="true"]
```

필요하면 semantic CSS token을 만들고 컴포넌트별로 적용하라.

## P0. Step2 가시성 완결

사용자 스크린샷 기준 Step2는 아직 실패다.

반드시 해결:

- `타겟 컬럼`
- selected target value
- `숫자형 스탯 (Base Stats)`
- Base Stats tags
- `카테고리/기믹 (Gimmicks)`
- Gimmicks tags
- `결측치 채우기`
- radio labels
- 공식 검증기의 변수 chip
- damage formula input
- disabled/secondary text
- 이전/다음 버튼

해결 방식:

- label에 파란 배경을 붙이지 마라.
- selectbox/multiselect 전체 surface와 text 색을 일관되게 잡아라.
- tag/pill은 dark theme 안에서 자연스럽게 보이게 하라.
- 밝은 input을 유지한다면 내부 값은 어두운 색, 주변 label은 밝은 색으로 하라.

## P0. Step5/Dashboard 가시성 완결

반드시 해결:

- metric value
- metric label
- metric delta
- `대기 중` 같은 상태 텍스트
- sidebar File/Target/Stats/Gimmicks caption
- chart axis/category label
- table header/cell
- toggle label
- tab text

## 검수 계약

완료 전 반드시 아래 산출물을 남겨라.

### 1. 실패 항목 목록

`.codex_tmp/ui4h_visual_qa/fail_items_before.md`

포함:

- 화면
- 텍스트/컴포넌트
- 실패 유형
- 수정 방식

예:

```text
Step2 / 타겟 컬럼 label / dark background 대비 부족 / label color token 보정
Step2 / selected value Is_Victorious / light selectbox 내부 텍스트 흐림 / selectbox text-on-light 보정
```

### 2. 스크린샷

필수:

- `.codex_tmp/ui4h_visual_qa/step1_empty_desktop.png`
- `.codex_tmp/ui4h_visual_qa/step1_uploaded_desktop.png`
- `.codex_tmp/ui4h_visual_qa/step2_mapping_desktop.png`
- `.codex_tmp/ui4h_visual_qa/step2_formula_desktop.png`
- `.codex_tmp/ui4h_visual_qa/step3_desktop.png`
- `.codex_tmp/ui4h_visual_qa/step5_dashboard_desktop.png`
- `.codex_tmp/ui4h_visual_qa/mobile_step1.png`
- `.codex_tmp/ui4h_visual_qa/mobile_step2.png`

### 3. 완료 체크 표

`.codex_tmp/ui4h_visual_qa/fail_items_after.md`

포함:

- before 실패 항목
- 해결 여부
- 근거 스크린샷
- 남은 이슈

하나라도 `미해결`이면 완료 보고하지 마라.

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

- 사용자-facing Step1 문자열에 `Pokemon Showdown`, `DB 코퍼스`, `코퍼스 파일`이 남지 않았는지 grep/test로 확인하라.
- `.db`/`.zip` 자동 분기는 그대로 동작하는지 확인하라.

## 검수요약 문서

루트에 아래 파일을 작성하라.

- `DB코퍼스_UI4h_visualQAContractNoPartialFix_검수요약.md`

포함:

- 수정 파일
- 사용자-facing 문구 정리 결과
- Step1 입력 구조 결과
- CSS/theme/selector 보정 요약
- before 실패 항목 수
- after 해결 항목 수
- 미해결 항목 수
- 스크린샷 경로
- 테스트 결과
- `Skipping` 발생 여부
- 남은 이슈

## 완료 보고 형식

```text
UI4h 완료 보고

1. 수정 파일
- ...

2. 반복 실패 방지 조치
- before 실패 항목 수:
- after 해결 항목 수:
- 미해결 항목 수:

3. 사용자-facing 문구
- 제거 완료:
- 최종 Step1 문구:

4. 가시성
- Step1:
- Step2:
- Step3:
- Dashboard:

5. 산출물
- fail_items_before:
- fail_items_after:
- screenshots:
- 검수요약:

6. 테스트 결과
- ...

7. 남은 이슈
- ...
```
