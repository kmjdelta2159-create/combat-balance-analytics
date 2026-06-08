# 1차목표 PR-CORPUS3 — Step6 Export Schema ↔ CLI Corpus Roundtrip

## 배경

CORPUS2에서 Step6 DB 로그 매핑/전투 실행 설정을 `db_corpus_schema.json`으로 다운로드할 수 있게 했다.

현재 검증된 것:

- `_build_db_corpus_schema_payload(...)`가 필요한 키를 만든다.
- `json.dumps(..., ensure_ascii=False)`가 성공한다.
- `entity_id_col`이 있으면 `game_config["preserve_ids"] = True`가 들어간다.

아직 고정 테스트로 확인하지 않은 것:

- Step6 helper가 만든 JSON을 실제 파일로 저장한 뒤
- `run_db_corpus_backtest.py --schema exported_schema.json ...`에 그대로 넣었을 때
- CLI가 정상 실행되고 summary에 기대 설정/분류가 반영되는지

이 작업은 새 전투 기능이 아니라, DB 로그 기반 복제 검증 루프의 연결 무결성 확인이다.

## 목표

Step6 export schema가 CLI corpus runner의 실제 입력 계약과 호환된다는 것을 테스트로 고정한다.

## 구현 요구사항

### 1. 새 roundtrip 테스트 추가

권장 파일명:

- `test_step6_export_schema_cli_roundtrip.py`

테스트 흐름:

1. `tempfile.TemporaryDirectory()`를 만든다.
2. `_build_db_corpus_schema_payload(...)`로 schema payload를 만든다.
3. payload를 `exported_schema.json`으로 저장한다.
4. 작은 DB 로그 CSV를 만든다.
5. `subprocess.run([... "run_db_corpus_backtest.py", "--schema", schema_path, "--out-dir", out_dir, csv_path])`로 CLI를 실행한다.
6. `db_corpus_backtest_summary.csv`를 읽어서 다음을 assert한다.

### 2. 테스트 데이터 조건

CSV는 HTML/replay가 아니라 DB 로그 형태여야 한다.

권장 최소 컬럼:

- `battle_id`
- `team`
- `entity_id`
- `result`
- `HP`
- `SPD`
- `turn`
- `actor`
- `target`
- `move`
- `hp_delta`

예시:

```python
pd.DataFrame({
    "battle_id": [1, 1],
    "team": ["Ally", "Enemy"],
    "entity_id": ["A1", "E1"],
    "result": [1, 0],
    "HP": [100, 100],
    "SPD": [10, 1],
    "turn": [1, 1],
    "actor": ["A1", "A1"],
    "target": ["E1", "E1"],
    "move": ["Hit", "Hit"],
    "hp_delta": [100, 100],
})
```

### 3. Export schema payload 조건

`_build_db_corpus_schema_payload(...)` 호출에는 다음을 넣는다.

- `system_stats=["HP", "SPD"]`
- `system_gimmicks=[]`
- `health_stat="HP"`
- `target_col="result"`
- `battle_size=2`
- `log_schema`
  - `battle_id_col="battle_id"`
  - `team_col="team"`
  - `entity_id_col="entity_id"`
  - `result_mode="battle_level"`
  - `ally_values=["Ally"]`
  - `enemy_values=["Enemy"]`
  - `initial_on_field_enabled=True`
  - `initial_on_field_col="team"`
  - `initial_on_field_values=["Ally", "Enemy"]`
  - `trace_moves_enabled=True`
  - `turn_col="turn"`
  - `actor_id_col="actor"`
  - `target_id_col="target"`
  - `move_name_col="move"`
  - `damage_trace_enabled=True`
  - `damage_turn_col="turn"`
  - `damage_actor_id_col="actor"`
  - `damage_target_id_col="target"`
  - `damage_value_col="hp_delta"`
  - `damage_value_kind="hp_delta"`
- `session_state_like`
  - `speed_stat="SPD"`
  - `global_damage_formula="999"`
  - `sim_max_turns=1`
  - `game_config={"preserve_initial_on_field": True}`
  - `combat_flow`는 명시하지 않아도 된다. helper가 `DEFAULT_COMBAT_FLOW`를 넣는지 확인한다.

### 4. Assert 조건

CLI 실행 결과:

- returncode == 0
- summary CSV가 생성된다.
- row count == 1
- `status == "ran"`
- `formula == "999"`
- `speed_stat == "SPD"`
- `trace_moves_enabled == True`
- `damage_trace_enabled == True`
- `action_damage_mismatches == 0`
- `outcome_mismatches == 0`
- `next_action == "passed_or_low_mismatch"`

Schema payload 자체:

- `payload["game_config"]["preserve_ids"] is True`
- 원본 `session_state_like["game_config"]`에는 `preserve_ids`가 새로 생기지 않아야 한다.

### 5. 선택 보강

가능하면 같은 테스트 안에서 저장된 `exported_schema.json`을 `json.load`로 다시 읽어 다음도 확인한다.

- `schema_version == "db_corpus_backtest.v1"`
- `generated_from == "step6_dashboard"`
- `log_schema["entity_id_col"] == "entity_id"`
- `game_config["preserve_ids"] is True`

## 금지사항

- HTML replay fixture를 쓰지 말 것.
- `run_db_corpus_backtest.py`를 HTML 기준으로 되돌리지 말 것.
- 테스트 통과만을 위해 CLI의 실제 schema 입력 계약을 느슨하게 망가뜨리지 말 것.
- 기존 `test_db_corpus_backtest_report.py`의 outcome 분류 테스트를 제거하거나 약화하지 말 것.

## 검증 명령

```powershell
$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -X utf8 -m py_compile modules/step6_dashboard.py run_db_corpus_backtest.py test_step6_export_schema_cli_roundtrip.py
& $py -X utf8 test_step6_export_schema_cli_roundtrip.py
& $py -X utf8 test_step6_db_corpus_schema_export.py
& $py -X utf8 test_db_corpus_backtest_report.py
& $py -X utf8 test_step6_mismatch_report.py
& $py -X utf8 test_i15_integration_smoke.py
& $py -X utf8 test_mechanism_detect_aliases.py
& $py -X utf8 test_mechanism_commit_canonical.py
```

## 완료 기준

- Step6 export helper가 만든 schema JSON이 실제 CLI corpus runner에서 그대로 동작한다.
- CLI summary가 exported schema의 핵심 실행 설정을 반영한다.
- DB 로그 기반 코퍼스 검증 루프가 UI 설정과 분리되지 않았다는 것을 테스트로 보장한다.
