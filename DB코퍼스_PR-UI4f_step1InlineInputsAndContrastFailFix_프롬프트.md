# DB코퍼스 PR-UI4f step1InlineInputsAndContrastFailFix 프롬프트

## 역할

너는 이 저장소의 UI/UX 구현을 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수와 프롬프트 작성만 담당한다. 이번 작업은 UI4e 결과의 미흡함을 바로잡는 후속 PR이다.

## 실패 판정

현재 UI4e 결과는 아직 통과가 아니다.

사용자 확인 결과:

1. 텍스트 가시성 문제가 여전히 남아 있다.
2. `무브 로그 업로드`와 `저장한 매핑 불러오기`가 보조 옵션이라는 이유로 접히거나 분리된 흐름처럼 취급될 이유가 없다.
3. Step1의 업로드 화면은 통합된 것처럼 보이지만, 실제로는 label/help/placeholder가 너무 흐려 사용자가 무엇을 올리는지 즉시 읽기 어렵다.
4. uploader 내부 `Upload`, `200MB per file`, 확장자 안내가 배경과 섞인다.
5. 하단 `다음 단계로` disabled 버튼 텍스트도 아직 흐리다.

이번 PR은 **Step1 입력 구조를 단순한 inline 입력 흐름으로 고정**하고, **텍스트 대비 실패를 실제 화면 기준으로 끝까지 수정**하는 작업이다.

## 핵심 UX 원칙

Step1은 파일 입력을 위한 작업 화면이다. 사용자는 이 화면에서 필요한 파일들을 한눈에 보고 올릴 수 있어야 한다.

따라서 다음을 금지한다.

- DB 코퍼스 입력을 별도 탭으로 분리
- 무브 로그 업로드를 접힌 expander 안에 숨김
- 매핑 프리셋 불러오기를 접힌 expander 안에 숨김
- 보조 파일 입력을 "고급 옵션"처럼 감춤
- 의미 없는 접힘/빈 expander/흰색 빈 바를 남김

## P0. Step1 입력 구조 수정

### 원하는 구조

Step1은 하나의 수직 흐름으로 구성하라.

1. 메인 파일 업로드
   - 일반 전투 로그 또는 Pokemon Showdown DB 코퍼스 파일
   - 지원: CSV, Excel, JSON, TSV, TXT, Parquet, DB, ZIP
   - `.db`/`.zip`은 DB 코퍼스로 자동 분기
   - 나머지는 일반 전투 로그로 자동 분기

2. 무브 로그 업로드
   - 선택 입력이지만 접지 말고 바로 보이게 둔다.
   - "없으면 건너뛰어도 된다"는 문구는 짧게, uploader 바로 위나 아래에 둔다.
   - 메인 업로드보다 시각적 위계는 낮아야 하지만 숨기면 안 된다.

3. 매핑 프리셋 불러오기
   - 선택 입력이지만 접지 말고 바로 보이게 둔다.
   - JSON만 받는다.
   - 기존 매핑을 불러오는 보조 입력이라는 점을 명확히 표시한다.

### 레이아웃 지침

- 탭 금지.
- expander 금지.
- 의미 없는 큰 빈 카드/빈 바 금지.
- 세 입력을 같은 화면 폭과 같은 컴포넌트 패턴으로 정렬하라.
- 각 섹션은 제목, 1줄 설명, uploader 순서로 간단하게 구성하라.
- 메인 업로드만 primary 영역처럼 약간 더 강조하고, 나머지는 inline secondary section으로 둔다.
- 카드 안에 카드를 넣지 마라.
- 화면 첫 viewport에서 세 입력의 존재가 모두 파악되어야 한다.

### 권장 문구

메인:

- 제목: `전투 로그 업로드`
- label: `전투 로그 또는 DB 코퍼스 파일`
- help/description: `CSV, Excel, JSON, TSV, TXT, Parquet, DB, ZIP 지원`

무브 로그:

- 제목: `무브 로그 업로드 (선택)`
- label: `무브 로그 파일`
- description: `무브별 행 데이터가 있으면 업로드하세요. 없으면 비워둬도 됩니다.`

프리셋:

- 제목: `매핑 프리셋 불러오기 (선택)`
- label: `매핑 프리셋 JSON`
- description: `이전에 저장한 매핑을 복원할 때만 사용합니다.`

하단 경고:

- `전투 로그 또는 DB 코퍼스 파일을 업로드해야 합니다.`

## P0. Step1 가시성 실패 수정

현재 스크린샷 기준 다음이 실패다.

- `전투 로그 또는 Pokemon Showdown DB 코퍼스 파일` label이 거의 안 보임
- uploader 내부 확장자 안내가 거의 안 보임
- `무브 로그 파일`, `매핑 프리셋 파일 (JSON)` label이 거의 안 보임
- `Upload` 버튼 텍스트/아이콘이 너무 흐림
- disabled `다음 단계로` 버튼 텍스트가 흐림
- 상단 step indicator에서 locked step 텍스트가 지나치게 흐림
- sidebar status 외 작은 caption이 흐림

필수 수정:

- file uploader label/help/placeholder/value/button 모두 hover 없이 읽히게 하라.
- 선택 입력 label도 primary text에 가까운 대비를 유지하라.
- secondary description은 약하게 하되 읽을 수 있어야 한다.
- disabled button은 비활성임을 알 수 있으면서도 텍스트가 읽혀야 한다.
- locked step indicator도 단계명을 읽을 수 있어야 한다.
- sidebar caption/status 작은 텍스트도 읽혀야 한다.

## P0. 전역 가시성 재검수

Step1만 고치고 끝내지 마라. 이전부터 남은 전역 문제가 계속 재발하고 있다.

반드시 다음 상태를 확인하고 보정하라.

- dark background 위 label/caption/help/disabled text
- light uploader/input/table 위 내부 텍스트
- selectbox/multiselect value와 placeholder
- multiselect tag/pill
- expander header가 남아 있다면 header text
- tabs가 남아 있다면 tab text
- metric label/value/delta
- chart axis/category label
- dataframe header/cell text

금지:

- 특정 문구만 inline style로 하드코딩
- 큰 숫자만 밝게 만들기
- 모든 `span`, `p`, `label`을 무조건 흰색으로 덮기
- 밝은 컴포넌트 내부 글자를 흰색으로 만들기
- disabled text를 거의 보이지 않게 만들기

## P0. 실제 브라우저 검수 필수

HTTP 200만으로 완료하지 마라. 반드시 실제 브라우저 화면을 보고 스크린샷을 남겨라.

필수 스크린샷:

- `.codex_tmp/ui4f_step1_inline_contrast/step1_empty_desktop.png`
- `.codex_tmp/ui4f_step1_inline_contrast/step1_db_uploaded_desktop.png`
- `.codex_tmp/ui4f_step1_inline_contrast/step1_csv_uploaded_desktop.png`
- `.codex_tmp/ui4f_step1_inline_contrast/step2_mapping_desktop.png`
- `.codex_tmp/ui4f_step1_inline_contrast/step5_dashboard_desktop.png`
- `.codex_tmp/ui4f_step1_inline_contrast/mobile_step1.png`
- `.codex_tmp/ui4f_step1_inline_contrast/mobile_step2.png`

필수 체크리스트:

- Step1에 탭이 없는가
- Step1에 무의미한 접힘/빈 expander/흰색 빈 바가 없는가
- 메인 업로드, 무브 로그, 매핑 프리셋이 모두 inline으로 보이는가
- uploader label/help/placeholder가 hover 없이 읽히는가
- disabled `다음 단계로` 버튼 텍스트가 읽히는가
- locked step indicator가 읽히는가
- Step2 selectbox/multiselect label이 읽히는가
- Dashboard metric label/caption이 읽히는가

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

추가 권장:

- Step1 단일 uploader의 supported type 목록 검증
- `.db`/`.zip` 자동 분기 검증
- 일반 로그 자동 분기 검증
- 무브 로그 uploader가 일반 로그 parser를 사용하는지 검증
- 프리셋 uploader가 JSON만 받는지 검증

## 검수요약 문서

루트에 아래 파일을 작성하라.

- `DB코퍼스_UI4f_step1InlineInputsAndContrastFailFix_검수요약.md`

포함 내용:

- 수정 파일
- Step1 구조 변경 전/후 요약
- 탭/expander/빈 바 제거 여부
- 세 입력 inline 노출 여부
- 가시성 보정 selector/token 요약
- 사용자 스크린샷 기준 실패 항목별 해결 여부
- 스크린샷 경로
- 실행한 테스트 명령과 결과
- `Skipping` 발생 여부
- 남은 이슈

## 완료 보고 형식

```text
UI4f 완료 보고

1. 수정 파일
- ...

2. Step1 입력 구조
- 탭 제거:
- expander/빈 바 제거:
- 메인/무브/프리셋 inline 노출:

3. 가시성 해결 여부
- uploader label/help:
- Upload 버튼:
- disabled 다음 단계:
- locked step indicator:
- Step2 label:
- Dashboard caption/metric label:

4. 스크린샷
- ...

5. 테스트 결과
- ...

6. 남은 이슈
- ...
```
