# DB코퍼스_PR-ADAPT4b - observed status trace replay

## 목적

ADAPT4 검수에서 first mismatch의 원인이 좁혀졌다.

현재 `.db` 입력 파이프라인과 어댑터 변환은 정상이다. 원본 SQLite DB에는 `StatusApplied p1:Gengen tox` 이벤트가 있고, 변환된 `battle_log.csv`에도 `p1:Gengen hp_status=tox` state row가 존재한다.

하지만 백테스트 재현 엔진의 actual state에는 turn 1 종료 시점 `p1:Gengen.status`가 빈 값으로 남는다.

이번 PR의 목적은 관측 DB 로그의 discrete status 이벤트를 재현 실행에 선택적으로 반영하는 `observed status trace`를 추가해서, 첫 mismatch인 `p1:Gengen status expected 'tox' actual ''`를 제거하는 것이다.

## 현재 상태

완료된 작업:

- ADAPT1d: roster-only species/nickname false positive 보정 완료
- ADAPT2: SQLite `.db` 직접 입력 지원 완료
- ADAPT3: `.db`, `.zip`, extracted folder 입력 파이프라인 검수 통과
- ADAPT4: first state mismatch 원인 분석 완료

실제 DB smoke 산출물:

```text
.codex_tmp\adapt3_db_pipeline_finalize\battle_log.csv
.codex_tmp\adapt3_db_pipeline_finalize\schema.json
.codex_tmp\adapt3_db_pipeline_finalize\adapter_report.json
```

ADAPT3 adapter report 핵심값:

```text
battle_count=1
event_count=343
participant_count=12
roster_only_entities=[]
winner_side=p1
```

현재 백테스트 결과:

```text
status=ran
accuracy_pct=0.0
outcome_mismatches=1
state_mismatches=68
first_mismatch_score_type=state
first_mismatch_turn=1
first_mismatch_id=p1:Gengen
first_mismatch_kind=status
first_mismatch_expected='tox'
first_mismatch_actual=''
next_action=inspect_mismatch
```

## 확정 사실

원본 SQLite DB의 `battle_events`에는 다음 이벤트가 있다.

```text
seq=73
turn_no=1
phase=Status
event_type=StatusApplied
actor_id=p1a: Gengen
actor_side=p1
actor_name=Gengen
effect=tox
details_json={"tags": ["[from] item: Toxic Orb"], "from": "item: Toxic Orb"}
raw_line=|-status|p1a: Gengen|tox|[from] item: Toxic Orb
```

변환된 `battle_log.csv`에도 대응 state row가 있다.

```text
seq=73
turn_no=1
row_kind=state
state_entity_id=p1:Gengen
hp_status=tox
fainted=False
```

따라서 문제 위치는 다음이 아니다.

- SQLite `.db` 입력 실패 아님
- roster-only 문제 아님
- adapter가 `tox` row를 누락한 문제 아님

문제 위치는 다음 쪽으로 분류한다.

- 백테스트 재현 엔진이 관측된 `StatusApplied` / `StatusCured` 이벤트를 trace input으로 소비하지 못함
- expected state snapshot은 `tox`를 알고 있지만, actual simulation state는 `tox`를 적용하지 않음

## 핵심 원칙

expected state snapshot을 actual state에 통째로 복사하면 안 된다.

이번 PR은 state snapshot을 덮어쓰는 PR이 아니다. 반드시 discrete event 기반으로만 처리한다.

허용되는 입력:

- `StatusApplied`
- `StatusCured`

허용되지 않는 입력:

- 일반 `DamageApplied` row의 `hp_status`
- 임의의 expected state snapshot 전체
- HP/fainted/resource snapshot 전체 덮어쓰기

## 작업 범위

### 1. adapter state row에 원본 이벤트 정보 보존

파일:

```text
modules/showdown_db_adapter.py
```

state row 생성 시 원본 이벤트 판별에 필요한 컬럼을 추가한다.

최소 컬럼:

```text
state_event_type
state_effect
state_source
state_details_json
state_raw_line
```

예상 값:

```text
state_event_type=StatusApplied
state_effect=tox
state_source=
state_details_json={"tags": ["[from] item: Toxic Orb"], "from": "item: Toxic Orb"}
state_raw_line=|-status|p1a: Gengen|tox|[from] item: Toxic Orb
```

기존 컬럼 계약은 유지한다.

- `hp_status`
- `state_entity_id`
- `hp_current`
- `hp_max`
- `fainted`

### 2. observed status trace builder 추가

파일 후보:

```text
modules/per_battle_backtest.py
```

새 helper를 추가한다.

예시 이름:

```python
build_observed_status_trace_from_group(...)
```

동작:

- `observed_status_trace_enabled`가 꺼져 있으면 아무 것도 만들지 않는다.
- `state_event_type == "StatusApplied"`인 row만 status apply 이벤트로 변환한다.
- `state_event_type == "StatusCured"`인 row만 status clear 이벤트로 변환한다.
- entity id는 `state_entity_id`를 사용한다.
- status 값은 `hp_status` 또는 `state_effect`를 사용한다.
- participant id 필터링을 적용한다.
- turn이 없는 row는 제외한다.
- `DamageApplied` row의 `hp_status`는 상태 적용 이벤트로 취급하지 않는다.

권장 trace 형태:

```python
[
    {"turn": 1, "entity_id": "p1:Gengen", "status": "tox", "op": "apply"},
    {"turn": 3, "entity_id": "p2:Rotom-Wash", "status": "", "op": "clear"},
]
```

### 3. schema/log config에 명시 플래그 추가

파일 후보:

```text
modules/showdown_db_adapter.py
```

`generate_schema()`의 `log_schema`에 다음을 추가한다.

```json
{
  "observed_status_trace_enabled": true,
  "status_event_type_col": "state_event_type",
  "status_entity_id_col": "state_entity_id",
  "status_value_col": "hp_status",
  "status_effect_col": "state_effect",
  "status_turn_col": "turn_no"
}
```

기존 `state_trace_enabled`는 유지한다.

### 4. battle game_config로 trace 전달

파일 후보:

```text
modules/per_battle_backtest.py
```

`build_battles_from_log_schema(...)`에서 observed status trace를 만들고, participant id 필터링 후 battle game_config에 넣는다.

예시:

```python
battle_gc["_observed_status_trace"] = filtered_observed_status_trace
```

기존 `_expected_state_snapshots`는 그대로 유지한다. 이 값은 scoring용이다.

### 5. engine/replay에서 observed status trace 적용

파일 후보:

```text
modules/engine.py
modules/trace_replay.py
```

재현 실행 중 observed status trace를 적용한다.

최소 요구:

- turn 1 종료 snapshot 전에 `p1:Gengen.status == "tox"`가 되어야 한다.
- `StatusApplied`는 해당 participant의 status를 설정한다.
- `StatusCured`는 해당 participant의 status를 빈 값으로 만든다.
- 없는 participant id는 무시하거나 안전하게 기록한다.
- HP/fainted/resource는 건드리지 않는다.

적용 시점:

- 상태 스냅샷 capture 전에 적용되어야 한다.
- first mismatch가 turn 1 종료 snapshot에서 발생하므로, turn 1의 observed status event는 turn 1 state snapshot 전에 반영되어야 한다.

### 6. report 인코딩 부수 정리

현재 다음 파일의 한글 설명부가 깨져 보인다.

```text
.codex_tmp\adapt3_db_pipeline_finalize\backtest\db_corpus_backtest_summary.md
```

기능과 무관하면 큰 작업으로 만들지 말고 다음 중 하나로 처리한다.

- 설명부를 영어 문장으로 바꾼다.
- 또는 별도 TODO로만 남긴다.

CSV 핵심 데이터는 정상이라, 이 이슈는 이번 PR의 차단 조건이 아니다.

## 금지 사항

- 원본 `.db` 파일 수정 금지
- `.db` 입력 파이프라인 리팩터링 금지
- expected state snapshot을 actual state에 통째로 복사 금지
- HP/fainted/resource snapshot 전체 덮어쓰기 금지
- damage formula 전체 개선 금지
- UI/UX 작업 금지
- 불필요한 대형 리팩터링 금지
- 요청 없으면 git stage/commit 금지

## 필수 검증

PowerShell 기준:

```powershell
$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'

& $py -X utf8 -m py_compile modules/showdown_db_adapter.py modules/per_battle_backtest.py modules/engine.py run_db_corpus_backtest.py
& $py -X utf8 test_showdown_db_extract_adapter.py
& $py -X utf8 test_db_corpus_backtest_report.py
& $py -X utf8 test_i15_integration_smoke.py

& $py -X utf8 convert_showdown_db_extract.py --input "C:\Users\kmjde\Downloads\pokemon_showdown_production_style.db" --out-dir ".codex_tmp\adapt4b_status_trace"

& $py -X utf8 run_db_corpus_backtest.py --schema ".codex_tmp\adapt4b_status_trace\schema.json" --out-dir ".codex_tmp\adapt4b_status_trace\backtest" --max-battles 1 ".codex_tmp\adapt4b_status_trace\battle_log.csv"
```

## 통과 기준

다음은 반드시 만족해야 한다.

- 모든 필수 테스트 통과
- 실제 DB 변환 성공
- `adapter_report.json`에서 `roster_only_entities == []`
- 백테스트 status가 `ran`
- first mismatch가 더 이상 아래 값이면 안 된다.

```text
turn=1
id=p1:Gengen
kind=status
expected='tox'
actual=''
```

허용되는 결과:

- mismatch가 HP로 이동
- mismatch가 outcome으로만 남음
- state_mismatches가 줄어듦
- next_action이 여전히 `inspect_mismatch`이지만 first mismatch 원인이 바뀜

이번 PR은 전체 accuracy를 100%로 만드는 PR이 아니다.

## 산출물

작업 완료 후 다음을 보고한다.

```text
1. 변경 파일 목록
2. observed status trace 적용 방식 요약
3. 원본 DB 이벤트와 변환 row 대응 요약
4. 수정 전/후 백테스트 핵심 수치
5. first mismatch 변화
6. 남은 mismatch의 다음 원인 후보
```

## 다음 단계 판단

ADAPT4b 이후 first mismatch가 HP damage 값으로 이동하면 다음 작업은 damage formula/roll/model 쪽으로 보낸다.

ADAPT4b 이후 status mismatch가 다른 entity로 남으면 observed status trace의 적용 범위, turn timing, StatusCured 처리를 재검수한다.

ADAPT4b 이후 outcome mismatch만 남으면 ADAPT5에서 outcome/accuracy 개선 단계로 넘어간다.
