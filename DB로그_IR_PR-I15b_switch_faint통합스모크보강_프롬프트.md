# DB로그 IR PR-I15b — switch/faint 통합 smoke 보강

## 목적

PR-I15는 통합 smoke를 추가했고 실행 통과했다.

다만 실제 검수 결과, I15의 worker 경로는 다음 축을 충분히 묶어 검증한다.

- move trace
- action damage score
- damage vs hp_delta
- observed resource delta filter
- strict extra mode
- state snapshot score

하지만 I15 목적 목록에 있던 아래 두 축은 실질 실행 smoke가 약하다.

- switch trace action
- faint incoming trace

이번 PR은 새 기능 구현이 아니라 `test_i15_integration_smoke.py`에 이 두 축의 통합 smoke를 추가하는 보강이다.

## 금지

- 포켓몬 전용 하드코딩 금지.
- 엔진 동작 의미 변경 금지.
- 기존 score 의미 변경 금지.
- 테스트를 통과시키기 위해 trace/switch/faint 로직을 느슨하게 만들지 말 것.
- 큰 UI 변경 금지.

가능하면 `test_i15_integration_smoke.py`만 수정한다. 테스트가 기존 버그를 드러내는 경우에만 최소 범위로 코드 수정한다.

## 추가할 테스트

### 1. Scenario D — switch trace 실행 smoke

목표: `trace_actions["switch"][(turn, outgoing_id)] = incoming_id`가 실제 엔진 실행에서 voluntary switch 경로로 소비되는지 확인한다.

권장 구성:

- Ally: `A1`, `A2`
- Enemy: `E1`
- 초기 on-field: `A1`, `E1`
- `game_config`:

```python
{
    "preserve_ids": True,
    "preserve_initial_on_field": True,
    "trace_actions": {
        "move": {},
        "switch": {(1, "A1"): "A2"},
    },
}
```

실행은 `modules.engine.run_simulation(...)`을 직접 써도 된다. `_worker_simulate_match(...)`는 logs를 반환하지 않으므로, switch 실행 여부를 보려면 `run_simulation` 로그나 입력 participant mutation을 확인하는 쪽이 낫다.

검증 기대:

- 실행 결과가 예외가 아님
- 로그에 `A1` switch와 `A2` 진입을 나타내는 문자열이 있음
- 가능하면 실행 후 `A1["on_field"] is False`, `A2["on_field"] is True`
- trace switch가 있을 때 A1이 공격하지 않았음을 로그 또는 damage count로 확인

정확한 한국어 로그 문구에 너무 강하게 묶지 말고, `A1`, `A2`, `교체` 또는 `switch` 중 현재 구현에 맞는 느슨한 조건을 사용한다.

### 2. Scenario E — faint incoming 실행 smoke

목표: active가 기절했을 때 `trace_faint_incoming`이 예비 진입자를 지정하고, `on_active_faint="replace_from_reserve"` 경로가 실제로 소비되는지 확인한다.

권장 구성:

- Ally: `A1`
- Enemy: `E1`, `E2`
- 초기 on-field: `A1`, `E1`
- `A1`이 `E1`을 한 방에 쓰러뜨리는 고정 damage formula 사용
- `E2`는 살아있는 예비
- `game_config`:

```python
{
    "preserve_ids": True,
    "preserve_initial_on_field": True,
    "trace_actions": {
        "move": {(1, "A1"): {"move": {"name": "KO", "priority": 0}, "target": "E1"}},
        "switch": {},
    },
    "trace_faint_incoming": [
        {"turn": 1, "side": "Enemy", "outgoing": "E1", "incoming": "E2"},
    ],
    "on_active_faint": "replace_from_reserve",
}
```

검증 기대:

- 실행 결과가 예외가 아님
- `E1`은 기절 또는 HP 0
- `E2`가 진입한 로그가 있음
- 가능하면 실행 후 `E1["on_field"] is False`, `E2["on_field"] is True`
- 로그에 `E2`와 `진입` 또는 현재 구현의 switch-in 로그 문구가 있음

### 3. Scenario F — build_battles가 switch/faint config를 함께 만든다

`modules.per_battle_backtest.build_battles(...)` 경유 config 검사도 추가한다.

작은 DataFrame에 다음 row를 넣는다.

- 참가자 row: `A1`, `A2`, `E1`, `E2`
- move row 또는 같은 row의 move trace 정보: `turn=1`, `actor=A1`, `target=E1`, `move_name=KO`
- switch row: `turn=1`, `event=switch`, `outgoing=A1`, `incoming=A2`
- faint incoming row: `turn=1`, `event=faint_replace`, `fainted=E1`, `replacement=E2`, `side=Enemy`

현재 builder가 한 row를 participant와 event 양쪽으로 읽는 구조라면, NaN/빈 값으로 참가자 필드를 유지해도 된다. 핵심은 builder helper가 빈 ID를 skip하게 하면서 필요한 trace만 남기는 것이다.

`log_schema`에는 다음을 포함한다.

```python
"trace_switches_enabled": True,
"switch_turn_col": "turn",
"switch_outgoing_id_col": "outgoing",
"switch_incoming_id_col": "incoming",
"switch_action_col": "event",
"switch_action_values": ["switch"],

"trace_faint_incoming_enabled": True,
"faint_turn_col": "turn",
"faint_side_col": "side",
"faint_outgoing_id_col": "fainted",
"faint_incoming_id_col": "replacement",
"faint_action_col": "event",
"faint_action_values": ["faint_replace"],
```

검증 기대:

- `gc["trace_actions"]["switch"][(1, "A1")] == "A2"`
- `gc["trace_faint_incoming"]`에 `{"turn": 1, "outgoing": "E1", "incoming": "E2"}` 계열 entry가 있음
- `gc["on_active_faint"] == "replace_from_reserve"`
- 기존 move trace/resource/state config가 깨지지 않음

### 4. 기존 I15 시나리오 유지

기존 Scenario A/B/C는 그대로 유지되어야 한다.

## 검증 명령

아래가 모두 통과해야 한다.

```powershell
python -X utf8 -m py_compile modules/engine.py modules/per_battle_backtest.py modules/step6_dashboard.py test_i15_integration_smoke.py
python -X utf8 test_i13.py
python -X utf8 test_i14.py
python -X utf8 test_i15_integration_smoke.py
```

## 완료 기준

- I15 기존 A/B/C 통과
- 신규 D/E/F 통과
- switch trace가 실제 실행에서 소비됨을 확인
- faint incoming이 실제 실행에서 소비됨을 확인
- build_battles가 switch/faint config를 한 battle game_config에 같이 싣는 것을 확인

## 보고 형식

작업 후 아래를 요약한다.

1. 변경 파일
2. 통과한 검증 명령
3. Scenario D/E/F 각각 무엇을 증명했는지
4. 코드 수정이 있었다면 왜 필요했는지
