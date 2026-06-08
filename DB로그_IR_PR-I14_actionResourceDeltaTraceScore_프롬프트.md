# DB로그 IR PR-I14 — action resource delta trace score

## 목표

PR-I12는 action damage score에서 `damage`와 `hp_delta`를 분리했다. PR-I13은 turn state snapshot에서 HP 외 임의 resource도 비교하게 했다.

하지만 실드/장갑/보호막/특수 자원 직격이 있는 게임에서는 action 단위로 다음 질문에 답해야 한다.

- 이 공격이 HP를 얼마나 깎았는가?
- 이 공격이 Shield/Armor/Barrier를 얼마나 깎았는가?
- DB 로그의 `shield_loss`, `armor_damage`, `mp_damage` 같은 컬럼과 엔진 결과가 맞는가?

이 PR은 `APPLY_DAMAGE` phase에서 target의 resource별 감소량을 캡처하고, DB 로그의 action resource delta trace와 비교하는 `action_resource_delta_score`를 추가한다.

이 작업은 최종 목표인 **DB 로그 기반 전투 시스템 복제/역설계**에서 HP 외 자원 라우팅, 실드 흡수, Armor/Barrier 모델을 검증하기 위한 축이다.

## 수정 대상

가능하면 아래 3개 파일만 수정한다.

- `modules/engine.py`
- `modules/per_battle_backtest.py`
- `modules/step6_dashboard.py`

## 설계 요약

expected action resource delta trace 포맷:

```python
[
    {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0},
    {"turn": 1, "actor": "A1", "target": "E1", "resource": "HP", "delta": 30.0},
]
```

의미:

- `delta`는 resource current 감소량이다.
- 양수 loss만 대상으로 한다.
- 회복/충전/비용 지불은 이번 PR 범위 밖이다. 이번 PR은 `APPLY_DAMAGE`로 인해 target resource가 감소한 값만 점수화한다.

## 구현 요구

### 1. engine damage_result에 resource_deltas 추가

`modules/engine.py`의 `_act_apply_damage(ctx)`에서 target resources의 before/after를 기록한다.

현재 I12에서 이미 `damage_result`를 만든다. 여기에 resource별 정보만 추가한다.

권장 구현:

```python
target_resources = t.get("resources") or {}
resources_before = {
    str(name): float((res or {}).get("current", 0.0) or 0.0)
    for name, res in target_resources.items()
}

# 기존 route_damage/apply_delta 실행

resources_after = {
    str(name): float((res or {}).get("current", 0.0) or 0.0)
    for name, res in (t.get("resources") or {}).items()
}
resource_deltas = {}
for name, before in resources_before.items():
    after = resources_after.get(name, 0.0)
    loss = max(0.0, before - after)
    if loss > 0:
        resource_deltas[name] = loss
```

그리고 `ctx["damage_result"]`에 넣는다.

```python
"resources_before": resources_before,
"resources_after": resources_after,
"resource_deltas": resource_deltas,
```

주의:

- 기존 `damage`, `hp_delta`, `absorbed`, `hp_before`, `hp_after` 의미를 바꾸지 않는다.
- `damage_result`는 `_broadcast_phase_event("APPLY_DAMAGE", ...)` 전에 세팅되어야 한다.
- resource dict가 비어 있어도 안전해야 한다.

### 2. worker에 action_resource_delta_score 추가

`modules/engine.py`에 helper를 추가한다.

권장 함수:

```python
def _score_action_resource_delta_for_worker(expected, actual, delta_tol=0.0):
    ...
```

비교 규칙:

- expected/actual은 list of dict.
- event identity는 `turn`, `actor`, `target`, `resource`.
- `delta`는 `abs(expected - actual) <= delta_tol`이면 일치.
- resource delta event는 같은 action 안에서 순서 의미가 약하므로, 비교 전 양쪽을 다음 key로 정렬해도 된다.

```python
key = (turn, actor, target, resource)
```

metrics:

- `checks`
- `mismatches`
- `identity_mismatches`
- `delta_mismatches`
- `missing`
- `extra`
- `accuracy`
- `first_mismatch`

`_worker_simulate_match()`에서:

```python
expected_resource_delta = (game_config or {}).get("_expected_action_resource_delta_trace")
resource_delta_cfg = (game_config or {}).get("_action_resource_delta_score_config") or {}
actual_resource_delta = []
```

`_capture_phase()`는 `expected_damage` 또는 `expected_resource_delta`가 있을 때 활성화한다.

```python
phase_cb = _capture_phase if (expected_damage or expected_resource_delta) else None
```

`APPLY_DAMAGE`에서 `damage_result["resource_deltas"]`를 actual event로 펼친다.

```python
if expected_resource_delta:
    for rname, delta in (dr.get("resource_deltas") or {}).items():
        if float(delta or 0.0) <= 0:
            continue
        actual_resource_delta.append({
            "turn": int(ctx.get("turn") or 0),
            "actor": str(actor.get("id")),
            "target": str(t.get("id")),
            "resource": str(rname),
            "delta": float(delta or 0.0),
            "move": str(move.get("name") or ""),
        })
```

시뮬레이션 후:

```python
if expected_resource_delta:
    sim_metrics["action_resource_delta_score"] = _score_action_resource_delta_for_worker(
        expected_resource_delta,
        actual_resource_delta,
        delta_tol=float(resource_delta_cfg.get("delta_tol", 0.0) or 0.0),
    )
```

주의:

- 기존 `action_damage_score`와 동시에 켜져도 둘 다 채점되어야 한다.
- `_worker_simulate_match` args tuple 구조를 바꾸지 않는다.
- `on_phase_event` I11b 수정 사항을 되돌리지 않는다.

### 3. per_battle_backtest builder 추가

`modules/per_battle_backtest.py`에 builder를 추가한다.

권장 함수:

```python
def build_action_resource_delta_trace_from_group(group, log_schema):
    ...
```

schema 키:

- `resource_delta_trace_enabled`
- `resource_delta_turn_col`
- `resource_delta_actor_id_col`
- `resource_delta_target_id_col`
- `resource_delta_cols`: dict, 예: `{"Shield": "shield_loss", "HP": "hp_loss"}`
- `resource_delta_action_col` 선택
- `resource_delta_action_values` 선택
- `resource_delta_order_col` 선택
- `resource_delta_order_direction` 선택, 기본 `"ascending_first"`

동작:

- enabled가 아니면 `[]`.
- turn/actor/target/resource_delta_cols가 없으면 `[]`.
- action column이 있고 action values가 있으면 해당 action value만 사용한다.
- 각 row마다 `resource_delta_cols`를 순회한다.
- 값이 비어 있거나 float 변환 실패/NaN이면 skip.
- `delta <= 0`이면 skip한다.
- event는 `{"turn", "actor", "target", "resource", "delta"}`.
- 중복 event는 제거한다.
- order column이 있으면 기존 `build_action_damage_trace_from_group()`와 유사하게 정렬한다. 정렬 후 `_ord` 같은 내부 키는 제거한다.

participant filter helper:

```python
def _filter_action_resource_delta_trace_for_participants(events, participant_ids):
    return [
        e for e in events
        if e.get("actor") in participant_ids and e.get("target") in participant_ids
    ]
```

`build_battles_from_log_schema()`에서:

- `action_resource_delta_trace = build_action_resource_delta_trace_from_group(group, log_schema)`
- battle_gc 생성 조건에 포함한다.
- filtered event가 있으면:

```python
battle_gc["_expected_action_resource_delta_trace"] = filtered_resource_delta
battle_gc["_action_resource_delta_score_config"] = {
    "delta_tol": float(log_schema.get("resource_delta_tolerance", 0.0) or 0.0),
}
has_battle_gc = True
```

### 4. Step6 UI 추가

`modules/step6_dashboard.py`의 `행동 trace 연결 (선택)` expander 안, damage trace score 아래에 추가한다.

권장 UI:

```python
st.markdown("---")
_trd_use = st.checkbox("resource delta trace score 사용", value=False)
```

필수 매핑:

- turn
- actor ID
- target ID
- resource delta columns

resource delta columns:

```python
_bb_resource_delta_cols = {}
_resource_config_for_delta = st.session_state.get("resource_config") or {}
_resource_names_for_delta = list(_resource_config_for_delta.keys())
_bb_resource_delta_names = st.multiselect(
    "resource delta 컬럼 추가",
    _resource_names_for_delta,
    default=[],
    help="APPLY_DAMAGE로 감소한 HP/Shield/Armor 등 target resource loss를 비교합니다."
)
for _rname in _bb_resource_delta_names:
    _guess = _guess_col([
        f"{_rname}_loss", f"{_rname}_delta", f"{_rname}_damage",
        str(_rname).lower(), str(_rname),
    ])
    _col = st.selectbox(
        f"{_rname} loss/delta 컬럼",
        _all_cols,
        index=_all_cols.index(_guess) if _guess in _all_cols else 0,
        key=f"bb_resource_delta_col_{_rname}",
    )
    if _col != "(없음)":
        _bb_resource_delta_cols[str(_rname)] = _col
```

추가 옵션:

- `resource delta action type 컬럼`
- `resource delta action 값 목록`
- `resource delta order 컬럼`
- `resource delta order 방향`
- `resource delta 허용 오차`

schema update:

```python
if _trd_use:
    if required missing:
        st.warning(...)
    elif not _bb_resource_delta_cols:
        st.warning(...)
    else:
        _bb_log_schema.update({
            "resource_delta_trace_enabled": True,
            "resource_delta_turn_col": _bb_resource_delta_turn_col,
            "resource_delta_actor_id_col": _bb_resource_delta_actor_col,
            "resource_delta_target_id_col": _bb_resource_delta_target_col,
            "resource_delta_cols": dict(_bb_resource_delta_cols),
            "resource_delta_action_col": None if _bb_resource_delta_action_col == "(없음)" else _bb_resource_delta_action_col,
            "resource_delta_action_values": [x.strip() for x in _bb_resource_delta_action_vals.split(",") if x.strip()],
            "resource_delta_order_col": None if _bb_resource_delta_order_col == "(없음)" else _bb_resource_delta_order_col,
            "resource_delta_order_direction": _bb_resource_delta_order_dir,
            "resource_delta_tolerance": float(_bb_resource_delta_tol),
        })
```

주의:

- `_bb_resource_delta_cols` 등은 checkbox가 꺼져 있어도 later reference가 안전하게 기본값을 갖게 한다.
- HP도 resource delta 대상에 포함할 수 있다. HP loss와 I12 `hp_delta`는 의미가 겹치지만, resource별 score에서는 HP/Shield를 같은 축으로 비교할 수 있어야 한다.

### 5. Step6 결과 집계 표시

per-battle worker result 수집부에:

```python
_bb_action_resource_delta_scores = []
...
if _metrics.get("action_resource_delta_score"):
    _bb_action_resource_delta_scores.append(_metrics["action_resource_delta_score"])
```

결과 표시:

- `자원 delta 일치율`
- `delta 불일치`
- `identity 불일치`
- `누락/추가 이벤트`
- 첫 불일치 샘플

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

### B. damage_result resource_deltas

Shield가 먼저 흡수하고 남은 피해가 HP로 들어가는 케이스를 캡처한다.

```powershell
@'
from modules.engine import run_simulation
from modules.resource import ResourceModule

events = []

def on_phase(pk, ctx, targets):
    if pk != "APPLY_DAMAGE":
        return
    events.append(ctx.get("damage_result") or {})

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 1,
          "resources": {
              "HP": {"current": 100, "max": 100},
              "Shield": {"current": 20, "max": 20},
          }}]
rm = ResourceModule({
    "HP": {"role": "vital", "stat": "HP", "regen": 0.0},
    "Shield": {"role": "shield", "stat": "Shield", "regen": 0.0},
})

run_simulation(
    ally, enemy, max_turns=1,
    speed_stat="SPD", sys_stats=["HP", "SPD"],
    global_damage_formula="50",
    game_config={"preserve_ids": True},
    resource_module=rm,
    on_phase_event=on_phase,
    silent=True,
)
print(events)
assert len(events) == 1
dr = events[0]
assert dr["resource_deltas"]["Shield"] == 20
assert dr["resource_deltas"]["HP"] == 30
assert dr["hp_delta"] == 30
assert dr["absorbed"] == 20
print("damage_result resource_deltas OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### C. worker action_resource_delta_score perfect match

```powershell
@'
from modules.engine import _worker_simulate_match
from modules.resource import ResourceModule

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 1,
          "resources": {
              "HP": {"current": 100, "max": 100},
              "Shield": {"current": 20, "max": 20},
          }}]
rm = ResourceModule({
    "HP": {"role": "vital", "stat": "HP", "regen": 0.0},
    "Shield": {"role": "shield", "stat": "Shield", "regen": 0.0},
})
gc = {
    "preserve_ids": True,
    "_expected_action_resource_delta_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "resource": "HP", "delta": 30.0},
        {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0},
    ],
    "_action_resource_delta_score_config": {"delta_tol": 0.0},
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, rm, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["action_resource_delta_score"]
assert score["checks"] == 2
assert score["mismatches"] == 0
assert score["accuracy"] == 1.0
print("worker action resource delta score OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### D. worker action_resource_delta_score mismatch

```powershell
@'
from modules.engine import _worker_simulate_match
from modules.resource import ResourceModule

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 1,
          "resources": {
              "HP": {"current": 100, "max": 100},
              "Shield": {"current": 20, "max": 20},
          }}]
rm = ResourceModule({
    "HP": {"role": "vital", "stat": "HP", "regen": 0.0},
    "Shield": {"role": "shield", "stat": "Shield", "regen": 0.0},
})
gc = {
    "preserve_ids": True,
    "_expected_action_resource_delta_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 10.0},
    ],
    "_action_resource_delta_score_config": {"delta_tol": 0.0},
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, rm, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["action_resource_delta_score"]
assert score["mismatches"] > 0
assert score["delta_mismatches"] == 1
assert score["first_mismatch"]["resource"] == "Shield"
print("worker action resource delta mismatch OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### E. action_damage_score와 action_resource_delta_score 공존

```powershell
@'
from modules.engine import _worker_simulate_match
from modules.resource import ResourceModule

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 1,
          "resources": {
              "HP": {"current": 100, "max": 100},
              "Shield": {"current": 20, "max": 20},
          }}]
rm = ResourceModule({
    "HP": {"role": "vital", "stat": "HP", "regen": 0.0},
    "Shield": {"role": "shield", "stat": "Shield", "regen": 0.0},
})
gc = {
    "preserve_ids": True,
    "_expected_action_damage_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "hp_delta": 30.0}
    ],
    "_action_damage_score_config": {"damage_tol": 0.0, "compare_field": "hp_delta"},
    "_expected_action_resource_delta_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "resource": "HP", "delta": 30.0},
        {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0},
    ],
    "_action_resource_delta_score_config": {"delta_tol": 0.0},
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, rm, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
assert res[1]["action_damage_score"]["accuracy"] == 1.0
assert res[1]["action_resource_delta_score"]["accuracy"] == 1.0
print("action damage + resource delta scores coexist OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### F. per_battle resource delta trace builder

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_action_resource_delta_trace_from_group

df = pd.DataFrame([
    {"turn": 1, "actor": "A1", "target": "E1", "hp_loss": 30, "shield_loss": 20, "event": "damage"},
    {"turn": 1, "actor": "A1", "target": "E1", "hp_loss": 30, "shield_loss": 20, "event": "note"},
])
schema = {
    "resource_delta_trace_enabled": True,
    "resource_delta_turn_col": "turn",
    "resource_delta_actor_id_col": "actor",
    "resource_delta_target_id_col": "target",
    "resource_delta_cols": {"HP": "hp_loss", "Shield": "shield_loss"},
    "resource_delta_action_col": "event",
    "resource_delta_action_values": ["damage"],
}
trace = build_action_resource_delta_trace_from_group(df, schema)
print(trace)
assert {"turn": 1, "actor": "A1", "target": "E1", "resource": "HP", "delta": 30.0} in trace
assert {"turn": 1, "actor": "A1", "target": "E1", "resource": "Shield", "delta": 20.0} in trace
assert len(trace) == 2
print("resource delta trace builder OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### G. build_battles DB path includes resource delta trace

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_battles

df = pd.DataFrame([
    {"battle": "B1", "team": "Ally", "unit": "A1", "result": 1, "HP": 100, "SPD": 999,
     "turn": 1, "actor": "A1", "target": "E1", "hp_loss": 30, "shield_loss": 20, "event": "damage"},
    {"battle": "B1", "team": "Enemy", "unit": "E1", "result": 0, "HP": 100, "SPD": 1,
     "turn": 1, "actor": "A1", "target": "E1", "hp_loss": 30, "shield_loss": 20, "event": "damage"},
])
schema = {
    "battle_id_col": "battle",
    "team_col": "team",
    "entity_id_col": "unit",
    "result_mode": "battle_level",
    "ally_values": ["Ally"],
    "enemy_values": ["Enemy"],
    "resource_delta_trace_enabled": True,
    "resource_delta_turn_col": "turn",
    "resource_delta_actor_id_col": "actor",
    "resource_delta_target_id_col": "target",
    "resource_delta_cols": {"HP": "hp_loss", "Shield": "shield_loss"},
    "resource_delta_action_col": "event",
    "resource_delta_action_values": ["damage"],
    "resource_delta_tolerance": 0.0,
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
assert len(gc["_expected_action_resource_delta_trace"]) == 2
assert gc["_action_resource_delta_score_config"]["delta_tol"] == 0.0
print("build_battles resource delta trace OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### H. Step6 source guard

```powershell
@'
from pathlib import Path
src = Path("modules/step6_dashboard.py").read_text(encoding="utf-8")
assert "resource_delta_trace_enabled" in src
assert "resource_delta_cols" in src
assert "action_resource_delta_score" in src
assert "_bb_action_resource_delta_scores" in src
print("step6 action resource delta source guard OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### I. 기존 I13 resource state score 회귀

```powershell
@'
from modules.engine import _worker_simulate_match

ally = [{
    "id": "A1", "name": "A1", "HP": 100, "SPD": 1,
    "resources": {"HP": {"current": 100, "max": 100}, "MP": {"current": 8, "max": 10}},
}]
enemy = [{"id": "E1", "name": "E1", "HP": 100, "SPD": 2,
          "resources": {"HP": {"current": 100, "max": 100}}}]
gc = {
    "preserve_ids": True,
    "_expected_state_snapshots": {1: {"A1": {"resources": {"MP": 8.0}}}},
    "_state_score_config": {
        "resource_names": ["MP"],
        "resource_mode": "absolute",
        "resource_tol": 0.0,
    },
}
res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "0",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
assert res[1]["state_score"]["accuracy"] == 1.0
print("I13 resource state score still OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

## 금지/주의

- 이번 PR은 `APPLY_DAMAGE`로 인한 target resource loss만 다룬다.
- MP cost 지불, 회복, 충전, 턴 시작/턴 종료 regen trace까지 확장하지 않는다.
- `damage_result["hp_delta"]`, action damage score, state resource score 의미를 바꾸지 않는다.
- `ResourceModule.route_damage()`의 동작을 바꾸지 않는다.
- `_worker_simulate_match` args tuple 구조를 바꾸지 않는다.

