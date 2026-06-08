# DB코퍼스 PR-ADAPT1c — Showdown DB Extract Adapter roster 스키마 호환/테스트 보강

## 목적

ADAPT1b는 핵심 회귀를 대부분 해결했다.

- enemy-first participant 순서에서도 battle-level `result`가 뒤집히지 않음
- `StatusApplied` / `StatusCured`가 HP 0 또는 faint로 오염되지 않음
- 직접 피해 actor 추론이 같은 턴 + 같은 target일 때만 연결됨
- battle별 `winner_side`가 report에 보존됨

다만 실제 `pokemon_showdown_db_extract.zip`의 roster 테이블은 `pokemon_name`이 아니라 `species` 컬럼을 사용한다.
현재 `roster_only_entities` 계산은 `pokemon_name` 컬럼만 확인하므로, 실전 extract 스키마에서는 roster-only 보고가 무음으로 비활성화된다.

이번 PR은 큰 기능 추가가 아니라 **실전 입력 스키마 호환성과 테스트 빈틈 보강**만 수행한다.

## 현재 확인된 문제

실제 zip 컬럼:

- `battles.csv`
  - `battle_id`, `source_system`, `source_replay_id`, `title`, `game_type`, `generation`, `tier`, `winner_side`, `winner_name`, `total_turns`, `imported_at`
- `battle_events.csv`
  - `event_id`, `battle_id`, `seq`, `turn_no`, `phase`, `event_type`, `command`, `actor_id`, `actor_side`, `actor_slot`, `actor_name`, `target_id`, `target_side`, `target_slot`, `target_name`, `move_name`, `pokemon_name`, `hp_current`, `hp_max`, `hp_status`, `delta_hp`, `effect`, `source`, `details_json`, `raw_args_json`, `raw_line`
- `battle_roster_pokemon.csv`
  - `roster_id`, `battle_id`, `side`, `slot_index`, `species`, `gender`, `raw_pokemon_text`

현재 `modules/showdown_db_adapter.py`의 roster-only 계산은 다음 조건에 묶여 있다.

```python
if 'battle_id' in rosters_df.columns and 'side' in rosters_df.columns and 'pokemon_name' in rosters_df.columns:
```

이 때문에 실제 DB extract에서는 `roster_only_entities`가 계산되지 않는다.

또한 `test_showdown_db_extract_adapter.py`에는 두 가지 테스트 빈틈이 있다.

- mock roster가 실제 스키마와 다른 `pokemon_name` 컬럼을 사용한다.
- `pytest.fail(...)`를 쓰지만 `pytest`를 import하지 않는다. 현재 예외가 없어서 드러나지 않을 뿐이다.
- 직접 피해 target mismatch 음성 케이스가 별도 assert로 고정되어 있지 않다.

## 작업 범위

### 1. roster species 컬럼 호환

`modules/showdown_db_adapter.py`의 `roster_only_entities` 계산을 다음 기준으로 수정한다.

- 필수 컬럼:
  - `battle_id`
  - `side`
  - species 계열 컬럼
- species 계열 컬럼 우선순위:
  1. `species`
  2. `pokemon_name`
  3. 필요하면 `name`

권장 helper:

```python
def _first_existing_column(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None
```

주의:

- `species` 값이 비어 있거나 NaN이면 skip한다.
- 기존 `pokemon_name` mock도 계속 지원해야 한다.
- `roster_only_entities` 항목 형태는 유지한다.

```json
{
  "battle_id": "...",
  "side": "p1",
  "species": "..."
}
```

### 2. 실제 스키마 기반 테스트로 교체/보강

`test_showdown_db_extract_adapter.py`의 mock roster를 실제 extract와 같은 컬럼으로 바꾼다.

권장:

```python
roster_data = {
    "battle_id": ["mock_battle_1", "mock_battle_1", "mock_battle_2", "mock_battle_3"],
    "side": ["p1", "p2", "p2", "p1"],
    "slot_index": [1, 1, 1, 1],
    "species": ["Tyranitar", "Politoed", "UnusedMon", "A"],
}
```

그리고 다음 assert를 유지/강화한다.

- `report["roster_only_entities"]`에 `UnusedMon`이 포함된다.
- `side == "p2"`가 보존된다.
- 기존 `pokemon_name` 컬럼 기반 mock도 별도 짧은 테스트로 호환성 확인 가능하면 좋다.

### 3. pytest 미수입 문제 제거

둘 중 하나로 정리한다.

- `import pytest` 추가
- 또는 `try/except pytest.fail` 구조를 제거하고 예외가 자연스럽게 test 실패로 올라오게 한다.

권장 방향은 후자다. 이 테스트 파일은 현재 스크립트 직접 실행 방식도 겸하므로 외부 pytest 의존을 늘리지 않는 편이 좋다.

### 4. 직접 피해 target mismatch 음성 테스트 고정

ADAPT1b 코드가 이미 동작하더라도 테스트로 고정한다.

시나리오:

- 같은 턴 직전 `MoveUsed` target은 `p2:B`
- 다음 `DamageApplied`는 source가 비어 있지만 피해 대상이 `p1:A`
- 이 경우 `damage_source_kind == "direct_move"`일 수는 있어도 `damage_actor_id == ""`여야 한다.

assert 예:

```python
assert mismatch_damage["damage_source_kind"] == "direct_move"
assert mismatch_damage["damage_actor_id"] == ""
assert mismatch_damage["damage_target_id"] == "p1:A"
```

### 5. 실제 zip smoke는 코드에 하드코딩하지 않기

테스트 파일이 `C:\Users\kmjde\Downloads\pokemon_showdown_db_extract.zip` 같은 로컬 경로에 의존하면 안 된다.

대신 검수자가 수동으로 아래 smoke를 실행할 수 있게만 유지한다.

```powershell
& $py -X utf8 convert_showdown_db_extract.py --input "C:\Users\kmjde\Downloads\pokemon_showdown_db_extract.zip" --out-dir ".codex_tmp\adapt1c_real_zip"
```

## 완료 조건

다음 명령이 통과해야 한다.

```powershell
$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -X utf8 -m py_compile modules/showdown_db_adapter.py convert_showdown_db_extract.py test_showdown_db_extract_adapter.py
& $py -X utf8 test_showdown_db_extract_adapter.py
& $py -X utf8 test_db_corpus_fixture_manifest.py
& $py -X utf8 test_db_corpus_backtest_report.py
& $py -X utf8 test_i15_integration_smoke.py
```

수동 smoke:

```powershell
& $py -X utf8 convert_showdown_db_extract.py --input "C:\Users\kmjde\Downloads\pokemon_showdown_db_extract.zip" --out-dir ".codex_tmp\adapt1c_real_zip"
& $py -X utf8 run_db_corpus_backtest.py --schema ".codex_tmp\adapt1c_real_zip\schema.json" --out-dir ".codex_tmp\adapt1c_real_zip\backtest" --max-battles 1 ".codex_tmp\adapt1c_real_zip\battle_log.csv"
```

주의:

- 현재 adapter schema의 `global_damage_formula`는 `"0"`이므로 실제 zip backtest 정확도 0% 자체는 이번 PR 실패가 아니다.
- 이번 PR의 목표는 어댑터 입력 정합성, 상태 오염 방지, actor 오연결 방지다.

## 금지 범위

- `.db` 직접 입력 지원 추가 금지. 그것은 다음 ADAPT2에서 다룬다.
- Streamlit UI 연결 금지.
- battle formula / type chart / ability inference 추가 금지.
- 대규모 리팩터 금지.

## 검수 포인트

검수자는 다음을 확인한다.

- 실제 extract roster의 `species` 컬럼으로도 `roster_only_entities`가 계산된다.
- 기존 `pokemon_name` 기반 테스트가 깨지지 않는다.
- Status 이벤트가 fake faint를 만들지 않는다.
- direct damage mismatch에서 actor가 잘못 붙지 않는다.
- 기존 DB corpus 회귀 테스트가 깨지지 않는다.
