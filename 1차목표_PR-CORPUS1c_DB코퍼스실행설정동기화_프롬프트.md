# 1차목표 PR-CORPUS1c — DB 코퍼스 하니스 실행 설정 동기화

## 배경

PR-CORPUS1b로 HTML 리플레이가 아니라 DB 로그 기반 `run_db_corpus_backtest.py`가 추가됐다.
방향은 맞다.

현재 통과 확인:

```text
python -X utf8 -m py_compile run_db_corpus_backtest.py test_db_corpus_backtest_report.py
python -X utf8 test_db_corpus_backtest_report.py
python -X utf8 test_i15_integration_smoke.py
python -X utf8 test_step6_mismatch_report.py
python -X utf8 test_mechanism_detect_aliases.py
python -X utf8 test_mechanism_commit_canonical.py
```

하지만 실제 검수에서 중요한 결함이 확인됐다.

`run_db_corpus_backtest.py`가 schema의 실행 설정을 충분히 반영하지 않고, 내부 worker task를 다음처럼 고정값으로 만든다.

```python
tasks.append((
    a_team, e_team, 0, None, sys_stats, "0",
    100, stoch_factory, rm, None, None, None, None, task_gc, i
))
```

즉:

- `combat_flow` 무시
- `speed_stat` 무시
- `global_damage_formula` 무시
- `sim_max_turns` / `max_turns` 무시
- `move_library` 무시
- `damage_type_map` 무시
- `spatial/range/move/deck` 실행 설정도 당장은 없지만, 최소한 schema에 있는 기본 실행 설정은 읽어야 함

## 직접 재현한 문제

임시 DB 로그:

```text
battle_id,team,entity_id,result,HP,SPD,turn,actor,target,move,hp_delta
1,Ally,A1,1,100,10,1,A1,E1,Hit,30
1,Enemy,E1,0,100,1,1,A1,E1,Hit,30
```

schema:

```json
{
  "system_stats": ["HP", "SPD"],
  "health_stat": "HP",
  "speed_stat": "SPD",
  "global_damage_formula": "30",
  "sim_max_turns": 1,
  "game_config": {"preserve_ids": true, "preserve_initial_on_field": true},
  "log_schema": {
    "battle_id_col": "battle_id",
    "team_col": "team",
    "entity_id_col": "entity_id",
    "trace_moves_enabled": true,
    "turn_col": "turn",
    "actor_id_col": "actor",
    "target_id_col": "target",
    "move_name_col": "move",
    "damage_trace_enabled": true,
    "damage_turn_col": "turn",
    "damage_actor_id_col": "actor",
    "damage_target_id_col": "target",
    "damage_value_col": "hp_delta",
    "damage_value_kind": "hp_delta"
  }
}
```

기대:

- 공식 `30`이 적용되어 `hp_delta=30`과 일치해야 한다.

현재 실제 결과:

```text
damage_trace.csv ran 1 0.0% state_miss=0 dmg_miss=1 next=inspect_mismatch
actual hp_delta=0.0
```

원인:

- 하니스가 schema의 `global_damage_formula`를 쓰지 않고 `"0"`을 worker에 넘긴다.

## 수정 대상

- `run_db_corpus_backtest.py`
- `test_db_corpus_backtest_report.py`

수정 금지:

- `modules/engine.py`
- `modules/per_battle_backtest.py`
- `modules/step6_dashboard.py`

## 구현 지시

### 1. schema에서 Step6 실행 설정을 읽어라

`run_db_corpus_backtest.py`에서 다음 값들을 schema JSON에서 읽어라.

```python
combat_flow = schema_data.get("combat_flow", DEFAULT_COMBAT_FLOW)
speed_stat = schema_data.get("speed_stat")
global_damage_formula = schema_data.get("global_damage_formula", "0")
max_turns = int(schema_data.get("sim_max_turns", schema_data.get("max_turns", 100)))
move_library = schema_data.get("move_library")
damage_type_map = schema_data.get("damage_type_map")
range_stat = schema_data.get("range_stat")
move_stat = schema_data.get("move_stat")
```

`DEFAULT_COMBAT_FLOW`는 `modules.engine`에서 import해도 된다.

```python
from modules.engine import _worker_simulate_match, default_stochasticity_factory, DEFAULT_COMBAT_FLOW
```

### 2. build_battles에 move_library를 전달하라

현재:

```python
move_library=None
```

수정:

```python
move_library=move_library
```

### 3. ResourceModule에 damage_type_map을 전달하라

현재:

```python
rm = ResourceModule(resource_config)
```

수정:

```python
rm = ResourceModule(resource_config, damage_type_map=damage_type_map)
```

### 4. worker task에 실행 설정을 넘겨라

현재:

```python
a_team, e_team, 0, None, sys_stats, "0",
100, stoch_factory, rm, None, None, None, None, task_gc, i
```

수정:

```python
a_team, e_team, combat_flow, speed_stat, sys_stats, global_damage_formula,
max_turns, stoch_factory, rm, None, range_stat, move_stat, None, task_gc, i
```

주의:

- spatial module 자체는 CLI schema에서 아직 만들지 않아도 된다. 없으면 `None`.
- deck module도 지금은 `None` 유지해도 된다.
- `range_stat`, `move_stat`은 값만 worker에 넘긴다.

### 5. game_config는 deepcopy하라

현재:

```python
task_gc = dict(game_config)
```

수정:

```python
import copy
task_gc = copy.deepcopy(game_config)
```

이유:

- `_expected_state_snapshots`, `_expected_action_damage_trace`, `_expected_action_resource_delta_trace`,
  `trace_actions` 같은 중첩 dict/list가 battle별로 들어간다.
- shallow copy는 나중에 누수/오염 원인이 될 수 있다.

### 6. report row에 실행 설정 일부를 남겨라

가능하면 report row에 다음 필드를 추가하라.

```text
speed_stat
max_turns
formula
trace_moves_enabled
state_trace_enabled
damage_trace_enabled
resource_delta_trace_enabled
```

이러면 나중에 리포트만 봐도 어떤 검증축이 켜졌는지 알 수 있다.

## 테스트 보강

`test_db_corpus_backtest_report.py`에 다음 테스트를 추가하라.

### A. global_damage_formula 반영 테스트

임시 CSV:

```text
battle_id,team,entity_id,result,HP,SPD,turn,actor,target,move,hp_delta
1,Ally,A1,1,100,10,1,A1,E1,Hit,30
1,Enemy,E1,0,100,1,1,A1,E1,Hit,30
```

schema:

```json
{
  "target_col": "result",
  "battle_size": 2,
  "system_stats": ["HP", "SPD"],
  "health_stat": "HP",
  "speed_stat": "SPD",
  "global_damage_formula": "30",
  "sim_max_turns": 1,
  "game_config": {"preserve_ids": true, "preserve_initial_on_field": true},
  "log_schema": {
    "battle_id_col": "battle_id",
    "team_col": "team",
    "entity_id_col": "entity_id",
    "result_mode": "battle_level",
    "ally_values": ["Ally"],
    "enemy_values": ["Enemy"],
    "initial_on_field_enabled": true,
    "initial_on_field_col": "team",
    "initial_on_field_values": ["Ally", "Enemy"],
    "trace_moves_enabled": true,
    "turn_col": "turn",
    "actor_id_col": "actor",
    "target_id_col": "target",
    "move_name_col": "move",
    "damage_trace_enabled": true,
    "damage_turn_col": "turn",
    "damage_actor_id_col": "actor",
    "damage_target_id_col": "target",
    "damage_value_col": "hp_delta",
    "damage_value_kind": "hp_delta"
  }
}
```

기대:

- `status == "ran"`
- `action_damage_mismatches == 0`
- `next_action`이 `inspect_mismatch`가 아니어야 한다.

### B. HTML 거부 테스트 유지

기존 HTML 거부 테스트는 유지하라.

### C. 기존 valid/invalid schema 테스트 유지

기존 `valid.csv`, `invalid.csv` 테스트도 유지하라.

## 실행 검증

다음은 반드시 통과해야 한다.

```bash
python -X utf8 -m py_compile run_db_corpus_backtest.py test_db_corpus_backtest_report.py
python -X utf8 test_db_corpus_backtest_report.py
python -X utf8 test_i15_integration_smoke.py
python -X utf8 test_step6_mismatch_report.py
python -X utf8 test_mechanism_detect_aliases.py
python -X utf8 test_mechanism_commit_canonical.py
```

## 금지

- 엔진/worker/score schema 변경 금지.
- DB 하니스에 HTML을 기본 입력으로 되살리지 마라.
- 테스트를 낮춰서 통과시키지 마라.
- 공식 `"0"` 고정, speed `None` 고정 같은 임시값을 남기지 마라.

## 완료 조건

- DB corpus 하니스가 schema의 `global_damage_formula`, `speed_stat`, `sim_max_turns`, `move_library`, `damage_type_map`을 반영한다.
- 위 damage trace 재현 테스트에서 `action_damage_mismatches == 0`이 된다.
- HTML은 기본 경로에서 계속 거부된다.
- 기존 회귀 테스트가 통과한다.
