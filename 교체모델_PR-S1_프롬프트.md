# 교체 모델 PR-S1 — 액티브/예비(reserve) 회전 골격
Antigravity 작업 지시서. 아래 find/replace를 **정확한 문자열 치환**으로 적용한다. 각 FIND 블록은 프로젝트 파일에 byte-exact 1회 등장함을 빌더가 Grep으로 확인했고, REPLACE 로직은 하니스 단위검증(4케이스) + 클린룸 컴파일을 통과했다.
## 목적

전투 모델에 '액티브/예비 회전'이라는 게임 중립 프리미티브를 신설한다. 현재는 양 팀의 모든 유닛이 동시에 필드에 올라 전원이 매 라운드 행동한다. 이 PR은 (1) `game_config['active_count']`로 팀별 액티브 수를 정하고 나머지를 예비(reserve)로 두며, (2) 턴 루프가 on_field 유닛만 행동하게 게이팅하고, (3) 액티브 사망 시 처리를 `game_config['on_active_faint']` 규칙으로 둔다.

**회귀 0 보장**: active_count 미설정 시 전원 on_field → 현행 전원-동시 동작과 동일. on_active_faint 미설정 시 강제 교체 무동작. S1은 `on_active_faint="replace_from_reserve"`만 구현한다("none"은 무동작이 정상 의미, "team_loss"는 후속 PR). 자발적 교체·타겟팅 제한·ON_SWITCH hook은 후속 PR-S2~S4.
## 변경 범위

`modules/turn_manager.py` 4곳, `modules/engine.py` 2곳. **다른 파일·다른 영역은 건들지 않는다.** 코드에 게임 이름이나 특정 게임 전용 분기를 두지 않는다(도메인 중립 원칙).
## 적용 규칙

- 아래 FIND를 찾아 REPLACE로 **그대로** 교체한다. 들여쓰기·공백·한글 주석 한 글자도 바꾸지 않는다.
- 임의 리팩터·이름 변경·추가 최적화·하드코딩 금지. 지시된 치환만 한다.
- 적용 후 `python -c "import modules.engine, modules.turn_manager"`가 에러 없이 통과해야 한다.

---
# 파일: `modules/turn_manager.py`
## TM-1 생성자 on_active_faint 파라미터

**FIND:**

```python
                 win_condition: WinCondition = None,
                 resource_module=None):
```

**REPLACE:**

```python
                 win_condition: WinCondition = None,
                 resource_module=None, on_active_faint=None):
```

## TM-2 생성자 본문 _on_active_faint 저장

**FIND:**

```python
        self.win_condition = win_condition or HPDepletion()
        self.resource_module = resource_module or ResourceModule()
```

**REPLACE:**

```python
        self.win_condition = win_condition or HPDepletion()
        self.resource_module = resource_module or ResourceModule()
        self._on_active_faint = on_active_faint
```

## TM-3 run 루프 on_field 게이팅 + 강제 교체 호출

**FIND:**

```python
            for active_char in participants:
                if not self.resource_module.is_alive(active_char):
                    continue

                self.resource_module.on_turn_start(active_char)
                ctx = build_ctx(active_char, turn, participants)

                # ── 턴 실행 (TurnExecutor 위임) ──
                self.turn_executor.execute(ctx, self.registry)
                if ctx["battle_over"]:
                    return "None", sim_metrics

                # ── 전투 종료 판정 (WinCondition 위임) ──
                is_over, winner = self.win_condition.check(participants, turn)
```

**REPLACE:**

```python
            for active_char in participants:
                # 액티브(on_field) 유닛만 행동. on_field 미설정 시 True(현행 전원-동시).
                if not active_char.get('on_field', True):
                    continue
                if not self.resource_module.is_alive(active_char):
                    continue

                self.resource_module.on_turn_start(active_char)
                ctx = build_ctx(active_char, turn, participants)

                # ── 턴 실행 (TurnExecutor 위임) ──
                self.turn_executor.execute(ctx, self.registry)
                if ctx["battle_over"]:
                    return "None", sim_metrics

                # ── 액티브 사망 시 처리 (on_active_faint 규칙) ──
                self._resolve_faint(participants, add_log)

                # ── 전투 종료 판정 (WinCondition 위임) ──
                is_over, winner = self.win_condition.check(participants, turn)
```

## TM-4 _resolve_faint 메서드 추가

**FIND:**

```python
        add_log(f"⏱️ 설정한 최대 턴 수({max_turns}) 내에 승부가 나지 않았습니다. 캐릭터 밸류나 데미지 공식을 점검하십시오.")
        return "None", sim_metrics
```

**REPLACE:**

```python
        add_log(f"⏱️ 설정한 최대 턴 수({max_turns}) 내에 승부가 나지 않았습니다. 캐릭터 밸류나 데미지 공식을 점검하십시오.")
        return "None", sim_metrics

    def _resolve_faint(self, participants, add_log):
        """on_active_faint 규칙 처리. 'replace_from_reserve'면 죽은 액티브 자리를
        예비(reserve) 유닛으로 roster_idx 순으로 채운다. 그 외 규칙은 무동작
        (승패는 win_condition이 판정). 게임 중립 — 특정 게임 분기 없음."""
        if self._on_active_faint != "replace_from_reserve":
            return
        for team in ("Ally", "Enemy"):
            members = [p for p in participants if p.get('team') == team]
            on_field = [p for p in members if p.get('on_field')]
            dead_on_field = [p for p in on_field
                             if not self.resource_module.is_alive(p)]
            if not dead_on_field:
                continue
            for p in dead_on_field:
                p['on_field'] = False
            reserve = sorted(
                (p for p in members
                 if not p.get('on_field') and self.resource_module.is_alive(p)),
                key=lambda x: x.get('roster_idx', 0)
            )
            for p in reserve[:len(dead_on_field)]:
                p['on_field'] = True
                add_log(f"🔁 {team} 예비 {p.get('id', '?')} "
                        f"({p.get('name', '?')}) 등장!")
```

---
# 파일: `modules/engine.py`
## ENG-1 참가자 초기화에 on_field/roster 지정 블록 삽입

**FIND:**

```python
            p.setdefault("active_states", [])
            participants.append(p)

    if not any(p['team'] == 'Ally' for p in participants) or \
       not any(p['team'] == 'Enemy' for p in participants):
```

**REPLACE:**

```python
            p.setdefault("active_states", [])
            participants.append(p)

    # ── 1b. 액티브/예비(reserve) 회전 — active_count 기반 on_field 지정 ──
    # 게임 중립 프리미티브. active_count 미설정/비정상 시 팀 크기로 → 전원 on_field
    # (현행 전원-동시 동작, 회귀 0). 특정 게임 분기 없음.
    _gc_field = game_config or {}
    try:
        _ac_cfg = int(_gc_field.get("active_count"))
    except (TypeError, ValueError):
        _ac_cfg = None
    for _team_name in ("Ally", "Enemy"):
        _team_members = [p for p in participants if p['team'] == _team_name]
        _ac = _ac_cfg if (_ac_cfg and _ac_cfg > 0) else len(_team_members)
        for _ri, _p in enumerate(_team_members):
            _p['roster_idx'] = _ri
            _p['on_field'] = _ri < _ac

    if not any(p['team'] == 'Ally' for p in participants) or \
       not any(p['team'] == 'Enemy' for p in participants):
```

## ENG-2 manager 생성에 on_active_faint 전달

**FIND:**

```python
    manager = TurnManagerCls(
        action_registry=registry,
        turn_executor=turn_executor,
        speed_stat=speed_stat,
        broadcast_phase_event=_broadcast_phase_event,
        win_condition=win_condition,
        resource_module=resource_module,
    )
```

**REPLACE:**

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

---
## 적용 후 검증 (Antigravity가 보고할 것)

1. `modules/turn_manager.py`와 `modules/engine.py`가 각각 py_compile 통과.
2. `grep -n "def _resolve_faint" modules/turn_manager.py` → 1건.
3. `grep -n "on_active_faint" modules/turn_manager.py` → 3건(파라미터·저장·_resolve_faint 비교).
4. `grep -n "on_active_faint" modules/engine.py` → 1건(manager 전달).
5. `grep -n "on_field" modules/turn_manager.py` → 2건 이상(게이팅·_resolve_faint).
6. `grep -n "_p\['on_field'\]" modules/engine.py` → 1건(1b 블록).
