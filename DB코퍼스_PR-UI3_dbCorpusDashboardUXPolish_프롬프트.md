# DB코퍼스 PR-UI3 dbCorpusDashboardUXPolish 프롬프트

## 역할

너는 이 저장소를 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수/프롬프트 작성 역할만 맡고 있으므로, 아래 요구사항을 기준으로 UI/UX 코드 수정, 테스트 보강, 스모크 실행, 결과 문서화를 수행해라.

## 현재 기준선

ADAPT9 검수 결과:

- scale validation runner 생성됨
- `.db` / `.zip` replicated fixture 처리 통과
- `accuracy_pct=100.0`
- `outcome_mismatches=0`
- `state_checks=234`
- `state_mismatches=0`
- observed status/HP/switch flag 유지
- 실제 다중 배틀 코퍼스는 없음
  - `real_corpus_unavailable`
  - 기존 후보들은 battle_count 1이라 대규모 검증 조건 미달

UI2 기준선:

- Step1 DB 코퍼스 업로드 가능
- Step6 DB schema 자동 적용 가능
- Step6 one-click backtest 가능
- summary/mismatch CSV 다운로드 가능
- 기존 Scenario A-H smoke 통과

검수 중 발견된 작은 리포트 무결성 이슈:

- `scale_validation_adapter_reports.json`에는 `move_count=72`가 정상 기록됨.
- 하지만 `scale_validation_summary.csv/json`에는 `move_count=0`으로 기록됨.
- 원인은 `run_db_corpus_scale_validation.py`에서 `row["move_count"] = report.get("move_count", 0)` 할당이 빠진 것으로 보임.
- 이 이슈는 core backtest 정확도 문제가 아니라 리포트 필드 누락이다.

## 목표

실제 대규모 코퍼스 확보가 지연되는 동안, DB 코퍼스 UI/UX 작업 순서를 앞당긴다.

UI3의 목표는 다음 두 가지다.

1. ADAPT9의 작은 리포트 필드 누락을 선행 보정해 검수 리포트 신뢰도를 맞춘다.
2. Step1/Step6 DB 코퍼스 화면을 실제 작업자가 반복 사용하기 편한 도구형 UI로 다듬는다.

이번 PR은 새 분석 알고리즘 확장이 아니라 UX polish와 report integrity 보강이 목적이다.

## 작업 범위

### 1. ADAPT9 리포트 무결성 선행 보정

`run_db_corpus_scale_validation.py`에서 summary row에 `move_count`를 올바르게 기록해라.

수용 기준:

- `scale_validation_summary.csv/json`의 `move_count`가 adapter report의 `move_count`와 일치해야 한다.
- ADAPT8 replicated fixture 기준 `.db`와 `.zip` 모두 `move_count=72`여야 한다.
- `test_db_corpus_scale_validation.py`에 `move_count` assert를 추가해라.

### 2. Step1 DB 코퍼스 업로드 UX 정리

`modules/step1_upload.py`의 DB 코퍼스 입력 섹션을 더 실사용 중심으로 다듬어라.

요구사항:

- 일반 전투 로그 업로드와 DB 코퍼스 업로드가 서로 헷갈리지 않게 섹션 구분을 명확히 해라.
- DB 코퍼스 변환 성공 후 즉시 핵심 상태가 보여야 한다.
  - Battles
  - Participants
  - Events
  - State Events
  - Damage Events
  - Roster-only count
  - Unknown damage actor count
- 변환 성공 후 “Step6에서 백테스트 가능” 상태가 분명히 보여야 한다.
- 변환 실패 시 에러와 입력 형식 문제를 명확히 분리해서 보여라.
- 긴 traceback은 기본 노출하지 말고 expander 안에 넣어라.

주의:

- 기존 일반 CSV/Excel 업로드 흐름은 유지해라.
- 일반 업로드를 하면 DB 코퍼스 session state가 초기화되는 기존 흐름은 유지하되, 초기화 범위가 과도하지 않은지 확인해라.

### 3. Step6 DB 코퍼스 패널 UX 정리

`modules/step6_dashboard.py`의 DB 코퍼스 감지 패널을 작업자가 빠르게 판단할 수 있게 정리해라.

권장 구조:

- 상단 상태줄:
  - DB 코퍼스 입력 감지됨
  - battle_count
  - accuracy 또는 “백테스트 미실행”
  - mismatch 상태
- 탭 또는 expander:
  - `Summary`
  - `Replay Flags`
  - `Downloads`
  - `Preview`
  - `Mismatch`

필수 표시:

- adapter report metrics
- observed status/HP/switch flags
- one-click backtest button
- backtest summary metrics
- mismatch 0 성공 상태
- first mismatch가 있으면 compact alert
- report downloads

UX 기준:

- metric column을 너무 많이 나열해 좁은 화면에서 겹치지 않게 해라.
- 반복 설명문을 줄이고, 버튼/상태/리포트 중심으로 구성해라.
- 현재 앱의 Streamlit wizard 흐름을 유지해라.
- 새 랜딩 페이지를 만들지 마라.
- 카드형 장식 UI보다 조밀한 작업 도구 UI를 우선해라.

### 4. 다운로드/리포트 이름 정리

다운로드 파일명이 일관되게 보여야 한다.

권장 파일명:

- `db_corpus_battle_log.csv`
- `db_corpus_schema.json`
- `db_corpus_adapter_report.json`
- `db_corpus_backtest_summary.csv`
- `db_corpus_mismatch_report.csv`

CSV/JSON은 UTF-8 기준으로 생성해라.

mismatch가 없을 때:

- 빈 mismatch CSV라도 header는 있어야 한다.
- 화면에는 “Mismatch 없음” 상태가 보여야 한다.

### 5. UI state 안정성

다음 상태 전환을 점검해라.

- DB 코퍼스 업로드 후 Step6 이동
- 다른 DB 코퍼스 파일 업로드 시 이전 backtest summary 초기화
- 일반 전투 로그 업로드 시 DB 코퍼스 state 초기화
- DB 코퍼스 변환 실패 시 이전 성공 결과가 잘못 남지 않음
- one-click backtest 재실행 시 이전 mismatch rows가 덮어써짐

### 6. 테스트 요구사항

기존 테스트 유지:

- `test_step1_db_corpus_upload_adapter.py`
- `test_step6_db_corpus_auto_schema.py`
- `test_step6_db_corpus_oneclick_backtest.py`
- `test_db_corpus_scale_validation.py`
- `test_showdown_db_extract_adapter.py`
- `test_db_corpus_backtest_report.py`
- `test_i15_integration_smoke.py`

보강할 테스트:

- `test_db_corpus_scale_validation.py`
  - summary `move_count`가 72인지 assert
- UI helper/state 테스트가 가능하면 추가:
  - DB 코퍼스 변환 성공 payload에 필요한 session keys가 있는지
  - 새 파일 변환 시 `db_corpus_last_backtest_has_run` 등 이전 결과가 초기화되는지
  - mismatch 없는 다운로드 CSV에 header가 있는지

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

runner smoke:

```powershell
python run_db_corpus_scale_validation.py --input .codex_tmp/adapt8_multi_battle_replay/pokemon_showdown_multi.db --input .codex_tmp/adapt8_multi_battle_replay/input_zip.zip --out .codex_tmp/ui3_db_corpus_dashboard_ux
```

Streamlit 앱도 가능한 범위에서 확인해라.

```powershell
streamlit run main.py
```

화면 검수 포인트:

- Step1 DB 코퍼스 섹션이 일반 업로드와 명확히 구분됨
- 변환 성공 상태가 직관적으로 보임
- Step6 DB 코퍼스 패널이 Summary/Flags/Downloads/Preview/Mismatch 흐름으로 읽힘
- one-click backtest 버튼과 결과가 같은 패널 안에서 자연스럽게 이어짐
- 좁은 화면에서도 버튼/metric 텍스트가 겹치지 않음

## 수용 기준

아래 조건을 모두 만족해야 한다.

- ADAPT9 summary의 `move_count`가 adapter report와 일치한다.
- replicated fixture `.db`와 `.zip` 모두 `move_count=72`로 기록된다.
- Step1 DB 코퍼스 업로드 UX가 일반 업로드와 명확히 분리된다.
- Step6 DB 코퍼스 패널에서 상태, one-click backtest, 다운로드, mismatch 상태를 한눈에 볼 수 있다.
- 기존 one-click backtest 기준선이 깨지지 않는다.
- 기존 일반 업로드 흐름이 깨지지 않는다.
- 테스트 출력에 `Skipping`이 없다.
- Streamlit 앱이 import/기동된다.

## 금지/주의

- 실제 대규모 코퍼스 검증을 이번 PR에 억지로 포함하지 마라.
- DB adapter/replay stack 내부 로직을 불필요하게 변경하지 마라.
- manual per-battle backtest UI를 제거하지 마라.
- 새 랜딩 페이지를 만들지 마라.
- pycache, `.codex_tmp` 산출물, 대용량 DB/ZIP을 커밋 대상으로 만들지 마라.

## 완료 보고 형식

완료 후 다음 형식으로 보고해라.

```text
UI3 완료 보고
- 변경 파일:
- ADAPT9 report integrity:
- Step1 UX:
- Step6 UX:
- 다운로드/리포트:
- state 안정성:
- 실행한 명령:
- 테스트 출력의 Skipping 여부:
- Streamlit 확인:
- 남은 이슈:
```
