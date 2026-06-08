# DB로그 IR PR-I12 — action damage applied HP delta 모드

## 목표

PR-I11의 `action_damage_score`는 action 단위 데미지 비교 축을 만들었다. 하지만 현재 worker capture는 기본적으로 `ctx["dmg"]`를 비교한다.

이 값은 엔진이 계산한 최종 데미지량에 가깝고, DB 로그가 흔히 저장하는 값인 **실제 HP 감소량**과 다를 수 있다.

예:

- 대상 HP 30, 계산 데미지 50
  - 계산 데미지: 50
  - 실제 HP 감소량: 30
- 실드/보호막/흡수 자원이 있는 게임
  - 계산 데미지: 50
  - 실드 흡수 후 HP 감소량: 20

DB 로그 기반 복제에서는 이 둘을 구분해야 한다. 이 PR은 action damage trace score에 `damage` 비교 모드와 `hp_delta` 비교 모드를 분리한다.

## 수정 대상

가능하면 아래 3개 파일만 수정한다.

- `modules/engine.py`
- `modules/per_battle_backtest.py`
- `modules/step6_dashboard.py`

## 구현 요구

### 1. engine APPLY_DAMAGE에서 damage_result 기록

`modules/engine.py`의 `_act_apply_damage(ctx)`에서 데미지 적용 전후 HP를 기록한다.

현재 흐름은 대략 다음과 같다.

```python
dmg = ctx.get("dmg", 0)
...
if resource_module is not None:
    absorbed = resource_module.route_damage(t, dmg, ctx.get("damage_type"))
else:
    apply_delta(t, -dmg)
    absorbed = 0
...
_broadcast_phase_event("APPLY_DAMAGE", ctx, targets=t)
```

이를 아래 의미가 되도록 보강한다.

```python
hp_before = float(get_current(t))

if resource_module is not None:
    absorbed = resource_module.route_damage(t, dmg, ctx.get("damage_type"))
else:
    apply_delta(t, -dmg)
    absorbed = 0

hp_after = float(get_current(t))
hp_delta = max(0.0, hp_before - hp_after)

ctx["damage_result"] = {
    "damage": float(dmg),
    "attempted_damage": float(dmg),
    "absorbed": float(absorbed or 0),
    "hp_before": hp_before,
    "hp_after": hp_after,
    "hp_delta": hp_delta,
}
```

주의:

- `damage_result`는 `_broadcast_phase_event("APPLY_DAMAGE", ...)` 호출 전에 세팅되어야 한다.
- 기존 `sim_metrics["total_damage"]`와 `damage_count` 의미는 바꾸지 않는다.
- 기존 로그 문구는 꼭 바꾸지 않아도 된다.
- recoil/self damage는 이번 PR 범위 밖이다.

### 2. worker APPLY_DAMAGE capture에 hp_delta 포함

`_worker_simulate_match()`의 `_capture_phase()`에서 actual damage event에 다음 필드를 포함한다.

```python
dr = ctx.get("damage_result") or {}
actual_damage.append({
    "turn": int(ctx.get("turn") or 0),
    "actor": str(actor.get("id")),
    "target": str(t.get("id")),
    "damage": float(dr.get("damage", ctx.get("dmg", 0.0)) or 0.0),
    "hp_delta": float(dr.get("hp_delta", ctx.get("dmg", 0.0)) or 0.0),
    "hp_before": float(dr.get("hp_before", 0.0) or 0.0),
    "hp_after": float(dr.get("hp_after", 0.0) or 0.0),
    "absorbed": float(dr.get("absorbed", 0.0) or 0.0),
    "move": str(move.get("name") or ""),
})
```

### 3. action damage score에 compare_field 추가

`_score_action_damage_for_worker(...)`를 확장한다.

권장 시그니처:

```python
def _score_action_damage_for_worker(expected, actual, damage_tol=0.0, compare_field="damage"):
```

비교 필드 동작:

- 기본값 `"damage"`: 기존 I11 동작 유지
- `"hp_delta"`: expected/actual의 `hp_delta`를 비교
- expected event에 `hp_delta`가 없고 compare_field가 `"hp_delta"`면 expected의 `damage`를 fallback으로 사용해도 된다.

예시:

```python
field = compare_field if compare_field in ("damage", "hp_delta") else "damage"
exp_val = exp.get(field, exp.get("damage", 0.0))
act_val = act.get(field, act.get("damage", 0.0))
```

`first_mismatch`에는 어떤 필드를 비교했는지 남긴다.

```python
{"kind": "damage", "field": field, "expected": exp_val, "actual": act_val, ...}
```

worker에서 호출할 때:

```python
sim_metrics["action_damage_score"] = _score_action_damage_for_worker(
    expected_damage,
    actual_damage,
    damage_tol=float(damage_cfg.get("damage_tol", 0.0) or 0.0),
    compare_field=str(damage_cfg.get("compare_field") or "damage"),
)
```

주의:

- 기존 I11 테스트가 그대로 통과해야 한다.
- identity 비교(turn/actor/target)는 그대로 유지한다.
- `checks`, `mismatches`, `missing`, `extra`, `accuracy` 의미를 바꾸지 않는다.

### 4. per_battle_backtest damage trace builder에 value kind 추가

`modules/per_battle_backtest.py`의 `build_action_damage_trace_from_group()`에 `damage_value_kind`를 반영한다.

schema 키:

```python
"damage_value_kind": "damage" | "hp_delta"
```

동작:

- 기본값은 `"damage"`로 해서 기존 I11 동작 유지.
- `"damage"`면 event에 `"damage": value`
- `"hp_delta"`면 event에 `"hp_delta": value`를 넣고, 호환을 위해 `"damage": value`도 함께 넣어도 된다.

권장:

```python
kind = str(log_schema.get("damage_value_kind") or "damage")
if kind == "hp_delta":
    event["hp_delta"] = dmg
    event["damage"] = dmg
else:
    event["damage"] = dmg
```

`build_battles_from_log_schema()`에서 `_action_damage_score_config`에 compare field를 추가한다.

```python
battle_gc["_action_damage_score_config"] = {
    "damage_tol": float(log_schema.get("damage_tolerance", 0.0) or 0.0),
    "compare_field": str(log_schema.get("damage_value_kind") or "damage"),
}
```

### 5. Step6 UI에 damage value 의미 선택 추가

`modules/step6_dashboard.py`의 damage trace score UI에 selectbox를 추가한다.

권장 UI:

```python
_bb_damage_value_kind = st.selectbox(
    "damage 값 의미",
    ["damage", "hp_delta"],
    index=0,
    help="damage는 엔진 계산 데미지, hp_delta는 실제 HP 감소량과 비교합니다."
)
```

schema update에 포함한다.

```python
"damage_value_kind": _bb_damage_value_kind,
```

결과 UI caption에 현재 비교 모드를 보여줘도 좋다.

```python
st.caption(f"행동 데미지 score 비교 기준: {_bb_log_schema.get('damage_value_kind', 'damage')}")
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

### B. APPLY_DAMAGE phase에서 damage_result 캡처

오버킬 케이스에서 계산 데미지와 실제 HP 감소량이 분리되어야 한다.

```powershell
@'
from modules.engine import run_simulation

events = []

def on_phase(pk, ctx, targets):
    if pk != "APPLY_DAMAGE":
        return
    dr = ctx.get("damage_result") or {}
    target_list = targets if isinstance(targets, list) else [targets]
    for t in target_list:
        events.append({
            "turn": ctx.get("turn"),
            "actor": ctx["active_char"]["id"],
            "target": t["id"],
            "damage": dr.get("damage"),
            "hp_before": dr.get("hp_before"),
            "hp_after": dr.get("hp_after"),
            "hp_delta": dr.get("hp_delta"),
        })

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 30, "SPD": 1,
          "resources": {"HP": {"current": 30, "max": 30}}}]

run_simulation(
    ally, enemy, max_turns=1,
    speed_stat="SPD", sys_stats=["HP", "SPD"],
    global_damage_formula="50",
    game_config={"preserve_ids": True},
    on_phase_event=on_phase,
    silent=True,
)

print(events)
assert len(events) == 1
e = events[0]
assert e["damage"] == 50
assert e["hp_before"] == 30
assert e["hp_after"] == 0
assert e["hp_delta"] == 30
print("damage_result overkill split OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### C. 기존 damage 비교 모드 유지

기본 compare field는 기존처럼 `damage`여야 한다.

```powershell
@'
from modules.engine import _worker_simulate_match

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 30, "SPD": 1,
          "resources": {"HP": {"current": 30, "max": 30}}}]
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
assert score["accuracy"] == 1.0
assert score["damage_mismatches"] == 0
print("default damage compare mode OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### D. hp_delta 비교 모드

`compare_field="hp_delta"`일 때는 실제 HP 감소량 30과 비교해야 한다.

```powershell
@'
from modules.engine import _worker_simulate_match

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 30, "SPD": 1,
          "resources": {"HP": {"current": 30, "max": 30}}}]
gc = {
    "preserve_ids": True,
    "_expected_action_damage_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "hp_delta": 30.0}
    ],
    "_action_damage_score_config": {"damage_tol": 0.0, "compare_field": "hp_delta"},
}

res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["action_damage_score"]
assert score["accuracy"] == 1.0
assert score["damage_mismatches"] == 0
print("hp_delta compare mode OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### E. hp_delta mismatch가 잡혀야 함

```powershell
@'
from modules.engine import _worker_simulate_match

ally = [{"id": "A1", "name": "A1", "HP": 100, "SPD": 999,
         "resources": {"HP": {"current": 100, "max": 100}}}]
enemy = [{"id": "E1", "name": "E1", "HP": 30, "SPD": 1,
          "resources": {"HP": {"current": 30, "max": 30}}}]
gc = {
    "preserve_ids": True,
    "_expected_action_damage_trace": [
        {"turn": 1, "actor": "A1", "target": "E1", "hp_delta": 50.0}
    ],
    "_action_damage_score_config": {"damage_tol": 0.0, "compare_field": "hp_delta"},
}

res = _worker_simulate_match((
    ally, enemy, None, "SPD", ["HP", "SPD"], "50",
    1, None, None, None, None, None, None, gc, 0
))
print(res)
assert not isinstance(res, str)
score = res[1]["action_damage_score"]
assert score["accuracy"] < 1.0
assert score["damage_mismatches"] == 1
assert score["first_mismatch"]["field"] == "hp_delta"
print("hp_delta mismatch detection OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### F. per_battle builder hp_delta mode

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_battles, build_action_damage_trace_from_group

df = pd.DataFrame([
    {"battle": "B1", "team": "Ally", "unit": "A1", "result": 1, "HP": 100, "SPD": 999,
     "turn": 1, "actor": "A1", "target": "E1", "hp_loss": 30, "event": "damage"},
    {"battle": "B1", "team": "Enemy", "unit": "E1", "result": 0, "HP": 30, "SPD": 1,
     "turn": 1, "actor": "A1", "target": "E1", "hp_loss": 30, "event": "damage"},
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
    "damage_value_col": "hp_loss",
    "damage_value_kind": "hp_delta",
    "damage_action_col": "event",
    "damage_action_values": ["damage"],
    "damage_tolerance": 0.0,
}

trace = build_action_damage_trace_from_group(df, schema)
print(trace)
assert trace[0]["hp_delta"] == 30.0

battles = build_battles(
    df, 2, "result", ["HP", "SPD"], [], "HP",
    max_battles=10,
    game_config={"preserve_ids": True},
    log_schema=schema,
)
print(battles)
gc = battles[0][3]
assert gc["_expected_action_damage_trace"][0]["hp_delta"] == 30.0
assert gc["_action_damage_score_config"]["compare_field"] == "hp_delta"
print("per_battle hp_delta mode OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

### G. Step6 source guard

```powershell
@'
from pathlib import Path
src = Path("modules/step6_dashboard.py").read_text(encoding="utf-8")
assert "damage_value_kind" in src
assert "hp_delta" in src
assert "damage_tolerance" in src
assert "action_damage_score" in src
print("step6 damage value kind source guard OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -
```

## 금지/주의

- 기존 `damage` 비교 모드를 깨지 않는다.
- I11의 action damage score 테스트가 계속 통과해야 한다.
- I11b의 `on_phase_event=None` 회귀 수정과 callback 중복 방지를 되돌리지 않는다.
- `sim_metrics["total_damage"]`의 기존 의미는 바꾸지 않는다.
- recoil, poison, weather, hazard 같은 간접 데미지 score까지 넓히지 않는다. 이번 PR은 `APPLY_DAMAGE`의 primary target HP delta만 다룬다.

