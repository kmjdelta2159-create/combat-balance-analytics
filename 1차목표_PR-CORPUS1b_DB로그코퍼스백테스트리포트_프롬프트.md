# 1차목표 PR-CORPUS1b — DB 로그 코퍼스 백테스트 리포트 하니스

## 정정 배경

PR-CORPUS1 초안은 기존 포켓몬 검증용 Showdown 리플레이 HTML 하니스를 주 경로로 삼았다.
그건 현재 프로젝트 전제와 맞지 않는다.

현재 앱의 Step1 업로드 지원 형식:

```text
csv, xlsx, xls, json, tsv, txt, parquet
```

최종 목표와 1차 목표의 검증 기준도 **리플레이 HTML이 아니라 DB 로그**다.

따라서 이 PR은 HTML 리플레이가 아니라, 앱이 실제로 받는 DB 로그 파일과 `log_schema`를
기준으로 코퍼스 백테스트 리포트를 만든다.

Showdown HTML 하니스(`run_xval.py`, `run_mechdetect.py`)는 포켓몬 레퍼런스 검증용 보조 도구로
남길 수 있지만, 1차 목표의 주 경로로 쓰면 안 된다.

## 목적

여러 DB 로그 파일을 한 번에 읽고, 각 파일/스키마 조합에 대해 다음을 표로 남긴다.

- 파일 로드 가능 여부
- schema 유효성
- battle 구성 가능 여부
- 백테스트 실행 가능 여부
- 승패 일치율
- state/action/resource score 요약
- 첫 mismatch
- 다음 조치 분류

즉, “코퍼스가 부르는 꼬리”를 HTML 리플레이가 아니라 **DB 로그 백테스트 결과**에서 뽑는다.

## 신규 파일

가능하면 신규 파일만 추가한다.

- `run_db_corpus_backtest.py`
- `test_db_corpus_backtest_report.py`

수정 금지:

- `modules/engine.py`
- `modules/per_battle_backtest.py`
- `modules/step1_upload.py`
- `modules/step6_dashboard.py`
- `modules/mechanism_detect.py`
- `modules/mechanism_commit.py`

## CLI 설계

기본 형태:

```bash
python -X utf8 run_db_corpus_backtest.py --schema corpus_schema.json logs/*.csv
python -X utf8 run_db_corpus_backtest.py --schema corpus_schema.json sample.csv sample.xlsx sample.json
```

선택 옵션:

```text
--schema PATH              log_schema와 실행 설정을 담은 JSON 파일
--out-dir PATH             기본값: 검증_코퍼스
--max-battles N            파일당 최대 전투 수
--battle-size N            row-count 방식 fallback용
--target-col COL           schema에 없을 때 fallback
```

HTML 입력은 기본 대상이 아니다.

만약 누군가 `.html`을 넘기면 다음 중 하나로 처리하라.

- 명확히 거부: `HTML replay is not a DB-log corpus input`
- 또는 `--allow-replay-html` 같은 별도 옵션이 있을 때만 legacy 경로로 처리

기본 경로에서 HTML을 자동 처리하지 마라.

## schema JSON 예시

`log_schema`는 Step6의 DB 역할 컬럼 매핑과 같은 의미를 가진다.

```json
{
  "target_col": "result",
  "battle_size": 2,
  "system_stats": ["HP", "SPD"],
  "system_gimmicks": [],
  "health_stat": "HP",
  "resource_config": {
    "HP": {"role": "vital", "stat": "HP", "regen": 0.0}
  },
  "game_config": {"preserve_ids": true},
  "log_schema": {
    "battle_id_col": "battle_id",
    "team_col": "team",
    "entity_id_col": "entity_id",
    "result_mode": "battle_level",
    "ally_values": ["Ally"],
    "enemy_values": ["Enemy"],
    "trace_moves_enabled": true,
    "turn_col": "turn",
    "actor_id_col": "actor",
    "target_id_col": "target",
    "move_name_col": "move",
    "damage_trace_enabled": true,
    "damage_value_kind": "hp_delta",
    "damage_value_col": "hp_delta"
  }
}
```

실제 사용자는 Step6 UI에서 만든 schema를 나중에 export할 수 있지만, 이번 PR은 우선 CLI에서 JSON으로 받으면 된다.

## 파일 로더

앱 Step1과 의미가 맞아야 한다.

지원:

- `.csv`
- `.tsv`
- `.txt`
- `.xlsx`
- `.xls`
- `.json`
- `.parquet`

가능하면 `modules/step1_upload.py`의 `_parse_log_file` 의미를 참고하되, Streamlit uploaded_file에
의존하지 않는 순수 파일 경로 loader를 `run_db_corpus_backtest.py` 안에 구현하라.

## report row

각 DB 로그 파일마다 다음 필드를 출력하라.

```text
file
format
rows
columns
status                       # loaded / schema_invalid / no_battles / ran / error
target_col
battle_count
actual_count
predicted_count
accuracy_pct
correct
errors
state_checks
state_mismatches
action_damage_checks
action_damage_mismatches
action_resource_delta_checks
action_resource_delta_mismatches
first_mismatch_score_type
first_mismatch_turn
first_mismatch_id
first_mismatch_kind
first_mismatch_resource
first_mismatch_expected
first_mismatch_actual
next_action
error
```

`next_action` 분류 예:

- `fix_schema`: 필수 컬럼 누락, schema 불일치
- `need_db_event_columns`: battle은 구성되지만 trace/state/damage 검증 컬럼이 부족함
- `inspect_mismatch`: 실행은 됐고 mismatch가 있음
- `inspect_engine_errors`: worker 에러 발생
- `passed_or_low_mismatch`: 실행됐고 mismatch가 없거나 낮음
- `no_battles`: 파일은 읽었지만 battle 구성 실패
- `error`: 예외

## 실행 방식

기존 코드를 재사용하라.

- `modules.per_battle_backtest.build_battles`
- `modules.per_battle_backtest.score_predictions`
- `modules.engine._worker_simulate_match`
- `modules.resource.ResourceModule`
- `modules.step6_dashboard._select_backtest_stochasticity_factory`는 Streamlit import 부담이 있으니 가능하면 같은 의미를 로컬 helper로 작게 복제

중요:

- 엔진/score schema를 바꾸지 않는다.
- Step6 UI와 같은 `build_battles(..., log_schema=...)` 경로를 사용한다.
- DB 역할 컬럼 방식이 있으면 그것을 우선 사용하고, 없으면 `battle_size` row-count fallback을 쓴다.

## 출력

콘솔 요약:

```text
=== DB Corpus Backtest Summary ===
file                 status      battles  acc     state_miss  dmg_miss  res_miss  next
sample.csv           ran         10       90.0%   2           1         0         inspect_mismatch
bad_schema.csv       schema_invalid -     -       -           -         -         fix_schema
```

파일 출력:

```text
검증_코퍼스/db_corpus_backtest_summary.csv
검증_코퍼스/db_corpus_backtest_summary.md
```

Markdown 리포트 상단에 다음 문구를 짧게 넣어라.

- 이 리포트는 DB 로그 기반 코퍼스 검증 리포트다.
- HTML 리플레이 검증은 별도 legacy/reference harness이며 주 경로가 아니다.
- 결측 컬럼/schema 문제는 엔진 결함이 아니라 입력 매핑 문제로 분리한다.
- mismatch는 복제본과 관측 DB 로그가 갈라진 첫 지점이다.

## 테스트

`test_db_corpus_backtest_report.py`를 추가하라.

테스트는 외부 파일에 의존하지 말고 임시 디렉터리에 작은 CSV/JSON/schema를 만들어 검증하라.

필수 테스트:

1. CSV DB 로그를 로드한다.
2. schema 필수 컬럼이 없으면 `schema_invalid` 또는 `fix_schema`로 분류한다.
3. 작은 1~2 battle DB 로그가 `build_battles` 경로로 실행된다.
4. mismatch row의 first mismatch 필드가 summary에 들어간다.
5. HTML 파일은 기본 입력에서 거부된다.
6. CSV/MD output 파일이 생성된다.

실행:

```bash
python -X utf8 -m py_compile run_db_corpus_backtest.py test_db_corpus_backtest_report.py
python -X utf8 test_db_corpus_backtest_report.py
python -X utf8 run_db_corpus_backtest.py --schema <테스트용 schema.json> <테스트용 csv>
```

기존 회귀:

```bash
python -X utf8 test_i15_integration_smoke.py
python -X utf8 test_step6_mismatch_report.py
python -X utf8 test_mechanism_detect_aliases.py
python -X utf8 test_mechanism_commit_canonical.py
```

## 금지

- HTML 리플레이를 기본 코퍼스 입력으로 삼지 마라.
- 이번 PR에서 engine/reference/mechanism detect 로직을 수정하지 마라.
- DB 로그 schema 문제를 포켓몬 데이터 결측처럼 말하지 마라.
- “리플레이 로그”와 “DB 로그”를 혼동하지 마라.
- 포켓몬 전용 하드코딩 금지.

## 완료 조건

- DB 로그 파일을 여러 개 받아 summary CSV/MD를 생성한다.
- HTML 파일은 기본 경로에서 거부되거나 명시적으로 legacy로 분리된다.
- Step6의 DB 역할 컬럼 백테스트와 같은 `build_battles` 경로를 사용한다.
- schema 문제 / no battles / worker error / mismatch / pass가 구분된다.
- 테스트와 기존 회귀가 통과한다.
