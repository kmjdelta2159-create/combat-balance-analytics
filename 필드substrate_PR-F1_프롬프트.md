# PR-F1 — 전장 동적 상태(field_state) substrate 도입 (engine.py)

## 역할/맥락
너는 Antigravity 에이전트다. 아래 변경을 `modules/engine.py`에 **정확히** 적용하라. 이 PR은
"전장(팀) 레벨 동적 상태"를 담을 substrate `field_state`를 도입한다 — 전투마다 새로 만들어지는
dict를 ctx에 스레딩하고, 진입 hook 계열에 선택 인자로 흘린다. **이 PR 자체는 동작 변화가 0이다**
(아무도 field_state에 쓰지 않으므로 전부 빈 dict → no-op). 동적 해저드(F2)·날씨(F3)가 이 위에
얹힌다.

설계 근거(정찰·확정):
- ctx는 `build_ctx`(run_simulation 내부 클로저)가 매 행동마다 만들고 game_config는 이미
  `ctx["game_config"]`로 흐른다. field_state도 같은 자리에 넣으면 모든 액션 hook이 자동으로 받는다.
- field_state는 build_ctx **정의 전에** `field_state = {}`로 한 번 선언한다. 클로저가 캡처 →
  매 build_ctx 호출이 **같은 dict 참조**를 ctx에 넣어 전투 내내 공유된다. 전투마다 run_simulation이
  새로 도므로 워커 재사용 누수 없음(game_config 런타임 sub-dict가 못 쓰는 이유를 회피).
- 진입 hook `_fire_switch_in`/`_apply_entry_hazard`는 ctx 비의존 시그니처라 field_state를 못
  본다. **선택 인자 `field_state=None`을 추가**(기본값으로 기존 호출 전부 호환)하고, ctx가 있는
  호출부에서 `ctx.get("field_state")`를, turn_manager 콜백 lambda에서 클로저 캡처로 전달한다.
- **turn_manager는 무변경.** `on_switch_in` 콜백 시그니처는 `(p, participants, add_log)` 그대로
  두고, engine의 lambda가 field_state를 클로저로 캡처한다.

## 제약
- `modules/engine.py` 한 파일만 수정. **turn_manager.py·step2는 손대지 마라.**
- 아래 7개 FIND/REPLACE를 **byte 단위로 정확히** 적용. 각 FIND는 파일에 **정확히 한 번** 나타난다.
- F1은 동작 변화 0이다 — `_apply_entry_hazard` **본문은 바꾸지 마라**(시그니처에 인자만 추가,
  field_state는 F2에서 읽는다).
- 적용 후
  `python -c "import ast; ast.parse(open('modules/engine.py',encoding='utf-8').read())"`로 확인.

## 변경 1/7 — `_apply_entry_hazard` 시그니처에 선택 인자 추가 (본문 불변)

```python
# FIND
def _apply_entry_hazard(char, participants, game_config, add_log):
```

```python
# REPLACE
def _apply_entry_hazard(char, participants, game_config, add_log, field_state=None):
```

## 변경 2/7 — `_fire_switch_in` 시그니처 + 해저드 호출에 field_state 전달

```python
# FIND
def _fire_switch_in(char, participants, game_config, add_log):
    """교체 진입 즉시 처리 — 진입 효과(Trace 등) + 진입 이벤트(상태 만료) + 진입 로그를 한 번에
    발화한다. ctx 비의존(add_log 콜백만 받음)이라 자발적 교체(engine)·강제 교체(turn_manager
    콜백) 양쪽에서 같은 함수를 부른다. 호출부가 직후 just_switched_in을 소비해 다음-턴
    _act_on_switch 이중 발화를 막는다."""
    _apply_switch_in_effects(char, participants, game_config, add_log)
    _apply_entry_hazard(char, participants, game_config, add_log)
```

```python
# REPLACE
def _fire_switch_in(char, participants, game_config, add_log, field_state=None):
    """교체 진입 즉시 처리 — 진입 효과(Trace 등) + 진입 이벤트(상태 만료) + 진입 로그를 한 번에
    발화한다. ctx 비의존(add_log 콜백만 받음)이라 자발적 교체(engine)·강제 교체(turn_manager
    콜백) 양쪽에서 같은 함수를 부른다. 호출부가 직후 just_switched_in을 소비해 다음-턴
    _act_on_switch 이중 발화를 막는다. field_state는 전장 동적 상태(F1 substrate) — 그대로
    _apply_entry_hazard에 전달돼 F2 동적 해저드가 읽는다. F1에선 None/빈 dict라 동작 변화 0."""
    _apply_switch_in_effects(char, participants, game_config, add_log)
    _apply_entry_hazard(char, participants, game_config, add_log, field_state)
```

## 변경 3/7 — `_maybe_voluntary_switch` 호출부에 field_state 전달

```python
# FIND
    incoming['just_switched_in'] = False
    _fire_switch_in(incoming, participants, gc, ctx["add_log"])
    return True
```

```python
# REPLACE
    incoming['just_switched_in'] = False
    _fire_switch_in(incoming, participants, gc, ctx["add_log"], ctx.get("field_state"))
    return True
```

## 변경 4/7 — `_act_on_switch`(다음-턴 fallback) 호출부에 field_state 전달

```python
# FIND
    char["just_switched_in"] = False
    _fire_switch_in(char, ctx["participants"], ctx.get("game_config"), ctx["add_log"])
```

```python
# REPLACE
    char["just_switched_in"] = False
    _fire_switch_in(char, ctx["participants"], ctx.get("game_config"), ctx["add_log"], ctx.get("field_state"))
```

## 변경 5/7 — run_simulation에 `field_state = {}` 선언 (build_ctx 앞)

```python
# FIND
    # ── ctx 빌더 ──
    def build_ctx(active_char, turn, participants_list):
```

```python
# REPLACE
    # ── 전장 동적 상태(field_state) — 전투마다 새 dict. build_ctx가 클로저로 캡처해 매 ctx에
    #    같은 참조를 넣는다. game_config(정적)와 분리 → 병렬 워커 재사용 누수 없음(F1 substrate).
    #    F1에선 아무도 쓰지 않아 빈 채로 남아 동작 변화 0. F2(동적 해저드)부터 채운다.
    field_state = {}

    # ── ctx 빌더 ──
    def build_ctx(active_char, turn, participants_list):
```

## 변경 6/7 — ctx dict에 field_state 추가

```python
# FIND
            "game_config":   game_config,
            "raw_dmg":       0,
```

```python
# REPLACE
            "game_config":   game_config,
            "field_state":   field_state,
            "raw_dmg":       0,
```

## 변경 7/7 — `on_switch_in` 콜백 lambda가 field_state 캡처 (turn_manager 무변경)

```python
# FIND
        on_switch_in=lambda _char, _parts, _alog: _fire_switch_in(_char, _parts, game_config, _alog),
```

```python
# REPLACE
        on_switch_in=lambda _char, _parts, _alog: _fire_switch_in(_char, _parts, game_config, _alog, field_state),
```

## 검증 (적용 후 수행)
1. `git diff modules/engine.py`로 변경이 위 7지점뿐인지 확인. `_apply_entry_hazard` **본문**
   (mechs/spec/team/percent 로직)은 무변경이어야 한다. turn_manager.py 무변경.
2. 컴파일: `python -c "import ast; ast.parse(open('modules/engine.py',encoding='utf-8').read())"`.
3. 마커:
   - `def _apply_entry_hazard(char, participants, game_config, add_log, field_state=None):` 1회.
   - `def _fire_switch_in(char, participants, game_config, add_log, field_state=None):` 1회.
   - `field_state = {}` 1회, `"field_state":   field_state,` 1회.
   - `_fire_switch_in(...)` 호출 3곳 모두 끝에 field_state 인자 포함(`ctx.get("field_state")`
     2회 + lambda의 `field_state` 1회).
4. **회귀 0 단위검증**: field_state를 빈 dict로 둔 채 기존 해저드(H1 정적, game_config
   `mechanisms.hazard`) 전투가 직전과 byte-동일하게 동작(진입 데미지 percent·로그 불변).
   field_state 미전달(None) 경로도 동일.

## 회귀/한계 메모
- F1은 substrate만 깐다 — 동작 변화 0. field_state를 읽는 쪽은 F2(동적 해저드: `_apply_entry_hazard`가
  field_state.hazard를 정적과 max 합성)·F3(날씨)에서 추가.
- field_state는 단일 전투 범위(전투마다 새 dict). 메타 진행·연전 누적 없음(설계 의도).
- turn_manager 무변경 — lambda 클로저 캡처로 강제 교체 콜백도 field_state를 받는다.
