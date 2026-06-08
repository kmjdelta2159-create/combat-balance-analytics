# DB로그 IR PR-I15 — 통합 backtest smoke 하니스

## 목적

PR-I8~I14c까지 붙은 DB-log IR 연결축이 각각 따로는 검증됐다.

이제 1차 목표 기준으로 필요한 것은 “포켓몬 복제에 필요한 기능군을 DB 로그로 검증할 수 있는가”를 한 전투 단위에서 확인하는 통합 smoke다.

이번 PR은 새 기능을 크게 추가하는 작업이 아니다. 이미 구현된 아래 축들이 한 전투 안에서 함께 켜져도 서로 깨지지 않는지 증명하는 회귀 하니스를 추가한다.

- initial on-field state
- move trace action
- switch trace action
- faint incoming trace
- action order / priority overlay
- action damage score
- damage vs hp_delta split
- action resource delta score
- observed resource filter / strict extra mode
- state snapshot score

## 금지

- 포켓몬 전용 하드코딩 금지.
- 특정 샘플 파일에 의존하는 테스트 금지.
- UI 대개편 금지.
- 기존 score 의미 변경 금지.
- 기존 `test_i13.py`, `test_i14.py`를 깨지 말 것.

## 구현 범위

### 1. 새 테스트 파일 추가

루트에 다음 파일을 추가한다.

```text
test_i15_integration_smoke.py
```

이 파일은 순수 Python 스크립트형 하니스로 둔다. pytest 의존은 추가하지 않는다.

실행 명령:

```powershell
python -X utf8 test_i15_integration_smoke.py
```

이 환경에서 plain `python`이 없으면 실제 검증자는 bundled python을 써도 된다.

### 2. 통합 시나리오 A — 관측 resource filter 기본 모드

작은 synthetic DB 로그를 DataFrame으로 만든다.

필수 조건:

- battle 1개
- Ally 2명: `A1`, `A2`
- Enemy 2명: `E1`, `E2`
- `A1`이 먼저 행동
- `A1 -> E1` 공격
- `E1`은 Shield 20과 HP 30을 잃고 기절하지 않음
- DB resource delta에는 Shield만 제공
- expected action damage는 `hp_delta=30`
- state snapshot은 turn 1 종료 시 `E1.hp=70`, `E1.Shield=0` 같은 값을 검증
- `resource_delta_strict_extra=False`

검증 기대:

- `action_damage_score.accuracy == 1.0`
- `action_resource_delta_score.accuracy == 1.0`
- `action_resource_delta_score.extra == 0`
- `state_score.accuracy == 1.0`
- worker 결과가 문자열 ERROR가 아님

핵심은 실제 엔진은 HP+Shield resource delta를 모두 만들지만, DB 로그가 Shield만 관측했으면 HP extra를 벌점 주지 않는다는 점이다.

### 3. 통합 시나리오 B — strict extra 모드

시나리오 A와 같은 expected resource delta를 쓰되:

```python
"resource_delta_strict_extra": True
```

검증 기대:

- `action_resource_delta_score.extra >= 1`
- `action_resource_delta_score.mismatches >= 1`
- `first_mismatch.kind == "extra_action_resource_delta"`

반격까지 존재하는 구성이라면 extra가 1보다 클 수 있다. 정확한 extra 수를 1로 고정하지 말고 `>= 1`로 검증한다.

### 4. 통합 시나리오 C — build_battles 경유

수동 `game_config`만 검사하지 말고, 반드시 `modules.per_battle_backtest.build_battles(...)`를 경유하는 케이스도 넣는다.

검증해야 할 것:

- `game_config["preserve_ids"] is True`
- `_expected_action_damage_trace` 존재
- `_expected_action_resource_delta_trace` 존재
- `_expected_state_snapshots` 존재
- `_action_resource_delta_score_config["resource_names"] == ["Shield"]`
- `_action_resource_delta_score_config["strict_extra"] is False`

이 테스트는 “Step6 DB 역할 컬럼 방식이 worker score config까지 전달하는가”를 검증하는 목적이다.

### 5. trace action / initial on-field smoke

가능하면 같은 테스트 파일 안에 아주 작은 trace action config를 포함한다.

목표:

- `initial_on_field`가 `A1/E1`로 유지됨
- turn 1 move trace가 `A1 -> E1`로 전달됨

이미 public helper가 있으면 helper를 사용한다. 없으면 `build_battles(...)` 결과 `game_config`에 다음 계열 key가 존재하는지만 검증해도 된다.

- `preserve_initial_on_field`
- `initial_on_field` 또는 동등한 현재 구현 key
- `trace_actions`

단, 현재 구현 key 이름을 억지로 바꾸지 말고 기존 구조를 따라간다.

### 6. 기존 회귀 실행

다음이 계속 통과해야 한다.

```powershell
python -X utf8 test_i13.py
python -X utf8 test_i14.py
python -X utf8 test_i15_integration_smoke.py
```

그리고 문법 검증:

```powershell
python -X utf8 -m py_compile modules/engine.py modules/per_battle_backtest.py modules/step6_dashboard.py test_i15_integration_smoke.py
```

## 완료 기준

- 새 통합 smoke가 추가되어 실행 통과한다.
- 기존 I13/I14 회귀가 깨지지 않는다.
- strict extra False/True 차이가 한 전투 단위 worker 경로에서 증명된다.
- build_battles가 resource observed config를 worker까지 넘기는 것이 증명된다.
- 구현 변경이 필요했다면 최소 범위로만 수정한다.

## 보고 형식

작업 후 아래를 요약 보고한다.

1. 변경 파일
2. 통과한 검증 명령
3. 시나리오 A/B/C 결과
4. 발견한 기존 한계가 있으면 “이번 PR 범위 밖”으로 따로 적기
