# DB코퍼스 PR-ADAPT9 realCorpusScaleValidationReport 프롬프트

## 역할

너는 이 저장소를 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수/프롬프트 작성 역할만 맡고 있으므로, 아래 요구사항을 기준으로 코드 보강, 검증 스크립트/테스트 추가, 스모크 실행, 결과 문서화를 수행해라.

## 현재 기준선

UI2는 통과 상태다.

- Step1 DB 코퍼스 `.db`/`.zip` 업로드 helper 통과
- Step6 DB schema 자동 적용 통과
- Step6 one-click backtest helper 통과
- `.db`와 `.zip` summary 동등:
  - `battle_count=2`
  - `actual_count=2`
  - `predicted_count=2`
  - `accuracy_pct=100.0`
  - `outcome_mismatches=0`
  - `state_checks=234`
  - `state_mismatches=0`
  - `next_action=passed_or_low_mismatch`
- mismatch rows 0, 빈 mismatch CSV 생성 확인
- ADAPT8 smoke Scenario A-H 통과
- Streamlit HTTP 200 응답 확인

남은 핵심 위험:

- 현재 다중 전투 기준선은 실제 다양한 배틀 여러 개가 아니라, 1개 전투를 복제한 fixture 기반이다.
- 따라서 “실제 여러 배틀셋”에서 parser, roster mapping, winner_sides, observed replay stack, one-click backtest가 안정적으로 동작하는지는 아직 검증되지 않았다.

## 목표

Pokemon Showdown DB 코퍼스 파이프라인을 실제 다중 배틀 입력으로 확장 검증하고, 검수자가 한눈에 판단할 수 있는 scale validation report를 작성해라.

이번 PR은 새 UI 기능 확장이 아니라 실제 코퍼스 검증과 리포트 정비가 목적이다.

## 작업 범위

### 1. 실제 다중 배틀 입력 탐색

가능하면 로컬에 있는 실제 Pokemon Showdown DB extract 또는 zip/folder를 사용해라.

우선 탐색 후보:

- `C:\Users\kmjde\Downloads`
- 현재 workspace
- `.codex_tmp`
- 이미 생성된 `db_corpus_fixtures`

찾을 대상:

- battle_id가 2개 이상인 실제 `.db`
- battle_id가 2개 이상인 실제 `.zip`
- 여러 battle extract 폴더

주의:

- 실제 파일이 없으면 임의로 성공 처리하지 마라.
- 실제 다중 배틀 파일이 없으면 `real_corpus_unavailable` 상태로 보고하고, 어떤 경로를 확인했는지 남겨라.
- 복제 fixture 결과와 실제 코퍼스 결과를 분리해서 기록해라.

### 2. scale validation runner 추가

실제 코퍼스 또는 fixture 목록을 받아 일괄 검증하는 runner를 추가해라.

권장 파일:

- `run_db_corpus_scale_validation.py`

입력:

- 단일 `.db`
- 단일 `.zip`
- 폴더
- 여러 입력 경로를 담은 manifest JSON/CSV

출력 위치:

- `.codex_tmp/adapt9_real_corpus_scale_validation`

필수 산출물:

- `scale_validation_summary.csv`
- `scale_validation_summary.json`
- `scale_validation_mismatch_report.csv`
- `scale_validation_adapter_reports.json`
- `scale_validation_schema_flags.csv`
- `scale_validation_inputs.json`

각 입력별 기록할 항목:

- input_path
- input_kind
- status
- battle_count
- event_count
- participant_count
- move_count
- state_event_count
- damage_event_count
- winner_sides_count
- roster_only_entities_count
- unknown_damage_actor_count
- rows
- accuracy_pct
- outcome_mismatches
- state_checks
- state_mismatches
- next_action
- first_mismatch_turn
- first_mismatch_id
- first_mismatch_kind
- first_mismatch_expected
- first_mismatch_actual
- error

### 3. 실제 코퍼스와 fixture 구분

리포트에는 반드시 입력 출처를 구분해라.

- `real_corpus`
- `generated_fixture`
- `replicated_fixture`
- `unknown`

ADAPT8의 `pokemon_showdown_multi.db`와 `input_zip.zip`은 `replicated_fixture`로 표시해야 한다.

실제 다중 배틀 입력이 없다면, ADAPT9는 실패가 아니라 “blocked by unavailable real corpus”로 문서화해도 된다. 단, fixture smoke는 계속 통과해야 한다.

### 4. 리포트 문서 작성

저장소 루트에 검수 요약 문서를 작성해라.

- `DB코퍼스_ADAPT9_realCorpusScaleValidation_검수요약.md`

문서 포함 항목:

- 사용한 입력 목록과 출처 분류
- 실제 코퍼스 사용 여부
- 총 battle_count
- 입력별 summary 표
- `.db`/`.zip`/folder 결과 차이
- mismatch 총계
- 첫 mismatch 상세
- observed status/HP/switch flag 유지 여부
- one-click helper와 CLI/runner 결과 일치 여부
- 실행 명령
- 남은 위험
- 다음 PR 후보

인코딩:

- 파일은 UTF-8로 저장해라.
- PowerShell 출력이 깨져도 파일 자체는 UTF-8이어야 한다.
- CSV/JSON은 UTF-8 기준으로 작성해라.

### 5. 테스트 보강

기존 테스트는 유지하고, scale runner의 최소 단위 테스트를 추가해라.

권장 테스트:

- `test_db_corpus_scale_validation.py`

테스트가 확인할 것:

- ADAPT8 replicated fixture `.db` 입력을 runner가 처리한다.
- ADAPT8 replicated fixture `.zip` 입력을 runner가 처리한다.
- `.db`와 `.zip` 결과 핵심 지표가 동등하다.
- `source_kind` 또는 source classification이 `replicated_fixture`로 기록된다.
- `scale_validation_summary.csv/json`이 생성된다.
- mismatch report가 mismatch 0일 때도 빈 CSV로 생성된다.
- 테스트 출력에 `Skipping`이 없어야 한다.

실제 코퍼스가 없을 때:

- 실제 코퍼스 테스트는 optional이어도 된다.
- 하지만 optional 경로는 명확히 `real_corpus_unavailable`로 기록하고 조용히 성공 처리하지 마라.

### 6. 검증 명령

환경에 맞는 Python 명령으로 아래를 실행해라.

```powershell
python -m py_compile modules/showdown_db_adapter.py modules/per_battle_backtest.py modules/ui_db_corpus_helper.py run_db_corpus_scale_validation.py
python test_db_corpus_scale_validation.py
python test_step1_db_corpus_upload_adapter.py
python test_step6_db_corpus_auto_schema.py
python test_step6_db_corpus_oneclick_backtest.py
python test_showdown_db_extract_adapter.py
python test_db_corpus_backtest_report.py
python test_i15_integration_smoke.py
```

runner smoke 예시:

```powershell
python run_db_corpus_scale_validation.py --input .codex_tmp/adapt8_multi_battle_replay/pokemon_showdown_multi.db --input .codex_tmp/adapt8_multi_battle_replay/input_zip.zip --out .codex_tmp/adapt9_real_corpus_scale_validation
```

실제 코퍼스가 발견되면 해당 경로도 포함해 실행해라.

### 7. 수용 기준

아래 조건을 모두 만족해야 한다.

- scale validation runner가 존재한다.
- ADAPT8 replicated fixture `.db`와 `.zip`을 둘 다 처리한다.
- `.db`와 `.zip` fixture 결과가 핵심 지표에서 동등하다.
- summary CSV/JSON, mismatch CSV, adapter report JSON, schema flags CSV가 생성된다.
- 테스트 출력에 `Skipping`이 없다.
- 실제 코퍼스가 있으면 실제 코퍼스 결과가 리포트에 포함된다.
- 실제 코퍼스가 없으면 `real_corpus_unavailable` 상태와 탐색 경로가 문서화된다.
- 기존 UI2/ADAPT8 기준선 테스트가 깨지지 않는다.

## 금지/주의

- 실제 다양한 코퍼스 mismatch를 억지로 0으로 만들기 위해 parser/engine을 무리하게 수정하지 마라.
- 이번 PR에서 UI 기능을 새로 확장하지 마라.
- ADAPT8 replay stack 내부 로직을 불필요하게 변경하지 마라.
- `.codex_tmp` 산출물이나 대용량 DB/ZIP을 커밋 대상으로 만들지 마라.
- pycache를 커밋 대상으로 만들지 마라.
- 실제 코퍼스가 없는데 있는 것처럼 보고하지 마라.

## 완료 보고 형식

완료 후 다음 형식으로 보고해라.

```text
ADAPT9 완료 보고
- 변경 파일:
- runner:
- 입력 목록:
- 실제 코퍼스 사용 여부:
- fixture 결과:
- real corpus 결과:
- 산출물:
- mismatch 총계:
- 실행한 명령:
- 테스트 출력의 Skipping 여부:
- 남은 이슈:
```
