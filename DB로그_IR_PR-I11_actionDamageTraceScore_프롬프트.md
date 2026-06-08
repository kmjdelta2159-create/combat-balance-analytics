# DB로그 IR PR-I11 — action damage trace score

## 목표

DB 역할 컬럼 백테스트에서 “누가 누구를 때렸는가”와 “턴 종료 상태가 맞는가” 다음 단계로, **각 행동이 실제로 얼마의 데미지를 냈는지**를 action 단위로 채점한다.

지금까지의 연결은 다음까지 왔다.

- 참가자 ID 보존
- move/switch/faint trace 구동
- action order/priority 반영
- initial on-field 반영
- state snapshot score
- state score 결정론 모드 분리

하지만 DB 로그에 `damage`, `hp_delta`, `damage_done` 같은 action outcome 컬럼이 있어도, 현재 per-battle 백테스트는 이것을 직접 점수화하지 않는다. 이 PR은 복제 오차를 더 잘 분해하기 위해 `action_damage_score`를 추가한다.

이 작업은 UI 표현력 개선이 아니라 최종 목표인 **DB 로그 기반 전투 시스템 복제/역설계**의 핵심 채점 축 보강이다.

## 수정 대상

가능하면 아래 3개 파일만 수정한다.

- `modules/engine.py`
- `modules/per_battle_backtest.py`
- `modules/step6_dashboard.py`

## 설계 요약

### 데이터 흐름

1. Step6 UI에서 damage trace 컬럼을 매핑한다.
2. `per_battle_backtest.build_battles_from_log_schema()`가 battle별 `_expected_action_damage_trace`를 만든다.
3. `_worker_simulate_match()`가 엔진 `APPLY_DAMAGE` phase를 캡처한다.
4. worker가 expected vs actual damage event를 비교해 `sim_metrics["action_damage_score"]`를 넣는다.
5. Step6 per-battle 결과 패널이 `action_damage_score`를 집계해 보여준다.

## 구현 요구

### 1. engine에 phase callback 표면 추가

`modules/engine.py`의 `run_simulation(...)`에 선택 인자를 추가한다.

```python
def run_simulation(..., on_turn_end=None, on_round_start=None, on_phase_event=None):
```

기존 `_broadcast_phase_event` wrapper를 확장한다.

요구 동작:

- 기존 `_broadcast_phase_event`는 항상 먼저 호출한다.
- `on_phase_event`가 있으면 모든 phase에 대해 `on_phase_event(phase_key, ctx, targets)`를 호출한다.
- 기존 `on_turn_end` 동작은 유지한다.
- `on_phase_event` 예외가 전투 전체를 죽이지 않도록 하고 싶다면 try/except로 보호해도 된다. 단, 테스트에서 조용히 누락되면 안 되므로 최소한 명확히 실패하게 두는 것도 허용한다.

예시:

```python
_btn = _broadcast_phase_event
if on_turn_end is not None or on_phase_event is not None:
    def _btn(_pk, _ctx, _targets=None, _orig=_broadcast_phase_event,
             _turn_cb=on_turn_end, _phase_cb=on_phase_event):
        _orig(_pk, _ctx, _targets)
        if _phase_cb is not None:
            _phase_cb(_pk, _ctx, _targets)
        if _turn_cb is not None and _pk == "TURN_END":
            _turn_cb(_ctx)
```

주의:

- 기존 `on_turn_end` 기반 state snapshot score를 깨지 않는다.
- `run_monte_carlo`, optimizer 호출 경로는 인자 추가만으로 기존 동작이 그대로여야 한다.

### 2. worker action damage capture 추가

`modules/engine.py`에 worker용 helper를 추가한다.

권장 helper:

```python
def _score_action_damage_for_worker(expected, actual, damage_tol=0.0):
    ...
```

expected/actual 포맷은 list of dict로 한다.

```python
{
    "turn": 1,
    "actor": "A1",
    "target": "E1",
    "damage": 50.0,
    "move": "Tackle",   # 선택
}
```

채점 최소 요구:

- list 순서대로 비교한다.
- 각 expected event마다 `turn`, `actor`, `target`, `damage`를 비교한다.
- `damage`는 `abs(expected - actual) <= damage_tol`이면 일치.
- actual event가 부족하면 `missing` 증가.
- actual event가 더 많으면 `extra` 증가.
- `identity_mismatches`: turn/actor/target 불일치 수
- `damage_mismatches`: damage 불일치 수
- `mismatches`: identity/damage/missing/extra 전체 불일치 수
- `checks`: expected event 수 + extra event 수
- `accuracy`: `1 - mismatches / checks`
- `first_mismatch`: 첫 불일치 샘플

`_worker_simulate_match()`에서:

```python
expected_damage = (game_config or {}).get("_expected_action_damage_trace")
damage_cfg = (game_config or {}).get("_action_damage_score_config") or {}
actual_damage = []
```

그리고 `on_phase_event` 콜백을 만든다.

```python
def _capture_phase(pk, ctx, targets=None):
    if pk != "APPLY_DAMAGE":
        return
    actor = ctx.get("active_char") or {}
    move = ctx.get("current_move") or {}
    target_list = targets if isinstance(targets, list) else [targets]
    for t in target_list:
        if not t:
            continue
        actual_damage.append({
            "turn": int(ctx.get("turn") or 0),
            "actor": str(actor.get("id")),
            "target": str(t.get("id")),
            "damage": float(ctx.get("dmg", 0.0) or 0.0),
            "move": str(move.get("name") or ""),
        })
```

`run_simulation(..., on_turn_end=cb, on_phase_event=phase_cb)`로 넘긴다.

시뮬 종료 후:

```python
if expected_damage:
    sim_metrics["action_damage_score"] = _score_action_damage_for_worker(
        expected_damage,
        actual_damage,
        damage_tol=float(damage_cfg.get("damage_tol", 0.0) or 0.0),
    )
```

주의:

- `expected_state`와 `expected_damage`가 동시에 있어도 둘 다 채점돼야 한다.
- `expected_damage`가 없으면 기존 metrics와 완전히 동일해야 한다.
- recoil/self-damage 같은 부가 피해는 현재 scope 밖이다. 이 PR은 `APPLY_DAMAGE`의 active actor -> current target 이벤트만 대상으로 한다.

### 3. per_battle_backtest에 damage trace builder 추가

`modules/per_battle_backtest.py`에 추가한다.

권장 함수:

```python
def build_action_damage_trace_from_group(group, log_schema):
    ...
```

입력 schema 키:

- `damage_trace_enabled`
- `damage_turn_col`
- `damage_actor_id_col`
- `damage_target_id_col`
- `damage_value_col`
- `damage_action_col` 선택
- `damage_action_values` 선택
- `damage_order_col` 선택
- `damage_order_direction` 선택, 기본 `"ascending_first"`
- `damage_move_name_col` 선택

동작:

- enabled가 아니면 `[]`.
- turn/actor/target/damage value 필수.
- action column이 있으면 `damage_action_values`에 포함되는 행만 사용한다.
- damage value는 float 변환 실패/NaN이면 skip.
- `_is_empty_id`, `_coerce_turn`, `_order_sort_key` 등 기존 helper를 재사용한다.
- `damage_order_col`이 있으면 turn별로 order 정렬한다. 없으면 row order 유지.
- 반환은 list of dict.

예시 반환:

```python
[
    {"turn": 1, "actor": "A1", "target": "E1", "damage": 50.0, "move": "Tackle"},
]
```

participant filter helper도 추가한다.

```python
def _filter_action_damage_trace_for_participants(events, participant_ids):
    return [
        e for e in events
        if e.get("actor") in participant_ids and e.get("target") in participant_ids
    ]
```

`build_battles_from_log_schema()`에서:

- `action_damage_trace = build_action_damage_trace_from_group(...)`
- battle_gc 조건에 action damage trace도 포함한다.
- filtered event가 있으면:

```python
battle_gc["_expected_action_damage_trace"] = filtered_damage
battle_gc["_action_damage_score_config"] = {
    "damage_tol": float(log_schema.get("damage_tolerance", 0.0) or 0.0),
}
has_battle_gc = True
```

주의:

- damage trace는 actor/target ID가 필요하므로 `preserve_ids=True`가 필요한 경로다. 기존 battle_gc가 만들어지는 경로와 동일하게 처리한다.
- state snapshot과 damage trace가 동시에 있어도 둘 다 battle_gc에 들어가야 한다.

### 4. Step6 UI에 damage trace 매핑 추가

`modules/step6_dashboard.py`의 `행동 trace 연결 (선택)` expander 안에 추가한다.

권장 위치:

- move trace/switch/faint trace 설정 아래
- 같은 expander 안에서 “관측 데미지 trace” 섹션으로 구분

UI 최소 요소:

```python
_td_use = st.checkbox("damage trace score 사용", value=False)
```

필수 컬럼:

- damage turn 컬럼
- damage actor ID 컬럼
- damage target ID 컬럼
- damage value 컬럼

선택 컬럼:

- damage action type 컬럼
- damage action 값 목록
- damage order 컬럼
- order 방향
- damage move name 컬럼
- damage 허용 오차

기본값/guess:

- turn/actor/target은 move trace와 같은 힌트를 재사용한다.
- damage value 힌트: `damage`, `dmg`, `hp_delta`, `damage_done`, `damage_amount`, `피해`, `데미지`, `딜`, `체력감소`
- action values 기본: `damage, hit, apply_damage, dmg, 피해, 데미지, 피격`
- tolerance 기본: `0.0`

schema update:

```python
if _td_use:
    ...
    _bb_log_schema.update({
        "damage_trace_enabled": True,
        "damage_turn_col": _bb_damage_turn_col,
        "damage_actor_id_col": _bb_damage_actor_col,
        "damage_target_id_col": _bb_damage_target_col,
        "damage_value_col": _bb_damage_value_col,
        "damage_action_col": None if _bb_damage_action_col == "(없음)" else _bb_damage_action_col,
        "damage_action_values": [x.strip() for x in _bb_damage_action_vals.split(",") if x.strip()],
        "damage_order_col": None if _bb_damage_order_col == "(없음)" else _bb_damage_order_col,
        "damage_order_direction": _bb_damage_order_dir,
        "damage_move_name_col": None if _bb_damage_move_name_col == "(없음)" else _bb_damage_move_name_col,
        "damage_tolerance": float(_bb_damage_tol),
    })
```

validation warning:

- damage trace를 켰는데 turn/actor/target/damage value 중 하나가 없으면 warning.
- 이 경우 schema에 `damage_trace_enabled`를 넣지 않는다.

### 5. Step6 결과 집계 표시

per-battle worker result 수집부에서:

```python
_bb_action_damage_scores = []
...
if isinstance(_metrics, dict) and _metrics.get("action_damage_score"):
    _bb_action_damage_scores.append(_metrics["action_damage_score"])
```

결과 UI:

- `행동 데미지 일치율`
- `damage 불일치`
- `actor/target/turn 불일치`
- `누락/추가 이벤트`
- 첫 불일치 샘플 caption

집계 예시:

```python
if _bb_action_damage_scores:
    _d_checks = sum(int(s.get("checks", 0) or 0) for s in _bb_action_damage_scores)
    _d_mismatch = sum(int(s.get("mismatches", 0) or 0) for s in _bb_action_damage_scores)
    _d_acc = (1.0 - (_d_mismatch / _d_checks)) * 100.0 if _d_checks > 0 else 0.0
```

## 수용 조건

### A. AST

```powershell
@'
import ast
from pathlib import Path
for p in ["modules/engine.py", "modules/per_battle_backtest.py", "modules/step6_dashboard.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### B. run_simulation phase callback

```powershell
@'
from modules.engine import run_simulation

events = []
def on_phase(pk, ctx, targets):
    if pk == "APPLY_DAMAGE":
        target_list = targets if isinstance(targets, list) else [targets]
        for t in target_list:
            events.append((ctx.get("turn"), ctx["active_char"]["id"], t["id"], ctx.get("dmg")))

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 50, "SPD": 1,
          "resources": {"HP": {"current": 50, "max": 50}}}]

run_simulation(
    ally, enemy, max_turns=1,
    speed_stat="SPD", sys_stats=["HP", "SPD"],
    global_damage_formula="50",
    game_config={"preserve_ids": True},
    on_phase_event=on_phase,
    silent=True,
)
print(events)
assert events == [(1, "A1", "E1", 50)]
print("phase callback damage capture OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### C. worker action_damage_score perfect match

```powershell
@'
from modules.engine import _worker_simulate_match

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 50, "SPD": 1,
          "resources": {"HP": {"current": 50, "max": 50}}}]
gc = {
    "preserve_ids": True,
    "_expected_action_damage_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "damage": 50.0}
    ],
    "_action_damage_score_config": {"damage_tol": 0.0},
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["action_damage_score"]
assert score["checks"] == 1
assert score["mismatches"] == 0
assert score["missing"] == 0
assert score["extra"] == 0
assert score["accuracy"] == 1.0
print("worker action damage score OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### D. state_score와 action_damage_score 공존

```powershell
@'
from modules.engine import _worker_simulate_match

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 50, "SPD": 1,
          "resources": {"HP": {"current": 50, "max": 50}}}]
gc = {
    "preserve_ids": True,
    "_expected_action_damage_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "damage": 50.0}
    ],
    "_action_damage_score_config": {"damage_tol": 0.0},
    "_expected_state_snapshots": {
        1: {
            "A1": {"hp": 100.0, "fainted": False},
            "E1": {"hp": 0.0, "fainted": True},
        }
    },
    "_state_score_config": {"hp_mode": "absolute", "hp_tol": 0.0},
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
assert res[1]["action_damage_score"]["accuracy"] == 1.0
assert res[1]["state_score"]["accuracy"] == 1.0
print("state + action damage scores coexist OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### E. per_battle damage trace builder

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_action_damage_trace_from_group

df = pd.DataFrame([
    {"battle": "B1", "turn": 1, "actor": "A1", "target": "E1", "dmg": 50, "event": "damage", "ord": 2},
    {"battle": "B1", "turn": 1, "actor": "E1", "target": "A1", "dmg": 10, "event": "note", "ord": 1},
])
schema = {
    "damage_trace_enabled": True,
    "damage_turn_col": "turn",
    "damage_actor_id_col": "actor",
    "damage_target_id_col": "target",
    "damage_value_col": "dmg",
    "damage_action_col": "event",
    "damage_action_values": ["damage"],
    "damage_order_col": "ord",
}
trace = build_action_damage_trace_from_group(df, schema)
print(trace)
assert trace == [{"turn": 1, "actor": "A1", "target": "E1", "damage": 50.0}]
print("damage trace builder OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### F. build_battles DB role path includes action damage trace

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_battles

df = pd.DataFrame([
    {"battle": "B1", "team": "Ally", "unit": "A1", "result": 1, "HP": 100, "SPD": 999,
     "turn": 1, "actor": "A1", "target": "E1", "dmg": 50, "event": "damage"},
    {"battle": "B1", "team": "Enemy", "unit": "E1", "result": 0, "HP": 50, "SPD": 1,
     "turn": 1, "actor": "A1", "target": "E1", "dmg": 50, "event": "damage"},
])
schema = {
    "battle_id_col": "battle",
    "team_col": "team",
    "entity_id_col": "unit",
    "result_mode": "battle_level",
    "ally_values": ["Ally"],
    "enemy_values": ["Enemy"],
    "damage_trace_enabled": True,
    "damage_turn_col": "turn",
    "damage_actor_id_col": "actor",
    "damage_target_id_col": "target",
    "damage_value_col": "dmg",
    "damage_action_col": "event",
    "damage_action_values": ["damage"],
    "damage_tolerance": 0.0,
}
battles = build_battles(
    df, 2, "result", ["HP", "SPD"], [], "HP",
    max_battles=10,
    game_config={"preserve_ids": True},
    log_schema=schema,
)
print(battles)
assert len(battles) == 1
assert len(battles[0]) == 4
gc = battles[0][3]
assert gc["_expected_action_damage_trace"] == [
    {"turn": 1, "actor": "A1", "target": "E1", "damage": 50.0}
]
assert gc["_action_damage_score_config"]["damage_tol"] == 0.0
print("build_battles action damage trace OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### G. Step6 source guard

```powershell
@'
from pathlib import Path
src = Path("modules/step6_dashboard.py").read_text(encoding="utf-8")
assert "damage_trace_enabled" in src
assert "action_damage_score" in src
assert "_bb_action_damage_scores" in src
assert "damage_tolerance" in src
print("step6 action damage score source guard OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

## 금지/주의

- `default_stochasticity_factory` 자체를 바꾸지 않는다.
- 기존 `state_score` 캡처를 깨지 않는다.
- `_worker_simulate_match`의 args tuple 구조를 바꾸지 않는다.
- recoil, poison, weather, hazard 등 간접 데미지까지 모두 action damage trace로 포함하려고 범위를 넓히지 않는다. 이번 PR은 active actor의 `APPLY_DAMAGE`만 점수화한다.
- Streamlit UI에서 변수가 조건부 블록 안에서만 정의되어 나중에 `NameError`가 나지 않게 한다.

