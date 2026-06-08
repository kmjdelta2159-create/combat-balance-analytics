# DB코퍼스 PR-UI4b visibleCriticalFlowFix 프롬프트

## 역할

너는 이 저장소를 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수/프롬프트 작성 역할만 맡고 있으므로, 아래 요구사항을 기준으로 UI/UX 코드 수정, 테스트 보강, Streamlit 화면 검수, 결과 문서화를 수행해라.

## 사용자 제보 기준

사용자가 실제 Streamlit 화면에서 당장 보이는 문제를 4개 제보했다.

1. Step1에서 CSV 파일만 받는 것처럼 보이고 실제 업로드 UX가 제한적임.
2. Step2 가독성이 매우 나쁨.
3. Step3에서 다음 단계로 넘어가지 않거나 Target Variable 오류가 발생함.
4. 하얀 배경 위에 글자도 흰색이라 마우스 커서를 올려야만 보이는 UI 요소가 있음.

첨부 화면 기준 주요 증상:

- Step1 제목과 uploader가 `새로운 전투 로그(CSV) 업로드`, `Upload Combat Logs (CSV)`로 보임.
- Step2의 selectbox/input/multiselect/pill/button/formula 후보 영역이 흰 배경 + 옅은 글자라 읽기 어려움.
- Step3에서 `2단계에서 설정한 Target Variable(결과값)을 찾을 수 없습니다. 다시 맵핑해주세요.` 오류가 뜸.
- Step3 화면에서도 `다음 단계로` 버튼은 보이지만 진행 상태가 신뢰되지 않음.
- Step2의 흰 박스 내부 텍스트, 버튼 텍스트, 후보 공식 텍스트가 hover 전에는 거의 안 보임.

이번 PR은 DB 코퍼스 신규 기능이 아니라, **보이는 사용 불가 UI/flow 결함을 우선 보정**하는 작업이다.

## 목표

4개 문제를 모두 해결해, 사용자가 일반 CSV/DB 코퍼스 어느 흐름으로 들어와도 Step1 → Step2 → Step3 진행이 막히지 않고, 화면 텍스트가 hover 없이 읽히도록 만들어라.

## 우선순위

### P0-1. Step3 진행 불가 / Target Variable 오류

현재 코드상 강하게 의심되는 원인:

- `modules/step2_system_definition.py`는 승인 시 `st.session_state["target_col"]`을 저장한다.
- `modules/step5_discrepancy.py`는 `st.session_state.get("target_variable")`만 읽는다.
- 따라서 Step2에서 target을 설정해도 Step3가 target을 못 찾을 수 있다.

필수 보정:

- `modules/step5_discrepancy.py`에서 target 읽기를 아래처럼 호환되게 고쳐라.
  - 우선 `target_col`
  - fallback `target_variable`
- Step2 승인 시에도 필요하면 `target_variable` alias를 같이 저장해 기존 코드와 호환되게 해라.
- Step3 진입 전 `target_col`이 `None`, `"None"`, 또는 df.columns에 없는 경우에는 Step2에서 다음 단계 버튼이 활성화되지 않게 해라.
- Step3에서 오류가 나더라도 “다음 단계로”가 잘못 활성화되지 않게 `can_proceed=False`를 명확히 반환해라.

수용 기준:

- Step2에서 유효한 target을 선택하고 승인하면 Step3에서 Target Variable 오류가 뜨지 않는다.
- Step2에서 target이 `None`이면 Step3로 넘어갈 수 없다.
- `target_col`과 `target_variable` 둘 중 하나만 있어도 Step3는 정상 동작한다.

### P0-2. Step1 업로드 제한/표시 문제

현재 로컬 코드에는 `_SUPPORTED_TYPES = ["csv", "xlsx", "xls", "json", "tsv", "txt", "parquet"]`가 있지만, 실제 화면에는 CSV 전용처럼 보인다.

필수 보정:

- Step1 일반 업로드 섹션 제목/라벨/help text를 실제 지원 형식과 일치시켜라.
- `file_uploader`의 `type`이 실제로 아래를 받는지 확인해라.
  - csv
  - xlsx
  - xls
  - json
  - tsv
  - txt
  - parquet
- DB 코퍼스 탭에서는 아래를 받는지 확인해라.
  - db
  - zip
- 배포/실행 화면에서 CSV-only 문구가 남지 않게 해라.
- 사용자가 CSV만 가능한 줄 착각하지 않도록 “일반 전투 로그”와 “Pokemon Showdown DB 코퍼스” 흐름을 명확히 나눠라.

수용 기준:

- Step1 화면에 `CSV only`로 오해될 문구가 없다.
- 일반 업로드 uploader가 `CSV · Excel · JSON · TSV · TXT · Parquet` 지원을 명확히 표시한다.
- DB 코퍼스 uploader가 `.db · .zip` 지원을 명확히 표시한다.
- 실제 `file_uploader(type=...)` 설정이 표시 문구와 일치한다.

### P1-1. Step2 가독성 문제

Step2는 정보량이 많아도 작업자가 읽을 수 있어야 한다. 현재는 흰 input/selectbox/multiselect/pill 내부 텍스트가 너무 옅고, 후보 공식/버튼이 배경과 섞인다.

필수 보정:

- Step2 화면의 input/selectbox/multiselect/text_area/button/pill/chip/expander/table 텍스트가 hover 없이 읽혀야 한다.
- 흰 배경 컴포넌트에는 어두운 텍스트를 강제하거나, 앱 다크 테마에 맞게 컴포넌트 배경을 어둡게 통일해라.
- 특히 아래를 확인해라.
  - Target 컬럼 selectbox
  - Base Stats & Gimmicks multiselect 선택 pill
  - Damage Formula text area
  - Symbolic Regression 후보 공식 박스
  - `이 공식 사용` 버튼
  - Mechanism Attach 섹션의 selectbox/input
  - number input 내부 값
- 긴 수식 후보는 한 줄에 무리하게 흐르지 않게 하거나, 읽기 가능한 대비와 스크롤/height를 보장해라.

수용 기준:

- Step2의 흰 박스 내부 텍스트가 마우스 hover 없이 읽힌다.
- 비활성 버튼/비활성 input도 최소한 상태를 식별할 수 있다.
- 텍스트와 배경 대비가 desktop/narrow viewport에서 모두 유지된다.

### P1-2. 전역 흰 배경/흰 글자 대비 문제

현재 `main.py` 전역 CSS가 `h1, h2, h3, h4, h5, h6, span, p, label { color: #E6EDF3 !important; }`처럼 광범위하게 적용되어 Streamlit 내부 컴포넌트의 흰 배경과 충돌할 수 있다.

필수 보정:

- 전역 CSS가 Streamlit input/selectbox/multiselect/button 내부 텍스트까지 무차별적으로 흰색으로 만들지 않게 범위를 조정해라.
- 필요한 경우 Streamlit component별 CSS를 추가해 명시적으로 대비를 맞춰라.
- 아래 selector 계열을 실제 DOM에 맞춰 확인하고 보정해라.
  - `input`
  - `textarea`
  - `[data-baseweb="select"]`
  - `[data-baseweb="tag"]`
  - `[data-testid="stTextInput"]`
  - `[data-testid="stTextArea"]`
  - `[data-testid="stSelectbox"]`
  - `[data-testid="stMultiSelect"]`
  - `[data-testid="stFileUploader"]`
  - `[data-testid="stButton"]`
  - disabled button/input 상태
- 단순히 `!important`를 더 많이 붙여 덮는 방식이 아니라, readable theme utility를 정리하는 방식으로 구현해라.

수용 기준:

- 하얀 배경 위 흰 글자 문제가 Step1~Step5에서 재현되지 않는다.
- hover해야만 글자가 보이는 요소가 없다.
- 비활성 요소도 최소한 읽을 수 있는 대비를 가진다.

## 화면 검수 요구사항

Streamlit 앱을 실제로 실행해 아래 화면을 확인하고, 가능하면 스크린샷을 남겨라.

검수 URL:

```powershell
streamlit run main.py
```

필수 확인 화면:

- Step1 일반 업로드
- Step1 DB 코퍼스 업로드
- Step2 필수 매핑 상단
- Step2 공식 검증/후보 공식 영역
- Step2 Mechanism Attach 또는 선택 규칙 하단 영역
- Step3 Discrepancy 진입 성공 화면
- Step3 target invalid 상태 화면

필수 viewport:

- desktop: 1366x768 또는 유사
- narrow: 390x844 또는 430x932

스크린샷 권장 위치:

- `.codex_tmp/ui4b_visible_critical_flow_fix/step1_upload.png`
- `.codex_tmp/ui4b_visible_critical_flow_fix/step2_mapping.png`
- `.codex_tmp/ui4b_visible_critical_flow_fix/step2_formula.png`
- `.codex_tmp/ui4b_visible_critical_flow_fix/step3_discrepancy.png`
- `.codex_tmp/ui4b_visible_critical_flow_fix/mobile_step2.png`

브라우저 자동화가 불가능하면 HTTP 200만으로 끝내지 말고, 무엇을 수동 검수해야 하는지 검수요약에 명확히 남겨라.

## 테스트 요구사항

기존 테스트 유지:

- `test_db_corpus_scale_validation.py`
- `test_db_corpus_ui_state.py`
- `test_step1_db_corpus_upload_adapter.py`
- `test_step6_db_corpus_auto_schema.py`
- `test_step6_db_corpus_oneclick_backtest.py`
- `test_showdown_db_extract_adapter.py`
- `test_db_corpus_backtest_report.py`
- `test_i15_integration_smoke.py`

추가/보강 테스트:

- `test_step3_target_flow.py`
  - `target_col`만 있는 session-like state에서 Step3 target resolve가 정상인지
  - `target_variable`만 있는 fallback도 정상인지
  - target이 없으면 진행 불가인지
- 가능하면 Step1 parser supported type 테스트
  - `_SUPPORTED_TYPES`가 UI 표시 문구와 일치하는지
- CSS는 단위 테스트가 어렵다면 화면 검수 문서와 screenshot으로 보완해라.

테스트 출력에 `Skipping`이 없어야 한다.

## 검수요약 문서

저장소 루트에 아래 문서를 작성해라.

- `DB코퍼스_UI4b_visibleCriticalFlowFix_검수요약.md`

포함할 내용:

- 사용자 제보 4개 문제별 해결 여부
- 수정 파일
- Step1 지원 형식 확인 결과
- Step2 가독성/대비 보정 내용
- Step3 target flow 보정 내용
- 스크린샷/viewport 검수 결과
- 실행한 테스트 명령
- 테스트 출력의 `Skipping` 여부
- 남은 이슈

## 검증 명령

환경에 맞는 Python 명령으로 아래를 실행해라.

```powershell
python -m py_compile main.py modules/step1_upload.py modules/step2_system_definition.py modules/step5_discrepancy.py modules/step6_dashboard.py modules/ui_db_corpus_helper.py
python test_step3_target_flow.py
python test_db_corpus_ui_state.py
python test_db_corpus_scale_validation.py
python test_step1_db_corpus_upload_adapter.py
python test_step6_db_corpus_auto_schema.py
python test_step6_db_corpus_oneclick_backtest.py
python test_showdown_db_extract_adapter.py
python test_db_corpus_backtest_report.py
python test_i15_integration_smoke.py
```

Streamlit 기동:

```powershell
streamlit run main.py
```

## 수용 기준

아래 조건을 모두 만족해야 한다.

- Step1이 CSV-only로 보이지 않는다.
- Step1 일반 업로드와 DB 코퍼스 업로드의 지원 형식이 실제 설정과 화면 문구 모두에서 일치한다.
- Step2 흰 배경/흰 글자 문제가 사라진다.
- Step2 주요 입력/선택/버튼/후보 공식이 hover 없이 읽힌다.
- Step3가 `target_col`을 정상 인식한다.
- Step3 target invalid 상태에서는 다음 단계 진행이 막힌다.
- 기존 DB 코퍼스 UI2/UI3 기준선이 깨지지 않는다.
- 테스트 출력에 `Skipping`이 없다.
- 검수요약 문서와 가능하면 스크린샷이 남는다.

## 금지/주의

- 이 PR에서 새 분석 기능을 추가하지 마라.
- 실제 대규모 코퍼스 검증을 이번 범위에 넣지 마라.
- DB adapter/replay stack 내부 로직을 불필요하게 변경하지 마라.
- manual backtest UI를 제거하지 마라.
- 새 랜딩 페이지를 만들지 마라.
- pycache, `.codex_tmp` 산출물, 대용량 DB/ZIP을 커밋 대상으로 만들지 마라.

## 완료 보고 형식

완료 후 다음 형식으로 보고해라.

```text
UI4b 완료 보고
- 변경 파일:
- Step1 업로드 형식:
- Step2 가독성:
- Step3 target flow:
- 흰 배경/흰 글자 대비:
- 화면 검수:
- 테스트:
- 테스트 출력의 Skipping 여부:
- 검수요약/스크린샷:
- 남은 이슈:
```
