# DB코퍼스 PR-UI4e unifiedUploadAndFullReadability 프롬프트

## 역할

너는 이 저장소의 UI/UX 구현을 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수와 프롬프트 작성만 담당한다. 이번 작업은 이전 UI4c/UI4d 결과의 미흡한 부분을 바로잡는 후속 PR이다.

## 실패 판정

현재 결과는 아직 사용자가 기대한 UI/UX가 아니다.

1. `Pokemon Showdown DB 코퍼스 입력`을 일반 업로드와 별도 탭/별도 입력으로 둔 것 자체가 어색하다.
2. 사용자는 파일을 올리고 싶을 뿐, 먼저 "일반 전투 로그"인지 "Pokemon Showdown DB 코퍼스"인지 탭을 골라야 하는 흐름을 원하지 않는다.
3. 텍스트 가시성 개선도 완료되지 않았다.
4. 일부 큰 숫자만 밝아졌고, label/caption/disabled/help/placeholder/secondary text는 여전히 배경과 섞인다.

이번 PR은 **Step1 입력 구조 통합 + 전역 텍스트 가시성 완결**이 목표다.

## 핵심 방향

Step1은 하나의 업로드 표면이어야 한다.

사용자는 파일을 하나 올린다. 앱은 파일명/확장자/내용을 보고 자동으로 처리한다.

- `.db`, DB 코퍼스 `.zip`이면 Pokemon Showdown DB 코퍼스로 자동 처리
- `.csv`, `.xlsx`, `.xls`, `.json`, `.tsv`, `.txt`, `.parquet`이면 일반 전투 로그로 처리
- JSON 매핑 프리셋은 주 입력이 아니라 보조 옵션/expander로 둔다

즉, "Pokemon Showdown DB 코퍼스 입력"을 별도 탭으로 분리하지 마라.

## P0. Step1 업로드 UX 통합

### 필수 변경

현재 Step1의 탭 구조를 제거하거나, 최소한 주 업로드 흐름에서는 탭을 쓰지 마라.

단일 primary uploader를 제공하라.

권장 문구:

- 제목: `전투 로그 업로드`
- uploader label: `전투 로그 또는 Pokemon Showdown DB 코퍼스 파일`
- help: `지원 형식: CSV, Excel, JSON, TSV, TXT, Parquet, SQLite DB, ZIP`

지원 확장자:

```python
["csv", "xlsx", "xls", "json", "tsv", "txt", "parquet", "db", "zip"]
```

자동 분기:

- `*.db` 또는 `*.zip`
  - `modules.ui_db_corpus_helper.process_db_corpus_upload(...)`로 처리
  - 성공 시 `db_corpus_adapter_report`, `db_corpus_schema`, `bb_last_log_schema`, `target_col`, `system_stats`, `system_gimmicks`, `health_stat`, `mapping_approved`를 기존 DB 코퍼스 자동 스키마 흐름과 동일하게 세팅
  - Step6 자동 백테스트 가능 상태를 유지
- 나머지 확장자
  - 기존 `_parse_log_file(...)`로 처리
  - 일반 mapping flow로 진행

### 보조 옵션

아래 항목은 주 흐름 아래의 접힌 expander에 넣어라.

- 선택: 별도 무브 로그 업로드
- 선택: 기존 매핑 프리셋 JSON 불러오기

주의:

- 보조 옵션이 주 입력보다 먼저 눈에 띄면 안 된다.
- DB 코퍼스 전용 탭/전용 페이지처럼 보이면 실패다.
- "다음 단계로 이동하려면 전투 로그 파일을 업로드해야 합니다" 같은 안내는 DB 코퍼스에도 맞는 표현으로 바꿔라.
  - 예: `전투 로그 또는 DB 코퍼스 파일을 업로드해야 합니다.`

### 수용 기준

- Step1 첫 화면에서 일반 로그와 DB 코퍼스가 하나의 입력으로 받아진다는 점이 즉시 이해된다.
- 사용자는 `.db`/`.zip`을 올리기 위해 별도 탭을 찾지 않아도 된다.
- `.db`/`.zip` 업로드 후 기존 DB 코퍼스 자동 변환/자동 스키마/Step6 백테스트 흐름이 유지된다.
- 일반 CSV/Excel/JSON 업로드 후 기존 Step2 매핑 흐름이 유지된다.

## P0. 텍스트 가시성 전면 재검수

이전 PR은 일부 큰 숫자만 개선했다. 이번에는 앱 전체의 text role을 정리하라.

### 반드시 고쳐야 하는 계열

- heading
- section title
- tab label
- expander header
- uploader label/help/placeholder
- input/select/multiselect 내부 값
- multiselect tag/pill
- checkbox/radio/toggle label
- metric label/value/delta
- caption
- sidebar caption/status
- disabled button text
- disabled input text
- alert/info/warning 내부 텍스트
- dataframe/table header/cell text
- chart axis/category/legend label

### 현재 스크린샷에서 아직 문제가 보이는 예

Step1:

- `DB 추출 파일 (.db, .zip)` label이 배경에 묻힘
- uploader 내부 `Upload`, `200MB per file · DB, ZIP`이 너무 흐림
- 잠긴 Step indicator의 텍스트가 흐림
- disabled `다음 단계로` 버튼 텍스트가 흐림

Step2:

- `타겟 컬럼`, `카테고리/기믹 (Gimmicks)` 같은 label이 거의 안 보임
- selectbox 내부 placeholder/value가 흐림
- expander/header 주변 텍스트가 흐림
- disabled/secondary 상태 텍스트가 배경과 섞임

Dashboard:

- metric value 일부만 선명하고 label/caption은 아직 약함
- sidebar File/Target/Stats/Gimmicks caption이 충분히 선명하지 않음
- toggle/disabled/help text가 흐림

### 구현 지침

공통 CSS에서 semantic token을 사용하라.

권장:

```css
:root {
  --app-bg: #0e1117;
  --sidebar-bg: #161a22;
  --panel-bg: #111827;
  --surface-light: #f8fafc;
  --text-primary: #f8fafc;
  --text-secondary: #d1d5db;
  --text-muted: #a7b0be;
  --text-disabled: #8b95a5;
  --text-on-light: #1f2937;
  --border-subtle: #30363d;
}
```

실제 색상은 앱 톤에 맞춰 조정해도 된다. 단, 대비가 충분해야 한다.

금지:

- `span`, `p`, `label` 전체를 무조건 흰색으로 만드는 방식
- 밝은 입력창/테이블 내부 텍스트를 흰색으로 만드는 방식
- 특정 숫자나 특정 문구만 개별 style로 고치는 방식
- disabled text를 읽을 수 없을 정도로 흐리게 만드는 방식

## P0. 실제 화면 검수 필수

HTTP 200만으로 완료하지 마라. 반드시 브라우저 화면을 확인하고 스크린샷을 남겨라.

필수 viewport:

- desktop 1366x768 이상
- mobile/narrow 390x844 또는 430x932

필수 스크린샷:

- `.codex_tmp/ui4e_unified_upload_contrast/step1_unified_empty_desktop.png`
- `.codex_tmp/ui4e_unified_upload_contrast/step1_unified_db_uploaded_desktop.png`
- `.codex_tmp/ui4e_unified_upload_contrast/step1_unified_csv_uploaded_desktop.png`
- `.codex_tmp/ui4e_unified_upload_contrast/step2_mapping_desktop.png`
- `.codex_tmp/ui4e_unified_upload_contrast/step2_formula_desktop.png`
- `.codex_tmp/ui4e_unified_upload_contrast/step5_dashboard_desktop.png`
- `.codex_tmp/ui4e_unified_upload_contrast/mobile_step1.png`
- `.codex_tmp/ui4e_unified_upload_contrast/mobile_step2.png`
- `.codex_tmp/ui4e_unified_upload_contrast/mobile_dashboard.png`

각 스크린샷에서 다음을 눈으로 체크하라.

- 모든 label/caption/help/disabled text가 hover 없이 읽히는가
- 밝은 uploader/input/table 내부 텍스트가 배경과 충돌하지 않는가
- 어두운 배경 위 secondary text가 너무 흐리지 않은가
- DB 코퍼스 입력이 별도 탭처럼 분리되어 있지 않은가

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

추가/보강 권장:

- Step1 단일 uploader가 `db`, `zip`, `csv`, `xlsx`, `json`, `tsv`, `txt`, `parquet` 확장자를 모두 받는지 테스트하라.
- `.db`/`.zip` 업로드 분기가 `process_db_corpus_upload`로 가는지 테스트하라.
- 일반 로그 업로드 분기가 `_parse_log_file`로 가는지 테스트하라.

`Skipping`이 있으면 검수요약에 사유를 적고, 가능하면 제거하라.

## 검수요약 문서

루트에 아래 파일을 작성하라.

- `DB코퍼스_UI4e_unifiedUploadAndFullReadability_검수요약.md`

포함 내용:

- 수정 파일
- Step1 통합 업로드 구조 설명
- `.db`/`.zip` 자동 분기 확인 결과
- 일반 로그 자동 분기 확인 결과
- 텍스트 가시성 보정 selector/token 요약
- Step1~Step5 화면별 가시성 확인 결과
- 스크린샷 경로
- 실행한 테스트 명령과 결과
- `Skipping` 발생 여부
- 남은 이슈

## 금지

- DB 코퍼스 입력을 별도 탭/별도 주 흐름으로 유지하지 마라.
- 일반 로그와 DB 코퍼스 중 하나만 우선시하는 UI를 만들지 마라.
- 새 분석 기능을 추가하지 마라.
- DB adapter/replay/backtest 계산 로직을 불필요하게 바꾸지 마라.
- 큰 숫자만 개별 style로 고치고 완료 처리하지 마라.
- pycache, 대용량 임시 파일, 무관한 데이터 파일을 커밋 대상으로 만들지 마라.

## 완료 보고 형식

```text
UI4e 완료 보고

1. 수정 파일
- ...

2. Step1 통합 업로드
- ...

3. 자동 분기 확인
- DB/ZIP:
- 일반 로그:

4. 텍스트 가시성
- ...

5. 스크린샷
- ...

6. 테스트 결과
- ...

7. 남은 이슈
- ...
```
