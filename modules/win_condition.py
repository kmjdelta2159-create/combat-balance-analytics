"""
Win Condition — 전투 종료 판정 추상화.
현재는 HPDepletion (한 팀 전멸 시 승리)만 구현.
향후 TurnLimit, ObjectiveCapture, Survival, Composite 등을 플러그인으로 추가.
"""

from modules.resource import is_alive


class WinCondition:
    """전투 종료 조건의 추상 베이스."""

    def check(self, participants, turn, ctx=None):
        """
        현재 상태에서 전투 종료 여부 및 승자를 판정한다.

        Args:
            participants: 전투 참가자 리스트
            turn: 현재 턴 번호
            ctx: 추가 컨텍스트 (선택)

        Returns:
            (is_over: bool, winner: str) 튜플.
            is_over가 False면 winner는 무시된다.
            winner는 "Ally", "Enemy", "None" 중 하나.
        """
        raise NotImplementedError


class ResourceDepletion(WinCondition):
    """vital 자원이 고갈된 캐릭터를 제외, 한 진영만 남으면 종료."""

    def __init__(self, vital_resources=("HP",)):
        self.vital_resources = tuple(vital_resources)

    def check(self, participants, turn, ctx=None):
        alives = [p for p in participants if is_alive(p, self.vital_resources)]
        teams_alive = set(p['team'] for p in alives)

        if len(teams_alive) <= 1:
            winner = list(teams_alive)[0] if teams_alive else "None"
            return True, winner

        return False, None


class HPDepletion(ResourceDepletion):
    """하위호환 — HP 단일 vital 자원. 기존 코드/기본값 유지용."""

    def __init__(self):
        super().__init__(vital_resources=("HP",))


class TurnLimit(WinCondition):
    """지정 턴 수 도달 시 종료. 단독 사용보다는 Composite와 함께 쓰임."""

    def __init__(self, max_turn, on_timeout_winner="None"):
        """
        Args:
            max_turn: 종료 기준 턴 수
            on_timeout_winner: 시간 초과 시 승자 ("Ally"/"Enemy"/"None")
        """
        self.max_turn = max_turn
        self.on_timeout_winner = on_timeout_winner

    def check(self, participants, turn, ctx=None):
        if turn >= self.max_turn:
            return True, self.on_timeout_winner
        return False, None


class CompositeWinCondition(WinCondition):
    """여러 WinCondition을 OR 조합. 먼저 True가 나오는 조건의 결과를 반환."""

    def __init__(self, conditions):
        """
        Args:
            conditions: WinCondition 인스턴스 리스트
        """
        self.conditions = conditions

    def check(self, participants, turn, ctx=None):
        for cond in self.conditions:
            is_over, winner = cond.check(participants, turn, ctx)
            if is_over:
                return True, winner
        return False, None
