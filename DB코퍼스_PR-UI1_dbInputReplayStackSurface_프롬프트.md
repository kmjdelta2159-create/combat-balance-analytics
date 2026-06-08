# DB코퍼스 PR-UI1 dbInputReplayStackSurface 프롬프트

## 역할

너는 이 저장소를 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수/프롬프트 작성 역할만 맡고 있으므로, 아래 요구사항을 기준으로 UI/UX 코드 수정, 테스트 추가, 스모크 실행, 결과 문서화를 수행해라.

## 현재 기준선

ADAPT8은 통과 상태다.

- 산출물 위치: `.codex_tmp/adapt8_multi_battle_replay`
- 다중 전투 smoke:
  - `battle_count=2`
  - `participant_count=24`
  - `state_event_count=244`
  - `damage_event_count=108`
  - `winner_sides` battle_id별 보존
  - `roster_only_entities=[]`
- 입력형식 parity:
  - `.db`, `.zip`, 폴더 입력 모두 논리 동등
  - `input_parity_report.json`의 `is_parity=true`
- backtest:
  - `accuracy_pct=100.0`
  - `outcome_mismatches=0`
  - `state_mismatches=0`
  - `state_checks=234`
- 통합 smoke:
  - Scenario A-H 통과
  - Scenario H에서 `_observed_status_trace`, `_observed_hp_trace`, `trace_actions["switch"]` payload 연결 확인

PR-UI1의 목표는 이 DB 코퍼스 파이프라인을 사용자가 Streamlit 화면에서 직접 사용할 수 있게 만드는 것이다.

## 목표

사용자가 기존 Streamlit 앱에서 Pokemon Showdown DB extract 입력을 직접 넣고, 변환/스키마/백테스트 결과를 화면에서 확인할 수 있는 UI 진입점을 추가해라.

핵심 흐름은 다음과 같다.

1. 사용자가 `.db` 또는 `.zip` 입력을 업로드한다.
2. 앱이 `modules.showdown_db_adapter`/기존 변환 파이프라인을 사용해 `battle_log.csv`, `schema.json`, `adapter_report.json`에 해당하는 데이터를 만든다.
3. 변환된 battle log를 `st.session_state["df"]`에 연결하고, 생성 schema/log_schema를 Step6 백테스트 기본값으로 연결한다.
4. 화면에서 adapter report, schema flags, backtest summary, mismatch report를 확인하고 다운로드할 수 있다.

## 작업 범위

### 1. Step1 업로드에 DB 코퍼스 빠른 입력 추가

현재 `modules/step1_upload.py`는 일반 CSV/Excel/JSON/TSV/TXT/Parquet 업로드 중심이다. 여기에 Pokemon Showdown DB 코퍼스 빠른 입력을 추가해라.

권장 UX:

- 기존 일반 전투 로그 업로드 영역과 별도 섹션으로 배치
- 이름 예시: `Pokemon Showdown DB 코퍼스 입력`
- 지원 입력:
  - SQLite `.db`
  - `.zip`
  - 로컬 개발/검수용 폴더 경로 입력은 선택 기능으로 제공 가능
- 업로드 후 버튼:
  - `DB 코퍼스 변환`
- 변환 완료 후 표시:
  - battle count
  - participant count
  - state event count
  - damage event count
  - winner sides 수
  - roster-only entities 수
  - warnings 수
  - unknown damage actor count
- 변환 성공 시 session state에 최소한 다음을 저장:
  - `df`: 변환된 battle log DataFrame
  - `current_file_name`
  - `db_corpus_adapter_report`
  - `db_corpus_schema`
  - `bb_last_corpus_schema`
  - `bb_last_log_schema`
  - `target_col`
  - `system_stats`
  - `system_gimmicks`
  - `health_stat`
  - 필요하면 `mapping_approved=True`

목표는 사용자가 수동 컬럼 매핑을 다시 하지 않아도 Step6의 DB 역할 컬럼 백테스트로 이어질 수 있게 하는 것이다.

### 2. Step6 Dashboard에 DB 코퍼스 결과 패널 추가

`modules/step6_dashboard.py`에는 이미 DB 역할 컬럼 기반 백테스트와 schema JSON 다운로드 흐름이 있다. 이를 덮어쓰지 말고, DB 코퍼스 입력이 감지되었을 때 상단 또는 백테스트 영역 근처에 compact panel을 추가해라.

패널 구성:

- `DB 코퍼스 입력 감지됨` 상태 표시
- adapter report metric grid
- schema flags 표시:
  - `trace_moves_enabled`
  - `state_trace_enabled`
  - `observed_status_trace_enabled`
  - `observed_hp_trace_enabled`
  - `observed_switch_trace_enabled`
- battle log preview table
- 다운로드 버튼:
  - `battle_log.csv`
  - `schema.json`
  - `adapter_report.json`
- backtest 실행 후:
  - `accuracy_pct`
  - `outcome_mismatches`
  - `state_mismatches`
  - `state_checks`
  - `next_action`
  - 첫 mismatch가 있으면 turn/id/kind/expected/actual 표시

이미 존재하는 mismatch report UI와 중복이 심하면 기존 mismatch report 컴포넌트를 재사용해라.

### 3. UI/UX 원칙

- 새 랜딩 페이지를 만들지 말고 기존 wizard 흐름에 통합해라.
- 카드 남발이나 설명문 중심 화면을 피하고, 작업자가 바로 업로드/변환/검수할 수 있는 조밀한 도구형 UI로 구성해라.
- 기존 Streamlit 다크 톤과 step navigation을 유지해라.
- 버튼/토글/탭/expander를 기존 스타일에 맞춰 사용해라.
- 오류 상태는 명확히 나누어 표시해라.
  - 입력 파일 파싱 실패
  - DB extract schema 불일치
  - 변환은 성공했지만 roster-only entities 존재
  - backtest mismatch 존재
- 긴 JSON은 화면에 전부 펼치지 말고 expander/code/download로 제공해라.
- 기존 CSV/Excel 일반 업로드 흐름을 깨지 마라.

### 4. 구현 가이드

가능하면 UI 코드에 변환 로직을 직접 많이 넣지 말고, 순수 helper를 분리해라.

권장 helper 예시:

- 업로드 파일을 임시 경로에 저장하는 함수
- DB/ZIP/folder 입력을 adapter output으로 변환하는 함수
- adapter report를 metric용 dict로 정규화하는 함수
- schema/log_schema를 session state에 적용하는 함수
- backtest summary row를 UI metric용으로 정규화하는 함수

임시 파일은 `.codex_tmp/ui1_db_corpus_surface` 아래에 둬라.

주의:

- Streamlit `file_uploader`의 file-like object를 그대로 SQLite 경로처럼 쓰지 마라. 반드시 안전한 임시 파일로 저장한 뒤 변환 파이프라인에 넘겨라.
- `.zip`은 zip 내부 구조를 기존 adapter가 처리하는 방식과 일치시켜라.
- 폴더 업로드는 브라우저에서 직접 어렵기 때문에, 필요하면 로컬 경로 입력을 개발/검수용 expander 안에만 둬라.
- 한 번 변환한 결과는 session state에 캐시하되, 업로드 파일명이 바뀌면 캐시를 무효화해라.

### 5. 테스트 요구사항

UI 자체는 Streamlit이라 전부 자동화하기 어렵더라도, 순수 helper는 테스트로 잠가라.

추가 또는 갱신할 테스트 후보:

- `test_step1_db_corpus_upload_adapter.py`
- `test_step6_db_corpus_surface.py`
- 기존 `test_showdown_db_extract_adapter.py`
- 기존 `test_db_corpus_backtest_report.py`
- 기존 `test_i15_integration_smoke.py`

테스트가 확인해야 할 것:

- `.db` 업로드 경로에서 battle log DataFrame, schema, adapter report가 반환된다.
- `.zip` 업로드 경로도 같은 핵심 값을 반환한다.
- session state에 적용될 payload가 `target_col`, `system_stats`, `system_gimmicks`, `bb_last_log_schema`를 포함한다.
- schema flags가 ADAPT8 기준과 동일하게 유지된다.
- 기존 일반 CSV/Excel 업로드 parser가 깨지지 않는다.
- Scenario A-H smoke가 계속 통과한다.

### 6. 검증 명령

환경에 맞는 Python 명령을 사용하되, 최소한 아래를 수행해라.

```powershell
python -m py_compile main.py modules/step1_upload.py modules/step6_dashboard.py modules/showdown_db_adapter.py modules/per_battle_backtest.py
python test_showdown_db_extract_adapter.py
python test_db_corpus_backtest_report.py
python test_i15_integration_smoke.py
```

새 테스트 파일을 추가했다면 개별 실행해라.

가능하면 Streamlit 앱도 실행해서 화면 확인을 남겨라.

```powershell
streamlit run main.py
```

화면 검수 시 최소 확인:

- Step1에서 DB 코퍼스 입력 섹션이 보이는지
- `.db` 또는 `.zip` 변환 버튼이 정상 동작하는지
- adapter report metrics가 표시되는지
- Step6에서 DB 코퍼스 schema/backtest 정보가 이어지는지
- 화면 폭이 좁아져도 주요 버튼/metric 텍스트가 겹치지 않는지

## 수용 기준

아래 조건을 모두 만족해야 한다.

- 사용자가 UI에서 `.db` 또는 `.zip`을 업로드해 battle log 변환을 시작할 수 있다.
- 변환 성공 후 `df`, schema, adapter report가 session state에 저장된다.
- Step6에서 DB 코퍼스 입력 상태와 adapter report가 보인다.
- Step6에서 기존 DB 역할 컬럼 백테스트를 수동 재매핑 없이 실행할 수 있거나, 최소한 생성 schema가 기본값으로 적용된다.
- `adapter_report.json`, `schema.json`, `battle_log.csv`를 다운로드할 수 있다.
- ADAPT8 backtest 기준선이 깨지지 않는다.
- 기존 일반 업로드 흐름이 깨지지 않는다.
- 새 UI helper 테스트와 기존 smoke 테스트가 통과한다.

## 금지/주의

- DB 코퍼스 변환 로직을 UI 안에 중복 구현하지 마라. 기존 adapter/CLI 로직을 재사용해라.
- ADAPT8의 observed status/HP/switch replay stack을 건드려 regression을 만들지 마라.
- UI 텍스트 인코딩을 더 악화시키지 마라. 새로 쓰는 한글 문구는 UTF-8로 정상 저장해라.
- pycache, 임시 산출물, 검수용 DB/ZIP을 커밋 대상으로 만들지 마라.
- 이번 PR에서 실제 다양한 배틀셋 정확도 확장은 하지 마라. UI surface가 목적이다.

## 완료 보고 형식

완료 후 다음 형식으로 결과를 보고해라.

```text
UI1 완료 보고
- 변경 파일:
- 추가 helper:
- 추가/갱신 테스트:
- UI 진입점:
- session state 연결:
- 다운로드 제공:
- 실행한 명령:
- Streamlit 화면 검수:
- 남은 이슈:
```
