# 1차목표 PR-CORPUS1d — DB 코퍼스 outcome mismatch 분류 보정

## 배경

PR-CORPUS1c 결과로 `run_db_corpus_backtest.py`가 schema의 실행 설정을 반영하게 됐다.

확인된 정상 동작:

- `combat_flow`
- `speed_stat`
- `global_damage_formula`
- `sim_max_turns`
- `move_library`
- `damage_type_map`
- `range_stat`
- `move_stat`
- `game_config` deep copy

테스트도 통과했다.

```text
python -X utf8 -m py_compile run_db_corpus_backtest.py test_db_corpus_backtest_report.py
python -X utf8 test_db_corpus_backtest_report.py
python -X utf8 test_i15_integration_smoke.py
python -X utf8 test_step6_mismatch_report.py
python -X utf8 test_mechanism_detect_aliases.py
python -X utf8 test_mechanism_commit_canonical.py
```

하지만 직접 검수에서 **next_action 분류 결함**이 보였다.

## 재현

DB 로그:

```text
battle_id,team,entity_id,result,HP,SPD,turn,actor,target,move,hp_delta
1,Ally,A1,1,100,10,1,A1,E1,Hit,30
1,Enemy,E1,0,100,1,1,A1,E1,Hit,30
```

schema 핵심:

```json
{
  "system_stats": ["HP", "SPD"],
  "health_stat": "HP",
  "speed_stat": "SPD",
  "global_damage_formula": "30",
  "sim_max_turns": 1,
  "log_schema": {
    "trace_moves_enabled": true,
    "damage_trace_enabled": true,
    "damage_value_kind": "hp_delta",
    "damage_value_col": "hp_delta"
  }
}
```

현재 결과:

```text
damage_trace.csv ran 1 acc=0.0% state_miss=0 dmg_miss=0 res_miss=0 next=passed_or_low_mismatch
```

해석:

- `global_damage_formula=30`은 정상 반영되어 action damage mismatch는 0이다.
- 하지만 승패 예측은 틀렸다. `accuracy_pct=0.0`.
- 그런데 `next_action`이 `passed_or_low_mismatch`로 나온다.

이건 리포트 사용자에게 “문제 없음”처럼 보이므로 부정확하다.

## 수정 대상

- `run_db_corpus_backtest.py`
- `test_db_corpus_backtest_report.py`

수정 금지:

- `modules/engine.py`
- `modules/per_battle_backtest.py`
- `modules/step6_dashboard.py`

## 구현 지시

### 1. outcome mismatch 필드를 추가하라

report row에 다음 필드를 추가하라.

```text
outcome_mismatches
outcome_accuracy_pct
```

계산:

```python
outcome_mismatches = sc["total"] - sc["correct"]
outcome_accuracy_pct = sc["accuracy"] * 100.0
```

기존 `accuracy_pct`, `correct`는 유지해도 된다. 다만 이름상 `accuracy_pct`도 outcome accuracy이므로 둘 중 하나를 alias로 둬도 된다.

### 2. next_action 분류에 outcome mismatch를 반영하라

현재 로직은 대략 다음 구조다.

```python
if engine_errors > 0:
    next_action = "inspect_engine_errors"
elif total_mismatches > 0:
    next_action = "inspect_mismatch"
else:
    if log_schema and not damage_trace_enabled and not state_trace_enabled:
        next_action = "need_db_event_columns"
    else:
        next_action = "passed_or_low_mismatch"
```

수정 권장:

```python
outcome_mismatches = sc["total"] - sc["correct"]

if engine_errors > 0:
    next_action = "inspect_engine_errors"
elif total_mismatches > 0:
    next_action = "inspect_mismatch"
elif outcome_mismatches > 0:
    next_action = "inspect_outcome_mismatch"
else:
    if log_schema and not (
        log_schema.get("damage_trace_enabled")
        or log_schema.get("state_trace_enabled")
        or log_schema.get("resource_delta_trace_enabled")
    ):
        next_action = "need_db_event_columns"
    else:
        next_action = "passed_or_low_mismatch"
```

우선순위 의미:

1. 엔진 에러
2. state/action/resource mismatch
3. 승패/outcome mismatch
4. 검증 컬럼 부족
5. 통과/낮은 mismatch

### 3. `need_db_event_columns` 조건도 resource delta를 포함하라

현재 조건은 damage/state만 본다.

```python
not damage_trace_enabled and not state_trace_enabled
```

resource delta trace도 event 검증축이므로 포함하라.

```python
not (
    damage_trace_enabled
    or state_trace_enabled
    or resource_delta_trace_enabled
)
```

### 4. 콘솔 요약에 outcome mismatch를 표시하라

가능하면 콘솔 표에도 outcome miss를 넣어라.

예:

```text
file status battles acc outcome_miss state_miss dmg_miss res_miss next
```

## 테스트 보강

`test_db_corpus_backtest_report.py`를 보강하라.

### A. 기존 formula 반영 테스트의 기대값 수정

현재 damage trace fixture는 action damage mismatch가 0이 되는 것이 핵심이다.
하지만 승패는 틀릴 수 있다.

따라서 기대:

```python
assert dmg_row["action_damage_mismatches"] == 0
assert dmg_row["outcome_mismatches"] > 0
assert dmg_row["next_action"] == "inspect_outcome_mismatch"
```

### B. passed 케이스 추가

가능하면 아주 작은 passed 케이스도 추가하라.

방법 1:

- formula를 `"999"`로 두어 한 턴에 Enemy를 쓰러뜨리게 한다.
- actual result도 Ally win.
- action damage expected도 `100` 또는 `hp_delta`가 실제 HP 감소량과 맞게 설정한다.

기대:

```python
outcome_mismatches == 0
total score mismatches == 0
next_action == "passed_or_low_mismatch"
```

단, HP cap 때문에 `hp_delta`는 100이어야 한다. 계산 데미지 999와 실제 hp_delta 100을 비교할 때는
`damage_value_kind: "hp_delta"`를 사용하라.

### C. HTML 거부 / schema_invalid 기존 테스트 유지

기존 테스트는 유지하라.

## 실행 검증

반드시 통과:

```bash
python -X utf8 -m py_compile run_db_corpus_backtest.py test_db_corpus_backtest_report.py
python -X utf8 test_db_corpus_backtest_report.py
python -X utf8 test_i15_integration_smoke.py
python -X utf8 test_step6_mismatch_report.py
python -X utf8 test_mechanism_detect_aliases.py
python -X utf8 test_mechanism_commit_canonical.py
```

## 금지

- 엔진 승패 판정 로직 변경 금지.
- score helper schema 변경 금지.
- outcome mismatch를 event mismatch로 섞어 계산하지 마라.
- `accuracy_pct=0`인데 `passed_or_low_mismatch`가 나오게 두지 마라.

## 완료 조건

- event score mismatch가 0이어도 승패가 틀리면 `inspect_outcome_mismatch`로 분류된다.
- outcome mismatch 수가 리포트에 표시된다.
- 진짜 통과 케이스만 `passed_or_low_mismatch`가 된다.
- 기존 회귀 테스트가 통과한다.
