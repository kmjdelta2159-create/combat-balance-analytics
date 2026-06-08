# DB코퍼스 PR-UI1c dbCorpusAutoSchemaRegressionLock 프롬프트

## 역할

너는 이 저장소를 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수/프롬프트 작성 역할만 맡고 있으므로, 아래 요구사항을 기준으로 UI/UX 코드 수정, 테스트 보강, 스모크 실행, 결과 문서화를 수행해라.

## 현재 UI1b 검수 결과

UI1b는 주요 기능 구현은 들어갔고 기존 기준선 테스트도 통과했다.

확인된 통과 항목:

- Step6 `전투 구성 방식` 라디오가 DB schema 감지 시 `DB 역할 컬럼으로 묶기`를 기본 선택하도록 변경됨.
- `bb_last_log_schema` 또는 `db_corpus_schema["log_schema"]`가 Step6의 `_bb_log_schema` 초기값으로 들어감.
- Step1 session state가 schema 기반 `system_stats`, `system_gimmicks`, `health_stat`, `target_col`로 정리됨.
- helper filename sanitize와 확장자 제한이 추가됨.
- 실행 확인:
  - `py_compile` 통과
  - `test_step1_db_corpus_upload_adapter.py` 통과
  - `test_step6_db_corpus_auto_schema.py` 통과
  - `test_showdown_db_extract_adapter.py` 통과
  - `test_db_corpus_backtest_report.py` 통과
  - `test_i15_integration_smoke.py` Scenario A-H 통과
  - Streamlit HTTP 200 응답 확인

하지만 회귀 테스트 품질에 중요한 빈틈이 남아 있다.

검수에서 확인된 문제:

1. `test_step1_db_corpus_upload_adapter.py`의 `.zip` 테스트가 실제 존재하지 않는 `.codex_tmp/adapt8_multi_battle_replay/pokemon_showdown_multi.zip`을 찾고 있어 스킵된다.
   - 실제 존재하는 zip은 `.codex_tmp/adapt8_multi_battle_replay/input_zip.zip`이다.
   - 따라서 `.zip` 업로드 자동 테스트는 현재 통과가 아니라 스킵이다.
2. `test_step6_db_corpus_auto_schema.py`는 실제 `modules.step6_dashboard` 구현 helper를 import하지 않고, 테스트 파일 내부에 복제한 함수만 검증한다.
   - 이 상태에서는 Step6 실제 코드가 깨져도 테스트가 통과할 수 있다.
3. Step6 DB 역할 컬럼 UI의 일부 기본값은 아직 schema key를 온전히 쓰지 않는다.
   - `result_mode`
   - `ally_values`
   - `enemy_values`
   - 다중 `sort_cols`
   - `move_order_col`
   - observed switch 관련 schema 표시/보존
4. `.zip` helper는 수동으로 직접 확인하면 정상이다.
   - `input_zip.zip` 기준 `rows=448`, `battle_count=2`, `participant_count=24`, observed status/HP/switch flag true
   - 하지만 자동 테스트에 잠겨 있지 않다.

## 목표

UI1c의 목표는 UI1b의 자동 DB schema 적용을 실제 구현 함수 기준으로 테스트에 잠그고, `.db`/`.zip` 업로드 회귀를 스킵 없이 검증하는 것이다.

이번 PR은 새 UI 기능 확장이 아니라 회귀 방어와 기본값 정합성 보강이다.

## 작업 범위

### 1. Step6 자동 schema helper를 실제 모듈 함수로 분리

`modules/step6_dashboard.py` 안의 DB schema 자동 적용 로직을 테스트 가능한 순수 helper로 분리해라.

권장 helper:

- `resolve_db_corpus_log_schema(session_state_like)`
- `has_db_corpus_schema(session_state_like, df=None)`
- `default_backtest_method_index(session_state_like, df=None)`
- `schema_col_default(log_schema, df_columns, schema_key, fallback_hints=None)`
- `schema_sort_cols_default(log_schema, df_columns)`
- `merge_db_corpus_log_schema(base_log_schema, db_corpus_log_schema, ui_flags)`

요구사항:

- helper는 Streamlit 객체에 의존하지 않아야 한다.
- 테스트는 반드시 이 실제 helper를 import해서 검증해야 한다.
- 테스트 파일 안에 동일 로직을 복제하지 마라.

### 2. `.zip` 테스트 스킵 제거

`test_step1_db_corpus_upload_adapter.py`의 `.zip` 테스트를 실제 fixture 경로와 일치시켜라.

우선순위:

1. `.codex_tmp/adapt8_multi_battle_replay/input_zip.zip`이 있으면 그것을 사용.
2. 없으면 테스트 fixture 생성 helper를 호출하거나, ADAPT8 fixture 생성 스크립트를 사용해 재생성.
3. 그래도 없으면 조용히 `return`으로 통과시키지 말고 명확한 실패 또는 actionable 메시지를 내라.

수용 기준:

- `.zip` 테스트는 스킵되면 안 된다.
- 테스트 출력에 `Skipping`이 나오면 실패로 간주한다.
- `.zip` 결과는 최소 아래를 assert해야 한다.
  - `len(df) == 448` 또는 `len(df) > 0`과 `battle_count == 2`
  - `participant_count == 24`
  - `schema["log_schema"]["observed_status_trace_enabled"] is True`
  - `schema["log_schema"]["observed_hp_trace_enabled"] is True`
  - `schema["log_schema"]["observed_switch_trace_enabled"] is True`

### 3. Step6 schema 기본값 정합성 보강

DB 코퍼스 schema가 있는 경우 Step6 기본값은 가능한 한 adapter schema와 일치해야 한다.

보강 대상:

- `result_mode`
- `ally_values`
- `enemy_values`
- `sort_cols`
- `move_order_col`
- `move_order_direction`
- `action_col`
- `move_action_values`
- `initial_on_field_col`
- `initial_on_field_values`
- `state_turn_col`
- `state_entity_id_col`
- `state_hp_col`
- `state_status_col`
- `state_fainted_col`

특히 `sort_cols`가 여러 개인 경우 첫 번째만 쓰지 말고 존재하는 schema sort cols 전체를 기본값으로 넣어라.

### 4. observed switch 상태 표시와 보존 확인

DB 코퍼스 schema는 legacy `trace_switches_enabled`가 아니라 observed replay 계열 키를 사용한다.

확인할 것:

- `observed_switch_trace_enabled=true`가 Step6 `_bb_log_schema`에 유지된다.
- legacy `switch trace 사용` 체크박스가 꺼져 있어도 observed switch replay가 꺼지지 않는다.
- `state snapshot trace 사용`을 끄면 observed status/HP/switch가 함께 꺼지는 현재 정책은 유지해도 된다. 단, DB 코퍼스 기본 상태에서는 켜져 있어야 한다.
- Step6 패널 또는 schema preview에서 observed switch flag가 true로 보인다.

### 5. 테스트 요구사항

필수 테스트:

- `test_step1_db_corpus_upload_adapter.py`
  - `.db` 업로드 테스트
  - `.zip` 업로드 테스트, 스킵 금지
  - filename sanitize 테스트
  - invalid extension 테스트
- `test_step6_db_corpus_auto_schema.py`
  - 실제 `modules.step6_dashboard` helper import
  - DB schema가 있으면 default method index가 1인지
  - DB schema가 없으면 default method index가 0인지
  - schema column defaults가 adapter schema 컬럼을 반환하는지
  - multi sort cols가 보존되는지
  - `merge_db_corpus_log_schema` 후 observed status/HP/switch flag가 true인지
  - state trace off override 시 observed flags가 false가 되는지

기존 기준선:

- `test_showdown_db_extract_adapter.py`
- `test_db_corpus_backtest_report.py`
- `test_i15_integration_smoke.py`

### 6. 검증 명령

환경에 맞는 Python 명령으로 아래를 모두 실행해라.

```powershell
python -m py_compile main.py modules/step1_upload.py modules/step6_dashboard.py modules/ui_db_corpus_helper.py modules/showdown_db_adapter.py modules/per_battle_backtest.py
python test_step1_db_corpus_upload_adapter.py
python test_step6_db_corpus_auto_schema.py
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

- DB 코퍼스 입력 후 Step6 기본 전투 구성 방식이 `DB 역할 컬럼으로 묶기`
- schema flags 표시에서 observed status/HP/switch true
- 다운로드 버튼 유지
- 기존 일반 업로드 UI가 깨지지 않음

## 수용 기준

아래 조건을 모두 만족해야 한다.

- `.zip` 업로드 테스트가 실제 실행되며 스킵되지 않는다.
- `test_step6_db_corpus_auto_schema.py`가 실제 `modules.step6_dashboard` helper를 import한다.
- DB schema 감지 시 Step6 default method index가 1이다.
- DB schema가 없으면 기존 default method index가 0이다.
- adapter schema의 주요 컬럼/값 기본값이 Step6에 반영된다.
- observed status/HP/switch flag가 기본 DB 코퍼스 모드에서 유지된다.
- 기존 ADAPT8 기준선 smoke가 깨지지 않는다.
- Streamlit 앱이 import/기동된다.

## 금지/주의

- 테스트 파일 내부에 실제 구현과 같은 helper를 복제하지 마라.
- `.zip` fixture가 없을 때 조용히 성공 처리하지 마라.
- 새 기능 확장이나 대규모 데이터 검증으로 범위를 넓히지 마라.
- 기존 일반 업로드 흐름을 깨지 마라.
- pycache, 임시 DB/ZIP, `.codex_tmp` 산출물을 커밋 대상으로 만들지 마라.

## 완료 보고 형식

완료 후 다음 형식으로 보고해라.

```text
UI1c 완료 보고
- 변경 파일:
- 실제 helper 분리:
- .zip 테스트:
- Step6 schema default:
- observed replay flags:
- 실행한 명령:
- 테스트 출력의 Skipping 여부:
- Streamlit 확인:
- 남은 이슈:
```
