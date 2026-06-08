# DB코퍼스_PR-ADAPT6 - observed switch trace replay

## 목적

ADAPT5는 통과했다.

관측 HP event replay가 적용되면서 기존 first mismatch였던 `p1:Nanami hp expected 278.0 actual 403.0`는 사라졌다.

현재 남은 first mismatch는 다음과 같다.

```text
first_mismatch_score_type=state
first_mismatch_turn=18
first_mismatch_id=p2:Metagross
first_mismatch_kind=missing
first_mismatch_expected=''
first_mismatch_actual=''
```

이번 PR의 목적은 관측 DB 로그의 `PokemonSwitched` 이벤트를 재현 실행에 반영하는 `observed switch trace`를 추가해서, turn 18의 `p2:Metagross` missing mismatch를 제거하는 것이다.

이번 PR은 damage formula나 outcome 정확도를 완성하는 PR이 아니다.  
관측된 switch/active transition을 discrete trace로 재현 실행에 공급하는 PR이다.

## 현재 상태

ADAPT5 검수 결과:

```text
status=ran
battle_count=1
rows=224
columns=35
state_checks=92
state_mismatches=22
outcome_mismatches=1
first_mismatch_turn=18
first_mismatch_id=p2:Metagross
first_mismatch_kind=missing
next_action=inspect_mismatch
```

ADAPT5 이전 대비:

```text
ADAPT4b state_mismatches=56
ADAPT5  state_mismatches=22
```

검증된 산출물:

```text
.codex_tmp\adapt5_hp_trace\battle_log.csv
.codex_tmp\adapt5_hp_trace\schema.json
.codex_tmp\adapt5_hp_trace\adapter_report.json
.codex_tmp\adapt5_hp_trace\backtest\db_corpus_backtest_summary.csv
```

재실행 검증 산출물:

```text
.codex_tmp\adapt5_hp_trace_verify\battle_log.csv
.codex_tmp\adapt5_hp_trace_verify\schema.json
.codex_tmp\adapt5_hp_trace_verify\adapter_report.json
.codex_tmp\adapt5_hp_trace_verify\backtest\db_corpus_backtest_summary.csv
```

현재 schema에는 다음 switch trace 설정이 없다.

```text
trace_switches_enabled=None
switch_turn_col=None
switch_outgoing_id_col=None
switch_incoming_id_col=None
trace_faint_incoming_enabled=None
```

## 확정 사실

원본 SQLite DB에는 turn 18 Metagross switch-in 이벤트가 있다.

```text
seq=236
turn_no=18
phase=Switch
event_type=PokemonSwitched
actor_id=p2a: Metagross
actor_side=p2
actor_name=Metagross
pokemon_name=Metagross
hp_current=344
hp_max=344
raw_line=|switch|p2a: Metagross|Metagross|344/344
```

바로 다음에 entry hazard damage가 있다.

```text
seq=237
turn_no=18
event_type=DamageApplied
actor_id=p2a: Metagross
hp_current=323
hp_max=344
delta_hp=-21
source=Stealth Rock
raw_line=|-damage|p2a: Metagross|323/344|[from] Stealth Rock
```

변환된 `battle_log.csv`에도 대응 state rows가 있다.

```text
seq=236
turn_no=18
row_kind=state
state_entity_id=p2:Metagross
hp_current=344
hp_max=344
state_event_type=PokemonSwitched

seq=237
turn_no=18
row_kind=state
state_entity_id=p2:Metagross
hp_current=323
hp_max=344
state_event_type=DamageApplied
```

따라서 문제 위치는 다음이 아니다.

- SQLite `.db` 입력 실패 아님
- adapter가 Metagross state row를 누락한 문제 아님
- observed HP trace가 turn 18 HP row를 누락한 문제 아님

문제 위치는 다음이다.

- 재현 실행이 관측된 `PokemonSwitched` active transition을 소비하지 못함
- 기존 `trace_actions.switch`는 outgoing/incoming 쌍을 요구하지만 Showdown DB row는 incoming만 직접 제공함
- Showdown DB의 `PokemonSwitched` sequence에서 outgoing을 추론해 switch trace를 만들어야 함

## 핵심 원칙

expected state snapshot 전체를 actual state에 복사하면 안 된다.

이번 PR은 state snapshot 덮어쓰기 PR이 아니다.  
반드시 discrete `PokemonSwitched` 이벤트 기반으로만 처리한다.

허용되는 입력:

- `state_event_type == "PokemonSwitched"`
- `state_entity_id`
- `turn_no`
- `seq`
- `hp_current`, `hp_max`는 ADAPT5 observed HP trace가 처리하므로 switch trace에서는 active transition에만 사용한다.

허용되지 않는 입력:

- expected state snapshot 전체 복사
- turn별 active set 전체를 강제로 복사
- outcome 강제 보정
- damage formula 전체 구현

## 작업 범위

### 1. observed switch trace builder 추가

파일 후보:

```text
modules/per_battle_backtest.py
```

새 helper를 추가한다.

예시 이름:

```python
build_observed_switch_trace_from_group(...)
```

동작:

- `observed_switch_trace_enabled`가 꺼져 있으면 빈 결과를 반환한다.
- `state_event_type == "PokemonSwitched"`인 row만 사용한다.
- `turn_no`, `seq`, `state_entity_id`가 없으면 제외한다.
- lead switch처럼 `turn_no`가 없는 row는 initial active state로만 사용하고 switch action으로 만들지 않는다.
- entity id prefix에서 side를 추출한다.
  - 예: `p2:Metagross` -> side `p2`
- 같은 side의 이전 active를 추적한다.
- turn이 있는 switch row에서 이전 active가 있고 incoming과 다르면 다음 switch trace를 만든다.

권장 trace 형태:

```python
{
    "switch": {
        (18, "p2:Latios"): "p2:Metagross"
    },
    "faint_incoming": [
        {"turn": 17, "outgoing": "p1:Gengen", "incoming": "p1:Nanami"}
    ]
}
```

### 2. voluntary switch와 faint replacement 구분

Showdown switch에는 크게 두 상황이 있다.

1. 일반/강제 switch
   - 이전 active가 살아 있음
   - 기존 engine의 `trace_actions.switch[(turn, outgoing)] = incoming`으로 전달한다.

2. faint 이후 replacement
   - 같은 side의 이전 active가 직전 또는 같은 turn에 fainted
   - 기존 engine의 `trace_faint_incoming`으로 전달한다.

필요하면 observed HP trace 또는 state rows의 `PokemonFainted` 정보를 함께 사용한다.

예시:

```text
seq=231 turn=17 PokemonFainted p1:Gengen
seq=234 turn=17 PokemonSwitched p1:Nanami
```

이 경우:

```python
{"turn": 17, "outgoing": "p1:Gengen", "incoming": "p1:Nanami"}
```

### 3. schema/log config에 명시 플래그 추가

파일 후보:

```text
modules/showdown_db_adapter.py
```

`generate_schema()`의 `log_schema`에 다음을 추가한다.

```json
{
  "observed_switch_trace_enabled": true,
  "switch_event_type_col": "state_event_type",
  "switch_entity_id_col": "state_entity_id",
  "switch_turn_col": "turn_no",
  "switch_order_col": "seq"
}
```

기존 설정은 유지한다.

```json
{
  "trace_moves_enabled": true,
  "state_trace_enabled": true,
  "observed_status_trace_enabled": true,
  "observed_hp_trace_enabled": true
}
```

### 4. battle game_config로 trace 전달

파일 후보:

```text
modules/per_battle_backtest.py
```

`build_battles_from_log_schema(...)`에서 observed switch trace를 만들고 participant id 필터링 후 battle game_config에 넣는다.

기존 engine 기능을 우선 재사용한다.

```python
battle_gc["trace_actions"]["switch"][(turn, outgoing)] = incoming
battle_gc["trace_faint_incoming"].append(...)
battle_gc["on_active_faint"] = "replace_from_reserve"
```

이미 move trace가 `trace_actions["move"]`를 사용하고 있으므로, switch trace를 merge할 때 move trace를 덮어쓰면 안 된다.

### 5. timing 확인

turn 18의 `p2:Metagross`는 turn 18 snapshot 전에 active로 들어와야 한다.

최소 요구:

- turn 18에 `p2:Latios -> p2:Metagross` switch가 재현되어야 한다.
- ADAPT5 observed HP trace가 turn 18 `p2:Metagross HP 323/344`를 적용할 수 있어야 한다.
- first mismatch가 더 이상 `turn=18 id=p2:Metagross kind=missing`이면 안 된다.

### 6. diagnostics 보강

가능하면 백테스트 summary 또는 debug log에 다음을 임시/영구 중 편한 방식으로 확인한다.

```text
observed_switch_trace_count
observed_faint_incoming_count
first observed switch: p2:Latios -> p2:Metagross at turn 18
```

필수는 아니지만, 검수에 도움이 된다.

## 금지 사항

- 원본 `.db` 파일 수정 금지
- expected state snapshot 전체를 actual state에 복사 금지
- outcome 강제 보정 금지
- damage formula 전체 구현 금지
- UI/UX 작업 금지
- ADAPT4b status trace를 되돌리거나 무력화 금지
- ADAPT5 HP trace를 되돌리거나 무력화 금지
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

& $py -X utf8 convert_showdown_db_extract.py --input "C:\Users\kmjde\Downloads\pokemon_showdown_production_style.db" --out-dir ".codex_tmp\adapt6_switch_trace"

& $py -X utf8 run_db_corpus_backtest.py --schema ".codex_tmp\adapt6_switch_trace\schema.json" --out-dir ".codex_tmp\adapt6_switch_trace\backtest" --max-battles 1 ".codex_tmp\adapt6_switch_trace\battle_log.csv"
```

## 통과 기준

다음은 반드시 만족해야 한다.

- 모든 필수 테스트 통과
- 실제 DB 변환 성공
- `adapter_report.json`에서 `roster_only_entities == []`
- 백테스트 status가 `ran`
- first mismatch가 더 이상 아래 값이면 안 된다.

```text
turn=18
id=p2:Metagross
kind=missing
```

권장 기대값:

```text
state_mismatches < 22
```

허용되는 결과:

- mismatch가 다른 HP/status/fainted event로 이동
- outcome mismatch는 남아도 됨
- accuracy_pct가 0.0%로 남아도 됨

이번 PR은 전체 accuracy를 100%로 만드는 PR이 아니다.

## 산출물

작업 완료 후 다음을 보고한다.

```text
1. 변경 파일 목록
2. observed switch trace 적용 방식 요약
3. turn 18 Metagross 원본 DB 이벤트와 변환 row 대응 요약
4. 추론된 switch trace 예시: p2:Latios -> p2:Metagross
5. 수정 전/후 백테스트 핵심 수치
6. first mismatch 변화
7. 남은 mismatch의 다음 원인 후보
```

## 다음 단계 판단

ADAPT6 이후 first mismatch가 Protect/Explosion 같은 move effect로 이동하면 다음 작업은 observed move-effect trace 또는 specific mechanic replay로 넘긴다.

ADAPT6 이후 first mismatch가 action damage trace mismatch로 이동하면 damage trace scoring 또는 formula/model 단계로 넘긴다.

ADAPT6 이후 state mismatch가 크게 줄고 outcome mismatch만 남으면 outcome/accuracy 개선 단계로 넘긴다.
