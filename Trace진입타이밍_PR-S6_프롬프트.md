# PR-S6 (Trace 진입 효과 메커니즘) Antigravity 프롬프트

## 목적
`modules/engine.py`에 첫 실제 진입형 동적 메커니즘 Trace를 얹는다 — 부착 캐릭터가 교체로
필드에 진입하면 상대 on_field 유닛의 타입을 복사해 자신의 current_type에 넣는다(기존
`_move_stab_multiplier`가 읽어 STAB로 되먹임). 진입 효과 핸들러 `_apply_switch_in_effects`를
추가하고 기존 `_act_on_switch`(다음-턴 hook)가 그것을 호출하게 한다. 타이밍은 현행 "다음 턴"
유지 — 진입 즉시 타이밍 교정은 PR-S7에서 별도로 한다.

## 제약
- `modules/engine.py` 한 파일만 수정. turn_manager·step2 손대지 말 것.
- 아래 find/replace 1건만 적용(핸들러 추가 + `_act_on_switch` 배선이 한 블록). 곁가지 수정 금지.
- 핸들러는 ctx 비의존 시그니처(`char, participants, game_config, add_log`)를 유지할 것 —
  PR-S7에서 turn_manager 콜백이 같은 함수를 재사용한다.

## 적용 — `_act_on_switch` 앞에 `_apply_switch_in_effects` 추가 + `_act_on_switch` 배선

다음 블록을 **정확히** 찾아서:

```python
def _act_on_switch(ctx):
    """교체 진입 hook (ON_SWITCH) — 이번 턴 행동 캐릭터가 직전에 필드로 진입(교체·강제 교체)
    했다면 진입 효과를 처리한다. 진입 효과 메커니즘(예: Trace)은 후속 PR에서 이 hook 위에
    얹는다. 현재는 진입 이벤트를 브로드캐스트하고 플래그를 소비하는 무동작 슬롯. 게임 중립.
    just_switched_in 미설정 시 즉시 no-op이라 회귀 0."""
    char = ctx["active_char"]
    if not char.get("just_switched_in"):
        return
    char["just_switched_in"] = False
    _notify_event("ON_SWITCH", char, ctx, role="actor")
    ctx["add_log"](
        f"  -> [Phase: ON_SWITCH] {char.get('id','?')} ({char.get('name','?')}) 진입"
    )
```

다음으로 **교체**:

```python
def _apply_switch_in_effects(char, participants, game_config, add_log):
    """교체 진입 효과 — game_config['mechanisms']['trace'] 기반. 부착 캐릭터(gimmick_col 값이
    match_value와 일치)가 필드에 진입하면 상대 팀 on_field 유닛의 타입을 복사해 자신의
    current_type에 넣는다(_move_stab_multiplier가 읽어 STAB로 되먹임). 미설정/미부착/상대
    없음/타입 없음 시 no-op이라 회귀 0. 게임 중립·config 구동. 부작용은 char['current_type']
    설정 + 로그뿐 — ctx 비의존이라 자발적 교체(engine)·강제 교체(turn_manager 콜백) 양쪽에서
    같은 함수를 호출할 수 있다(S7에서 진입 즉시 타이밍에 재사용)."""
    mechs = (game_config or {}).get("mechanisms") or {}
    spec = mechs.get("trace")
    if not spec:
        return
    col = spec.get("gimmick_col")
    want = str(spec.get("match_value", "")).strip().lower()
    have = str(char.get("gimmicks", {}).get(col, "")).strip().lower() if col else ""
    if not col or have != want:
        return
    opp = next((p for p in participants
                if p.get('team') != char.get('team') and p.get('on_field', True)
                and get_current(p) > 0), None)
    if opp is None:
        return
    type_col = spec.get("type_col")
    src_type = opp.get("current_type") or (
        opp.get("gimmicks", {}).get(type_col) if type_col else None)
    if not src_type:
        return
    if char.get("current_type") != src_type:
        char["current_type"] = src_type
        add_log(f"  -> [Phase: ON_SWITCH] {char.get('id','?')} 타입이 "
                f"{src_type}(으)로 복사됨 (Trace ← {opp.get('id','?')})")


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

## 적용 후 자가 점검 (보고만, 코드 변경 금지)
1. `def _apply_switch_in_effects(` 1회, `def _act_on_switch(` 1회 존재.
2. `_act_on_switch`가 `_apply_switch_in_effects(char, ctx["participants"], ...)`를 호출.
3. `modules/engine.py` 구문 오류 없이 import/compile 됨.
4. turn_manager.py·step2 변경 없음.

## 회귀 0 / 정확성 근거
- `mechanisms['trace']` 미설정 → 핸들러 즉시 return → current_type 불변 → STAB·전투 동일.
- 미부착(gimmick 불일치)·상대 on_field 없음·상대 타입 없음 → 모두 no-op.
- 보조자 하니스(verify_trace_s6.py) 8케이스 통과 — 미설정 불변, type_col/current_type 복사,
  미부착 불변, 상대없음 no-op, 동일타입 무변경, 죽은 상대 건너뜀.

## 한계 (설계안 §6)
- Trace를 "타입 복사"로 모델링(엔진에 특성 substrate 없음). 멀티 액티브에서 "어느 상대 복사"는
  미해결(싱글만 결정적). 타이밍은 이 PR에서 "다음 턴" — 라이브 확인은 PR-S7(진입 즉시) 후 권장.
