# DB코퍼스 PR-ADAPT1 — Pokemon Showdown DB Extract 어댑터

## 배경

현재 DB 코퍼스 검증 파이프라인은 기본적으로 다음 입력을 받는다.

```text
단일 로그 테이블(csv/xlsx/json/tsv/parquet) + schema.json
→ run_db_corpus_backtest.py
```

그런데 사용자가 제공한 `pokemon_showdown_db_extract.zip`은 실제 DB export에 더 가까운 다중 테이블 구조다.

```text
battles.csv
battle_players.csv
battle_roster_pokemon.csv
battle_rules.csv
battle_events.csv
schema.sql
export_manifest.json
README.md
```

이 데이터는 단일 이벤트 CSV보다 품질이 좋다. 하지만 현재 하네스는 zip/다중 테이블을 직접 먹지 못한다.

따라서 병목은 엔진 표현력보다 **입력 어댑터/코퍼스 수용 구조**에 있다.

이 PR은 첫 어댑터 확장이다. 목표는 Showdown 특화 DB extract를 현재 DB corpus backtest가 이해하는 단일 fixture 형태로 변환하는 것이다.

## 목표

다음 변환기를 추가한다.

```text
pokemon_showdown_db_extract.zip 또는 extract folder
→ battle_log.csv
→ schema.json
→ adapter_report.json
```

이 단계는 UI 연결이 아니다. 먼저 CLI/모듈형 변환기로 만든다.

## 신규 파일 권장

- `modules/showdown_db_adapter.py`
- `convert_showdown_db_extract.py`
- `test_showdown_db_extract_adapter.py`

## 입력 포맷

입력은 zip 또는 폴더를 지원한다.

필수 테이블:

- `battles.csv`
- `battle_events.csv`

권장/선택 테이블:

- `battle_players.csv`
- `battle_roster_pokemon.csv`
- `battle_rules.csv`
- `export_manifest.json`
- `schema.sql`

필수 컬럼은 실제 파일 기준을 따른다.

### `battles.csv`

```text
battle_id, source_system, source_replay_id, title, game_type,
generation, tier, winner_side, winner_name, total_turns, imported_at
```

### `battle_events.csv`

```text
event_id,battle_id,seq,turn_no,phase,event_type,command,
actor_id,actor_side,actor_slot,actor_name,
target_id,target_side,target_slot,target_name,
move_name,pokemon_name,hp_current,hp_max,hp_status,delta_hp,
effect,source,details_json,raw_args_json,raw_line
```

## 출력 1 — `battle_log.csv`

현재 `run_db_corpus_backtest.py` / `modules.per_battle_backtest.build_battles_from_log_schema`가 읽을 수 있는 **단일 wide table**을 출력한다.

권장 컬럼:

```text
battle_id
seq
turn_no
row_kind
team
entity_id
name
species
HP
result
initial_on_field

move_actor_id
move_target_id
move_name
move_order

state_entity_id
hp_current
hp_max
hp_status
fainted

damage_actor_id
damage_target_id
damage_value
damage_source
damage_source_kind

effect
source
raw_line
details_json
```

### participant rows

`row_kind = "participant"`인 행을 생성한다.

규칙:

- `team`: `p1 → ally`, `p2 → enemy`
- `result`: `battles.winner_side == "p1"`이면 ally 기준 win, 아니면 loss
- `entity_id`: 이벤트에 등장한 nickname 기준으로 안정화한다. 예: `p1:Gengen`
- `name`: nickname
- `species`: `PokemonSwitched.pokemon_name` 또는 roster 매핑으로 추론
- `HP`: 해당 entity에서 관측된 최대 `hp_max`
- `initial_on_field`: 첫 전투 진입 switch에서 각 side의 첫 active만 true

주의:

- trace/event row는 `team`을 비워 둔다. 그래야 participant dedup이 trace row로 덮이지 않는다.
- roster에만 있고 이벤트에 전혀 등장하지 않은 포켓몬은 `adapter_report.json`에 `roster_only_entities`로 기록한다. 첫 PR에서는 participant row 생성은 관측 entity 중심이어도 된다.

### move rows

`battle_events.event_type == "MoveUsed"`를 다음으로 변환한다.

- `row_kind = "move"`
- `move_actor_id = "{actor_side}:{actor_name}"`
- `move_target_id = "{target_side}:{target_name}"`
- `move_name`
- `move_order = seq`
- `team`은 비움

### state rows

HP/status/faint가 관측되는 이벤트를 state row로 남긴다.

대상 이벤트 예:

- `PokemonSwitched`
- `DamageApplied`
- `HealApplied`
- `StatusApplied`
- `StatusCured`
- `PokemonFainted`

규칙:

- `row_kind = "state"`
- `state_entity_id = "{actor_side}:{actor_name}"`
- `hp_current`, `hp_max`, `hp_status`
- `fainted = true` if `PokemonFainted` 또는 `hp_current <= 0`

### damage rows

`DamageApplied`는 현재 Showdown 이벤트에서 actor가 “피해를 받은 포켓몬”인 경우가 많다.

따라서 다음 컬럼을 만든다.

- `damage_target_id`: 피해를 받은 entity. 즉 `"{actor_side}:{actor_name}"`
- `damage_value`: `abs(delta_hp)`
- `damage_source`: 원본 `source`
- `damage_source_kind`:
  - source 없음 + 직전 MoveUsed가 같은 turn에서 target과 일치 → `direct_move`
  - source가 `item: ...` → `item`
  - source가 `ability: ...` → `ability`
  - source가 `Stealth Rock` → `hazard`
  - source가 `sandstorm`/weather 계열 → `weather`
  - source가 `psn`/`brn`/`tox` 등 → `status`
  - 기타 → `other`
- `damage_actor_id`:
  - `direct_move`면 같은 turn의 가장 최근 MoveUsed actor
  - `details_json["of"]`가 있으면 해당 entity를 우선 사용
  - 알 수 없으면 빈 값

주의:

- 이 PR에서 damage trace를 완전 정확히 맞출 필요는 없다.
- 하지만 “피해자 actor를 공격자 actor로 오해하지 않는 것”은 필수다.

## 출력 2 — `schema.json`

`run_db_corpus_backtest.py`가 읽을 수 있는 schema를 생성한다.

권장 기본:

```json
{
  "system_stats": ["HP"],
  "system_gimmicks": ["species"],
  "health_stat": "HP",
  "target_col": "result",
  "battle_size": 2,
  "global_damage_formula": "0",
  "sim_max_turns": 100,
  "log_schema": {
    "battle_id_col": "battle_id",
    "team_col": "team",
    "entity_id_col": "entity_id",
    "sort_cols": ["seq"],
    "result_mode": "battle_level",
    "ally_values": ["ally"],
    "enemy_values": ["enemy"],

    "initial_on_field_enabled": true,
    "initial_on_field_col": "initial_on_field",
    "initial_on_field_values": ["true", "1", "yes", "lead"],

    "trace_moves_enabled": true,
    "turn_col": "turn_no",
    "actor_id_col": "move_actor_id",
    "target_id_col": "move_target_id",
    "move_name_col": "move_name",
    "move_order_col": "move_order",
    "move_order_direction": "ascending_first",
    "action_col": "row_kind",
    "move_action_values": ["move"],

    "state_trace_enabled": true,
    "state_turn_col": "turn_no",
    "state_entity_id_col": "state_entity_id",
    "state_hp_col": "hp_current",
    "state_status_col": "hp_status",
    "state_fainted_col": "fainted",
    "state_hp_mode": "absolute",
    "state_hp_tolerance": 0.0,

    "damage_trace_enabled": false
  }
}
```

`damage_trace_enabled`는 첫 PR에서는 `false` 기본값을 권장한다. damage columns는 생성하되, 엔진 데미지 공식/기술 사전이 아직 없으므로 바로 mismatch를 대량 발생시키지 않게 한다.

## 출력 3 — `adapter_report.json`

변환 품질을 사람이 확인할 수 있게 report를 남긴다.

권장 필드:

```json
{
  "source_kind": "pokemon_showdown_db_extract",
  "battle_count": 1,
  "event_count": 343,
  "participant_count": 12,
  "move_count": 36,
  "state_event_count": 100,
  "damage_event_count": 54,
  "winner_side": "p1",
  "ally_side": "p1",
  "warnings": [],
  "roster_only_entities": [],
  "unknown_damage_actor_count": 0
}
```

## CLI

신규 CLI 예:

```powershell
$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -X utf8 convert_showdown_db_extract.py `
  --input "C:\Users\kmjde\Downloads\pokemon_showdown_db_extract.zip" `
  --out-dir "db_corpus_fixtures\showdown_gen5ou_59402"
```

CLI는 다음을 출력한다.

```text
Wrote battle_log.csv
Wrote schema.json
Wrote adapter_report.json
```

## 테스트

`test_showdown_db_extract_adapter.py`를 추가한다.

테스트는 외부 Downloads 파일에 의존하지 말고, temp 폴더에 최소 DB extract fixture를 직접 만든다.

최소 fixture:

- `battles.csv`: 1 battle, winner_side p1
- `battle_events.csv`:
  - 초기 switch p1/p2
  - turn 1 MoveUsed p1 → p2
  - DamageApplied p2
  - StatusApplied p2
  - PokemonFainted p2
- 선택: `battle_roster_pokemon.csv`

검증:

1. zip 입력과 folder 입력 둘 다 변환 가능
2. `battle_log.csv`에 participant/move/state/damage row가 생성됨
3. participant row의 `team`만 ally/enemy이고 trace row의 `team`은 비어 있음
4. `schema.json`에 `battle_id_col`, `team_col`, `entity_id_col`, `trace_moves_enabled`, `state_trace_enabled` 존재
5. direct damage의 `damage_target_id`가 피해자이고, `damage_actor_id`가 직전 move actor로 연결됨
6. 생성된 `battle_log.csv + schema.json`을 `run_db_corpus_backtest.py`에 넣었을 때 최소한 로드/빌드가 실패하지 않음

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

- `run_db_corpus_backtest.py`의 기존 단일 파일 입력 계약을 깨지 말 것.
- Step1/Step2/Step6 UI 연결은 이번 PR에서 하지 말 것.
- Showdown HTML parser(`modules/showdown_trace.py`)를 억지로 재사용하지 말 것. 이번 입력은 이미 DB extract다.
- damage actor/target을 임의로 뒤집어 단순화하지 말 것.
- 외부 인터넷이나 패키지 설치에 의존하지 말 것.

## 완료 기준

- Showdown DB extract zip/folder를 현재 DB corpus fixture 형태로 변환 가능
- 생성된 schema가 기존 backtest harness와 호환
- 테스트가 외부 파일 없이 통과
- 기존 DB corpus/IR 회귀 테스트 통과
- 이 어댑터가 “실제 DB식 다중 테이블 로그를 단일 검증 코퍼스로 낮추는 입구”라는 역할을 문서/리포트에서 분명히 드러냄
