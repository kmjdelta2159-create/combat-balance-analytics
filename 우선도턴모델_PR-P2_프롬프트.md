# 우선도 턴 모델 PR-P2 — 교체-우선 행동 순서 정렬
Antigravity 작업 지시서. 아래 find/replace를 **정확한 문자열 치환**으로 적용한다. 각 FIND 블록은 프로젝트 파일에 byte-exact 1회 등장함을 빌더가 Grep으로 확인했고, REPLACE 로직은 하니스 단위검증(4케이스) + 클린룸 컴파일을 통과했다.
## 목적

현재 행동 순서는 순수 속도순이라 '교체는 공격보다 먼저 해결'을 표현 못 한다. 이 PR은 라운드 행동 순서를 *행동 우선도*로 안정 재정렬해, 이번 턴 교체할 유닛을 행동 순서 앞으로 보낸다. engine이 read-only 예측기 `_will_voluntary_switch`로 각 유닛의 교체 여부를 미리 보고(부작용 없음), 교체 예정 유닛에 `switch_priority` 티어(기본 6)를 부여하는 콜백을 turn_manager에 넘긴다. turn_manager는 그 콜백으로 행동자를 안정 정렬한다(동순위는 속도순 유지).

파이프라인 분리 없음 — 위험이 작다. 무브 우선도 예측은 우선도-인지 무브 정책이 생겨 관측 가능해질 때로 연기한다(현재 그리디 AI에서는 선택 무브 우선도가 거의 0이라 잠복).

**회귀 0 보장**: switch_policy 미설정 시 예측기가 모든 유닛에 0을 반환 → 안정 정렬이 순수 속도순을 그대로 보존한다(전원-동시·교체 미설정에서 동작 동일).
## 변경 범위

`modules/engine.py` 2곳(`_will_voluntary_switch` 함수 + manager 생성에 예측기 콜백), `modules/turn_manager.py` 3곳(생성자 파라미터·저장·run 재정렬). **다른 파일·다른 영역은 건들지 않는다.** 게임 이름·전용 분기 없음(도메인 중립).
## 적용 규칙

- FIND를 찾아 REPLACE로 **그대로** 교체한다. 들여쓰기·공백·한글 주석 한 글자도 바꾸지 않는다.
- 임의 리팩터·이름 변경·추가 최적화·하드코딩 금지. 지시된 치환만 한다.
- 적용 후 `python -c "import modules.engine, modules.turn_manager"`가 통과해야 한다.

---
# 파일: `modules/engine.py`
## ENG-1 _will_voluntary_switch 예측기 함수 추가 (_maybe_voluntary_switch 직전)

**FIND:**

```python
def _maybe_voluntary_switch(ctx):
```

**REPLACE:**

```python
def _will_voluntary_switch(char, participants, game_config):
    """read-only — _maybe_voluntary_switch가 이번 턴 교체를 할지 예측한다(부작용 없음).
    행동 우선도 정렬용. _maybe_voluntary_switch의 판정 조건과 일치해야 한다."""
    gc = game_config or {}
    pol = gc.get("switch_policy")
    if not pol:
        return False
    reserve_alive = any(
        p.get('team') == char.get('team') and not p.get('on_field') and get_current(p) > 0
        for p in participants
    )
    if not reserve_alive:
        return False
    ptype = pol.get("type") if isinstance(pol, dict) else str(pol)
    if ptype == "hp_threshold":
        thr = float(pol.get("threshold", 0.25)) if isinstance(pol, dict) else 0.25
        mx = get_max(char)
        return mx > 0 and (get_current(char) / mx) <= thr
    return False


def _maybe_voluntary_switch(ctx):
```

## ENG-2 manager 생성에 행동 우선도 예측기 콜백 전달

**FIND:**

```python
    manager = TurnManagerCls(
        action_registry=registry,
        turn_executor=turn_executor,
        speed_stat=speed_stat,
        broadcast_phase_event=_broadcast_phase_event,
        win_condition=win_condition,
        resource_module=resource_module,
        on_active_faint=(game_config or {}).get("on_active_faint"),
    )
```

**REPLACE:**

```python
    # 교체 우선 정렬용 행동 우선도 예측기 — 이번 턴 교체할 유닛을 행동 순서 앞으로.
    def _switch_action_priority(unit):
        if _will_voluntary_switch(unit, participants, game_config):
            return int((game_config or {}).get("switch_priority", 6))
        return 0

    manager = TurnManagerCls(
        action_registry=registry,
        turn_executor=turn_executor,
        speed_stat=speed_stat,
        broadcast_phase_event=_broadcast_phase_event,
        win_condition=win_condition,
        resource_module=resource_module,
        on_active_faint=(game_config or {}).get("on_active_faint"),
        action_priority=_switch_action_priority,
    )
```

---
# 파일: `modules/turn_manager.py`
## TM-1 생성자 action_priority 파라미터

**FIND:**

```python
                 resource_module=None, on_active_faint=None):
```

**REPLACE:**

```python
                 resource_module=None, on_active_faint=None, action_priority=None):
```

## TM-2 생성자 본문 _action_priority 저장

**FIND:**

```python
        self.resource_module = resource_module or ResourceModule()
        self._on_active_faint = on_active_faint
```

**REPLACE:**

```python
        self.resource_module = resource_module or ResourceModule()
        self._on_active_faint = on_active_faint
        self._action_priority = action_priority
```

## TM-3 run 라운드 행동자 우선도 안정 재정렬

**FIND:**

```python
            # 라운드 시작 시점의 on_field 유닛만 이번 라운드 행동자로 고정.
            # (교체로 라운드 중간에 진입한 유닛은 다음 라운드부터 행동)
            acting_units = [p for p in participants if p.get('on_field', True)]
            for active_char in acting_units:
```

**REPLACE:**

```python
            # 라운드 시작 시점의 on_field 유닛만 이번 라운드 행동자로 고정.
            # (교체로 라운드 중간에 진입한 유닛은 다음 라운드부터 행동)
            acting_units = [p for p in participants if p.get('on_field', True)]
            # 행동 우선도(예: 교체 티어)로 안정 재정렬 — 동순위는 속도순 유지.
            # action_priority 미설정 시 재정렬 없음 → 순수 속도순(회귀 0).
            if self._action_priority is not None:
                acting_units.sort(key=lambda x: -self._action_priority(x))
            for active_char in acting_units:
```

---
## 적용 후 검증 (Antigravity가 보고할 것)

1. `modules/engine.py`와 `modules/turn_manager.py`가 각각 py_compile 통과.
2. `grep -n "def _will_voluntary_switch" modules/engine.py` → 1건.
3. `grep -n "action_priority=_switch_action_priority" modules/engine.py` → 1건.
4. `grep -n "_action_priority" modules/turn_manager.py` → 2건(저장·재정렬 사용).
5. `grep -n "acting_units.sort" modules/turn_manager.py` → 1건.
