# DB코퍼스 PR-ADAPT1b — Showdown DB Adapter 결과/상태 스냅샷 보정

## 배경

PR-ADAPT1로 다음 파일이 추가됐다.

- `modules/showdown_db_adapter.py`
- `convert_showdown_db_extract.py`
- `test_showdown_db_extract_adapter.py`

기본 검증은 통과했다.

```powershell
& $py -X utf8 -m py_compile modules/showdown_db_adapter.py convert_showdown_db_extract.py test_showdown_db_extract_adapter.py
& $py -X utf8 test_showdown_db_extract_adapter.py
& $py -X utf8 test_db_corpus_fixture_manifest.py
& $py -X utf8 test_db_corpus_backtest_report.py
& $py -X utf8 test_i15_integration_smoke.py
```

실제 zip도 변환은 된다.

```powershell
& $py -X utf8 convert_showdown_db_extract.py `
  --input "C:\Users\kmjde\Downloads\pokemon_showdown_db_extract.zip" `
  --out-dir ".codex_tmp\adapt1_real_zip"
```

하지만 코드 검수와 추가 재현에서 구조적 보정점이 확인됐다.

## 문제 1 — battle-level `result`가 enemy participant에서 반대로 저장됨

현재 participant row 생성 로직:

```python
team = 'ally' if side == 'p1' else 'enemy'
result = ally_win if team == 'ally' else (1 - ally_win)
```

이건 `schema.json`의 `result_mode = "battle_level"` 계약과 충돌한다.

`modules.per_battle_backtest.build_battles_from_log_schema`의 battle-level result 해석은 battle group의 첫 non-null `target_col`을 ally 승리 신호로 읽는다. 따라서 participant row가 enemy 먼저 나오면, p1이 이긴 전투도 `ally_wins=False`로 뒤집힌다.

재현:

```python
import pandas as pd
from modules.showdown_db_adapter import convert_to_battle_log, generate_schema
from modules.per_battle_backtest import build_battles_from_log_schema

battles = pd.DataFrame([{"battle_id": "b1", "winner_side": "p1"}])
events = pd.DataFrame([
    {"battle_id": "b1", "seq": 1, "turn_no": 0, "event_type": "PokemonSwitched",
     "actor_side": "p2", "actor_name": "EnemyLead", "pokemon_name": "EnemyMon",
     "hp_max": 100, "hp_current": 100},
    {"battle_id": "b1", "seq": 2, "turn_no": 0, "event_type": "PokemonSwitched",
     "actor_side": "p1", "actor_name": "AllyLead", "pokemon_name": "AllyMon",
     "hp_max": 100, "hp_current": 100},
])

log, _ = convert_to_battle_log(battles, events)
schema = generate_schema()
built = build_battles_from_log_schema(
    log, schema["target_col"], schema["system_stats"], schema["system_gimmicks"],
    schema["health_stat"], log_schema=schema["log_schema"]
)

# 현재 결과: False
# 기대 결과: True
print(built[0][2])
```

### 수정 요구

participant row의 `result`는 team별 승패가 아니라 **battle-level ally result**로 통일한다.

```python
result = ally_win
```

즉 p1이 이기면 ally/enemy participant 모두 `result=1`, p2가 이기면 모두 `result=0`.

## 문제 2 — StatusApplied/StatusCured가 HP 0 + fainted=True로 변환됨

현재 state row 생성에서 `hp_current`가 없으면 0으로 채운다.

```python
hp_curr = row.get('hp_current', None)
if pd.isna(hp_curr): hp_curr = 0
...
if etype == 'PokemonFainted' or float(hp_curr) <= 0:
    fainted = True
```

이 때문에 HP가 없는 상태 이벤트가 모두 기절 스냅샷이 된다.

실제 변환 결과 예:

```text
seq 70  StatusApplied p2:Rotom-Wash hp_current=0 hp_max=100 fainted=True
seq 73  StatusApplied p1:Gengen     hp_current=0 hp_max=100 fainted=True
seq 119 StatusApplied p2:Hippowdon  hp_current=0 hp_max=100 fainted=True
```

이건 상태 스냅샷을 크게 오염시키고, 실제 zip backtest에서 `state_mismatches=72` 같은 대량 mismatch를 만든다.

### 수정 요구

state row 생성 규칙을 바꾼다.

- `hp_current`가 원본에 없으면 `None`/빈 값으로 둔다. 0으로 채우지 말 것.
- `hp_max`가 원본에 없으면 가능하면 해당 entity의 마지막 관측 `hp_max`를 사용하고, 없으면 `None`.
- `fainted=True`는 다음 경우에만:
  - `event_type == "PokemonFainted"`
  - 또는 `hp_current`가 실제 숫자로 존재하고 `hp_current <= 0`
- `StatusApplied`의 status는 `hp_status`가 있으면 그 값을 쓰고, 없으면 `effect` 값을 사용한다.
  - 예: `effect="slp"` → `hp_status="slp"`
- `StatusCured`는 가능하면 status를 빈 문자열 또는 `"None"`으로 표시하되, HP를 0으로 만들지 않는다.
- `PokemonFainted`에 HP가 없으면 `hp_current=0`, `fainted=True`로 둬도 된다.

가능하면 entity별 마지막 관측 상태를 유지한다.

권장:

```python
last_hp_by_entity = {}
last_hp_max_by_entity = {}
last_status_by_entity = {}
```

단, 이 PR에서 완전한 상태 리플레이어를 만들 필요는 없다. 핵심은 “정보 없음”을 “HP 0/기절”로 오해하지 않는 것이다.

## 문제 3 — direct damage actor 추론이 target/turn을 확인하지 않음

현재 `DamageApplied` source가 없으면 단순히 `last_move_actor`를 사용한다.

```python
if not source:
    d_source_kind = "direct_move"
    d_actor_id = last_move_actor if last_move_actor else ""
```

하지만 요구사항은 다음이었다.

```text
source 없음 + 직전 MoveUsed가 같은 turn에서 target과 일치 → direct_move
```

즉 최소한 같은 turn이고, move target이 damage target과 일치해야 한다.

### 수정 요구

MoveUsed를 저장할 때 actor만 저장하지 말고, 최소 다음을 함께 저장한다.

```python
last_move = {
    "turn_no": turn,
    "actor_id": move_actor_id,
    "target_id": move_target_id,
    "seq": seq,
}
```

DamageApplied에서 `source`가 비어 있으면:

- `last_move.turn_no == damage.turn_no`
- `last_move.target_id == damage_target_id`

를 만족할 때만 `direct_move` actor로 사용한다.

만족하지 않으면:

- `damage_source_kind = "direct_move"`는 유지해도 되지만
- `damage_actor_id = ""`
- `unknown_damage_actor_count += 1`

## 문제 4 — `adapter_report.json`의 `winner_side`가 항상 p1로 고정됨

현재 report:

```python
"winner_side": "p1"
```

실제 battles 테이블의 winner_side를 반영해야 한다.

### 수정 요구

- battle이 1개면 실제 `winner_side`를 넣는다.
- battle이 여러 개면 `winner_sides` map을 추가한다.

예:

```json
{
  "winner_side": "p1",
  "winner_sides": {
    "smogtours-gen5ou-59402": "p1"
  }
}
```

## 문제 5 — `roster_only_entities`가 항상 빈 배열

현재 `roster_only_entities`는 선언만 하고 계산하지 않는다.

### 수정 요구

`battle_roster_pokemon.csv`가 있으면 다음을 report에 넣는다.

- roster에는 있지만 이벤트 switch에서 관측되지 않은 species
- side 포함

예:

```json
"roster_only_entities": [
  {"battle_id": "b1", "side": "p2", "species": "UnusedMon"}
]
```

이 PR에서 roster-only participant row를 만들 필요는 없다. report만 정확히 남긴다.

## 테스트 보강

`test_showdown_db_extract_adapter.py`를 보강한다.

필수 테스트:

1. **enemy-first result guard**
   - p2 switch가 먼저 나오고 winner_side=p1
   - `build_battles_from_log_schema(...)[0][2] is True`

2. **p2 winner guard**
   - winner_side=p2
   - 모든 participant row의 `result`가 0
   - build 결과 `ally_wins is False`
   - report winner_side가 p2

3. **status event must not faint**
   - `StatusApplied`에 `hp_current/hp_max` 없음
   - 생성된 state row가 `fainted=True`가 아님
   - `hp_current`가 0으로 강제되지 않음
   - `hp_status`가 effect(`slp`, `tox`, `brn` 등)를 반영

4. **direct damage target matching**
   - 같은 turn의 직전 MoveUsed target과 damage target이 일치하면 actor 연결
   - target이 일치하지 않으면 `damage_actor_id`를 비워 둔다

5. **roster_only_entities report**
   - roster에만 있고 switch 이벤트에 없는 species를 report에 기록

기존 zip/folder 입력 테스트는 유지한다.

## 실제 zip 확인 권장

수정 후 실제 zip으로 다시 확인한다.

```powershell
$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -X utf8 convert_showdown_db_extract.py `
  --input "C:\Users\kmjde\Downloads\pokemon_showdown_db_extract.zip" `
  --out-dir ".codex_tmp\adapt1_real_zip_fixed"

& $py -X utf8 run_db_corpus_backtest.py `
  --schema ".codex_tmp\adapt1_real_zip_fixed\schema.json" `
  --out-dir ".codex_tmp\adapt1_real_zip_fixed\backtest" `
  --max-battles 1 `
  ".codex_tmp\adapt1_real_zip_fixed\battle_log.csv"
```

주의:

- `global_damage_formula`가 0이고 move library가 없으므로 outcome/state mismatch가 남는 것은 정상이다.
- 그러나 StatusApplied가 대량 faint로 바뀌는 현상은 사라져야 한다.

## 검증 명령

```powershell
$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -X utf8 -m py_compile modules/showdown_db_adapter.py convert_showdown_db_extract.py test_showdown_db_extract_adapter.py
& $py -X utf8 test_showdown_db_extract_adapter.py
& $py -X utf8 test_db_corpus_fixture_manifest.py
& $py -X utf8 test_db_corpus_backtest_report.py
& $py -X utf8 test_i15_integration_smoke.py
```

## 금지 사항

- Step1/Step2/Step6 UI 연결은 이번 PR에서 하지 말 것.
- `run_db_corpus_backtest.py`의 기존 입력 계약을 바꾸지 말 것.
- damage trace를 기본 활성화하지 말 것. `damage_trace_enabled=false` 유지.
- 상태 이벤트의 정보 없음을 임의의 0 HP로 채우지 말 것.
- 외부 패키지 추가 금지.

## 완료 기준

- battle-level result가 switch/event 순서에 영향받지 않음
- StatusApplied/StatusCured가 가짜 기절 상태를 만들지 않음
- direct damage actor가 최소한 same-turn target match를 확인함
- report가 실제 winner_side와 roster-only 정보를 반영함
- 기존 회귀 테스트 통과
