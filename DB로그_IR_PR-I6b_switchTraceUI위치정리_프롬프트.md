# DB로그 IR PR-I6b — switch trace UI 위치 정리

## 목적

PR-I6의 핵심 기능은 통과했다.

확인된 통과 항목:

- `build_switch_trace_actions_from_group(...)` 동작 OK
- participant ID 필터가 switch도 검증 OK
- switch-only trace가 battle 4튜플로 반환 OK
- move trace + switch trace 병합 OK
- 엔진이 `trace_actions["switch"]`를 실제 교체로 실행 OK

다만 UI 배치가 프롬프트 의도와 조금 다르다.

현재 `modules/step6_dashboard.py`에서 switch trace UI가 `with st.expander("행동 trace 연결 (선택)", ...)` 밖, 그리고 `_bb_log_schema` 생성 블록 안쪽에 있다.

의도:

- move trace UI와 switch trace UI는 같은 `행동 trace 연결 (선택)` expander 안에 있어야 한다.
- `_bb_log_schema` 생성 블록은 UI 값을 읽어 schema에 반영만 해야 한다.

## 수정 대상

- `modules/step6_dashboard.py`만 수정

## 변경 요구

### 1. switch trace 위젯을 trace expander 안으로 이동

현재 위치:

```python
if _bb_id_col != "(없음)" and _bb_team_col != "(없음)":
    _bb_log_schema = {...}
    ...
    st.markdown("---")
    _ts_use = st.checkbox("switch trace 사용", value=False)
    ...
```

이 UI 블록을 다음 위치로 이동한다.

```python
with st.expander("행동 trace 연결 (선택)", expanded=False):
    _tc_use = st.checkbox("move trace 사용", value=False)
    ...
    # move trace UI
    ...
    st.markdown("**행동 순서 (선택)**")
    ...

    st.markdown("---")
    _ts_use = st.checkbox("switch trace 사용", value=False)
    ...
    # switch trace UI
```

즉, `_ts_use`, `_bb_switch_turn_col`, `_bb_switch_out_col`, `_bb_switch_in_col`, `_bb_switch_action_col`, `_bb_switch_action_vals`는 expander 안에서 정의되어야 한다.

### 2. schema 반영 로직은 기존 위치 유지

아래 로직은 `_bb_log_schema`가 만들어진 뒤에 있어야 하므로 기존처럼 `if _bb_id_col != "(없음)" ...` 블록 안에 둔다.

```python
if _ts_use:
    if _bb_ent_col == "(없음)":
        st.warning(...)
    elif _bb_switch_turn_col == "(없음)" or ...:
        st.warning(...)
    else:
        _bb_log_schema.update({
            "trace_switches_enabled": True,
            ...
        })
```

단, 이 로직 안에 UI 위젯 생성 코드는 남기지 않는다.

### 3. move trace 독립성 유지

- `_tc_use`와 `_ts_use`는 독립 checkbox여야 한다.
- switch trace만 켜도 schema에 switch trace 설정이 들어가야 한다.
- move trace만 켜도 기존 동작이 그대로여야 한다.
- 둘 다 끄면 trace schema가 들어가지 않아야 한다.

## 금지

- `modules/per_battle_backtest.py` 수정 금지
- `modules/engine.py` 수정 금지
- `modules/turn_manager.py` 수정 금지
- switch trace builder 동작 변경 금지
- move trace / order priority 동작 변경 금지

## 수동 검증 코드

### 1. AST

```powershell
@'
import ast
from pathlib import Path
for p in ["modules/step6_dashboard.py"]:
    ast.parse(Path(p).read_text(encoding="utf-8"))
    print(p, "AST OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

### 2. indentation sanity check

아래 스크립트로 `_ts_use`가 trace expander 안에 있고, `_bb_id_col` schema 블록보다 먼저 정의되는지 확인한다.

```powershell
@'
from pathlib import Path
lines = Path("modules/step6_dashboard.py").read_text(encoding="utf-8").splitlines()
for i, line in enumerate(lines, 1):
    if 'with st.expander("행동 trace 연결' in line:
        print("trace_expander", i, len(line) - len(line.lstrip()))
    if '_ts_use = st.checkbox("switch trace 사용"' in line:
        print("ts_use", i, len(line) - len(line.lstrip()))
    if 'if _bb_id_col != "(없음)" and _bb_team_col != "(없음)"' in line:
        print("schema_if", i, len(line) - len(line.lstrip()))
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

기대:

- `trace_expander`가 먼저 출력된다.
- `ts_use`가 그 뒤에 출력된다.
- `schema_if`는 `ts_use`보다 뒤에 출력된다.
- `ts_use` indent는 `trace_expander` indent보다 커야 한다.

### 3. PR-I6 핵심 기능 회귀 확인

```powershell
@'
import pandas as pd
from modules.per_battle_backtest import build_battles

df = pd.DataFrame([
    {"battle_id": 1, "side": "Ally", "unit_id": "A1", "result": "win", "HP": 100, "SPD": 10,
     "turn": 1, "actor": "A1", "incoming": "A2", "action": "switch"},
    {"battle_id": 1, "side": "Ally", "unit_id": "A2", "result": "win", "HP": 100, "SPD": 20,
     "turn": "", "actor": "", "incoming": "", "action": ""},
    {"battle_id": 1, "side": "Enemy", "unit_id": "E1", "result": "lose", "HP": 100, "SPD": 30,
     "turn": "", "actor": "", "incoming": "", "action": ""},
])
schema = {
    "battle_id_col": "battle_id",
    "team_col": "side",
    "entity_id_col": "unit_id",
    "result_mode": "battle_level",
    "trace_switches_enabled": True,
    "switch_turn_col": "turn",
    "switch_outgoing_id_col": "actor",
    "switch_incoming_id_col": "incoming",
    "switch_action_col": "action",
    "switch_action_values": ["switch"],
}
battles = build_battles(df, 2, "result", ["HP", "SPD"], [], "HP",
                        max_battles=10, game_config={}, log_schema=schema)
assert len(battles) == 1 and len(battles[0]) == 4
assert battles[0][3]["trace_actions"]["switch"] == {(1, "A1"): "A2"}
print("switch trace regression OK")
'@ | & 'C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

## 완료 기준

- switch trace UI가 `행동 trace 연결 (선택)` expander 안에 있다.
- schema update 로직은 기존처럼 `_bb_log_schema` 생성 뒤에 남아 있다.
- PR-I6 switch trace 기능이 회귀하지 않는다.
