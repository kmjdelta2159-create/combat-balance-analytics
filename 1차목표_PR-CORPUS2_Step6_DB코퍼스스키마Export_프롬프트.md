# 1차목표 PR-CORPUS2 — Step6 DB 코퍼스 스키마 Export

## 배경

현재 `run_db_corpus_backtest.py`는 DB 로그 코퍼스 검증용 CLI로 정리되었다.

CLI는 다음 형태의 schema JSON을 입력으로 받는다.

- `system_stats`
- `system_gimmicks`
- `health_stat`
- `resource_config`
- `game_config`
- `log_schema`
- `target_col`
- `battle_size`
- `combat_flow`
- `speed_stat`
- `global_damage_formula`
- `sim_max_turns`
- `move_library`
- `damage_type_map`
- `range_stat`
- `move_stat`

문제는 Step6 UI에서 사용자가 DB 로그 역할 컬럼, trace 컬럼, damage/resource 설정을 이미 맞춰도 그 설정을 CLI용 schema JSON으로 내보내는 연결이 아직 없다.

이 작업의 목표는 새 전투 기능을 추가하는 것이 아니라, 이미 구현된 DB 로그 복제 검증 루프를 실제 사용 흐름에 연결하는 것이다.

## 목표

`modules/step6_dashboard.py`의 Step6 백테스트 UI에서 현재 DB 로그 매핑과 엔진 실행 설정을 JSON으로 다운로드할 수 있게 한다.

다운로드된 JSON은 그대로 다음 명령에 사용할 수 있어야 한다.

```powershell
python -X utf8 run_db_corpus_backtest.py --schema exported_schema.json logs/*.csv
```

HTML/replay용 export가 아니다. DB 로그 코퍼스 검증용 schema JSON이어야 한다.

## 구현 요구사항

### 1. 테스트 가능한 helper 추가

`modules/step6_dashboard.py`에 UI와 분리된 helper를 추가한다.

권장 이름:

- `_json_safe`
- `_build_db_corpus_schema_payload`

`_build_db_corpus_schema_payload(...)`는 Streamlit UI 없이도 테스트에서 직접 호출 가능해야 한다.

입력 예시는 다음 값을 받을 수 있게 구성한다.

- `system_stats`
- `system_gimmicks`
- `health_stat`
- `target_col`
- `battle_size`
- `log_schema`
- `session_state_like`

반환 payload에는 최소 다음 키가 있어야 한다.

```python
{
    "schema_version": "db_corpus_backtest.v1",
    "generated_from": "step6_dashboard",
    "system_stats": ...,
    "system_gimmicks": ...,
    "health_stat": ...,
    "resource_config": ...,
    "game_config": ...,
    "log_schema": ...,
    "target_col": ...,
    "battle_size": ...,
    "combat_flow": ...,
    "speed_stat": ...,
    "global_damage_formula": ...,
    "sim_max_turns": ...,
    "move_library": ...,
    "damage_type_map": ...,
    "range_stat": ...,
    "move_stat": ...
}
```

주의:

- `game_config`는 `copy.deepcopy` 기반으로 복사한다.
- `log_schema.entity_id_col`이 있으면 backtest 실행부와 동일하게 `game_config["preserve_ids"] = True`가 들어가야 한다.
- `numpy` scalar, `pandas.NA`, `NaN`, tuple 등 JSON 직렬화가 깨질 수 있는 값은 `_json_safe`에서 안전하게 처리한다.
- `json.dumps(payload, ensure_ascii=False)`가 예외 없이 성공해야 한다.

### 2. Step6 UI에 다운로드 버튼 추가

Step6의 DB 역할 컬럼 방식에서 `_bb_log_schema`가 유효하게 만들어진 경우, 백테스트 실행 버튼 근처에 schema JSON 다운로드 버튼을 추가한다.

권장 버튼:

- label: `DB 코퍼스 schema JSON 다운로드`
- file name: `db_corpus_schema.json`
- mime: `application/json`

동작:

- 백테스트를 실행하지 않아도 schema가 유효하면 다운로드 가능해야 한다.
- 기존 `백테스트 실행` 버튼, `Mismatch Report`, `Mechanism RE` 렌더링 위치를 깨지 않는다.
- 다운로드 payload를 `st.session_state["bb_last_corpus_schema"]`에 캐시한다.
- 원본 log schema도 필요하면 `st.session_state["bb_last_log_schema"]`에 캐시한다.

### 3. 기존 백테스트 실행과 동일한 설정을 담기

Export payload는 Step6 백테스트 실행부에서 쓰는 값과 맞아야 한다.

반드시 포함:

- `st.session_state["combat_flow"]` 또는 `DEFAULT_COMBAT_FLOW`
- `st.session_state["speed_stat"]`
- `st.session_state["global_damage_formula"]` 또는 `"0"`
- `st.session_state["sim_max_turns"]` 또는 `100`
- `st.session_state["move_library"]`
- `st.session_state["resource_config"]`
- `st.session_state["damage_type_map"]`
- `st.session_state["game_config"]`
- `st.session_state["range_stat"]`
- `st.session_state["move_stat"]`

`run_db_corpus_backtest.py`가 이미 읽는 키 이름과 반드시 동일해야 한다.

### 4. 테스트 추가

새 테스트 파일을 추가한다.

권장 이름:

- `test_step6_db_corpus_schema_export.py`

테스트 케이스:

1. payload 기본 키 검증
   - fake `log_schema`에 `entity_id_col` 포함
   - fake session state에 `combat_flow`, `speed_stat`, `global_damage_formula`, `sim_max_turns`, `move_library`, `resource_config`, `damage_type_map`, `game_config`, `range_stat`, `move_stat` 포함
   - payload가 위 값을 그대로 포함하는지 확인

2. `preserve_ids` 보정 검증
   - `log_schema["entity_id_col"]`이 있으면 `payload["game_config"]["preserve_ids"] is True`
   - 원본 `game_config` 객체를 직접 mutate하지 않았는지 확인

3. JSON 직렬화 검증
   - `json.dumps(payload, ensure_ascii=False)` 성공
   - `json.loads(...)` 후 주요 값이 유지되는지 확인

4. entity id가 없을 때 보정 없음 또는 기존 값 유지 검증
   - `entity_id_col`이 없거나 `None`이면 새로 `preserve_ids=True`를 강제로 넣지 않는다.

## 금지사항

- HTML replay/export 기능으로 만들지 말 것.
- `run_db_corpus_backtest.py`의 DB-log 중심 설계를 HTML 기준으로 되돌리지 말 것.
- 기존 Step6 backtest 결과 캐시(`bb_last_backtest_has_run`, `bb_last_mismatch_rows`, `bb_last_backtest_summary`) 렌더링을 다시 버튼 블록 안으로 넣지 말 것.
- 대규모 UI 문구/인코딩 정리는 하지 말 것. 현재 파일에 깨진 한글이 있어도 이번 PR의 범위가 아니다.

## 검증 명령

아래 명령을 통과시켜라.

```powershell
$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -X utf8 -m py_compile modules/step6_dashboard.py test_step6_db_corpus_schema_export.py
& $py -X utf8 test_step6_db_corpus_schema_export.py
& $py -X utf8 test_step6_mismatch_report.py
& $py -X utf8 test_db_corpus_backtest_report.py
& $py -X utf8 test_i15_integration_smoke.py
& $py -X utf8 test_mechanism_detect_aliases.py
& $py -X utf8 test_mechanism_commit_canonical.py
```

## 완료 기준

- Step6에서 만든 DB 로그 매핑/trace 설정을 schema JSON으로 다운로드할 수 있다.
- 다운로드 JSON이 `run_db_corpus_backtest.py --schema`의 입력 계약과 맞다.
- `entity_id_col` 기반 `preserve_ids` 보정이 UI backtest와 CLI corpus backtest에서 동일하게 적용된다.
- 새 테스트와 기존 핵심 smoke/regression 테스트가 통과한다.
