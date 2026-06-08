# PR-B3c — 기절-교체 incoming 트레이스 교정 (FIND/REPLACE, 앱사이드)

## 목적
기절한 유닛 자리에 *어느 예비가 들어오는지*를 로그 지정대로 맞춘다. 엔진 기본은
`roster_idx[0]` 순이지만 로그는 특정 예비를 지정 — 어긋나면 첫 기절(이 로그 T10)부터
divergence가 연쇄한다. `turn_manager._resolve_faint`에 트레이스 분기를 넣어 닫는다.
B3a가 공급한 `trace_faint_incoming`(outgoing→incoming) 소비. 미설정 시 현행 roster 순(회귀0).

## 검증 제약
engine.py truncation으로 전체 실행은 앱사이드. **단 turn_manager.py는 9KB라 샌드박스 정상**
— `_resolve_faint` 분기 로직은 standalone 검증됨(아래). 앵커는 Read로 고정한 현재 텍스트.

## 대상
`modules/turn_manager.py`(2건) + `modules/battle_setup.py`(1건) + `modules/engine.py`(1건).

## 설계 근거 (standalone 검증됨)
- `_resolve_faint`는 team별로 죽은 on_field를 예비로 교체. 트레이스 분기: 죽은 유닛 id를
  `trace_faint_incoming`의 `outgoing`과 매칭해 그 `incoming`을 진입(소비 추적). 지정 없음·
  지정 예비 사망 시 기존 roster_idx 폴백.
- B3a `prepare_run`이 `on_active_faint`를 안 깔면 `_resolve_faint`가 즉시 return(기절 미처리)
  → prepare_run에 `on_active_faint="replace_from_reserve"` 한 줄 보강.
- 검증 시나리오 3종 통과: (1) 지정 incoming(Latios) 정확 선택, (2) tfi 없으면 roster 폴백
  (Stoutland), (3) 지정 incoming 사망 시 폴백.

## FIND/REPLACE 1 — `battle_setup.prepare_run`에 on_active_faint 보강

**FIND**:
```python
    gc["trace_faint_incoming"] = ta["faint_incoming"]
    gc["switch_policy"] = {"type": "trace"}   # 트레이스 구동 — hp_threshold 정책 대체
    return parts, spec, ta
```

**REPLACE**:
```python
    gc["trace_faint_incoming"] = ta["faint_incoming"]
    gc["switch_policy"] = {"type": "trace"}   # 트레이스 구동 — hp_threshold 정책 대체
    gc["on_active_faint"] = "replace_from_reserve"  # 기절 시 예비 진입(로그 지정 incoming)
    return parts, spec, ta
```

## FIND/REPLACE 2 — `SequentialTurnManager.__init__` 시그니처에 param 추가

**FIND**:
```python
    def __init__(self, action_registry, turn_executor,
                 speed_stat=None, broadcast_phase_event=None,
                 win_condition: WinCondition = None,
                 resource_module=None, on_active_faint=None, action_priority=None,
                 on_switch_in=None):
```

**REPLACE**:
```python
    def __init__(self, action_registry, turn_executor,
                 speed_stat=None, broadcast_phase_event=None,
                 win_condition: WinCondition = None,
                 resource_module=None, on_active_faint=None, action_priority=None,
                 on_switch_in=None, trace_faint_incoming=None):
```

## FIND/REPLACE 3 — `__init__` 본문에 self 저장 추가

**FIND**:
```python
        self._on_active_faint = on_active_faint
        self._action_priority = action_priority
        self._on_switch_in = on_switch_in
```

**REPLACE**:
```python
        self._on_active_faint = on_active_faint
        self._action_priority = action_priority
        self._on_switch_in = on_switch_in
        self._trace_faint_incoming = trace_faint_incoming
        self._trace_faint_used = set()
```

## FIND/REPLACE 4 — `_resolve_faint` 트레이스 구동 incoming

**FIND** (per-team 교체 블록 — `for p in dead_on_field:`부터 함수 끝까지):
```python
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
                # 진입 즉시 처리 (S7) — engine 콜백으로 진입 효과·이벤트 발화. 콜백 미전달 시
                # 다음-턴 _act_on_switch fallback을 위해 just_switched_in을 세팅(회귀 0).
                if self._on_switch_in is not None:
                    p['just_switched_in'] = False
                    self._on_switch_in(p, participants, add_log)
                else:
                    p['just_switched_in'] = True
```

**REPLACE**:
```python
            for p in dead_on_field:
                p['on_field'] = False
            reserve = sorted(
                (p for p in members
                 if not p.get('on_field') and self.resource_module.is_alive(p)),
                key=lambda x: x.get('roster_idx', 0)
            )
            # incoming 결정: 죽은 유닛별로 트레이스 지정(outgoing→incoming) 우선, 없으면
            # roster_idx 순 폴백(현행). trace_faint_incoming 미설정 시 전부 폴백 = 회귀 0.
            _tfi = self._trace_faint_incoming
            ri = 0
            for dead in dead_on_field:
                inc = None
                if _tfi is not None:
                    ent = next((e for e in _tfi
                                if e.get('outgoing') == dead.get('id')
                                and e.get('outgoing') not in self._trace_faint_used), None)
                    if ent is not None:
                        cand = next((q for q in members
                                     if q.get('id') == ent.get('incoming')
                                     and not q.get('on_field')
                                     and self.resource_module.is_alive(q)), None)
                        if cand is not None:
                            self._trace_faint_used.add(ent['outgoing'])
                            inc = cand
                if inc is None:
                    while ri < len(reserve) and reserve[ri].get('on_field'):
                        ri += 1
                    if ri < len(reserve):
                        inc = reserve[ri]
                        ri += 1
                if inc is None:
                    continue
                inc['on_field'] = True
                add_log(f"🔁 {team} 예비 {inc.get('id', '?')} "
                        f"({inc.get('name', '?')}) 등장!")
                # 진입 즉시 처리 (S7) — engine 콜백으로 진입 효과·이벤트 발화. 콜백 미전달 시
                # 다음-턴 _act_on_switch fallback을 위해 just_switched_in을 세팅(회귀 0).
                if self._on_switch_in is not None:
                    inc['just_switched_in'] = False
                    self._on_switch_in(inc, participants, add_log)
                else:
                    inc['just_switched_in'] = True
```

## FIND/REPLACE 5 — `engine.py` 매니저 생성에 param 전달

**FIND**:
```python
        on_active_faint=(game_config or {}).get("on_active_faint"),
        action_priority=_predict_action_priority,
        on_switch_in=lambda _char, _parts, _alog: _fire_switch_in(_char, _parts, game_config, _alog, field_state),
    )
```

**REPLACE**:
```python
        on_active_faint=(game_config or {}).get("on_active_faint"),
        action_priority=_predict_action_priority,
        on_switch_in=lambda _char, _parts, _alog: _fire_switch_in(_char, _parts, game_config, _alog, field_state),
        trace_faint_incoming=(game_config or {}).get("trace_faint_incoming"),
    )
```

## 검증
- **standalone(turn_manager 분기 로직, 작성 시 수행)**: 3 시나리오 통과 — 지정 incoming
  선택 / tfi None 폴백 / 지정 사망 폴백. resource_module·on_switch_in 스텁.
- **battle_setup 보강(클린룸)**: `prepare_run`이 `on_active_faint="replace_from_reserve"`를
  game_config에 싣는지 확인.
- **앱사이드(engine 통합)**:
  1. `ast.parse` (turn_manager·battle_setup·engine) OK.
  2. `trace_faint_incoming` 미설정 일반 전투 한 판 → 기존 roster_idx 교체 동작 무변경.
  3. gen5 prepare_run 셋업으로 돌려 T10 기절 시 Latios(로그 지정)가 진입하는지 확인(B4에서
     라운드 대조).

## 회귀 0
turn_manager: `trace_faint_incoming=None`이면 모든 incoming이 roster 폴백 = 기존
`reserve[:len(dead)]`와 동일(roster_idx 순). 새 param 기본 None. battle_setup: 한 줄 추가
(prepare_run은 트레이스 전용 경로라 일반 전투 무관). engine: kwargs 한 줄 추가, 미설정 시 None.

## 다음 (PR-B4)
통합 run — `prepare_run`(gen5) → 엔진 `run_simulation` 실행(트레이스 selector·자발교체·기절
incoming 전부 발동) → `fullbattle_diff.build_snapshots`(로그) vs 엔진 라운드 상태 →
`divergence` 리포트(앱 실행). 라운드별 첫 divergence가 미모델 메커니즘(피벗 Volt Switch·
Psyshock 방어타격·SR 타입스케일·Hidden Power 타입·턴내 교체순서)을 지목 → 역설계→수정 루프.
```
