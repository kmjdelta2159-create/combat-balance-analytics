# Phase 5.0 — 턴 실행기(TurnExecutor) 추출 리팩토링

## 배경
Phase 5(Deck) 착수 전 정지작업. 덱빌더는 턴 **스케줄링**(순차 순서, 라운드 루프)은
현행과 동일하고, 턴 **안에서 하는 행동**만 다르다(공격 1회 → 드로우 + 카드 여러 장 +
버림). 현재 `SequentialTurnManager.run()`은 스케줄링과 "턴 바디"가 한 덩어리라 턴
바디를 교체할 수 없다.

턴 바디를 `TurnExecutor`로 분리해, 스케줄러(`TurnManager`)는 그대로 두고 턴 행동만
교체 가능하게 만든다. 이후 Phase 5.x에서 덱 실행기를 이 자리에 끼운다.

**이것은 순수 리팩토링이다 — 동작을 한 글자도 바꾸지 않는다.** 로직·문자열·공식 변경 금지.

## 변경 파일 (정확히 2개)
- **수정**: `modules/turn_manager.py`
- **수정**: `modules/engine.py` (`run_simulation`의 TurnManager 생성부만)
- 그 외 모든 파일 무수정.

---

## 1. `modules/turn_manager.py` — 파일 전체를 아래로 교체

`TurnExecutor`(추상) + `StandardTurnExecutor`(현행 턴 바디)를 신설하고,
`SequentialTurnManager`가 `pre/per_target_actions` 대신 `turn_executor`를 받아 위임한다.

```python
"""
Turn Manager — 턴 실행 모델 추상화.

설계: 턴 스케줄링(누가 / 어떤 순서로 행동하는가)과 턴 실행(한 유닛이 자기 턴에
무엇을 하는가)을 분리한다.
- TurnManager  : 스케줄링 — 라운드 루프, 행동 순서, 승리 판정
- TurnExecutor : 한 유닛의 턴 안 행동
현재 SequentialTurnManager(순차 스케줄러) + StandardTurnExecutor(공격 1회 실행기)만
구현. 향후 스케줄러(SimultaneousTurnManager 등)·실행기(덱 실행기 등)를 플러그인으로 추가.
"""

from modules.win_condition import WinCondition, HPDepletion
from modules.resource import ResourceModule


class TurnExecutor:
    """턴 실행기 — 한 유닛이 자기 턴에 하는 행동을 정의한다."""

    def execute(self, ctx, registry):
        """active_char(ctx 안)의 한 턴 행동을 실행한다.
        전투 종료 신호는 ctx['battle_over'] = True 로 전달한다."""
        raise NotImplementedError


class StandardTurnExecutor(TurnExecutor):
    """현행 동작 — pre-target 액션들 실행 후, 타겟별로 per-target 액션들 실행.
    (추출 전 SequentialTurnManager.run() 의 A/B 블록과 동일)"""

    def __init__(self, pre_target_actions, per_target_actions):
        """
        Args:
            pre_target_actions: [(key, label), ...] 타겟 선택 이전 액션 리스트
            per_target_actions: [(key, label), ...] 타겟별 반복 액션 리스트
        """
        self.pre_target_actions = pre_target_actions
        self.per_target_actions = per_target_actions

    def execute(self, ctx, registry):
        # ── A. pre-target 액션 실행 ──
        for key, label in self.pre_target_actions:
            func = registry.get(key)
            if func:
                func(ctx)
            if ctx["battle_over"]:
                return
        # ── B. per-target 액션 실행 ──
        if ctx["targets"]:
            for t in ctx["targets"]:
                ctx["current_target"] = t
                ctx["raw_dmg"] = 0
                ctx["dmg"] = 0
                ctx["elem_mult"] = 1.0
                for key, label in self.per_target_actions:
                    func = registry.get(key)
                    if func:
                        func(ctx)


class TurnManager:
    """턴 스케줄링 모델의 추상 베이스."""

    def run(self, participants, max_turns, sim_metrics, build_ctx, add_log):
        """
        전체 전투를 실행한다.

        Args:
            participants: 전투 참가자 리스트 (active_states 초기화 완료 상태)
            max_turns: 최대 턴 수
            sim_metrics: 시뮬레이션 지표 누적 dict
            build_ctx: callable. (active_char, turn, participants) -> ctx dict
            add_log: callable. (str) -> None

        Returns:
            (winner: str, sim_metrics: dict) 튜플.
            winner는 "Ally", "Enemy", 또는 "None".
        """
        raise NotImplementedError


class SequentialTurnManager(TurnManager):
    """순차 스케줄링 — 속도 스탯 기준 정렬 후 한 명씩 턴 진행. (현재 엔진 기본 동작)"""

    def __init__(self, action_registry, turn_executor,
                 speed_stat=None, broadcast_phase_event=None,
                 win_condition: WinCondition = None,
                 resource_module=None):
        """
        Args:
            action_registry: ActionRegistry 인스턴스
            turn_executor: TurnExecutor 인스턴스 — 한 유닛의 턴 행동을 실행
            speed_stat: 정렬 기준 스탯 이름
            broadcast_phase_event: 턴 종료 이벤트 브로드캐스터 (콜백)
            win_condition: WinCondition 인스턴스. None이면 HPDepletion() 기본값.
            resource_module: ResourceModule 인스턴스. None이면 기본값(HP vital, 재생 0).
        """
        self.registry = action_registry
        self.turn_executor = turn_executor
        self.speed_stat = speed_stat
        self.broadcast_phase_event = broadcast_phase_event
        self.win_condition = win_condition or HPDepletion()
        self.resource_module = resource_module or ResourceModule()

    def run(self, participants, max_turns, sim_metrics, build_ctx, add_log):
        turn = 1
        while turn <= max_turns:
            participants.sort(
                key=lambda x: (-x.get(self.speed_stat, 0) if self.speed_stat else 0, x['id'])
            )

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
                if is_over:
                    add_log(f"🏆 전투 종료! {turn}턴 만에 {winner} 진영이 승리했습니다!")
                    return winner, sim_metrics

                # ── 턴 종료 이벤트 ──
                if self.broadcast_phase_event:
                    self.broadcast_phase_event("TURN_END", ctx)

            turn += 1

        add_log(f"⏱️ 설정한 최대 턴 수({max_turns}) 내에 승부가 나지 않았습니다. 캐릭터 밸류나 데미지 공식을 점검하십시오.")
        return "None", sim_metrics
```

---

## 2. `modules/engine.py` 수정 (2곳)

### 2-1. import (현재 6행)
`from modules.turn_manager import SequentialTurnManager` 를:
```python
from modules.turn_manager import SequentialTurnManager, StandardTurnExecutor
```

### 2-2. `run_simulation`의 TurnManager 생성부 (현재 759~767행)
현재:
```python
    manager = TurnManagerCls(
        action_registry=registry,
        pre_target_actions=pre_target_actions,
        per_target_actions=per_target_actions,
        speed_stat=speed_stat,
        broadcast_phase_event=_broadcast_phase_event,
        win_condition=win_condition,
        resource_module=resource_module,
    )
```
교체:
```python
    turn_executor = StandardTurnExecutor(pre_target_actions, per_target_actions)
    manager = TurnManagerCls(
        action_registry=registry,
        turn_executor=turn_executor,
        speed_stat=speed_stat,
        broadcast_phase_event=_broadcast_phase_event,
        win_condition=win_condition,
        resource_module=resource_module,
    )
```
`pre_target_actions`/`per_target_actions`를 만드는 앞단 코드(combat_flow 파싱 + 피벗
분리)는 **그대로 둔다** — 이제 그 결과가 `StandardTurnExecutor`로 들어간다.

---

## 동작 100% 동일성 — 핵심 논거
`StandardTurnExecutor.execute()`는 추출 전 `run()` 안의 A/B 블록과 **동일한 코드**다.
- `battle_over`는 현재 pre-target의 `_act_target_select`에서만 설정된다. A 블록 루프가
  그 시점에 즉시 `return`(execute 종료) → 스케줄러가 `execute()` 직후 `ctx['battle_over']`를
  확인해 `"None"` 반환 → per-target·승리판정·턴종료를 모두 건너뜀. 추출 전 "루프 안에서
  바로 `return`"과 결과가 동일하다.
- per-target 액션 중 `battle_over`를 설정하는 것은 없다(데미지/속성/크리/온힛/사망판정
  모두). 따라서 `execute()` 정상 종료 후의 `battle_over` 확인은 추출 전과 같은 경로다.

## 제약
- 변경 파일 2개 한정. 로직·문자열·공식 변경 0건 (순수 리팩토링).
- `TurnManager`/`TurnExecutor`는 `run_simulation` 내부에서 생성되며 MC 워커로 pickle되지
  않는다 (워커는 각자 `run_simulation`을 호출해 새로 만든다) — Pickling 고려 불필요, 현행과 동일.
- `run_simulation`의 `turn_manager_cls` 파라미터는 유지. 커스텀 매니저는 새 시그니처
  (`action_registry`, `turn_executor`, ...)를 받아야 한다.

## 완료 기준 체크리스트
- [ ] `turn_manager.py`: `TurnExecutor`(추상) + `StandardTurnExecutor` 신설
- [ ] `StandardTurnExecutor.execute()`가 추출 전 A/B 블록과 동일 로직
- [ ] `SequentialTurnManager.__init__`이 `pre/per_target_actions` 대신 `turn_executor` 수용
- [ ] `SequentialTurnManager.run()`이 `turn_executor.execute()`에 위임 + `battle_over` 확인
- [ ] `engine.py`: `StandardTurnExecutor` import + `run_simulation`에서 생성·전달
- [ ] 변경 파일 정확히 2개, 그 외 무수정
- [ ] `python -c "import modules.engine"` 에러 없이 통과
- [ ] 로직·문자열·공식 변경 0건
- [ ] 회귀: 단일 전투 + Monte Carlo 결과 추출 전과 동일
- [ ] 회귀 베이스라인 일치: NoVariance 1v1 lopsided 620.0 / near-even 1026.0
