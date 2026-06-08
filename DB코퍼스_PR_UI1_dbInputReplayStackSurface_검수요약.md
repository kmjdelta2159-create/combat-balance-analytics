# DB코퍼스 PR-UI1 dbInputReplayStackSurface 검수 요약

## 1. UI 진입점 추가
- `modules/step1_upload.py`에 일반 전투 로그 업로드 하단 별도의 "Pokemon Showdown DB 코퍼스 입력" 섹션을 추가했습니다.
- 지원 포맷: SQLite `.db` 및 추출된 CSV를 포함한 `.zip`
- 사용자가 복잡한 매핑 과정을 거치지 않고, 파일 업로드 및 "DB 코퍼스 변환" 버튼 클릭만으로 즉시 추출, 변환, 스키마 생성을 완료할 수 있게 구현했습니다.

## 2. Session State 연결 및 자동 매핑
- 변환 완료 시 다음 데이터를 `st.session_state`에 자동 연결했습니다:
  - `df`: 변환된 `battle_log_df`
  - `db_corpus_adapter_report`, `db_corpus_schema`
  - `bb_last_corpus_schema`, `bb_last_log_schema`
  - `target_col`, `system_stats`, `system_gimmicks`, `health_stat` 기본값 세팅
  - `mapping_approved=True`
- 이를 통해 Step 2~5의 과정 생략 및 Step 6으로의 다이렉트 백테스트 연결이 가능해졌습니다.

## 3. Step 6 Dashboard 패널 추가 및 다운로드 제공
- `modules/step6_dashboard.py` 상단에 DB 코퍼스 입력이 감지되면 나타나는 **DB 코퍼스 입력 감지 패널**을 추가했습니다.
- 표시되는 내용:
  - Adapter Report Metrics (Battles, Participants, Events 등)
  - 활성화된 Replay Stack 플래그 (`observed_status_trace`, `observed_hp_trace` 등)
  - 100행 분량의 Battle Log 미리보기
- 산출물 다운로드: `battle_log.csv`, `schema.json`, `adapter_report.json` 파일을 다운로드할 수 있는 버튼 3개를 제공합니다.

## 4. 추가/갱신 테스트
- **추가 테스트**: `test_step1_db_corpus_upload_adapter.py`
  - UI 렌더링 코드와 독립된 순수 헬퍼 `ui_db_corpus_helper.py`의 동작을 검증합니다.
  - ADAPT8에서 쓰인 `.db` fixture를 입력받아 battle count >= 2 확인 및 schema의 trace flag 확인 통과.
- **기존 테스트**:
  - `test_showdown_db_extract_adapter.py`, `test_db_corpus_backtest_report.py`, `test_i15_integration_smoke.py` 모두 성공.

## 5. 남은 이슈 및 향후 과제
- 로컬 파일 시스템 경로가 아닌 브라우저 업로드를 통하므로 파일이 클 경우 브라우저 메모리에 일시적 부하가 있을 수 있습니다. 초대용량 DB 파일에 대한 최적화(Chunk 처리 등)는 향후 확장 영역입니다.
- Streamlit 환경에서의 다중 배틀 백테스트 실행 시 결과 렌더링에 필요한 기존 Streamlit UI(Mismatch Report 등) 요소들이 잘 융화되는지 수동 E2E 테스트가 필요합니다.
