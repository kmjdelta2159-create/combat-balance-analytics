# DB코퍼스 PR-ADAPT1d - roster-only species/nickname false positive 보정

## 목적

ADAPT1c는 실제 roster 테이블의 `species` 컬럼을 읽도록 보강했고, 기본 테스트와 실제 zip 변환은 통과했다.

하지만 검수 결과 실제 `pokemon_showdown_db_extract.zip`에서 `roster_only_entities`가 잘못 계산되는 문제가 확인됐다.

핵심 원인은 다음과 같다.

- `battle_events.csv`의 `actor_name`은 실제 플레이어가 붙인 닉네임일 수 있다.
- 같은 이벤트의 `pokemon_name`에는 실제 species가 들어 있다. 예: `Breloom, F`, `Jirachi`, `Garchomp, M`
- `battle_roster_pokemon.csv`의 `species`는 `Breloom`, `Jirachi`, `Garchomp`처럼 순수 종명이다.
- 현재 코드는 관측 포켓몬을 `side:actor_name`으로 저장한 뒤 roster의 `side:species`와 exact match한다.
- 그래서 닉네임을 쓴 실제 등장 포켓몬이 모두 roster-only false positive로 보고된다.

이번 PR은 큰 기능 추가가 아니라 **roster-only 판정에서 nickname/species mismatch를 정규화해 false positive를 제거하는 보정**만 수행한다.

## 실제 재현

수동 smoke:

```powershell
$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -X utf8 convert_showdown_db_extract.py --input "C:\Users\kmjde\Downloads\pokemon_showdown_db_extract.zip" --out-dir ".codex_tmp\adapt1c_real_zip"
```

현재 `adapter_report.json`:

```text
roster_only_count=6
roster_only=[
  {'battle_id': 'smogtours-gen5ou-59402', 'side': 'p1', 'species': 'Politoed'},
  {'battle_id': 'smogtours-gen5ou-59402', 'side': 'p1', 'species': 'Jirachi'},
  {'battle_id': 'smogtours-gen5ou-59402', 'side': 'p1', 'species': 'Breloom'},
  {'battle_id': 'smogtours-gen5ou-59402', 'side': 'p1', 'species': 'Garchomp'},
  {'battle_id': 'smogtours-gen5ou-59402', 'side': 'p1', 'species': 'Zapdos'},
  {'battle_id': 'smogtours-gen5ou-59402', 'side': 'p1', 'species': 'Tentacruel'}
]
```

하지만 같은 변환 결과의 participant는 이미 이 species들을 관측했다.

```text
team  entity_id      name       species
ally  p1:Gengen      Gengen     Breloom, F
ally  p1:Nanami      Nanami     Jirachi
ally  p1:Rikimaru    Rikimaru   Garchomp, M
ally  p1:Bonaparte   Bonaparte  Politoed, M
ally  p1:Riou        Riou       Zapdos
ally  p1:Zamza       Zamza      Tentacruel, M
```

즉 이 6개는 roster-only가 아니다.

## 현재 문제 위치

`modules/showdown_db_adapter.py`

현재 관측 entity 저장:

```python
entity_id = f"{side}:{name}"
...
entities_seen.add(entity_id)
...
battle_entities_seen[str(b_id)] = entities_seen
```

현재 roster-only 비교:

```python
species = str(species_val)
entity_id = f"{side}:{species}"
seen = battle_entities_seen.get(b_id_str, set())
if entity_id not in seen:
    roster_only_entities.append(...)
```

이 비교는 `actor_name == species`일 때만 맞는다.

실제 Showdown extract에서는 닉네임 사용 시 `actor_name != pokemon_name/species`가 흔하다.

## 작업 범위

### 1. species 정규화 helper 추가

`modules/showdown_db_adapter.py`에 작은 helper를 추가한다.

권장 형태:

```python
def _normalize_species(value):
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text or text == "nan":
        return ""
    # Showdown pokemon_name may be "Breloom, F" or "Garchomp, M".
    return text.split(",", 1)[0].strip()
```

주의:

- roster `species`와 event `pokemon_name` 모두 이 helper를 통과시킨다.
- 성별 suffix `, F`, `, M` 제거가 핵심이다.
- species 내부에 쉼표가 필요한 특수 포켓몬명은 현재 Gen5 Showdown extract 범위에서는 다루지 않는다.
- helper는 이 adapter 내부 전용이면 충분하다.

### 2. 관측 species set을 별도로 저장

기존 `battle_entities_seen`은 participant/entity 추적용으로 유지해도 된다.

다만 roster-only 판정에는 별도 set을 쓴다.

권장:

```python
battle_species_seen = {}
...
species = _normalize_species(row.get("pokemon_name", name))
...
if species:
    species_seen.add((side, species))
...
battle_species_seen[str(b_id)] = species_seen
```

또는 battle별 dict 안에 `entity_ids`와 `species_by_side`를 같이 저장해도 된다.

중요한 조건:

- participant row의 기존 `entity_id`는 바꾸지 않는다. 닉네임 기반 entity id는 현재 trace/state/damage 연결에 필요하다.
- participant row의 `species` 값은 기존처럼 `pokemon_name` 원문을 유지해도 되고, 정규화한 값으로 바꿔도 된다. 단, 바꿀 경우 기존 테스트와 downstream 영향이 없는지 확인한다.
- roster-only 판정은 반드시 `(side, normalized_species)` 기준으로 해야 한다.

### 3. roster-only 비교를 species 기준으로 변경

현재:

```python
entity_id = f"{side}:{species}"
seen = battle_entities_seen.get(b_id_str, set())
if entity_id not in seen:
    roster_only_entities.append(...)
```

변경:

```python
species = _normalize_species(species_val)
if not species:
    continue

seen_species = battle_species_seen.get(b_id_str, set())
if (side, species) not in seen_species:
    roster_only_entities.append({
        "battle_id": b_id_str,
        "side": side,
        "species": species,
    })
```

주의:

- 출력 항목의 `species`는 정규화된 순수 종명으로 둔다.
- 기존 `pokemon_name` fallback 테스트도 그대로 통과해야 한다.
- roster에 `species`, `pokemon_name`, `name` 중 어떤 컬럼이 와도 같은 정규화 경로를 타야 한다.

### 4. 테스트에 nickname/species mismatch 케이스 추가

`test_showdown_db_extract_adapter.py`에 false positive 방지 테스트를 추가한다.

최소 시나리오:

```python
def test_roster_only_uses_species_not_actor_nickname():
    battles_df = pd.DataFrame({
        "battle_id": ["nick_1"],
        "winner_side": ["p1"],
    })
    events_df = pd.DataFrame({
        "battle_id": ["nick_1", "nick_1"],
        "seq": [1, 2],
        "turn_no": [0, 0],
        "event_type": ["PokemonSwitched", "PokemonSwitched"],
        "actor_side": ["p1", "p2"],
        "actor_name": ["Gengen", "Rotom-Wash"],
        "pokemon_name": ["Breloom, F", "Rotom-Wash"],
        "hp_current": [100, 100],
        "hp_max": [100, 100],
    })
    rosters_df = pd.DataFrame({
        "battle_id": ["nick_1", "nick_1", "nick_1"],
        "side": ["p1", "p2", "p2"],
        "species": ["Breloom", "Rotom-Wash", "UnusedMon"],
    })

    _, report = convert_to_battle_log(battles_df, events_df, rosters_df)

    assert report["roster_only_entities"] == [
        {"battle_id": "nick_1", "side": "p2", "species": "UnusedMon"}
    ]
```

이 테스트가 현재 ADAPT1c 코드에서는 실패해야 하고, 수정 후 통과해야 한다.

기존 테스트도 유지한다.

- 실제 schema `species` 컬럼 기반 mock
- `pokemon_name` fallback mock
- direct damage target mismatch guard
- status event fake faint 방지
- winner_side 보존

### 5. 실제 zip smoke 검수 포인트 보강

수동 smoke 후 다음을 확인한다.

```powershell
& $py -X utf8 -c "import json; from pathlib import Path; r=json.loads(Path('.codex_tmp/adapt1d_real_zip/adapter_report.json').read_text(encoding='utf-8')); print(len(r.get('roster_only_entities', []))); print(r.get('roster_only_entities', []))"
```

기대:

- 위 실제 zip 기준으로 `roster_only_entities`는 `0`이어야 한다.
- 적어도 `Politoed`, `Jirachi`, `Breloom`, `Garchomp`, `Zapdos`, `Tentacruel` 같은 이미 등장한 p1 species가 roster-only로 보고되면 안 된다.

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
& $py -X utf8 convert_showdown_db_extract.py --input "C:\Users\kmjde\Downloads\pokemon_showdown_db_extract.zip" --out-dir ".codex_tmp\adapt1d_real_zip"
& $py -X utf8 run_db_corpus_backtest.py --schema ".codex_tmp\adapt1d_real_zip\schema.json" --out-dir ".codex_tmp\adapt1d_real_zip\backtest" --max-battles 1 ".codex_tmp\adapt1d_real_zip\battle_log.csv"
```

그리고 `adapter_report.json`에서 다음을 확인한다.

```text
roster_only_entities == []
```

단, 다른 실제 extract에서 정말 roster에는 있으나 switch/event에 등장하지 않은 포켓몬이 있으면 roster-only로 남아야 한다.

## 금지 범위

- `.db` 직접 입력 지원 추가 금지. 이것은 ADAPT2에서 다룬다.
- `.sql` dump 지원 추가 금지.
- Streamlit UI 연결 금지.
- battle formula / type chart / ability inference 추가 금지.
- damage 정확도 개선 금지. 현재 schema의 `global_damage_formula = "0"` 때문에 실제 zip backtest 정확도 0%가 나오는 것은 이번 PR 실패가 아니다.
- participant/entity id를 species 기반으로 바꾸는 대규모 변경 금지. trace/state/damage 연결 안정성을 위해 entity id는 기존 닉네임 기반을 유지한다.

## 검수 포인트

검수자는 다음을 확인한다.

- `actor_name`이 닉네임이고 `pokemon_name`이 `Breloom, F`인 경우 roster `species=Breloom`과 같은 포켓몬으로 인식된다.
- 실제 `pokemon_showdown_db_extract.zip`에서 이미 등장한 p1 포켓몬들이 roster-only로 보고되지 않는다.
- 기존 `species` 컬럼 기반 roster-only 테스트가 깨지지 않는다.
- 기존 `pokemon_name` fallback 테스트가 깨지지 않는다.
- Status 이벤트가 fake faint를 만들지 않는다.
- direct damage mismatch에서 actor가 잘못 붙지 않는다.
- 기존 DB corpus 회귀 테스트가 깨지지 않는다.
