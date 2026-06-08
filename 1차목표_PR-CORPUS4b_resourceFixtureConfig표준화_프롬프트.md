# 1차목표 PR-CORPUS4b — Resource Fixture Config 표준화

## 배경

CORPUS4에서 DB-log fixture manifest와 runner가 추가되었고, 전체 테스트는 통과했다.

다만 `db_corpus_fixtures/resource_delta_trace_pass/schema.json`의 `resource_config`가 현재 엔진의 표준 계약과 다르다.

현재:

```json
"resource_config": {
  "HP": {"max": 100, "vital": true, "stat": "HP"},
  "Shield": {"max": 100, "shield": true, "stat": "Shield"}
}
```

현재 `ResourceModule`은 `spec.get("role") == "vital"` / `"shield"`를 기준으로 동작한다.
위 형태는 테스트를 당장 깨지는 않지만, fixture pack을 앞으로 확장할 때 “DB-log corpus 표준 schema”로 보기 어렵다.

임시 확인 결과, 아래 표준 형태로 바꿔도 manifest runner는 그대로 통과한다.

```json
"resource_config": {
  "HP": {"role": "vital", "stat": "HP", "regen": 0.0},
  "Shield": {"role": "shield", "stat": "Shield", "regen": 0.0}
}
```

## 목표

`resource_delta_trace_pass` fixture의 `resource_config`를 엔진 표준 형태로 고정하고, 테스트가 이를 확인하게 한다.

## 구현 요구사항

### 1. fixture schema 수정

파일:

- `db_corpus_fixtures/resource_delta_trace_pass/schema.json`

수정:

```json
"resource_config": {
  "HP": {"role": "vital", "stat": "HP", "regen": 0.0},
  "Shield": {"role": "shield", "stat": "Shield", "regen": 0.0}
}
```

주의:

- `max`, `vital`, `shield` 키 기반의 비표준 형태를 남기지 말 것.
- 다른 fixture case의 schema는 필요 없으면 건드리지 말 것.

### 2. 테스트 보강

파일:

- `test_db_corpus_fixture_manifest.py`

manifest runner 실행 전 또는 후에 `resource_delta_trace_pass/schema.json`을 읽어서 다음을 assert한다.

```python
rc = schema["resource_config"]
assert rc["HP"]["role"] == "vital"
assert rc["HP"]["stat"] == "HP"
assert rc["Shield"]["role"] == "shield"
assert rc["Shield"]["stat"] == "Shield"
assert "vital" not in rc["HP"]
assert "shield" not in rc["Shield"]
```

이 테스트는 “fixture가 우연히 통과한다”가 아니라 “앞으로 확장 가능한 표준 schema를 쓴다”를 보장하기 위한 것이다.

### 3. runner 변경은 선택

`run_db_corpus_fixture_manifest.py`는 현재 동작한다.
필요하면 최소한의 함수 분리만 허용한다.

단, 이번 PR의 핵심은 runner 구조 변경이 아니라 fixture schema 표준화다.

## 금지사항

- 테스트 통과를 위해 `ResourceModule`의 role 계약을 느슨하게 바꾸지 말 것.
- `resource_delta_trace_pass`를 제거하지 말 것.
- HTML/replay fixture를 추가하지 말 것.
- 기존 CORPUS1~3 테스트를 약화하지 말 것.

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

- `resource_delta_trace_pass/schema.json`이 `role: vital/shield` 기반 표준 resource config를 사용한다.
- 테스트가 이 schema 계약을 직접 확인한다.
- fixture manifest 전체와 기존 corpus/export/regression 테스트가 통과한다.
