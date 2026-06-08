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
import inspect

def _accepts_turn_arg(fn):
    if fn is None:
        return False
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return False
    if any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params):
        return True
    positional = [
        p for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                      inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    return len(positional) >= 2



class TurnExecutor:
    """턴 실행기 — 한 유닛이 자기 턴에 하는 행동을 정의한다."""

    def execute(self, ctx, registry):
        """active_char(ctx 안)의 한 턴 행동을 실행한다.
        전투 종료 신호는 ctx['battle_over'] = True 로 전달한다."""
        raise NotImplementedError


class StandardTurnExecutor(TurnExecutor):
    """현행 동작 — pre-target 액션들 실행 후, 타겟별로 per-target 액션들 실행.
    (추출 전 SequentialTurnManager.run() 의 A/B 블록과 동일)"""

    def __init__(self, pre_target_actions, per_target_actions, post_target_actions=None):
        """
        Args:
            pre_target_actions: [(key, label), ...] 타겟 선택 이전 액션 리스트
            per_target_actions: [(key, label), ...] 타겟별 반복 액션 리스트
            post_target_actions: [(key, label), ...] 타겟 처리 후 캐릭터 단위 1회 액션 (턴 종료 hook)
        """
        self.pre_target_actions = pre_target_actions
        self.per_target_actions = per_target_actions
        self.post_target_actions = post_target_actions or []

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
        # ── C. post-target 액션 실행 (캐릭터 단위, 타겟 무관, 턴 종료 hook) ──
        for key, label in self.post_target_actions:
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
                 resource_module=None, on_active_faint=None, action_priority=None,
                 on_switch_in=None, trace_faint_incoming=None, on_round_start=None):
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
        self._on_active_faint = on_active_faint
        self._action_priority = action_priority
        self._action_priority_accepts_turn = _accepts_turn_arg(action_priority)
        self._on_switch_in = on_switch_in
        self._trace_faint_incoming = trace_faint_incoming
        self._trace_faint_used = set()
        self._on_round_start = on_round_start

    def run(self, participants, max_turns, sim_metrics, build_ctx, add_log):
        turn = 1
        while turn <= max_turns:
            if self._on_round_start is not None:
                self._on_round_start(turn, participants)   # 라운드 시작 resync(트레이스 모드)
            participants.sort(
                key=lambda x: (-x.get(self.speed_stat, 0) if self.speed_stat else 0, x['id'])
            )

            # 라운드 시작 시점의 on_field 유닛만 이번 라운드 행동자로 고정.
            # (교체로 라운드 중간에 진입한 유닛은 다음 라운드부터 행동)
            acting_units = [p for p in participants if p.get('on_field', True)]
            # 행동 우선도(예: 교체 티어)로 안정 재정렬 — 동순위는 속도순 유지.
            # action_priority 미설정 시 재정렬 없음 → 순수 속도순(회귀 0).
            if self._action_priority is not None:
                if self._action_priority_accepts_turn:
                    acting_units.sort(key=lambda x: -self._action_priority(x, turn))
                else:
                    acting_units.sort(key=lambda x: -self._action_priority(x))
            for active_char in acting_units:
                # 라운드 중간에 교체로 빠진 유닛은 제외. on_field 미설정 시 True(현행 전원-동시).
                if not active_char.get('on_field', True):
                    continue
                if not self.resource_module.is_alive(active_char):
                    continue

                self.resource_module.on_turn_start(active_char)
                ctx = build_ctx(active_char, turn, participants)

                # ── 턴 실행 (TurnExecutor 위임) ──
                self.turn_executor.execute(ctx, self.registry)
                
                if self.broadcast_phase_event:
                    self.broadcast_phase_event("ACTION_END", ctx)

                def _emit_turn_end(_ctx):
                    if self.broadcast_phase_event:
                        self.broadcast_phase_event("TURN_END", _ctx)

                if ctx["battle_over"]:
                    _emit_turn_end(ctx)
                    return "None", sim_metrics

                # ── 액티브 사망 시 처리 (on_active_faint 규칙) ──
                self._resolve_faint(participants, add_log)

                # ── 전투 종료 판정 (WinCondition 위임) ──
                is_over, winner = self.win_condition.check(participants, turn)
                if is_over:
                    _emit_turn_end(ctx)
                    add_log(f"🏆 전투 종료! {turn}턴 만에 {winner} 진영이 승리했습니다!")
                    return winner, sim_metrics

                # ── 턴 종료 이벤트 ──
                _emit_turn_end(ctx)

            turn += 1

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
