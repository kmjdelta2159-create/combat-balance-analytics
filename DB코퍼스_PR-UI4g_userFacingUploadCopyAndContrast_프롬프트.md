# DB코퍼스 PR-UI4g userFacingUploadCopyAndContrast 프롬프트

## 역할

너는 이 저장소의 UI/UX 구현을 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수와 프롬프트 작성만 담당한다. 이번 작업은 UI4f 결과의 미흡함을 바로잡는 후속 PR이다.

## 실패 판정

현재 화면은 아직 통과가 아니다.

사용자 확인 결과:

1. 텍스트 가시성 문제가 여전히 남아 있다.
2. Step1 메인 uploader label에 `전투 로그 또는 Pokemon Showdown DB 코퍼스 파일` 같은 문장이 노출된다.
3. `Pokemon Showdown DB 코퍼스 파일`은 내부 구현/검증 용어에 가깝고, 사용자가 보는 업로드 문구로는 부자연스럽다.
4. 일반 사용자에게는 `.db`, `.zip`까지 지원하는 “전투 데이터 파일”로 안내하는 것이 맞다.
5. uploader label/help/placeholder, 작은 설명문, disabled text가 여전히 배경과 충분히 대비되지 않는다.

이번 PR은 **사용자-facing 업로드 문구 정리 + 남은 가시성 문제 완결**이 목표다.

## P0. 사용자-facing 문구에서 내부 용어 제거

Step1 화면의 사용자-facing 문구에서 아래 표현을 제거하라.

- `Pokemon Showdown DB 코퍼스 파일`
- `Pokemon Showdown DB 코퍼스`
- `DB 코퍼스 파일`
- `DB 코퍼스`
- `코퍼스 파일`

주의:

- 내부 변수명, 테스트명, schema key, helper 함수명은 유지해도 된다.
- 사용자 화면에 보이는 제목/label/help/alert/caption/button 문구에서만 제거하라.
- `.db`, `.zip` 지원 자체는 유지해야 한다.
- 검수요약 문서나 개발자용 설명에서는 DB 코퍼스라는 말을 써도 된다.

### 권장 사용자-facing 문구

메인 섹션:

- 제목: `전투 로그 업로드`
- 설명: `전투 데이터 파일을 업로드하면 형식에 맞춰 자동으로 처리합니다.`
- uploader label: `전투 데이터 파일`
- help/placeholder: `지원 형식: CSV, Excel, JSON, TSV, TXT, Parquet, DB, ZIP`

하단 경고:

- 기존: `전투 로그 또는 DB 코퍼스 파일을 업로드해야 합니다.`
- 변경: `전투 데이터 파일을 업로드해야 합니다.`

성공 메시지:

- `.db`/`.zip` 처리 성공 시에도 사용자에게는 `DB 코퍼스`보다 `전투 데이터 변환 완료` 또는 `전투 데이터 업로드 완료`처럼 표현하라.
- 단, 상세 검수/개발 로그에는 내부 분기명을 남겨도 된다.

## P0. Step1 구조 유지 조건

Step1은 지금처럼 세 입력이 inline으로 보이는 방향은 맞다. 다만 문구와 대비가 실패했다.

유지:

- 메인 전투 데이터 업로드
- 무브 로그 업로드 (선택)
- 매핑 프리셋 불러오기 (선택)
- 탭 없음
- expander 없음

수정:

- 메인 uploader label에서 내부 용어 제거
- 세 uploader label/help/placeholder 대비 개선
- 설명문 대비 개선
- disabled 다음 단계 버튼 대비 개선
- step indicator locked text 대비 개선

## P0. 가시성 실패 항목

현재 스크린샷 기준 다음은 실패다.

- `전투 로그 또는 Pokemon Showdown DB 코퍼스 파일` label이 너무 어둡고 문구도 부적절함
- `무브 로그 파일` label이 너무 어두움
- `매핑 프리셋 JSON` label이 너무 어두움
- uploader 내부 `Upload` 버튼 텍스트/아이콘이 흐림
- uploader 내부 `200MB per file · ...` 안내는 보이지만 더 선명해야 함
- locked step indicator 텍스트가 어둡고 단계명이 잘 안 읽힘
- 하단 disabled `다음 단계로` 버튼은 읽히지만 비활성/활성 상태 구분이 충분히 명확하지 않음
- 전체적으로 작은 label/caption/help text가 배경과 섞임

필수 수정:

- uploader label은 최소 `--text-secondary` 이상 대비로 표시하라.
- uploader help/extension text는 `--text-muted`라도 확실히 읽혀야 한다.
- disabled text는 `--text-disabled`를 쓰되 배경과 3:1에 가깝게 맞춰라.
- locked step indicator는 잠김 상태를 표현하되 단계명은 읽을 수 있어야 한다.
- 모든 Step1 label/help/placeholder는 hover 없이 읽혀야 한다.

## P0. 전역 selector 보정

특정 문구에 inline style을 박지 말고, Streamlit 컴포넌트 selector를 보정하라.

필수 확인 selector 후보:

```css
[data-testid="stFileUploader"]
[data-testid="stFileUploader"] label
[data-testid="stFileUploader"] small
[data-testid="stFileUploader"] span
[data-testid="stFileUploader"] button
[data-testid="stMarkdownContainer"]
[data-testid="stCaptionContainer"]
[data-testid="stButton"]
button:disabled
[aria-disabled="true"]
[data-testid="stHeader"]
[data-testid="stSidebar"]
label
small
```

Streamlit DOM이 다르면 실제 브라우저 inspector 기준으로 맞는 selector를 사용하라.

금지:

- 모든 `span`을 흰색으로 만드는 전역 덮어쓰기
- 밝은 uploader/input/table 내부 텍스트를 흰색으로 만드는 처리
- 특정 텍스트만 하드코딩 style로 밝게 만드는 처리

## P1. Step2/Dashboard 가시성도 재확인

이번 실패는 Step1에서 보이지만, 이전부터 Step2/Dashboard에도 같은 문제가 반복됐다. Step1만 고치고 끝내지 마라.

반드시 다음도 재확인하라.

- Step2 selectbox/multiselect label
- Step2 placeholder/value
- Step2 disabled/secondary text
- Dashboard metric label/caption
- sidebar File/Target/Stats/Gimmicks caption
- chart/table label

## 검수 요구사항

HTTP 200만으로 완료하지 마라. 실제 브라우저 화면을 보고 스크린샷을 남겨라.

필수 스크린샷:

- `.codex_tmp/ui4g_upload_copy_contrast/step1_empty_desktop.png`
- `.codex_tmp/ui4g_upload_copy_contrast/step1_csv_uploaded_desktop.png`
- `.codex_tmp/ui4g_upload_copy_contrast/step1_db_uploaded_desktop.png`
- `.codex_tmp/ui4g_upload_copy_contrast/step2_mapping_desktop.png`
- `.codex_tmp/ui4g_upload_copy_contrast/step5_dashboard_desktop.png`
- `.codex_tmp/ui4g_upload_copy_contrast/mobile_step1.png`

스크린샷 검수 체크리스트:

- Step1 사용자-facing 문구에 `Pokemon Showdown`, `DB 코퍼스`, `코퍼스 파일`이 보이지 않는가
- `.db`, `.zip` 지원 안내는 남아 있는가
- 메인/무브/프리셋 uploader label이 hover 없이 읽히는가
- uploader 내부 help/extension text가 hover 없이 읽히는가
- disabled `다음 단계로` 버튼 텍스트가 읽히는가
- locked step indicator가 읽히는가
- Step2/Dashboard의 작은 label/caption도 읽히는가

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

- 화면 문자열 grep 또는 테스트로 사용자-facing Step1 문구에 `Pokemon Showdown`, `DB 코퍼스`, `코퍼스 파일`이 남지 않았는지 확인하라.
- `.db`/`.zip` 자동 분기는 그대로 동작하는지 확인하라.

## 검수요약 문서

루트에 아래 파일을 작성하라.

- `DB코퍼스_UI4g_userFacingUploadCopyAndContrast_검수요약.md`

포함 내용:

- 수정 파일
- 제거한 사용자-facing 내부 용어 목록
- 최종 Step1 문구
- `.db`/`.zip` 지원 유지 확인
- 가시성 보정 selector/token 요약
- Step1/Step2/Dashboard 가시성 확인 결과
- 스크린샷 경로
- 실행한 테스트 명령과 결과
- `Skipping` 발생 여부
- 남은 이슈

## 완료 보고 형식

```text
UI4g 완료 보고

1. 수정 파일
- ...

2. 사용자-facing 문구 정리
- 제거:
- 최종 문구:

3. 업로드 지원 유지
- DB/ZIP:
- 일반 로그:

4. 가시성 해결 여부
- Step1 uploader label/help:
- disabled button:
- step indicator:
- Step2:
- Dashboard:

5. 스크린샷
- ...

6. 테스트 결과
- ...

7. 남은 이슈
- ...
```
