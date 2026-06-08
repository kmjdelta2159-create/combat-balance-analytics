# 툴화 PR-T4b — mechanism commit canonical 호환 보강

## 배경

PR-T4로 `modules/mechanism_detect.py`가 weather/status alias를 canonical name으로 정규화한다.

예:

- `Hail` → `hail`
- `Sandstorm` → `sand`
- `burned` → `brn`
- `badly poisoned` → `tox`

검출기 자체는 좋아졌다. 실제 `run_mechdetect.py` 결과도 `Stealth Rock`, `Spikes`, `Recoil`이 이미 구현/지원된 항목으로 `YES`가 되어 NO 목록이 비었다.

하지만 회귀가 하나 생겼다.

`run_mechcommit.py`의 `DECISIONS`는 아직:

```python
'hail': {'src': 'Hail', ...}
```

처럼 원본 Showdown src 이름을 찾는다. 그런데 `detect_mechanisms(...)` 결과 key는 이제 `hail`이다.

현재 실제 실행:

```text
[경고] 'Hail' 검출 안 됨 — 건너뜀
```

즉 RE 검출기는 좋아졌지만, 수정 surface/commit 경로가 canonical name과 원본 src 사이를 못 잇고 있다.

이번 PR은 그 호환을 보강한다.

## 목표

- `run_mechcommit.py`가 `src: "Hail"`과 canonical result `hail`을 같은 항목으로 찾게 한다.
- `infer_conditions(trace, ref, src_match)`도 canonical name으로 들어와도 원본 env src와 매칭할 수 있게 한다.
- Streamlit surface(`step_mechanism_re.py`)에서 alias canonical name을 넘겨도 조건 추론이 동작하게 한다.
- PR-T4의 catalog-only false positive 방지는 유지한다.

## 금지

- 전투 엔진 동작 변경 금지.
- `reference_gen5.py` 데이터 변경 금지.
- `mechanism_commit.commit(...)` 출력 spec 의미 변경 금지.
- canonicalization을 위해 engine import 금지.
- 단순히 `DECISIONS`의 `"Hail"`을 `"hail"`로 바꾸는 것만으로 끝내지 말 것.
  - 사용자가 앞으로 원본 src 이름으로 decisions를 쓰는 경우도 계속 동작해야 한다.

## 구현 요구

### 1. mechanism_detect에 public-ish canonical helper 추가

`modules/mechanism_detect.py`에 다음 계열 helper를 추가한다.

```python
def canonical_mechanism_key(cls_or_src, name=None):
    ...
```

동작 예:

```python
canonical_mechanism_key("Hail") == ("weather", "hail")
canonical_mechanism_key("Sandstorm") == ("weather", "sand")
canonical_mechanism_key("weather", "Hail") == ("weather", "hail")
canonical_mechanism_key("status", "badly poisoned") == ("status", "tox")
canonical_mechanism_key("hazard", "Stealth Rock") == ("hazard", "Stealth Rock")
canonical_mechanism_key("item", "Leftovers") == ("item", "Leftovers")
```

내부적으로 기존 `_norm(...)`을 재사용해도 된다.

이 helper는 `mechanism_commit.py`, `run_mechcommit.py`, 테스트에서 import할 수 있어야 한다.

### 2. detect_mechanisms 결과에 원본 src 힌트 보존

결과 row에 optional 필드를 추가한다.

```python
"sources": sorted([...])
```

각 group에 들어온 원본 `e.get("src")` 값을 모아둔다.

예:

```python
{
    "class": "weather",
    "name": "hail",
    "sources": ["Hail"],
    ...
}
```

기존 소비자는 이 필드를 몰라도 깨지지 않아야 한다.

구현 힌트:

현재 `g[(cls, name, kind)].append((frac, species))` 구조라면 tuple에 src를 하나 더 넣거나 별도 `srcs` dict를 둔다.

### 3. mechanism_commit.infer_conditions canonical 매칭

현재:

```python
if e.get('action') == 'env' and e.get('src') == src_match:
```

이 비교는 canonical name과 원본 src가 다르면 실패한다.

보강:

- `src_match`를 canonical key로 바꾼다.
- 각 env event의 `src`도 canonical key로 바꾼다.
- 둘이 같으면 affected로 본다.
- 단, src가 비어 있어서 move fallback이 필요한 경우는 기존 의미를 보존한다.

권장:

```python
from modules.mechanism_detect import canonical_mechanism_key

target_cls, target_name = canonical_mechanism_key(src_match)
...
if e.get("action") == "env":
    e_cls, e_name = canonical_mechanism_key(e.get("src"))
    if (e_cls, e_name) == (target_cls, target_name):
        ...
```

주의:

- `src_match`가 이미 `"hail"`이어도 매칭되어야 한다.
- `src_match`가 `"Hail"`이어도 매칭되어야 한다.
- `src_match`가 `"item: Leftovers"`이어도 item key로 매칭되면 좋다.

### 4. run_mechcommit decision lookup 보강

현재:

```python
det = {r['name']: r for r in detect_mechanisms(trace, ref)}
r = det.get(d['src'])
```

이 방식을 canonical-aware lookup으로 바꾼다.

권장:

```python
from modules.mechanism_detect import canonical_mechanism_key

rows = detect_mechanisms(trace, ref)
det = {}
for r in rows:
    det[(r["class"], r["name"])] = r
    for src in r.get("sources", []):
        det[canonical_mechanism_key(src)] = r

...
src_key = canonical_mechanism_key(d["src"])
r = det.get(src_key)
```

fallback으로 기존 `det.get(d["src"])`도 유지해도 된다.

완료 후 `run_mechcommit.py`에서 `src: "Hail"`이 더 이상 경고를 내면 안 된다.

### 5. step_mechanism_re 조건 추론 호환

`step_mechanism_re.py`는 `infer_conditions(trace, ref, name)`을 호출한다.

`infer_conditions`가 canonical-aware가 되면 대부분 해결된다.

단, 화면 표시에 `sources`가 있으면 작은 caption으로 원본 src를 보여줘도 된다. UI 변경은 선택이다. 큰 UI 변경은 하지 않는다.

## 테스트 추가/보강

기존 `test_mechanism_detect_aliases.py`에 이어서 새 테스트 파일을 추가하거나 같은 파일에 보강한다.

권장 파일:

```text
test_mechanism_commit_canonical.py
```

pytest 없이 실행 가능한 스크립트형 테스트.

### 테스트 A — detect row sources 보존

fake trace:

```python
trace = {
    "nick2species": {"P1": "Mon"},
    "events": [
        {"turn": 1, "action": "env", "src": "Hail", "who": "P1", "kind": "damage", "delta": -10, "max": 160},
    ],
}
```

검증:

- row `class=="weather"` and `name=="hail"` 존재
- `sources`에 `"Hail"` 존재

### 테스트 B — infer_conditions accepts original and canonical

fake ref:

```python
class Ref:
    SPECIES_TYPES = {"Mon": ("Normal", "")}
    SETS = {}
```

trace에 `src="Hail"` env event를 넣는다.

검증:

```python
infer_conditions(trace, Ref, "Hail")
infer_conditions(trace, Ref, "hail")
```

둘 다 affected/spared 계산이 같은 결과여야 한다.

`infer_conditions` 반환값에는 affected가 직접 없으므로, 최소한 `spared`, `not_ability_hint`, `not_types_hint`가 동일함을 확인한다.

### 테스트 C — decision lookup helper

`run_mechcommit.py`의 lookup을 함수로 빼면 테스트가 좋다.

권장:

```python
def _index_detected(rows):
    ...

def _lookup_detected(index, src):
    ...
```

테스트:

- rows에 `{"class": "weather", "name": "hail", "sources": ["Hail"]}`가 있을 때
- `_lookup_detected(index, "Hail")` returns row
- `_lookup_detected(index, "hail")` returns row

함수로 빼기 어렵다면 테스트에서 같은 로직을 간접적으로 검증해도 된다.

### 테스트 D — run_mechcommit no warning for Hail

스크립트 테스트에서 subprocess까지 쓰기 부담스럽다면 직접 함수 테스트로 충분하다.

그래도 가능하면 실제 명령 검증:

```powershell
python -X utf8 run_mechcommit.py
```

출력에 다음이 없어야 한다.

```text
'Hail' 검출 안 됨
```

그리고 출력에는 `'hail':` 커밋 블록이 있어야 한다.

## 검증 명령

아래가 모두 통과해야 한다.

```powershell
python -X utf8 -m py_compile modules/mechanism_detect.py modules/mechanism_commit.py run_mechcommit.py modules/step_mechanism_re.py test_mechanism_detect_aliases.py test_mechanism_commit_canonical.py
python -X utf8 test_mechanism_detect_aliases.py
python -X utf8 test_mechanism_commit_canonical.py
python -X utf8 run_mechdetect.py
python -X utf8 run_mechcommit.py
```

그리고 기존 통합 smoke도 유지:

```powershell
python -X utf8 test_i15_integration_smoke.py
```

## 완료 기준

- `run_mechdetect.py`는 T4 결과처럼 NO 목록이 비거나 줄어든 상태를 유지한다.
- `run_mechcommit.py`에서 `src: "Hail"`이 canonical `hail` row를 찾아 경고 없이 커밋된다.
- `infer_conditions`가 원본 src와 canonical name 양쪽을 처리한다.
- 기존 alias/model 판정 테스트가 깨지지 않는다.
- 전투 엔진 동작은 바뀌지 않는다.

## 보고 형식

작업 후 아래를 요약한다.

1. 변경 파일
2. canonical lookup 보강 방식
3. `run_mechcommit.py`의 Hail 경고가 사라졌는지
4. 통과한 검증 명령
5. 남은 한계가 있으면 별도 표시
