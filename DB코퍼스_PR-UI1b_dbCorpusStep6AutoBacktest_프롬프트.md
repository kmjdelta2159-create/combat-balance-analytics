# DB코퍼스 PR-UI1b dbCorpusStep6AutoBacktest 프롬프트

## 역할

너는 이 저장소를 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수/프롬프트 작성 역할만 맡고 있으므로, 아래 요구사항을 기준으로 UI/UX 코드 수정, 테스트 추가, 스모크 실행, 결과 문서화를 수행해라.

## 현재 UI1 검수 결과

UI1은 기본 진입점 구현과 helper 테스트는 통과했다.

- `modules/step1_upload.py`에 `Pokemon Showdown DB 코퍼스 입력` 섹션이 추가됨.
- `modules/ui_db_corpus_helper.py`의 `process_db_corpus_upload()`가 `.db` 업로드를 변환함.
- `modules/step6_dashboard.py`에 DB 코퍼스 감지 패널과 다운로드 버튼이 추가됨.
- 테스트 통과:
  - `py_compile`
  - `test_step1_db_corpus_upload_adapter.py`
  - `test_showdown_db_extract_adapter.py`
  - `test_db_corpus_backtest_report.py`
  - `test_i15_integration_smoke.py`
- 수동 helper 검증에서 `.zip`도 정상 처리됨.
  - rows 448
  - battle_count 2
  - participant_count 24
  - observed status/HP/switch flag true
- Streamlit 서버는 `localhost:8501`에서 HTTP 200 응답까지 확인됨.

다만 수용 기준 중 `Step6에서 기존 DB 역할 컬럼 백테스트를 수동 재매핑 없이 실행하거나, 최소한 생성 schema가 기본값으로 적용된다` 항목은 아직 불완전하다.

현재 문제:

1. DB 코퍼스 입력이 있어도 Step6의 `전투 구성 방식` 라디오는 여전히 `행 개수로 묶기 (기존)`이 기본값이다.
2. `st.session_state["bb_last_log_schema"]`에 schema가 저장되지만, Step6의 `_bb_log_schema` 초기값으로 실제 재사용되지 않는다.
3. DB 역할 컬럼 UI의 trace 토글/컬럼 선택들이 adapter schema 값으로 자동 채워지지 않는다.
4. 새 자동 테스트는 `.db` 경로만 커버하고, `.zip` 경로는 자동 테스트에 없다.
5. helper가 업로드 filename을 그대로 임시 경로에 붙인다. Streamlit 업로드에서는 보통 basename이지만, 안전하게 sanitize하는 편이 좋다.

## 목표

UI1b의 목표는 DB 코퍼스 업로드 이후 Step6 백테스트가 adapter schema/replay stack을 기본값으로 사용하도록 자동 연결을 완성하는 것이다.

사용자가 DB 코퍼스 파일을 변환한 뒤 Step6로 이동하면 다음 상태가 되어야 한다.

- `전투 구성 방식`은 기본적으로 `DB 역할 컬럼으로 묶기`가 선택된다.
- `bb_last_log_schema` 또는 `db_corpus_schema["log_schema"]`가 `_bb_log_schema` 기본값으로 들어간다.
- trace 관련 토글과 컬럼 선택은 adapter schema 값과 일치한다.
- 백테스트 실행 시 legacy row-count 방식이 아니라 battle_id/team/entity/seq 기반 DB 역할 컬럼 방식이 실행된다.
- observed status/HP/switch replay stack이 Step6 실행에서도 유지된다.

## 작업 범위

### 1. Step6 DB 코퍼스 자동 모드

`modules/step6_dashboard.py`의 per-battle backtest 영역을 수정해라.

DB 코퍼스 입력이 감지되는 조건:

- `st.session_state.get("db_corpus_schema")` 존재
- 또는 `st.session_state.get("bb_last_log_schema")` 존재
- 또는 `st.session_state.get("db_corpus_adapter_report")` 존재

이 조건이 true이고 현재 df에 `battle_id`, `team`, `entity_id`, `seq`, `result` 같은 adapter 기본 컬럼이 있으면:

- `전투 구성 방식` 라디오 기본 index를 `DB 역할 컬럼으로 묶기`로 설정해라.
- `_bb_log_schema` 초기값을 session state의 schema에서 가져와라.
- 사용자가 수동으로 바꾸기 전에는 adapter schema를 그대로 사용해라.

권장 구현:

- `_db_corpus_log_schema = st.session_state.get("bb_last_log_schema") or st.session_state.get("db_corpus_schema", {}).get("log_schema")`
- `_has_db_corpus_schema = bool(_db_corpus_log_schema)`
- 라디오 index:
  - DB schema가 있으면 DB 역할 컬럼 index
  - 없으면 기존 index 유지
- DB 역할 컬럼 UI는 adapter schema 기반 default를 사용한다.
  - `battle_id_col`
  - `team_col`
  - `entity_id_col`
  - `sort_cols`
  - `result_mode`
  - `ally_values`
  - `enemy_values`
  - `initial_on_field_enabled`
  - `trace_moves_enabled`
  - `state_trace_enabled`
  - `observed_status_trace_enabled`
  - `observed_hp_trace_enabled`
  - `observed_switch_trace_enabled`
- 기존 수동 UI는 유지하되, DB 코퍼스 schema가 있을 때는 “adapter schema 적용됨” 상태를 표시해라.

### 2. observed replay stack 토글/컬럼 기본값 반영

현재 Step6 UI에는 state snapshot, move trace, switch trace 등 수동 설정 expander가 있다. DB 코퍼스 schema가 있을 때 다음 값들이 UI 기본값과 `_bb_log_schema`에 유지되어야 한다.

- `state_trace_enabled=true`
- `observed_status_trace_enabled=true`
- `observed_hp_trace_enabled=true`
- `observed_switch_trace_enabled=true`
- `trace_moves_enabled=true`
- `initial_on_field_enabled=true`

주의:

- 기존 UI의 `trace_switches_enabled`와 adapter schema의 `observed_switch_trace_enabled`/`switch_event_type_col` 계열 명칭이 다를 수 있다. ADAPT6-8에서 사용 중인 실제 schema 키를 우선해라.
- DB 코퍼스 schema를 사용하는 경우 기존 수동 `switch outgoing/incoming` 방식으로 덮어써서 observed switch replay가 꺼지지 않게 해라.
- 사용자가 수동 편집을 켠 경우에만 수동 입력값으로 override되게 해라.

### 3. Step1 session state 정합성

`modules/step1_upload.py`에서 DB 코퍼스 변환 성공 시 session state 값이 adapter schema와 일관되게 저장되도록 정리해라.

현재 `schema = generate_schema()`는:

- `system_stats=["HP"]`
- `system_gimmicks=["species"]`
- `health_stat="HP"`
- `target_col="result"`
- `log_schema.state_hp_col="hp_current"`

Step1에서 임의로 `system_stats=["hp_current"]`, `health_stat="hp_current"`로 바꾸는 것이 Step6 백테스트에 더 맞는지, schema와 일치시키는 것이 더 맞는지 확인하고 하나로 정리해라.

수용 기준:

- Step6 `_bb_ready`가 true여야 한다.
- backtest 실행 시 `health_stat`과 `system_stats` 불일치 때문에 실패하지 않아야 한다.
- 저장된 `db_corpus_schema`, `bb_last_corpus_schema`, `bb_last_log_schema`와 session mapping 값이 서로 모순되지 않아야 한다.

### 4. helper 안전성

`modules/ui_db_corpus_helper.py`를 보완해라.

- 업로드 filename을 그대로 path join하지 말고 basename/safe name으로 sanitize해라.
- 지원 확장자가 `.db`, `.zip`이 아니면 명확한 ValueError를 내라.
- 임시 파일 삭제는 유지해라.
- 가능하면 `.codex_tmp/ui1_db_corpus_surface` 아래에 변환 검수용 파일을 선택적으로 남기되, UI 업로드마다 불필요한 산출물이 누적되지 않게 해라.

### 5. 테스트 보강

자동 테스트를 추가/보강해라.

필수 테스트:

- `.db` 업로드 helper 테스트
- `.zip` 업로드 helper 테스트
- filename sanitize 테스트
- DB 코퍼스 schema를 session-like dict에 적용했을 때 Step6 backtest 기본값이 DB 역할 컬럼 방식으로 선택되는지 검증하는 순수 helper 테스트
- schema flags가 Step6용 log_schema에 유지되는지 검증

가능하면 Step6 내부 로직 일부를 순수 helper로 분리해 테스트하라.

예시 helper:

- `resolve_db_corpus_log_schema(session_state_like)`
- `default_backtest_method_index(session_state_like, df)`
- `apply_db_corpus_schema_defaults(log_schema, df_columns)`

예시 테스트 파일:

- `test_step1_db_corpus_upload_adapter.py`
- `test_step6_db_corpus_auto_schema.py`

### 6. 검증 명령

환경에 맞는 Python 명령으로 최소 아래를 실행해라.

```powershell
python -m py_compile main.py modules/step1_upload.py modules/step6_dashboard.py modules/ui_db_corpus_helper.py modules/showdown_db_adapter.py modules/per_battle_backtest.py
python test_step1_db_corpus_upload_adapter.py
python test_step6_db_corpus_auto_schema.py
python test_showdown_db_extract_adapter.py
python test_db_corpus_backtest_report.py
python test_i15_integration_smoke.py
```

Streamlit 앱도 가능한 범위에서 확인해라.

```powershell
streamlit run main.py
```

화면 검수 포인트:

- Step1에서 `.db`/`.zip` 변환 성공
- Step6에서 DB 코퍼스 감지 패널 표시
- Step6 전투 구성 방식 기본값이 `DB 역할 컬럼으로 묶기`
- adapter schema 기반 컬럼/trace 설정 적용됨
- 백테스트 실행 시 `battle_count=2`, `accuracy_pct=100.0`, `state_mismatches=0` 기준선 유지

## 수용 기준

아래 조건을 모두 만족해야 한다.

- DB 코퍼스 변환 후 Step6에서 legacy row-count 방식이 기본으로 선택되지 않는다.
- adapter schema가 Step6 `_bb_log_schema` 기본값으로 실제 사용된다.
- observed status/HP/switch replay stack flag가 Step6 기본 실행에서도 유지된다.
- `.db`와 `.zip` 업로드 helper 테스트가 모두 통과한다.
- filename sanitize 테스트가 통과한다.
- ADAPT8 기준선 smoke가 깨지지 않는다.
- UI1에서 추가한 다운로드/리포트 패널이 유지된다.

## 금지/주의

- DB adapter 변환 로직을 UI 코드 안에 중복 구현하지 마라.
- ADAPT8의 replay stack 내부 로직을 불필요하게 변경하지 마라.
- 기존 일반 CSV/Excel 업로드 흐름을 깨지 마라.
- 새 랜딩 페이지를 만들지 마라. 기존 Step1/Step6에만 좁게 보정해라.
- pycache, 임시 DB/ZIP, `.codex_tmp` 산출물을 커밋 대상으로 만들지 마라.

## 완료 보고 형식

완료 후 다음 형식으로 보고해라.

```text
UI1b 완료 보고
- 변경 파일:
- Step6 자동 DB schema 적용:
- 기본 backtest 방식:
- observed replay flags:
- helper 안전성:
- 추가/갱신 테스트:
- 실행한 명령:
- Streamlit 확인:
- 남은 이슈:
```
