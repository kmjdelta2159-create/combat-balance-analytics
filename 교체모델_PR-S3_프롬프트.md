# 교체 모델 PR-S3 — ON_SWITCH 진입 hook 인프라
Antigravity 작업 지시서. 아래 find/replace를 **정확한 문자열 치환**으로 적용한다. 각 FIND 블록은 프로젝트 파일에 byte-exact 1회 등장함을 빌더가 Grep으로 확인했고, REPLACE 로직은 하니스 단위검증(4케이스) + 클린룸 컴파일을 통과했다.
## 목적

PR-S1의 강제 교체로 예비 유닛이 필드로 진입할 수 있게 됐다. 이 PR은 유닛이 교체로 진입한 직후 한 번 발화하는 ON_SWITCH hook을 신설한다. 진입한 유닛에 `just_switched_in` 플래그를 달고, 그 유닛이 다음 턴에 행동할 때 흐름 맨 앞에서 `_act_on_switch`가 플래그를 소비하며 진입 이벤트를 브로드캐스트한다. 진입 효과 메커니즘(예: Trace=상대 특성 복사, 입장 해저드)은 후속 PR에서 이 hook 위에 얹는다.

**현재는 무동작 슬롯**: ON_SWITCH 트리거를 소비하는 메커니즘이 아직 없어 플래그 소비 + 진입 로그 + active_states 만료 처리만 한다. **회귀 0 보장**: just_switched_in은 PR-S1의 강제 교체(`_resolve_faint`)에서만 설정된다. 전원-동시 기본 경로에서는 어떤 유닛도 이 플래그를 갖지 않아 `_act_on_switch`가 항상 즉시 no-op이다.
## 변경 범위

`modules/engine.py` 3곳(함수 정의·레지스트리 등록·흐름 자동삽입), `modules/turn_manager.py` 1곳(`_resolve_faint` 진입 플래그). **다른 파일·다른 영역은 건들지 않는다.** 게임 이름·전용 분기 없음(도메인 중립).
## 적용 규칙

- FIND를 찾아 REPLACE로 **그대로** 교체한다. 들여쓰기·공백·한글 주석 한 글자도 바꾸지 않는다.
- 임의 리팩터·이름 변경·추가 최적화·하드코딩 금지. 지시된 치환만 한다.
- 적용 후 `python -c "import modules.engine, modules.turn_manager"`가 에러 없이 통과해야 한다.

---
# 파일: `modules/engine.py`
## ENG-1 _act_on_switch 함수 삽입 (등록부 직전)

**FIND:**

```python
# ── 디폴트 액션을 글로벌 레지스트리에 등록 ──
```

**REPLACE:**

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


# ── 디폴트 액션을 글로벌 레지스트리에 등록 ──
```

## ENG-2 ON_SWITCH 레지스트리 등록

**FIND:**

```python
DEFAULT_ACTION_REGISTRY.register("ON_MOVE_EFFECT", _act_move_effect)
```

**REPLACE:**

```python
DEFAULT_ACTION_REGISTRY.register("ON_MOVE_EFFECT", _act_move_effect)
DEFAULT_ACTION_REGISTRY.register("ON_SWITCH",      _act_on_switch)
```

## ENG-3 ON_SWITCH 흐름 자동삽입 (맨 앞)

**FIND:**

```python
    # ON_STATUS_TICK 자동 삽입 — ON_TURN_END 직후, 턴 종료 상태이상 데미지 hook
    if "ON_STATUS_TICK" not in [k for k, _ in all_actions]:
        all_actions.append(("ON_STATUS_TICK", "Status Tick (상태이상 처리)"))

    # 피벗 기준으로 캐릭터 단위 / 타겟 단위 분리
```

**REPLACE:**

```python
    # ON_STATUS_TICK 자동 삽입 — ON_TURN_END 직후, 턴 종료 상태이상 데미지 hook
    if "ON_STATUS_TICK" not in [k for k, _ in all_actions]:
        all_actions.append(("ON_STATUS_TICK", "Status Tick (상태이상 처리)"))

    # ON_SWITCH 자동 삽입 — 흐름 맨 앞, 교체로 진입한 유닛의 진입 효과 hook
    if "ON_SWITCH" not in [k for k, _ in all_actions]:
        all_actions.insert(0, ("ON_SWITCH", "On Switch In (교체 진입 효과)"))

    # 피벗 기준으로 캐릭터 단위 / 타겟 단위 분리
```

---
# 파일: `modules/turn_manager.py`
## TM-1 _resolve_faint 진입 유닛에 just_switched_in 플래그

**FIND:**

```python
            for p in reserve[:len(dead_on_field)]:
                p['on_field'] = True
                add_log(f"🔁 {team} 예비 {p.get('id', '?')} "
                        f"({p.get('name', '?')}) 등장!")
```

**REPLACE:**

```python
            for p in reserve[:len(dead_on_field)]:
                p['on_field'] = True
                p['just_switched_in'] = True
                add_log(f"🔁 {team} 예비 {p.get('id', '?')} "
                        f"({p.get('name', '?')}) 등장!")
```

---
## 적용 후 검증 (Antigravity가 보고할 것)

1. `modules/engine.py`와 `modules/turn_manager.py`가 각각 py_compile 통과.
2. `grep -n "def _act_on_switch" modules/engine.py` → 1건.
3. `grep -n 'register("ON_SWITCH"' modules/engine.py` → 1건.
4. `grep -n "ON_SWITCH 자동 삽입" modules/engine.py` → 1건.
5. `grep -n "just_switched_in" modules/engine.py` → 2건(설정 해제·검사), `modules/turn_manager.py` → 1건(진입 설정).
