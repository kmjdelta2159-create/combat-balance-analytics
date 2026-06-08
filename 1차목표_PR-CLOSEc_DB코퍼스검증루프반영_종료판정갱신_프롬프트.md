# 1차목표 PR-CLOSEc — DB Corpus 검증 루프 반영 종료판정 갱신

## 배경

기존 `1차목표_포켓몬복제_커버리지_종료판정.md`는 PR-CLOSEb 시점의 판정이다.

그 뒤 CORPUS 계열 작업으로 다음 흐름이 추가/검증되었다.

- `run_db_corpus_backtest.py`
  - DB CSV/XLSX/JSON/TSV/TXT/Parquet 로그 코퍼스용 CLI runner
  - HTML replay는 기본 거부
  - schema JSON의 실행 설정을 읽어 backtest 실행
  - outcome mismatch와 event/score mismatch를 분리 분류
- Step6 schema export
  - `_build_db_corpus_schema_payload(...)`
  - Step6 DB 역할 컬럼 매핑/trace 설정을 `db_corpus_schema.json`으로 다운로드
  - `entity_id_col` 기반 `preserve_ids=True` 보정
- Step6 export schema CLI roundtrip
  - export helper가 만든 schema가 실제 `run_db_corpus_backtest.py --schema`에 들어가 통과
- DB corpus fixture manifest
  - `db_corpus_fixtures/manifest.json`
  - `basic_damage_pass`
  - `outcome_mismatch_triage`
  - `resource_delta_trace_pass`
  - `run_db_corpus_fixture_manifest.py`
  - resource fixture는 표준 `role: vital/shield` resource config로 보정 완료

이 작업은 새 기능 추가가 아니라, 1차 목표 종료판정 문서를 최신 코드/검증 상태와 맞추는 정리 작업이다.

## 목표

`1차목표_포켓몬복제_커버리지_종료판정.md`를 최신 상태로 갱신한다.

특히 “DB 로그 기반 복제 검증 루프”가 이제 단순 기능 목록이 아니라 아래 형태로 닫혔음을 명확히 반영한다.

```text
Step6 DB mapping/export
→ schema JSON
→ run_db_corpus_backtest.py
→ manifest fixture pack
→ mismatch/outcome triage
→ mechanism RE/user intervention
```

## 수정 요구사항

### 1. DB-log 검증 IR 섹션 갱신

기존 DB-log IR 표에 다음 항목을 추가하거나 갱신한다.

- DB corpus CLI runner
- Step6 schema JSON export
- export schema ↔ CLI roundtrip
- corpus fixture manifest
- outcome mismatch triage
- resource fixture standard config

각 상태는 코드/테스트 기준으로 `완료` 또는 이에 준하는 표현으로 정리한다.

### 2. 검증 명령/테스트 목록 갱신

검증 명령 목록에 다음 테스트를 추가한다.

- `python -X utf8 test_db_corpus_fixture_manifest.py`
- `python -X utf8 test_step6_export_schema_cli_roundtrip.py`
- `python -X utf8 test_step6_db_corpus_schema_export.py`
- `python -X utf8 test_db_corpus_backtest_report.py`

기존 핵심 테스트도 유지한다.

- `test_i15_integration_smoke.py`
- `test_step6_mismatch_report.py`
- `test_mechanism_detect_aliases.py`
- `test_mechanism_commit_canonical.py`

### 3. 최종 판정 문구 보정

최종 판정은 기존처럼 `조건부 완료`를 유지해도 된다.

단, 조건의 의미를 더 정확히 쓴다.

권장 표현:

```text
1차 목표는 "포켓몬의 모든 예외 규칙을 사전 등록했다"가 아니라,
"포켓몬 복제에 필요한 핵심 전투 구조와 DB-log 기반 검증/개입 루프가 완성됐다"는 의미에서 조건부 완료다.
```

그리고 다음을 분명히 한다.

- 부족한 것은 핵심 복제 엔진 결함이라기보다 실제 코퍼스 확장과 제품 UI 이주/정리다.
- Streamlit은 최종 제품 UI가 아니라 현재 검증 콘솔로 둔다.
- Streamlit 교체/제품화는 1차 목표의 필수 조건이 아니라 1차 종료 후 이주 준비/2차 제품화 작업으로 분리한다.

### 4. 남은 작업 섹션 갱신

남은 작업을 다음처럼 분리한다.

#### 1차 종료 전/직후 정리

- 실제 DB 로그 코퍼스가 들어오면 manifest case 추가
- mismatch/outcome triage 결과를 사용자 개입 후보로 연결
- 종료판정 문서와 데모 설명 정리

#### 1차 이후 제품화/2차

- Streamlit 구조 분리 또는 대체 UI 이주
- 프로젝트/코퍼스/스키마 파일 관리
- 장기 실행 job 관리
- 대규모 corpus dashboard
- AI/controller policy, full teambuild inference, doubles/multi-target 등

### 5. 주의

- Showdown HTML/replay를 주 경로처럼 다시 쓰지 말 것.
- “HTML 코퍼스”라는 표현을 쓰지 말 것.
- DB 로그가 주 입력이라는 전제를 명확히 유지할 것.
- 비-스탯 게임까지 포괄한다고 쓰지 말 것. 범위는 스탯 기반 턴제 게임이다.
- Streamlit 교체를 지금 1차 목표 미완료 사유로 과장하지 말 것.

## 검증 명령

문서 수정 후 아래 명령을 실행해 최신 테스트 상태를 확인한다.

```powershell
$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
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

- 종료판정 문서가 CORPUS1~4b 이후의 실제 검증 루프를 반영한다.
- 1차 목표의 의미가 “기능 사전 전체 등록”이 아니라 “핵심 구조 + DB-log 검증/개입 루프 완성”으로 명확해진다.
- Streamlit 이주는 1차 종료 조건이 아니라 이후 제품화/구조개편 작업으로 분리된다.
- 최신 테스트 명령이 문서에 반영되고 실제로 통과한다.
