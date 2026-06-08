# DB코퍼스_PR-ADAPT5 - observed HP trace replay

## 목적

ADAPT4b는 통과했다.

관측 status event replay가 적용되면서 기존 first mismatch였던 `p1:Gengen status expected 'tox' actual ''`는 사라졌다.

현재 남은 first mismatch는 HP mismatch다.

```text
first_mismatch_score_type=state
first_mismatch_turn=2
first_mismatch_id=p1:Nanami
first_mismatch_kind=hp
first_mismatch_expected=278.0
first_mismatch_actual=403.0
```

이번 PR의 목적은 관측 DB 로그의 discrete HP change 이벤트를 재현 실행에 선택적으로 반영하는 `observed HP trace`를 추가해서, 위 first mismatch를 제거하는 것이다.

이번 PR은 Pokemon damage formula를 완성하는 PR이 아니다.  
trace replay 모드에서 관측된 HP event를 actual state에 반영하는 PR이다.

## 현재 상태

ADAPT4b 검수 결과:

```text
status=ran
battle_count=1
rows=224
columns=34
state_checks=117
state_mismatches=56
outcome_mismatches=1
first_mismatch_turn=2
first_mismatch_id=p1:Nanami
first_mismatch_kind=hp
first_mismatch_expected=278.0
first_mismatch_actual=403.0
next_action=inspect_mismatch
```

검증된 산출물:

```text
.codex_tmp\adapt4b_status_trace\battle_log.csv
.codex_tmp\adapt4b_status_trace\schema.json
.codex_tmp\adapt4b_status_trace\adapter_report.json
.codex_tmp\adapt4b_status_trace\backtest\db_corpus_backtest_summary.csv
```

재실행 검증 산출물:

```text
.codex_tmp\adapt4b_status_trace_verify\battle_log.csv
.codex_tmp\adapt4b_status_trace_verify\schema.json
.codex_tmp\adapt4b_status_trace_verify\adapter_report.json
.codex_tmp\adapt4b_status_trace_verify\backtest\db_corpus_backtest_summary.csv
```

## 확정 사실

원본 SQLite DB의 turn 2 이벤트는 다음 순서다.

```text
seq=84
turn_no=2
event_type=PokemonSwitched
actor_id=p1a: Nanami
actor_name=Nanami
pokemon_name=Jirachi
hp_current=403
hp_max=403
raw_line=|switch|p1a: Nanami|Jirachi|403/403

seq=85
turn_no=2
event_type=MoveUsed
actor_id=p2a: Rotom-Wash
target_id=p1a: Nanami
move_name=Hydro Pump
raw_line=|move|p2a: Rotom-Wash|Hydro Pump|p1a: Nanami

seq=86
turn_no=2
event_type=DamageApplied
actor_id=p1a: Nanami
hp_current=253
hp_max=403
delta_hp=-150
raw_line=|-damage|p1a: Nanami|253/403

seq=87
turn_no=2
event_type=HealApplied
actor_id=p1a: Nanami
hp_current=278
hp_max=403
delta_hp=25
source=item: Leftovers
raw_line=|-heal|p1a: Nanami|278/403|[from] item: Leftovers
```

변환된 `battle_log.csv`에도 대응 state rows가 있다.

```text
seq=84
row_kind=state
state_entity_id=p1:Nanami
hp_current=403
hp_max=403
state_event_type=PokemonSwitched

seq=86
row_kind=state
state_entity_id=p1:Nanami
hp_current=253
hp_max=403
state_event_type=DamageApplied

seq=87
row_kind=state
state_entity_id=p1:Nanami
hp_current=278
hp_max=403
state_event_type=HealApplied
```

따라서 문제 위치는 다음이 아니다.

- SQLite `.db` 입력 실패 아님
- adapter가 turn 2 HP row를 누락한 문제 아님
- status trace 문제 아님

문제 위치는 다음이다.

- 백테스트 재현 엔진이 관측된 HP change 이벤트를 trace input으로 소비하지 못함
- 현재 `global_damage_formula="0"`이라 엔진 자체 damage 계산만으로는 Nanami HP가 403에서 내려가지 않음

## 핵심 원칙

expected state snapshot 전체를 actual state에 복사하면 안 된다.

이번 PR은 state snapshot 덮어쓰기 PR이 아니다.  
반드시 discrete event 기반으로만 처리한다.

허용되는 입력:

- `PokemonSwitched`의 `hp_current`, `hp_max`
- `DamageApplied`의 `hp_current`, `hp_max`
- `HealApplied`의 `hp_current`, `hp_max`
- `PokemonFainted`의 fainted/HP 0 처리

허용되지 않는 입력:

- turn별 expected state snapshot 전체 복사
- status-only row의 HP 임의 생성
- resource snapshot 전체 복사
- outcome 강제 보정

## 작업 범위

### 1. adapter state row에 HP event replay용 컬럼 보강

파일:

```text
modules/showdown_db_adapter.py
```

ADAPT4b에서 이미 다음 컬럼이 추가되어 있다.

```text
state_event_type
state_effect
state_source
state_details_json
state_raw_line
```

이번 PR에서는 HP event replay에 필요한 값이 충분한지 확인하고, 필요하면 다음 컬럼을 추가한다.

```text
state_delta_hp
```

`state_delta_hp`는 원본 DB의 `delta_hp`를 그대로 보존한다.  
필수는 아니지만, report/triage에 도움이 된다.

기존 컬럼은 유지한다.

```text
hp_current
hp_max
fainted
state_entity_id
seq
turn_no
```

### 2. observed HP trace builder 추가

파일 후보:

```text
modules/per_battle_backtest.py
```

새 helper를 추가한다.

예시 이름:

```python
build_observed_hp_trace_from_group(...)
```

동작:

- `observed_hp_trace_enabled`가 꺼져 있으면 빈 list를 반환한다.
- `state_event_type`이 다음 중 하나인 row만 사용한다.
  - `PokemonSwitched`
  - `DamageApplied`
  - `HealApplied`
  - `PokemonFainted`
- `turn_no`가 없으면 제외한다. 단, lead switch처럼 turn이 없는 초기 상태는 initial participant/on_field 처리에 맡긴다.
- `state_entity_id`가 없으면 제외한다.
- `hp_current`가 있으면 absolute HP로 사용한다.
- `hp_max`가 있으면 max HP도 갱신한다.
- `fainted`가 true거나 `PokemonFainted`면 fainted를 true로 둔다.
- 같은 turn 안에서 event 순서가 중요하므로 `seq` 기준으로 정렬한다.
- participant id 필터링을 적용한다.

권장 trace 형태:

```python
[
    {"turn": 2, "seq": 84, "entity_id": "p1:Nanami", "hp": 403.0, "hp_max": 403.0, "fainted": False, "event_type": "PokemonSwitched"},
    {"turn": 2, "seq": 86, "entity_id": "p1:Nanami", "hp": 253.0, "hp_max": 403.0, "fainted": False, "event_type": "DamageApplied"},
    {"turn": 2, "seq": 87, "entity_id": "p1:Nanami", "hp": 278.0, "hp_max": 403.0, "fainted": False, "event_type": "HealApplied"}
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
  "observed_hp_trace_enabled": true,
  "hp_event_type_col": "state_event_type",
  "hp_entity_id_col": "state_entity_id",
  "hp_value_col": "hp_current",
  "hp_max_col": "hp_max",
  "hp_fainted_col": "fainted",
  "hp_turn_col": "turn_no",
  "hp_order_col": "seq"
}
```

기존 설정은 유지한다.

```json
{
  "state_trace_enabled": true,
  "observed_status_trace_enabled": true
}
```

### 4. battle game_config로 trace 전달

파일 후보:

```text
modules/per_battle_backtest.py
```

`build_battles_from_log_schema(...)`에서 observed HP trace를 만들고 participant id 필터링 후 battle game_config에 넣는다.

예시:

```python
battle_gc["_observed_hp_trace"] = filtered_observed_hp_trace
```

기존 `_expected_state_snapshots`는 scoring용으로 그대로 유지한다.

### 5. engine/replay에서 observed HP trace 적용

파일 후보:

```text
modules/engine.py
modules/trace_replay.py
```

재현 실행 중 observed HP trace를 적용한다.

최소 요구:

- turn 2 종료 snapshot 전에 `p1:Nanami.HP == 278.0`이 되어야 한다.
- 같은 turn의 HP events는 `seq` 오름차순으로 적용되어야 한다.
- HP 값은 absolute 값으로 적용한다.
- `hp_max`가 있으면 해당 participant max HP도 갱신한다.
- `fainted=True`면 fainted/down 상태도 반영한다.
- 없는 participant id는 무시하거나 안전하게 기록한다.

적용 시점:

- 상태 스냅샷 capture 전에 적용되어야 한다.
- ADAPT4b의 observed status trace와 충돌하지 않아야 한다.
- 같은 `_capture_state` 안에서 처리한다면 HP trace 적용 후 status trace 적용, 또는 status trace 적용 후 HP trace 적용 모두 가능하나, 둘 다 snapshot 전에 끝나야 한다.

### 6. trace replay임을 report에서 구분

가능하면 report 또는 schema에 다음 사실을 남긴다.

```text
observed_hp_trace_enabled=true
```

이 작업은 damage formula 정확도 개선이 아니라 observed trace replay 보강이라는 점을 결과 요약에 명확히 적는다.

## 금지 사항

- 원본 `.db` 파일 수정 금지
- expected state snapshot 전체를 actual state에 복사 금지
- outcome 강제 보정 금지
- damage formula 전체 구현 금지
- UI/UX 작업 금지
- ADAPT4b status trace를 되돌리거나 무력화 금지
- `.db`, `.zip`, extracted folder 입력 파이프라인 리팩터링 금지
- 요청 없으면 git stage/commit 금지

## 필수 검증

PowerShell 기준:

```powershell
$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'

& $py -X utf8 -m py_compile modules/showdown_db_adapter.py modules/per_battle_backtest.py modules/engine.py run_db_corpus_backtest.py
& $py -X utf8 test_showdown_db_extract_adapter.py
& $py -X utf8 test_db_corpus_backtest_report.py
& $py -X utf8 test_i15_integration_smoke.py

& $py -X utf8 convert_showdown_db_extract.py --input "C:\Users\kmjde\Downloads\pokemon_showdown_production_style.db" --out-dir ".codex_tmp\adapt5_hp_trace"

& $py -X utf8 run_db_corpus_backtest.py --schema ".codex_tmp\adapt5_hp_trace\schema.json" --out-dir ".codex_tmp\adapt5_hp_trace\backtest" --max-battles 1 ".codex_tmp\adapt5_hp_trace\battle_log.csv"
```

## 통과 기준

다음은 반드시 만족해야 한다.

- 모든 필수 테스트 통과
- 실제 DB 변환 성공
- `adapter_report.json`에서 `roster_only_entities == []`
- 백테스트 status가 `ran`
- first mismatch가 더 이상 아래 값이면 안 된다.

```text
turn=2
id=p1:Nanami
kind=hp
expected=278.0
actual=403.0
```

권장 기대값:

```text
state_mismatches < 56
```

허용되는 결과:

- mismatch가 다른 HP event로 이동
- mismatch가 fainted/status/outcome으로 이동
- outcome mismatch는 남아도 됨
- accuracy_pct가 0.0%로 남아도 됨

이번 PR은 전체 accuracy를 100%로 만드는 PR이 아니다.

## 산출물

작업 완료 후 다음을 보고한다.

```text
1. 변경 파일 목록
2. observed HP trace 적용 방식 요약
3. Nanami turn 2 원본 DB 이벤트와 변환 row 대응 요약
4. 수정 전/후 백테스트 핵심 수치
5. first mismatch 변화
6. 남은 mismatch의 다음 원인 후보
```

## 다음 단계 판단

ADAPT5 이후 first mismatch가 switch/on-field 문제로 이동하면 다음 작업은 observed switch trace 보강으로 넘긴다.

ADAPT5 이후 first mismatch가 action damage trace mismatch로 이동하면 damage trace scoring 또는 formula/model 단계로 넘긴다.

ADAPT5 이후 state mismatch가 크게 줄고 outcome mismatch만 남으면 outcome/accuracy 개선 단계로 넘긴다.
