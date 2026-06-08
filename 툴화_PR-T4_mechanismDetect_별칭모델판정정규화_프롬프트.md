# 툴화 PR-T4 — mechanism_detect 별칭/모델 판정 정규화

## 목적

`modules/mechanism_detect.py`는 트레이스의 env stream을 읽어 “미구현/미표현 메커니즘 후보”를 사용자 수정 surface로 보낸다.

현재 문제는 `modeled` 판정이 거의 `ref.EFFECTS` key 직접 비교에만 묶여 있다는 점이다.

그 결과 실제로는 이미 engine/ref의 다른 substrate 또는 registry로 표현 가능한 항목이 `NO`로 보일 수 있다.

예:

- `Sandstorm` / `sandstorm` / `sand`는 ref.EFFECTS의 `sand`와 같은 weather 메커니즘이어야 한다.
- `Hail` / `hail`은 ref.EFFECTS의 `hail`과 같은 weather 메커니즘이어야 한다.
- `Recoil`은 `ref.RECOIL_MOVES`가 있으면 “generic recoil support가 있음”으로 볼 수 있다.
- `Stealth Rock`, `Spikes`는 현재 engine/fullbattle substrate가 지원하는 entry hazard이다.

이번 PR은 새 전투 기능 구현이 아니다. RE 검출기의 **표시 정확도**와 **사용자 수정 surface 품질**을 올리는 작업이다.

## 금지

- 엔진 전투 동작 변경 금지.
- `reference_gen5.py`의 전투 데이터 의미 변경 금지.
- `mechanism_commit.py` 커밋 형식 변경 금지.
- 단순히 모든 MOVES/ITEMS에 존재한다고 modeled=True 처리하지 말 것.
  - `Life Orb`, `Wish`처럼 이름은 알려져 있어도 env effect가 아직 별도 구현되지 않은 항목은 registry/EFFECTS가 없으면 NO로 남아야 한다.
- `modules.mechanism_detect`가 engine import에 의존하게 만들지 말 것.

가능하면 수정 파일은 아래 둘로 제한한다.

- `modules/mechanism_detect.py`
- `test_mechanism_detect_aliases.py` 신규

## 구현 요구

### 1. source alias canonicalization

`mechanism_detect.py`에 작은 alias 정규화 layer를 추가한다.

권장 구조:

```python
_WEATHER_ALIASES = {
    "hail": "hail",
    "sand": "sand",
    "sandstorm": "sand",
    "sand storm": "sand",
    "rain": "rain",
    "raindance": "rain",
    "rain dance": "rain",
    "sun": "sun",
    "sunnyday": "sun",
    "sunny day": "sun",
}

_STATUS_ALIASES = {
    "brn": "brn",
    "burn": "brn",
    "burned": "brn",
    "psn": "psn",
    "poison": "psn",
    "poisoned": "psn",
    "tox": "tox",
    "toxic": "tox",
    "badly poisoned": "tox",
    "par": "par",
    "paralysis": "par",
    "paralyzed": "par",
    "frz": "frz",
    "freeze": "frz",
    "frozen": "frz",
    "slp": "slp",
    "sleep": "slp",
    "asleep": "slp",
}
```

`_norm(src)`는 weather/status에 대해 canonical name을 반환한다.

예:

```python
_norm("Sandstorm") == ("weather", "sand")
_norm("sand storm") == ("weather", "sand")
_norm("Hail") == ("weather", "hail")
_norm("poisoned") == ("status", "psn")
```

기존 `item:` / `ability:` prefix 처리는 유지한다.

### 2. modeled 판정 helper 추가

`detect_mechanisms(...)` 내부의:

```python
modeled = name in mk or str(name).lower() in mk
```

를 helper로 분리한다.

권장:

```python
def _is_modeled(cls, name, ref):
    ...
```

판정 원칙:

1. `ref.EFFECTS`에 exact/lower/canonical key가 있으면 modeled=True.
2. weather/status는 alias canonical name으로도 비교한다.
3. `cls == "move"`이고 `name == "Recoil"`이면 `ref.RECOIL_MOVES`가 비어 있지 않을 때 modeled=True.
4. `cls == "move"`이고 `name`이 `ref.RECOIL_MOVES` key에 있으면 modeled=True.
5. `cls == "move"`이고 `name`이 `ref.FIXED_DAMAGE_MOVES` key에 있으면 modeled=True.
6. `cls == "hazard"`이고 name이 현재 engine substrate가 지원하는 entry hazard면 modeled=True.

현재 지원 hazard는 다음만 modeled=True로 본다.

```python
_SUPPORTED_ENTRY_HAZARDS = {"Stealth Rock", "Spikes"}
```

`Toxic Spikes`는 현재 `_hazard_entry_pct`가 독 상태 부여까지 처리하지 않으므로 자동으로 modeled=True 처리하지 않는다.

주의:

- `name in ref.MOVES`만으로 modeled=True 처리하지 말 것.
- `name in ref.ITEMS`만으로 modeled=True 처리하지 말 것.
- 이것은 “카탈로그에 이름이 있음”과 “효과가 구현되어 있음”을 분리하기 위한 장치다.

### 3. output name 안정성

weather/status는 canonical name으로 output에 나와도 된다.

예:

- 기존 `Hail` → `hail`
- 기존 `Sandstorm` → `sand`

다만 item/ability/move/hazard의 사람-readable 이름은 가능하면 기존 case를 유지한다.

### 4. run_mechdetect 회귀

현재 기본 corpus에서 `run_mechdetect.py`를 실행했을 때 최소한 아래가 깨지지 않아야 한다.

- 스크립트 예외 없음
- `Hail` 또는 `hail`은 modeled YES
- `Leftovers`는 modeled YES
- `Poison Heal`은 modeled YES

그리고 가능하면 현재 이미 substrate/registry가 있는 항목은 NO에서 빠져야 한다.

- `Stealth Rock` modeled YES
- `Spikes` modeled YES
- `Recoil` modeled YES, 단 `ref.RECOIL_MOVES`가 존재할 때

## 테스트 추가

루트에 `test_mechanism_detect_aliases.py`를 추가한다.

pytest 의존 없이 실행 가능한 스크립트형 테스트로 만든다.

### 테스트 A — weather alias

fake ref:

```python
class Ref:
    EFFECTS = {"sand": {}, "hail": {}}
```

fake trace:

```python
trace = {
    "nick2species": {"P1": "Mon"},
    "events": [
        {"turn": 1, "action": "env", "src": "Sandstorm", "who": "P1", "kind": "damage", "delta": -10, "max": 160},
        {"turn": 2, "action": "env", "src": "Hail", "who": "P1", "kind": "damage", "delta": -10, "max": 160},
    ],
}
```

검증:

- 결과에 `("weather", "sand")`가 있고 modeled True
- 결과에 `("weather", "hail")`가 있고 modeled True

### 테스트 B — status alias

fake ref:

```python
class Ref:
    EFFECTS = {"brn": {}, "psn": {}, "tox": {}}
```

fake trace에 `src="burned"`, `src="poisoned"`, `src="badly poisoned"`를 넣는다.

검증:

- `brn`, `psn`, `tox`로 canonicalize된다.
- 모두 modeled True.

### 테스트 C — registry modeled

fake ref:

```python
class Ref:
    EFFECTS = {}
    RECOIL_MOVES = {"Brave Bird": 1/3}
    FIXED_DAMAGE_MOVES = {"Seismic Toss": 100}
```

검증:

- `src="Recoil"` env event는 modeled True.
- `_is_modeled("move", "Brave Bird", Ref)`가 True.
- `_is_modeled("move", "Seismic Toss", Ref)`가 True.

직접 helper를 import하기 싫으면 `detect_mechanisms`로 검증해도 된다. helper import가 더 명확하면 `_is_modeled`를 모듈 내부 public-ish helper로 둬도 괜찮다.

### 테스트 D — hazard substrate

fake ref는 비어 있어도 된다.

검증:

- `Stealth Rock` modeled True
- `Spikes` modeled True
- `Toxic Spikes` modeled False

### 테스트 E — catalog-only false positive 방지

fake ref:

```python
class Ref:
    EFFECTS = {}
    MOVES = {"Wish": (0, "status", None)}
    ITEMS = {"Life Orb": {"atk": 1.3}}
```

검증:

- `_is_modeled("move", "Wish", Ref)`는 False
- `_is_modeled("item", "Life Orb", Ref)`는 False

이 테스트가 중요하다. 이름만 아는 것과 효과 구현은 다르다.

## 검증 명령

아래가 모두 통과해야 한다.

```powershell
python -X utf8 -m py_compile modules/mechanism_detect.py test_mechanism_detect_aliases.py
python -X utf8 test_mechanism_detect_aliases.py
python -X utf8 run_mechdetect.py
```

가능하면 기존 smoke도 한 번 확인한다.

```powershell
python -X utf8 test_i15_integration_smoke.py
```

## 완료 기준

- source alias가 canonicalize된다.
- modeled 판정이 `EFFECTS` 외의 현재 지원 substrate/registry를 반영한다.
- catalog-only 항목을 modeled로 오판하지 않는다.
- `run_mechdetect.py`가 정상 실행된다.
- 전투 엔진 동작은 변경하지 않는다.

## 보고 형식

작업 후 아래를 요약한다.

1. 변경 파일
2. alias 처리 요약
3. modeled 판정에 새로 반영한 진실원천
4. 통과한 검증 명령
5. `run_mechdetect.py`에서 NO 목록이 어떻게 바뀌었는지
