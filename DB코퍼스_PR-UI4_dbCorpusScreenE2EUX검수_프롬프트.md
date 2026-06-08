# DB코퍼스 PR-UI4 dbCorpusScreenE2EUX검수 프롬프트

## 역할

너는 이 저장소를 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수/프롬프트 작성 역할만 맡고 있으므로, 아래 요구사항을 기준으로 UI/UX 검수, 필요한 소규모 안정화 수정, 테스트 보강, 화면 검수 문서화를 수행해라.

## 현재 기준선

UI3까지 통과 또는 부분 검수 완료 상태다.

- Step1 DB 코퍼스 업로드 탭이 일반 업로드와 분리됨.
- Step6 DB 코퍼스 패널이 Summary / Replay Flags / Downloads / Preview / Mismatch 구조로 정리됨.
- one-click backtest 통과.
- `.db` / `.zip` replicated fixture 결과 동등.
- `accuracy_pct=100.0`
- `outcome_mismatches=0`
- `state_checks=234`
- `state_mismatches=0`
- ADAPT9 runner summary의 `move_count` 누락이 보정됨.
- `.db` / `.zip` 모두 `move_count=72`.
- `test_db_corpus_scale_validation.py` 통과.
- `test_step6_db_corpus_oneclick_backtest.py` 통과.

현재 남은 핵심은 실제 대규모 코퍼스가 아니라, **현재 UI가 실제 화면에서 작업자가 쓰기에 충분히 명확하고 안정적인지** 확인하는 것이다.

## 목표

Streamlit 앱을 실제로 실행해서 Step1부터 Step6까지 DB 코퍼스 사용자 흐름을 화면 기준으로 검수하고, 화면/상태/다운로드/재실행 흐름의 불편이나 깨짐을 보정해라.

이번 PR은 새 분석 기능 추가가 아니라 **화면 E2E 검수와 UX 안정화**가 목적이다.

## 핵심 사용자 흐름

검수할 실제 흐름:

1. `streamlit run main.py`로 앱 실행
2. Step1 진입
3. `Pokemon Showdown DB 코퍼스 업로드` 탭 선택
4. `.db` fixture 업로드
5. `DB 코퍼스 변환` 실행
6. 변환 성공 상태 확인
7. Step6로 이동
8. DB 코퍼스 감지 패널 확인
9. `DB 코퍼스 전체 백테스트 실행` 클릭
10. Summary / Replay Flags / Downloads / Preview / Mismatch 탭 확인
11. summary/mismatch 다운로드 버튼 확인
12. `.zip` fixture도 동일 흐름으로 반복 확인
13. 다른 파일 업로드 시 이전 백테스트 결과가 초기화되는지 확인
14. 일반 전투 로그 업로드 탭으로 전환했을 때 DB 코퍼스 state가 잘 초기화되는지 확인

## 작업 범위

### 1. Streamlit E2E 화면 검수

가능하면 Playwright 또는 Streamlit-compatible browser automation을 사용해 화면을 실제로 검수해라.

검수 대상 fixture:

- `.codex_tmp/adapt8_multi_battle_replay/pokemon_showdown_multi.db`
- `.codex_tmp/adapt8_multi_battle_replay/input_zip.zip`

검수 항목:

- 앱이 HTTP 200으로 기동되는지
- Step1의 일반 업로드 탭과 DB 코퍼스 업로드 탭이 명확히 구분되는지
- `.db` 업로드 후 변환 성공 metric이 표시되는지
- `.zip` 업로드 후 변환 성공 metric이 표시되는지
- Step6에서 DB 코퍼스 감지 상태줄이 보이는지
- Summary 탭에서 one-click 백테스트 버튼이 보이는지
- 백테스트 실행 후 `Accuracy 100.0%`, `Outcome Mismatches 0`, `State Mismatches 0 / 234`가 표시되는지
- Replay Flags 탭에서 observed status/HP/switch가 true로 보이는지
- Downloads 탭에서 아래 버튼들이 보이는지
  - `db_corpus_battle_log.csv`
  - `db_corpus_schema.json`
  - `db_corpus_adapter_report.json`
  - `db_corpus_backtest_summary.csv`
  - `db_corpus_mismatch_report.csv`
- Preview 탭이 100행 이하 미리보기를 안정적으로 표시하는지
- Mismatch 탭이 mismatch 0일 때 “Mismatch 없음” 상태를 보여주는지

### 2. 화면 밀도와 반응형 UX 점검

최소 두 viewport에서 확인해라.

- desktop: 1366x768 또는 유사
- narrow/mobile-ish: 390x844 또는 430x932

확인할 것:

- metric 텍스트가 겹치지 않음
- 버튼 텍스트가 잘리지 않음
- 탭 라벨이 너무 길어 화면을 깨지 않음
- expander 내부 JSON/traceback이 화면을 밀어내지 않음
- 다운로드 버튼이 과밀하지 않음
- 오류 메시지와 성공 메시지가 한 화면에서 구분됨

필요하면 UI를 소폭 조정해라.

허용되는 조정:

- 탭 라벨 축약
- metric column 수 조정
- 긴 문구 축약
- traceback을 expander 안으로 이동
- success/warning/info 상태 문구 정리
- 다운로드 버튼을 2열 또는 3열로 재배치
- preview height 제한

금지:

- 새 랜딩 페이지 생성
- 기존 wizard 구조 제거
- manual per-battle backtest UI 제거
- DB adapter/replay stack 내부 로직 변경

### 3. UI state 안정성 검수

다음 상태 전환을 실제로 확인하고, 필요하면 보정해라.

- `.db` 변환 후 one-click backtest 실행
- `.zip`으로 다시 변환하면 이전 `.db` backtest summary가 초기화됨
- 변환 실패 시 이전 성공 결과가 계속 성공처럼 보이지 않음
- 일반 전투 로그 업로드를 사용하면 DB 코퍼스 관련 state가 초기화됨
- one-click backtest 재실행 시 이전 mismatch rows가 덮어써짐

세션 키 확인 대상:

- `db_corpus_adapter_report`
- `db_corpus_schema`
- `bb_last_corpus_schema`
- `bb_last_log_schema`
- `db_corpus_last_backtest_summary`
- `db_corpus_last_mismatch_rows`
- `db_corpus_last_backtest_has_run`

### 4. 다운로드 결과 검수

UI 또는 helper 테스트로 다운로드 데이터가 올바른지 확인해라.

필수 확인:

- `db_corpus_backtest_summary.csv`에 `accuracy_pct=100.0`
- `db_corpus_backtest_summary.csv`에 `state_mismatches=0`
- `db_corpus_mismatch_report.csv`는 mismatch 0이어도 header가 있음
- `db_corpus_schema.json`에 observed status/HP/switch flag가 true
- CSV/JSON은 UTF-8 기준

### 5. 검수 산출물 작성

저장소 루트에 검수 요약 문서를 작성해라.

- `DB코퍼스_UI4_dbCorpusScreenE2EUX검수요약.md`

문서 포함 항목:

- 실행한 앱 URL
- 사용한 fixture
- 확인한 viewport
- Step1 검수 결과
- Step6 검수 결과
- one-click backtest 결과
- 다운로드 검수 결과
- state 초기화 검수 결과
- 발견한 UX 문제와 보정 내용
- 실행한 테스트 명령
- 남은 이슈

가능하면 screenshot 저장:

- `.codex_tmp/ui4_db_corpus_screen_e2e/step1_db_upload.png`
- `.codex_tmp/ui4_db_corpus_screen_e2e/step6_summary.png`
- `.codex_tmp/ui4_db_corpus_screen_e2e/step6_downloads.png`
- `.codex_tmp/ui4_db_corpus_screen_e2e/mobile_summary.png`

브라우저 자동화가 불가능하면:

- HTTP 200 기동 확인
- DOM/Streamlit 상태 확인 가능한 범위
- 수동 검수 필요 항목

을 문서에 명확히 남겨라.

### 6. 테스트 요구사항

기존 테스트 유지:

- `test_db_corpus_scale_validation.py`
- `test_step1_db_corpus_upload_adapter.py`
- `test_step6_db_corpus_auto_schema.py`
- `test_step6_db_corpus_oneclick_backtest.py`
- `test_showdown_db_extract_adapter.py`
- `test_db_corpus_backtest_report.py`
- `test_i15_integration_smoke.py`

가능하면 추가:

- `test_db_corpus_ui_state.py`

추가 테스트가 확인할 것:

- DB 코퍼스 새 변환 payload가 이전 backtest summary를 초기화함
- 다운로드 CSV helper가 mismatch 0일 때 header를 유지함
- schema flag가 다운로드 JSON에 유지됨

테스트 출력에 `Skipping`이 없어야 한다.

### 7. 검증 명령

환경에 맞는 Python 명령으로 아래를 실행해라.

```powershell
python -m py_compile main.py modules/step1_upload.py modules/step6_dashboard.py modules/ui_db_corpus_helper.py modules/showdown_db_adapter.py modules/per_battle_backtest.py run_db_corpus_scale_validation.py
python test_db_corpus_scale_validation.py
python test_step1_db_corpus_upload_adapter.py
python test_step6_db_corpus_auto_schema.py
python test_step6_db_corpus_oneclick_backtest.py
python test_showdown_db_extract_adapter.py
python test_db_corpus_backtest_report.py
python test_i15_integration_smoke.py
```

새 테스트를 추가했다면 함께 실행해라.

Streamlit 기동:

```powershell
streamlit run main.py
```

## 수용 기준

아래 조건을 모두 만족해야 한다.

- Streamlit 앱이 기동된다.
- Step1 DB 코퍼스 업로드 흐름이 화면에서 확인된다.
- Step6 DB 코퍼스 one-click backtest 흐름이 화면에서 확인된다.
- `.db`와 `.zip` fixture 모두 화면 또는 E2E helper로 검수된다.
- desktop/narrow viewport에서 주요 UI가 겹치지 않는다.
- 다운로드 데이터가 올바르다.
- state 초기화 흐름이 검증된다.
- 기존 테스트가 모두 통과한다.
- 테스트 출력에 `Skipping`이 없다.
- 검수요약 문서가 작성된다.

## 금지/주의

- 새 분석 기능을 추가하지 마라.
- 실제 대규모 코퍼스 검증을 이번 PR 범위에 넣지 마라.
- DB adapter/replay stack 내부 로직을 불필요하게 변경하지 마라.
- manual backtest UI를 제거하지 마라.
- 새 랜딩 페이지를 만들지 마라.
- pycache, `.codex_tmp` 산출물, 대용량 DB/ZIP을 커밋 대상으로 만들지 마라.

## 완료 보고 형식

완료 후 다음 형식으로 보고해라.

```text
UI4 완료 보고
- 변경 파일:
- 화면 검수:
- viewports:
- Step1 결과:
- Step6 결과:
- 다운로드 검수:
- state 초기화:
- 테스트:
- 테스트 출력의 Skipping 여부:
- 스크린샷/검수요약:
- 남은 이슈:
```
