# PR-H1 — 정적 진입 해저드 추가 (engine.py)

## 역할/맥락
너는 Antigravity 에이전트다. 아래 변경을 `modules/engine.py`에 **정확히** 적용하라. 이 PR은
교체 진입 시 지정 진영(team)으로 들어오는 유닛에게 주 자원 max의 percent만큼 데미지를 주는
정적(상수) 해저드를 추가한다. 진입 hook `_fire_switch_in` 위에 ctx 비의존 헬퍼
`_apply_entry_hazard`를 얹고, `_fire_switch_in`이 Trace(`_apply_switch_in_effects`) 다음에
이를 호출한다. **회귀 0**: `game_config['mechanisms']['hazard']` 미설정이면 no-op.

설계 근거(이미 정찰·확정):
- `_fire_switch_in(char, participants, game_config, add_log)`은 **교체 진입에서만** 호출된다
  (자발적 교체 + 강제 교체 콜백). 초기 on_field 배치는 부르지 않으므로 **리드(첫 액티브)는
  자연히 해저드를 면제**받는다(Pokemon 해저드와 동일). 시그니처는 바꾸지 않는다.
- 데미지는 모듈 레벨 헬퍼로 적용한다. `engine.py`는 이미 9번째 줄에서
  `from modules.resource import get_current, get_max, apply_delta, ResourceModule`을 import한다.
  `apply_delta(char, delta)`는 주 자원에 delta를 [0, max] 클램프로 적용하고 **실제 변화량**을
  반환한다(데미지면 음수). `get_max`/`get_current`는 주 자원의 max/current. 따라서
  `_apply_entry_hazard`는 `resource_module`/`ctx` 없이도 작동한다.
- char에는 `team` 필드가 있다(`_apply_switch_in_effects`가 `char.get('team')`/`p.get('team')`로
  사용). 해저드 config의 `team`이 그 진영과 일치할 때만 발동한다. `"both"`(대소문자 무시)면
  진영 무관 발동.

## 제약
- 아래 FIND/REPLACE 블록을 **byte 단위로 정확히** 적용하라. 다른 곳은 절대 건드리지 마라.
- FIND 문자열은 `modules/engine.py`에 **정확히 한 번만** 나타난다(앵커 유일).
- import 줄은 이미 존재하므로 추가하지 마라(`get_current`/`get_max`/`apply_delta` 사용 가능).
- 적용 후
  `python -c "import ast; ast.parse(open('modules/engine.py',encoding='utf-8').read())"`로
  컴파일을 확인하라.

## 변경 1/1 — `_apply_entry_hazard` 추가 + `_fire_switch_in` 호출 삽입

`_fire_switch_in` 정의 바로 앞에 `_apply_entry_hazard`를 새로 정의하고, `_fire_switch_in` 본문
에서 `_apply_switch_in_effects(...)` 호출 **다음 줄**에 `_apply_entry_hazard(...)` 호출을 넣는다.
(호출 순서: Trace → 해저드 → 진입 이벤트 → 진입 로그.)

```python
# FIND
def _fire_switch_in(char, participants, game_config, add_log):
    """교체 진입 즉시 처리 — 진입 효과(Trace 등) + 진입 이벤트(상태 만료) + 진입 로그를 한 번에
    발화한다. ctx 비의존(add_log 콜백만 받음)이라 자발적 교체(engine)·강제 교체(turn_manager
    콜백) 양쪽에서 같은 함수를 부른다. 호출부가 직후 just_switched_in을 소비해 다음-턴
    _act_on_switch 이중 발화를 막는다."""
    _apply_switch_in_effects(char, participants, game_config, add_log)
```

```python
# REPLACE
def _apply_entry_hazard(char, participants, game_config, add_log):
    """교체 진입 정적 해저드 — game_config['mechanisms']['hazard'] 기반. 지정 진영(team)으로
    교체 진입하는 유닛이 주 자원 max의 percent만큼 데미지를 받는다. 모듈 레벨
    get_current/get_max/apply_delta만 쓰므로 ctx·resource_module 비의존 → _fire_switch_in
    시그니처 불변. spec 미설정/team 불일치/자원 없음 시 no-op이라 회귀 0. _fire_switch_in은
    교체 진입에서만 호출되므로 초기 리드(첫 액티브)는 자연히 면제(Pokemon 해저드와 동일).
    spec 예: {"team": "Enemy", "percent": 0.125}. team="both"(대소문자 무시)면 진영 무관."""
    mechs = (game_config or {}).get("mechanisms") or {}
    spec = mechs.get("hazard")
    if not spec:
        return
    team = spec.get("team")
    if team and str(team).lower() != "both" and str(team) != str(char.get("team")):
        return
    before = get_current(char)
    if before <= 0:
        return
    mx = get_max(char)
    if mx <= 0:
        return
    percent = float(spec.get("percent", 0.125))
    apply_delta(char, -mx * percent)          # apply_delta는 새 current를 반환하므로 차분으로 계산
    lost = before - get_current(char)
    if lost > 0:
        add_log(f"  -> [Phase: ON_SWITCH] {char.get('id','?')} 진입 데미지 {int(lost)} (Hazard)")
    if get_current(char) <= 0:
        add_log(f"  [Phase: ON_SWITCH] ☠️ {char.get('id','?')} 진입 데미지로 쓰러짐! (Hazard)")


def _fire_switch_in(char, participants, game_config, add_log):
    """교체 진입 즉시 처리 — 진입 효과(Trace 등) + 진입 이벤트(상태 만료) + 진입 로그를 한 번에
    발화한다. ctx 비의존(add_log 콜백만 받음)이라 자발적 교체(engine)·강제 교체(turn_manager
    콜백) 양쪽에서 같은 함수를 부른다. 호출부가 직후 just_switched_in을 소비해 다음-턴
    _act_on_switch 이중 발화를 막는다."""
    _apply_switch_in_effects(char, participants, game_config, add_log)
    _apply_entry_hazard(char, participants, game_config, add_log)
```

## 검증 (적용 후 수행)
1. `git diff modules/engine.py`로 변경이 위 두 지점(새 함수 추가 + 호출 한 줄)뿐인지 확인.
2. 컴파일: `python -c "import ast; ast.parse(open('modules/engine.py',encoding='utf-8').read())"`.
3. 동작 단위검증(아래 4케이스를 통과해야 한다):
   - **team 매칭**: `mechanisms={"hazard":{"team":"Enemy","percent":0.25}}`, char.team="Enemy",
     주 자원 max=200 → 진입 후 current가 50 감소(데미지 50), 로그에 "진입 데미지 50 (Hazard)".
   - **team 불일치**: 같은 spec, char.team="Ally" → no-op(데미지 0, 로그 없음).
   - **미설정**: `mechanisms={}` 또는 hazard 키 없음 → no-op(회귀 0).
   - **자원 없음/0**: 주 자원 current=0 또는 max=0 → no-op(음수/예외 없음).
4. Trace와 공존: hazard와 trace를 동시에 설정했을 때 둘 다 발화하고(타입 복사 → 데미지 순서),
   진입 로그가 그 뒤에 한 번만 찍히는지 확인.

## 회귀/한계 메모
- 진입 데미지로 진입 유닛이 즉사할 수 있다. `_fire_switch_in`은 `_resolve_faint` 도중 호출되므로
  즉사 시 그 사망 정리는 다음 `_resolve_faint` 사이클/`win_condition`에서 처리된다(즉시 연쇄
  교체 아님). H1은 이 근사를 수용하고 "진입 데미지로 쓰러짐" 로그로 드러낸다.
- H1은 상시 진입세(무브로 켜고 끄는 다이내믹은 후속 H2 — 필드-상태 substrate 필요).
- 후속: PR-H3(step2 메커니즘 expander에 해저드 체크박스 + team + percent UI, `_mech_cfg["hazard"]`).
