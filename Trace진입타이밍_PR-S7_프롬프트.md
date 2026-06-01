# PR-S7 (진입 즉시 타이밍) Antigravity 프롬프트

## ⚠️ 적용 순서
**PR-S6 적용 후**에 적용한다(S7은 S6이 만든 `_apply_switch_in_effects`를 호출). engine 3건 +
turn_manager 3건, 총 6건의 find/replace.

## 목적
교체 진입 효과(Trace 등)를 진입 유닛의 "다음 턴"이 아니라 **교체가 일어나는 그 시점에 즉시**
발화시킨다. 진입 처리를 한 함수 `_fire_switch_in`(진입 효과 + 진입 이벤트 + 로그)으로 모으고,
두 교체 수행 지점에서 즉시 호출한다 — 자발적 교체(`_maybe_voluntary_switch`, engine 직접 호출)와
강제 교체(`SequentialTurnManager._resolve_faint`, engine이 넘긴 `on_switch_in` 콜백). 기존
다음-턴 hook `_act_on_switch`는 즉시 처리를 놓친 진입에 대한 안전망(fallback)으로 남는다.
즉시 처리 시 `just_switched_in`을 소비해 이중 발화를 막는다.

## 제약
- `modules/engine.py`(3건)와 `modules/turn_manager.py`(3건)만 수정. step2 손대지 말 것.
- 아래 find/replace **6건만** 적용. 곁가지 수정 금지.
- turn_manager는 engine을 import하지 않는다 — engine이 콜백(`on_switch_in`)으로만 넘긴다.

---

## [engine.py] 적용 1 — `_fire_switch_in` 추가 + `_act_on_switch`를 fallback으로 리팩터

찾기:

```python
def _act_on_switch(ctx):
    """교체 진입 hook (ON_SWITCH) — 이번 턴 행동 캐릭터가 직전에 필드로 진입(교체·강제 교체)
    했다면 진입 효과(_apply_switch_in_effects: Trace 등)를 처리하고 진입 이벤트를 브로드캐스트
    한다. just_switched_in 미설정 시 즉시 no-op이라 회귀 0. (S7에서 진입 즉시 타이밍으로
    당기면 이 hook은 이미 소비된 플래그로 인해 자동 no-op이 된다.)"""
    char = ctx["active_char"]
    if not char.get("just_switched_in"):
        return
    char["just_switched_in"] = False
    _apply_switch_in_effects(char, ctx["participants"],
                             ctx.get("game_config"), ctx["add_log"])
    _notify_event("ON_SWITCH", char, ctx, role="actor")
    ctx["add_log"](
        f"  -> [Phase: ON_SWITCH] {char.get('id','?')} ({char.get('name','?')}) 진입"
    )
```

교체:

```python
def _fire_switch_in(char, participants, game_config, add_log):
    """교체 진입 즉시 처리 — 진입 효과(Trace 등) + 진입 이벤트(상태 만료) + 진입 로그를 한 번에
    발화한다. ctx 비의존(add_log 콜백만 받음)이라 자발적 교체(engine)·강제 교체(turn_manager
    콜백) 양쪽에서 같은 함수를 부른다. 호출부가 직후 just_switched_in을 소비해 다음-턴
    _act_on_switch 이중 발화를 막는다."""
    _apply_switch_in_effects(char, participants, game_config, add_log)
    _notify_event("ON_SWITCH", char, {"add_log": add_log}, role="actor")
    add_log(f"  -> [Phase: ON_SWITCH] {char.get('id','?')} ({char.get('name','?')}) 진입")


def _act_on_switch(ctx):
    """교체 진입 hook (ON_SWITCH) — 다음-턴 안전망(fallback). S7 이후 진입은 보통 교체 시점에
    _fire_switch_in으로 즉시 처리되고 just_switched_in이 그때 소비되므로, 이 hook은 즉시 처리를
    놓친 진입에 대한 fallback이다. 미설정 시 no-op이라 회귀 0."""
    char = ctx["active_char"]
    if not char.get("just_switched_in"):
        return
    char["just_switched_in"] = False
    _fire_switch_in(char, ctx["participants"], ctx.get("game_config"), ctx["add_log"])
```

## [engine.py] 적용 2 — `_maybe_voluntary_switch` 진입 즉시 발화

찾기:

```python
    incoming['on_field'] = True
    incoming['just_switched_in'] = True
    ctx["add_log"](
        f"[Turn {ctx['turn']}] {char.get('id','?')} 교체 → "
        f"{incoming.get('id','?')} ({incoming.get('name','?')}) 진입"
    )
```

교체:

```python
    incoming['on_field'] = True
    ctx["add_log"](
        f"[Turn {ctx['turn']}] {char.get('id','?')} 교체 → "
        f"{incoming.get('id','?')} ({incoming.get('name','?')}) 진입"
    )
    # 진입 즉시 처리 (S7) — 다음 턴이 아니라 교체 시점에 진입 효과·이벤트 발화 + 이중 발화 방지.
    incoming['just_switched_in'] = False
    _fire_switch_in(incoming, participants, gc, ctx["add_log"])
```

## [engine.py] 적용 3 — manager 생성부에 `on_switch_in` 콜백 전달

찾기:

```python
        on_active_faint=(game_config or {}).get("on_active_faint"),
        action_priority=_predict_action_priority,
```

교체:

```python
        on_active_faint=(game_config or {}).get("on_active_faint"),
        action_priority=_predict_action_priority,
        on_switch_in=lambda _char, _parts, _alog: _fire_switch_in(_char, _parts, game_config, _alog),
```

---

## [turn_manager.py] 적용 4 — `__init__` 시그니처에 `on_switch_in` 추가

찾기:

```python
                 resource_module=None, on_active_faint=None, action_priority=None):
```

교체:

```python
                 resource_module=None, on_active_faint=None, action_priority=None,
                 on_switch_in=None):
```

## [turn_manager.py] 적용 5 — `on_switch_in` 저장

찾기:

```python
        self._action_priority = action_priority
```

교체:

```python
        self._action_priority = action_priority
        self._on_switch_in = on_switch_in
```

## [turn_manager.py] 적용 6 — `_resolve_faint`에서 진입 즉시 콜백 호출

찾기:

```python
            for p in reserve[:len(dead_on_field)]:
                p['on_field'] = True
                p['just_switched_in'] = True
                add_log(f"🔁 {team} 예비 {p.get('id', '?')} "
                        f"({p.get('name', '?')}) 등장!")
```

교체:

```python
            for p in reserve[:len(dead_on_field)]:
                p['on_field'] = True
                add_log(f"🔁 {team} 예비 {p.get('id', '?')} "
                        f"({p.get('name', '?')}) 등장!")
                # 진입 즉시 처리 (S7) — engine 콜백으로 진입 효과·이벤트 발화. 콜백 미전달 시
                # 다음-턴 _act_on_switch fallback을 위해 just_switched_in을 세팅(회귀 0).
                if self._on_switch_in is not None:
                    p['just_switched_in'] = False
                    self._on_switch_in(p, participants, add_log)
                else:
                    p['just_switched_in'] = True
```

---

## 적용 후 자가 점검 (보고만, 코드 변경 금지)
1. engine: `def _fire_switch_in(` 1회, `_act_on_switch`가 `_fire_switch_in(`을 호출.
2. engine: `_maybe_voluntary_switch`에 `_fire_switch_in(incoming, participants, gc, ...)` 존재,
   기존 `incoming['just_switched_in'] = True` 제거됨.
3. engine: manager 생성부에 `on_switch_in=lambda ...` 존재.
4. turn_manager: `__init__`에 `on_switch_in=None` 파라미터 + `self._on_switch_in = on_switch_in`.
5. turn_manager: `_resolve_faint`에 `self._on_switch_in(p, participants, add_log)` 호출 +
   콜백 미전달 시 `else: p['just_switched_in'] = True`.
6. engine.py·turn_manager.py 둘 다 구문 오류 없이 compile. step2 변경 없음.

## 회귀 0 / 정확성 근거
- `mechanisms['trace']` 미설정 → `_fire_switch_in` 안의 효과가 no-op(진입 로그만). 전투 동일.
- turn_manager `on_switch_in` 미전달(단독 사용 시) → 기존처럼 `just_switched_in=True` →
  다음-턴 `_act_on_switch` fallback. 동작 보존.
- 즉시 발화 후 `just_switched_in` 소비 → 다음-턴 hook no-op → 이중 발화 없음.
- 보조자 하니스(verify_trace_s7.py) 7케이스 통과 — 자발/강제 즉시 발화, 이중 발화 없음,
  콜백 미전달 회귀 0(다음-턴 fallback), trace 미설정 no-op.

## 라이브 확인 (S7 적용 후 한 번)
Trace 부착 캐릭터가 교체로 진입하는 전투에서 — 진입 **즉시**(다음 턴이 아니라) "타입이 …(으)로
복사됨 (Trace ←…)" 로그가 뜨면 진입 즉시 타이밍 + Trace가 end-to-end로 실증된다. (Trace 부착
입력 UI는 후속 PR-S8. 그 전엔 game_config에 `mechanisms.trace`를 직접 넣어 테스트 가능.)
