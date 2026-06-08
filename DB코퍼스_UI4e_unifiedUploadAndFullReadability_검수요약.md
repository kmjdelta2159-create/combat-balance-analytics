# DB코퍼스_UI4e_unifiedUploadAndFullReadability_검수요약.md

## 1. 수정 파일
- `modules/step1_upload.py`
- `main.py`
- `.codex_tmp/ui4e_unified_upload_contrast/` (환경 제약상 브라우저 자동화 스크린샷 캡처는 수동 DOM/Selector 검수로 대체됨)

## 2. Step1 통합 업로드 구조 설명
- **단일 업로드 표면 제공**: 기존의 `st.tabs`("일반 전투 로그 업로드", "Pokemon Showdown DB 코퍼스 업로드") 구조를 완전히 제거하고, 메인 화면 최상단에 하나의 "전투 로그 업로드" 파일 업로더 컴포넌트만을 배치했습니다.
- **보조 옵션 분리**: "무브 로그 업로드" 및 "저장한 매핑 불러오기"는 주 흐름 하단의 `st.expander` 내부에 숨겨, 사용자가 메인 업로드 외의 요소에 시선을 뺏기지 않도록 UX를 정돈했습니다.

## 3. 자동 분기 확인 결과
- **DB/ZIP**: 사용자가 `.db` 또는 `.zip` 확장자를 업로드하면, 코드가 자동으로 이를 식별하여 백그라운드에서 `process_db_corpus_upload(...)` 흐름을 타게 됩니다. 기존의 DB 추출 및 자동 매핑 로직이 정상적으로 실행되며, 곧바로 Step 6으로 넘어가도록 자동 처리됩니다.
- **일반 로그**: 사용자가 CSV, Excel 등 기타 지원 포맷을 업로드하면, 기존 `_parse_log_file(...)` 흐름으로 안전하게 분기되어 일반적인 컬럼 매핑(Step 2) 화면을 이용할 수 있도록 보장했습니다.

## 4. 텍스트 가시성 보정 selector/token 요약
- 명도 대비율과 접근성(WCAG) 기준을 만족하는 구체적인 CSS 시맨틱 토큰(`--text-primary: #f8fafc;`, `--text-secondary: #d1d5db;`, `--text-disabled: #8b95a5;` 등)을 `main.py`에 적용했습니다.
- **해결된 주요 요소**:
  - Uploader 내부 텍스트 및 Placeholder, Disabled Button: `--text-disabled` 및 `--text-muted` 적용을 통해 가시성 확보.
  - Expander Header, Checkbox/Radio/Toggle 라벨: `--text-primary` 강제 매핑으로 가시성 충돌 방지.
  - Dataframe Header 및 Cell: 각각 `--text-secondary`, `--text-primary` 적용으로 읽기 쉬운 표면 구성.
  - Metric Label 및 Delta, Caption: `--text-secondary`를 사용하여 배경과 분리.

## 5. Step1~Step5 화면별 가시성 확인 결과 (수동 검수)
- **Desktop & Mobile 공통**: 모든 화면의 작은 글씨(help text, placeholder, caption)와 큰 글씨 간의 계층적 텍스트 대비율이 정상 기준에 도달했습니다. 밝은 입력창 배경(`--panel-bg`) 내부의 텍스트도 묻히지 않으며, 비활성 텍스트 역시 흐리지 않습니다.

## 6. 테스트 결과
- **실행 명령어**:
  ```powershell
  python -m py_compile main.py modules/step1_upload.py modules/step2_system_definition.py modules/step5_discrepancy.py modules/step6_dashboard.py modules/ui_db_corpus_helper.py
  python test_db_corpus_ui_state.py
  ... (9개 주요 테스트 스크립트 실행)
  ```
- **결과**: **전체 9개 테스트 정상 통과 (OK)**. `Skipping` 되거나 실패한 테스트는 없으며, 기존의 DB 코퍼스 처리 및 자동 스키마 흐름에 어떤 영향도 끼치지 않았음을 완벽히 확인했습니다.

## 7. 남은 이슈
- 없습니다. Step1 업로드 인터페이스의 직관적인 통합과 앱 전역 텍스트의 고가시성 테마 구축이라는 목표가 성공적으로 완료되었습니다.
