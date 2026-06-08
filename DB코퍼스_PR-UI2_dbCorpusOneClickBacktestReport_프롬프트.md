# DB코퍼스 PR-UI2 dbCorpusOneClickBacktestReport 프롬프트

## 역할

너는 이 저장소를 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수/프롬프트 작성 역할만 맡고 있으므로, 아래 요구사항을 기준으로 UI/UX 코드 수정, 테스트 보강, 스모크 실행, 결과 문서화를 수행해라.

## 현재 기준선

UI1c는 통과 상태다.

- `.db` 업로드 helper 테스트 통과
- `.zip` 업로드 helper 테스트 통과, 스킵 없음
- filename sanitize/invalid extension 테스트 통과
- `test_step6_db_corpus_auto_schema.py`가 실제 `modules.step6_dashboard` helper를 import함
- DB schema 감지 시 Step6 default method index가 1
- observed status/HP/switch flag가 Step6 schema merge 후 유지됨
- ADAPT8 기준선 smoke Scenario A-H 통과
- Streamlit HTTP 200 응답 확인

현재 UI는 DB 코퍼스 업로드, 변환, schema 자동 적용까지는 연결됐다. UI2의 목표는 사용자가 Step6에서 별도 수동 매핑 패널을 만지지 않고, DB 코퍼스 감지 패널에서 바로 백테스트를 실행하고 결과 리포트를 받을 수 있게 만드는 것이다.

## 목표

Step6의 `DB 코퍼스 입력 감지 패널`에 one-click 백테스트 실행과 결과 리포트 표시/다운로드 기능을 추가해라.

사용자 흐름:

1. Step1에서 `.db` 또는 `.zip` 업로드
2. `DB 코퍼스 변환` 클릭
3. Step6로 이동
4. 상단 DB 코퍼스 패널에서 `DB 코퍼스 백테스트 실행` 클릭
5. 같은 패널에서 backtest summary, mismatch 요약, 다운로드를 즉시 확인

핵심은 기존 하단의 수동 per-battle backtest UI를 제거하는 것이 아니라, DB 코퍼스 입력이 있을 때 빠른 실행 경로를 제공하는 것이다.

## 작업 범위

### 1. DB 코퍼스 one-click backtest helper

Step6 UI에서 직접 복잡한 로직을 길게 쓰지 말고, 테스트 가능한 helper를 분리해라.

권장 helper:

- `run_db_corpus_backtest_from_session(session_state_like, max_battles=None)`
- 또는 순수 입력형:
  - `run_db_corpus_backtest_payload(df, schema, game_config, combat_flow, move_library, resource_config, ...)`
- `summarize_db_corpus_backtest_result(score_result)`
- `build_db_corpus_backtest_downloads(df, schema, adapter_report, summary, mismatch_rows)`

재사용 우선순위:

- 기존 `modules.per_battle_backtest.build_battles`
- 기존 `modules.per_battle_backtest.score_predictions`
- 기존 `_worker_simulate_match`
- 기존 Step6 per-battle backtest summary/mismatch row 생성 로직

새 CLI를 만들기보다 UI helper를 우선한다. 이미 CLI 함수가 명확히 재사용 가능하면 그쪽을 호출해도 된다.

### 2. Step6 패널 UI

`modules/step6_dashboard.py`의 DB 코퍼스 감지 패널에 아래를 추가해라.

표시:

- adapter report metric 유지
- replay stack flags 유지
- battle log preview 유지
- 다운로드 버튼 유지

추가 버튼:

- `DB 코퍼스 백테스트 실행`

버튼 실행 후 표시할 metric:

- `battle_count`
- `actual_count`
- `predicted_count`
- `accuracy_pct`
- `outcome_mismatches`
- `state_checks`
- `state_mismatches`
- `next_action`

mismatch가 있으면:

- 첫 mismatch의 `turn`
- `id`
- `kind`
- `expected`
- `actual`
- mismatch table preview

다운로드:

- `db_corpus_backtest_summary.csv`
- `db_corpus_mismatch_report.csv` 또는 mismatch rows가 없으면 빈 CSV
- 기존 `battle_log.csv`
- 기존 `schema.json`
- 기존 `adapter_report.json`

session state 저장:

- `db_corpus_last_backtest_summary`
- `db_corpus_last_mismatch_rows`
- `db_corpus_last_backtest_has_run=True`

### 3. UX 기준

- DB 코퍼스 패널은 조밀한 도구형 UI로 구성해라.
- 긴 설명문을 늘리지 마라.
- 기존 manual per-battle backtest UI는 유지하되, DB 코퍼스 입력이 감지되면 one-click 패널이 먼저 보이게 해라.
- 버튼/metric/다운로드가 좁은 화면에서 겹치지 않게 columns 수를 과도하게 늘리지 마라.
- mismatch가 0이면 명확히 성공 상태를 표시해라.
- mismatch가 있으면 경고 상태와 첫 mismatch를 바로 보여라.
- JSON/CSV는 expander 또는 download로 제공하고 화면에 지나치게 길게 펼치지 마라.

### 4. 결과 인코딩

새로 생성하는 CSV/JSON/Markdown 다운로드 문자열은 UTF-8 기준으로 만들어라.

주의:

- PowerShell 기본 출력에서 한글이 깨져 보여도 파일 자체는 UTF-8일 수 있다.
- 새 문서/다운로드에서 BOM 필요 여부는 앱 동작 기준으로 판단하되, 한글 column/header가 깨지지 않게 처리해라.
- summary markdown을 저장한다면 `encoding="utf-8"`로 작성해라.

### 5. 테스트 요구사항

필수 테스트:

- `test_step6_db_corpus_auto_schema.py`
  - 기존 helper 테스트 유지
- 새 테스트 파일 권장:
  - `test_step6_db_corpus_oneclick_backtest.py`

새 테스트가 확인해야 할 것:

- ADAPT8 `.db` fixture를 입력했을 때 one-click helper가 summary를 반환한다.
- ADAPT8 `.zip` fixture를 입력했을 때 one-click helper가 summary를 반환한다.
- `.db`와 `.zip` 결과가 핵심 지표에서 동일하다.
- summary 핵심값:
  - `battle_count=2`
  - `actual_count=2`
  - `predicted_count=2`
  - `accuracy_pct=100.0`
  - `outcome_mismatches=0`
  - `state_mismatches=0`
  - `state_checks=234`
- observed status/HP/switch flags가 helper 실행 시 유지된다.
- mismatch rows가 없을 때 빈 report 다운로드 데이터가 생성된다.
- 테스트 출력에 `Skipping`이 없어야 한다.

기존 기준선:

- `test_step1_db_corpus_upload_adapter.py`
- `test_showdown_db_extract_adapter.py`
- `test_db_corpus_backtest_report.py`
- `test_i15_integration_smoke.py`

### 6. 검증 명령

환경에 맞는 Python 명령으로 아래를 모두 실행해라.

```powershell
python -m py_compile main.py modules/step1_upload.py modules/step6_dashboard.py modules/ui_db_corpus_helper.py modules/showdown_db_adapter.py modules/per_battle_backtest.py
python test_step1_db_corpus_upload_adapter.py
python test_step6_db_corpus_auto_schema.py
python test_step6_db_corpus_oneclick_backtest.py
python test_showdown_db_extract_adapter.py
python test_db_corpus_backtest_report.py
python test_i15_integration_smoke.py
```

추가로 테스트 출력에 `Skipping`이 없는지 확인해라.

Streamlit 앱도 가능한 범위에서 확인해라.

```powershell
streamlit run main.py
```

화면 검수 포인트:

- Step6 DB 코퍼스 패널에 `DB 코퍼스 백테스트 실행` 버튼이 보인다.
- 버튼 실행 후 summary metric이 표시된다.
- mismatch 0이면 성공 상태가 표시된다.
- summary/mismatch 다운로드 버튼이 보인다.
- 기존 schema/adapter/battle_log 다운로드 버튼이 유지된다.

## 수용 기준

아래 조건을 모두 만족해야 한다.

- DB 코퍼스 입력 후 Step6 패널에서 one-click backtest를 실행할 수 있다.
- ADAPT8 `.db`와 `.zip` fixture가 one-click helper 테스트에서 모두 실행된다.
- `.db`와 `.zip` summary 핵심 지표가 동등하다.
- `accuracy_pct=100.0`, `outcome_mismatches=0`, `state_mismatches=0` 기준선이 유지된다.
- mismatch 0 상태와 다운로드 데이터가 UI/helper에서 정상 처리된다.
- 기존 manual per-battle backtest UI가 깨지지 않는다.
- 기존 일반 업로드 흐름이 깨지지 않는다.
- 테스트 출력에 `Skipping`이 없다.

## 금지/주의

- DB adapter 변환 로직을 중복 구현하지 마라.
- ADAPT8 replay stack 내부 로직을 불필요하게 변경하지 마라.
- manual per-battle backtest UI를 제거하지 마라.
- 새 랜딩 페이지를 만들지 마라.
- pycache, 임시 DB/ZIP, `.codex_tmp` 산출물을 커밋 대상으로 만들지 마라.

## 완료 보고 형식

완료 후 다음 형식으로 보고해라.

```text
UI2 완료 보고
- 변경 파일:
- one-click helper:
- Step6 UI:
- .db/.zip summary:
- mismatch/download 처리:
- 실행한 명령:
- 테스트 출력의 Skipping 여부:
- Streamlit 확인:
- 남은 이슈:
```
