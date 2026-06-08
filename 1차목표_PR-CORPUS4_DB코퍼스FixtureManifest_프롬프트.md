# 1차목표 PR-CORPUS4 — DB Corpus Fixture Manifest

## 배경

CORPUS1~3로 다음 흐름이 연결되었다.

1. Step6에서 DB 로그 역할 컬럼/trace 컬럼을 매핑한다.
2. Step6 설정을 `db_corpus_schema.json`으로 export한다.
3. export schema를 `run_db_corpus_backtest.py --schema`에 그대로 넣어 CLI 코퍼스 검증을 실행한다.

이제 필요한 것은 실제 외부 DB 로그가 들어오기 전에도 계속 회귀검증할 수 있는 **DB-log fixture pack**이다.

중요:

- HTML replay fixture가 아니다.
- Showdown HTML을 DB 로그처럼 취급하지 않는다.
- 작고 명확한 DB 테이블/CSV fixture로 corpus runner의 입력 계약을 고정한다.

## 목표

`run_db_corpus_backtest.py`가 실제 DB-log 코퍼스 묶음을 반복 검증하는 흐름을 manifest 기반 fixture pack으로 고정한다.

이 작업은 새 전투 메커니즘을 추가하는 PR이 아니다.
이미 구현된 DB-log IR / schema export / CLI runner를 “실제 운영 가능한 코퍼스 단위”로 묶는 연결 작업이다.

## 구현 요구사항

### 1. fixture 디렉터리 추가

권장 디렉터리:

```text
db_corpus_fixtures/
```

그 아래에 최소 2개 case를 둔다.

권장 구조:

```text
db_corpus_fixtures/
  manifest.json
  basic_damage_pass/
    schema.json
    battle_log.csv
  outcome_mismatch_triage/
    schema.json
    battle_log.csv
```

가능하면 3번째 case도 추가한다.

```text
  resource_delta_trace_pass/
    schema.json
    battle_log.csv
```

단, 3번째가 예상보다 커지면 2개 case만 안정적으로 끝내도 된다.

### 2. manifest 형식

`db_corpus_fixtures/manifest.json`은 테스트/러너가 읽을 수 있는 구조로 만든다.

예시:

```json
{
  "version": "db_corpus_fixture_manifest.v1",
  "cases": [
    {
      "name": "basic_damage_pass",
      "schema": "basic_damage_pass/schema.json",
      "logs": ["basic_damage_pass/battle_log.csv"],
      "expected": {
        "status": "ran",
        "formula": "999",
        "speed_stat": "SPD",
        "action_damage_mismatches": 0,
        "outcome_mismatches": 0,
        "next_action": "passed_or_low_mismatch"
      }
    }
  ]
}
```

경로는 manifest 파일 위치 기준 상대경로로 해석한다.

### 3. case: `basic_damage_pass`

목적:

- DB 로그 CSV + schema JSON이 CLI에서 정상 통과하는 최소 성공 케이스.
- CORPUS3 roundtrip과 같은 핵심 계약을 fixture pack에 고정한다.

schema 조건:

- `system_stats`: `["HP", "SPD"]`
- `health_stat`: `"HP"`
- `target_col`: `"result"`
- `battle_size`: `2`
- `speed_stat`: `"SPD"`
- `global_damage_formula`: `"999"`
- `sim_max_turns`: `1`
- `game_config`: `{"preserve_ids": true, "preserve_initial_on_field": true}`
- `log_schema`
  - `battle_id_col`: `"battle_id"`
  - `team_col`: `"team"`
  - `entity_id_col`: `"entity_id"`
  - `result_mode`: `"battle_level"`
  - `ally_values`: `["Ally"]`
  - `enemy_values`: `["Enemy"]`
  - `initial_on_field_enabled`: `true`
  - `initial_on_field_col`: `"team"`
  - `initial_on_field_values`: `["Ally", "Enemy"]`
  - `trace_moves_enabled`: `true`
  - `turn_col`: `"turn"`
  - `actor_id_col`: `"actor"`
  - `target_id_col`: `"target"`
  - `move_name_col`: `"move"`
  - `damage_trace_enabled`: `true`
  - `damage_turn_col`: `"turn"`
  - `damage_actor_id_col`: `"actor"`
  - `damage_target_id_col`: `"target"`
  - `damage_value_col`: `"hp_delta"`
  - `damage_value_kind`: `"hp_delta"`

CSV 조건:

```csv
battle_id,team,entity_id,result,HP,SPD,turn,actor,target,move,hp_delta
1,Ally,A1,1,100,10,1,A1,E1,Hit,100
1,Enemy,E1,0,100,1,1,A1,E1,Hit,100
```

기대:

- `status == "ran"`
- `formula == "999"`
- `speed_stat == "SPD"`
- `action_damage_mismatches == 0`
- `outcome_mismatches == 0`
- `next_action == "passed_or_low_mismatch"`

### 4. case: `outcome_mismatch_triage`

목적:

- 액션 데미지 trace는 맞지만 최종 outcome이 틀릴 때 `inspect_outcome_mismatch`로 분류되는지 fixture pack에 고정한다.

schema/CSV는 `basic_damage_pass`와 거의 같게 하되:

- `global_damage_formula`: `"30"`
- CSV `hp_delta`: `30`

기대:

- `status == "ran"`
- `action_damage_mismatches == 0`
- `outcome_mismatches > 0`
- `next_action == "inspect_outcome_mismatch"`

### 5. 선택 case: `resource_delta_trace_pass`

목적:

- HP 외 자원 trace가 DB corpus runner에서도 읽히는지 확인한다.

기존 `test_i14.py`, `test_i15_integration_smoke.py`의 resource delta fixture를 재사용해도 된다.

권장 조건:

- `resource_config`
  - `HP`: vital / stat `HP`
  - `Shield`: shield / stat `Shield`
- `damage_type_map`은 필요하면 생략하거나 현재 엔진 계약에 맞게 둔다.
- `log_schema.resource_delta_trace_enabled = true`
- `resource_delta_cols = {"HP": "hp_loss", "Shield": "shield_loss"}`
- `resource_delta_action_col = "event"`
- `resource_delta_action_values = ["damage"]`
- `resource_delta_strict_extra = false`

기대:

- `status == "ran"`
- `action_resource_delta_mismatches == 0`
- `next_action`은 outcome까지 맞추기 어렵다면 `inspect_outcome_mismatch`여도 된다.
- 단, 이 case가 불안정하면 이번 PR에서는 제외한다. 억지로 엔진을 바꾸지 말 것.

### 6. manifest runner 추가

권장 파일:

- `run_db_corpus_fixture_manifest.py`

기능:

```powershell
python -X utf8 run_db_corpus_fixture_manifest.py db_corpus_fixtures/manifest.json --out-dir 검증_코퍼스_fixture
```

동작:

- manifest를 읽는다.
- 각 case마다 `run_db_corpus_backtest.py --schema ... --out-dir <case_out_dir> ...logs`를 subprocess로 실행한다.
- 각 case의 `db_corpus_backtest_summary.csv`를 읽고 expected 조건을 검증한다.
- `expected` 값이 정수/문자열이면 equality를 본다.
- `expected`에 `">0"` 같은 문자열이 있으면 greater-than-zero 조건으로 처리해도 된다.
- 실패 시 어떤 case, 어떤 컬럼, 실제 값/기대 값이 다른지 명확한 AssertionError를 낸다.

### 7. 테스트 추가

권장 파일:

- `test_db_corpus_fixture_manifest.py`

테스트:

- manifest runner를 직접 import해서 함수 호출하거나 subprocess로 실행한다.
- fixture manifest 전체가 통과해야 한다.
- runner 출력 디렉터리에 case별 summary CSV가 생성되는지 확인한다.

## 금지사항

- HTML fixture를 넣지 말 것.
- Showdown replay 파일을 fixture pack의 입력으로 넣지 말 것.
- fixture 통과를 위해 `run_db_corpus_backtest.py`의 오류 분류를 느슨하게 만들지 말 것.
- `test_db_corpus_backtest_report.py`, `test_step6_export_schema_cli_roundtrip.py`를 제거하거나 약화하지 말 것.
- 대형 포켓몬 전체 코퍼스를 만들려고 하지 말 것. 이번 PR은 작고 반복 가능한 DB-log corpus 뼈대다.

## 검증 명령

```powershell
$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -X utf8 -m py_compile run_db_corpus_fixture_manifest.py test_db_corpus_fixture_manifest.py run_db_corpus_backtest.py
& $py -X utf8 test_db_corpus_fixture_manifest.py
& $py -X utf8 test_step6_export_schema_cli_roundtrip.py
& $py -X utf8 test_step6_db_corpus_schema_export.py
& $py -X utf8 test_db_corpus_backtest_report.py
& $py -X utf8 test_step6_mismatch_report.py
& $py -X utf8 test_i15_integration_smoke.py
& $py -X utf8 test_mechanism_detect_aliases.py
& $py -X utf8 test_mechanism_commit_canonical.py
```

## 완료 기준

- DB-log fixture pack이 생긴다.
- manifest runner로 fixture pack 전체를 한 번에 검증할 수 있다.
- fixture pack은 HTML/replay가 아니라 DB CSV + schema JSON 기반이다.
- 성공 case와 outcome mismatch triage case가 최소한 고정된다.
- 이후 실제 DB 로그 코퍼스가 들어오면 같은 manifest 형식으로 확장할 수 있다.
