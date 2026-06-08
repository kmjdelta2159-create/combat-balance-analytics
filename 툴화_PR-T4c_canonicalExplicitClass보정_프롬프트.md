# 툴화 PR-T4c — canonical_mechanism_key explicit class 보정

## 배경

PR-T4b로 `run_mechcommit.py`의 Hail canonical lookup 회귀는 해결됐다.

실제 확인:

```text
run_mechcommit.py
    'hail': {...}
```

이제 `src: "Hail"`이 canonical row `("weather", "hail")`을 찾아 경고 없이 커밋된다.

하지만 `canonical_mechanism_key(cls, name)` helper에 작은 버그가 남았다.

현재 직접 검증:

```python
canonical_mechanism_key("item", "Leftovers")
# actual:   ("weather", "Leftovers")
# expected: ("item", "Leftovers")
```

마찬가지로 explicit class가 `ability`, `item`, 일부 `move`인 경우 class 보존이 깨질 수 있다.

이번 PR은 전투 기능 변경이 아니다. canonical helper의 계약을 정확히 맞추고, 테스트가 그 계약을 잡게 하는 작은 하드닝이다.

## 금지

- 전투 엔진 동작 변경 금지.
- `reference_gen5.py` 데이터 변경 금지.
- `detect_mechanisms(...)`의 기존 output 의미 변경 금지.
- `run_mechcommit.py`의 Hail 호환을 다시 깨지 말 것.
- `Life Orb`, `Wish` 같은 catalog-only false positive 방지 테스트를 깨지 말 것.

수정 범위는 가능하면 아래로 제한한다.

- `modules/mechanism_detect.py`
- `test_mechanism_commit_canonical.py`
- 필요하면 `test_mechanism_detect_aliases.py`

## 요구사항

### 1. canonical_mechanism_key 계약 명확화

`modules/mechanism_detect.py`의 `canonical_mechanism_key(cls_or_src, name=None)`를 아래 계약대로 고친다.

#### A. raw src 모드

`name is None`이면 기존처럼 `_norm(src)`를 쓴다.

```python
canonical_mechanism_key("Hail") == ("weather", "hail")
canonical_mechanism_key("Sandstorm") == ("weather", "sand")
canonical_mechanism_key("item: Leftovers") == ("item", "Leftovers")
canonical_mechanism_key("ability: Poison Heal") == ("ability", "Poison Heal")
```

#### B. explicit class 모드

`name is not None`이면 첫 번째 인자는 이미 신뢰할 class다. 이때 fallback `_norm(name)`이 class를 덮어쓰면 안 된다.

기대:

```python
canonical_mechanism_key("weather", "Hail") == ("weather", "hail")
canonical_mechanism_key("weather", "Sandstorm") == ("weather", "sand")
canonical_mechanism_key("status", "badly poisoned") == ("status", "tox")
canonical_mechanism_key("hazard", "Stealth Rock") == ("hazard", "Stealth Rock")
canonical_mechanism_key("hazard", "spikes") == ("hazard", "Spikes")
canonical_mechanism_key("hazard", "toxic spikes") == ("hazard", "Toxic Spikes")
canonical_mechanism_key("move", "Recoil") == ("move", "Recoil")
canonical_mechanism_key("move", "Brave Bird") == ("move", "Brave Bird")
canonical_mechanism_key("item", "Leftovers") == ("item", "Leftovers")
canonical_mechanism_key("ability", "Poison Heal") == ("ability", "Poison Heal")
```

즉 explicit class가 주어진 경우:

- `weather`는 weather alias만 적용
- `status`는 status alias만 적용
- `hazard`는 hazard alias/case normalization만 적용
- `move`, `item`, `ability`는 기본적으로 원래 이름을 보존
- `move`의 `"recoil"` 정도는 `"Recoil"`로 case normalization해도 됨

권장 구현:

```python
_HAZARD_ALIASES = {
    "stealth rock": "Stealth Rock",
    "spikes": "Spikes",
    "toxic spikes": "Toxic Spikes",
}

def canonical_mechanism_key(cls_or_src, name=None):
    if name is None:
        return _norm(cls_or_src)

    cls = str(cls_or_src or "").strip()
    n = str(name or "").strip()
    nl = n.lower()

    if cls == "weather":
        return cls, _WEATHER_ALIASES.get(nl, n)
    if cls == "status":
        return cls, _STATUS_ALIASES.get(nl, n)
    if cls == "hazard":
        return cls, _HAZARD_ALIASES.get(nl, n)
    if cls == "move":
        return cls, "Recoil" if nl == "recoil" else n
    if cls in ("item", "ability"):
        return cls, n
    return cls, n
```

`_norm(src)`도 가능하면 `_HAZARD_ALIASES`를 재사용해 lowercase hazard src를 처리하게 하면 좋다.

```python
if s_lower in _HAZARD_ALIASES:
    return "hazard", _HAZARD_ALIASES[s_lower]
```

### 2. 테스트 보강

`test_mechanism_commit_canonical.py`에 explicit class 계약 테스트를 추가한다.

필수 assertion:

```python
assert canonical_mechanism_key("item", "Leftovers") == ("item", "Leftovers")
assert canonical_mechanism_key("ability", "Poison Heal") == ("ability", "Poison Heal")
assert canonical_mechanism_key("move", "Brave Bird") == ("move", "Brave Bird")
assert canonical_mechanism_key("move", "recoil") == ("move", "Recoil")
assert canonical_mechanism_key("hazard", "spikes") == ("hazard", "Spikes")
assert canonical_mechanism_key("weather", "Hail") == ("weather", "hail")
assert canonical_mechanism_key("status", "badly poisoned") == ("status", "tox")
```

또 raw src prefix도 확인한다.

```python
assert canonical_mechanism_key("item: Leftovers") == ("item", "Leftovers")
assert canonical_mechanism_key("ability: Poison Heal") == ("ability", "Poison Heal")
```

### 3. 기존 회귀 유지

아래 동작은 유지되어야 한다.

- `run_mechdetect.py` NO 목록이 다시 늘지 않음
- `run_mechcommit.py`에서 `"Hail" 검출 안 됨` 경고 없음
- `test_mechanism_detect_aliases.py` 통과
- `test_i15_integration_smoke.py` 통과

## 검증 명령

아래가 모두 통과해야 한다.

```powershell
python -X utf8 -m py_compile modules/mechanism_detect.py modules/mechanism_commit.py run_mechcommit.py test_mechanism_detect_aliases.py test_mechanism_commit_canonical.py
python -X utf8 test_mechanism_detect_aliases.py
python -X utf8 test_mechanism_commit_canonical.py
python -X utf8 run_mechdetect.py
python -X utf8 run_mechcommit.py
python -X utf8 test_i15_integration_smoke.py
```

그리고 직접 확인:

```powershell
python -X utf8 - <<'PY'
from modules.mechanism_detect import canonical_mechanism_key
assert canonical_mechanism_key("item", "Leftovers") == ("item", "Leftovers")
assert canonical_mechanism_key("ability", "Poison Heal") == ("ability", "Poison Heal")
print("explicit class canonical OK")
PY
```

PowerShell에서는 here-string으로 대체해도 된다.

## 완료 기준

- explicit class 모드에서 class가 보존된다.
- raw src 모드의 T4/T4b 동작이 유지된다.
- Hail commit 경고가 사라진 상태를 유지한다.
- 전투 엔진 동작은 바뀌지 않는다.

## 보고 형식

작업 후 아래를 요약한다.

1. 변경 파일
2. canonical helper 계약 보정 내용
3. 새로 추가한 테스트
4. 통과한 검증 명령
5. `run_mechcommit.py` Hail 경고 유무
