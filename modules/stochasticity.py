"""
Stochasticity System — 전투 엔진의 랜덤 요소 추상화.
현재는 NoVariance (결정론적)가 기본값.
게임마다 다른 RNG 모델을 플러그인으로 주입 가능.

설계 원칙:
- random.Random 인스턴스를 내부에 가짐 (시드 제어 가능)
- 멀티프로세싱 안전성을 위해 워커별로 독립 인스턴스 생성 가능
"""

import random


class StochasticityModule:
    """전투 엔진의 RNG 모델 추상 베이스."""

    def __init__(self, seed=None):
        """
        Args:
            seed: RNG 시드. None이면 시스템 시간 기반.
                  Monte Carlo 워커별로 다른 시드를 주입해야 다양한 결과가 나옴.
        """
        self.rng = random.Random(seed)

    def apply_damage_variance(self, damage: float, ctx=None) -> float:
        """
        데미지 계산 직후 호출. 분산을 적용하여 변형된 데미지 반환.
        기본: 분산 없음.
        """
        return damage

    def roll_critical(self, attacker, target, ctx=None) -> tuple:
        """
        크리티컬 판정. (is_crit: bool, multiplier: float) 튜플 반환.
        기본: 크리티컬 없음.
        """
        return (False, 1.0)

    def roll_hit(self, attacker, target, ctx=None) -> bool:
        """
        명중 판정. True면 공격 적중, False면 빗나감.
        기본: 항상 적중.
        """
        return True

    def roll_chance(self, p: float, ctx=None) -> bool:
        """범용 확률 판정 — p 확률로 True. 시드 제어되는 self.rng 사용(재현성).
        마비/혼란 등 행동 게이팅 판정에 쓴다. NoVariance(기본 결정론)도 상속하므로
        시드 고정 시 재현 가능."""
        return self.rng.random() < float(p)

    def roll_range(self, lo: int, hi: int, ctx=None) -> int:
        """범용 정수 균등 추출 — [lo,hi] 닫힌구간. 시드 제어 self.rng(재현). 다중 hit 횟수 등."""
        return self.rng.randint(int(lo), int(hi))

    def shuffle_tie_order(self, participants_with_same_speed: list) -> list:
        """
        같은 속도 캐릭터들의 행동 순서 결정.
        기본: 입력 순서 유지.
        """
        return participants_with_same_speed


class NoVariance(StochasticityModule):
    """결정론적 — 현재 엔진 기본 동작. 아무 RNG도 적용 안 함."""
    pass


class DamageVariance(StochasticityModule):
    """데미지에 ±X% 분산 적용."""

    def __init__(self, variance_pct: float = 0.1, seed=None):
        """
        Args:
            variance_pct: 분산 폭. 0.1 = ±10%.
            seed: RNG 시드.
        """
        super().__init__(seed)
        self.variance_pct = variance_pct

    def apply_damage_variance(self, damage: float, ctx=None) -> float:
        lo = 1.0 - self.variance_pct
        hi = 1.0 + self.variance_pct
        return damage * self.rng.uniform(lo, hi)


class CritSystem(StochasticityModule):
    """크리티컬 확률 + 배율 시스템."""

    def __init__(self, crit_rate: float = 0.15, crit_multiplier: float = 1.5,
                 crit_rate_stat: str = None, crit_mult_stat: str = None, seed=None):
        """
        Args:
            crit_rate: 기본 크리티컬 확률 (0~1).
            crit_multiplier: 기본 크리티컬 배율.
            crit_rate_stat: 캐릭터 스탯에서 크리티컬률을 읽을 키 (예: "Crit_Rate"). None이면 기본값 사용.
            crit_mult_stat: 캐릭터 스탯에서 크리티컬 배율을 읽을 키. None이면 기본값 사용.
            seed: RNG 시드.
        """
        super().__init__(seed)
        self.crit_rate = crit_rate
        self.crit_multiplier = crit_multiplier
        self.crit_rate_stat = crit_rate_stat
        self.crit_mult_stat = crit_mult_stat

    def roll_critical(self, attacker, target, ctx=None) -> tuple:
        rate = self.crit_rate
        mult = self.crit_multiplier

        if self.crit_rate_stat and attacker:
            try:
                rate = float(attacker.get(self.crit_rate_stat, rate))
                if rate > 1.0:
                    rate = rate / 100.0  # 퍼센트 표기 자동 변환
            except (ValueError, TypeError):
                pass

        if self.crit_mult_stat and attacker:
            try:
                mult = float(attacker.get(self.crit_mult_stat, mult))
            except (ValueError, TypeError):
                pass

        is_crit = self.rng.random() < rate
        return (is_crit, mult if is_crit else 1.0)


class HitChance(StochasticityModule):
    """명중률 시스템 (회피/빗맞음 모델링)."""

    def __init__(self, base_hit_rate: float = 0.95, seed=None):
        super().__init__(seed)
        self.base_hit_rate = base_hit_rate

    def roll_hit(self, attacker, target, ctx=None) -> bool:
        return self.rng.random() < self.base_hit_rate


class CompositeStochasticity(StochasticityModule):
    """여러 RNG 모듈을 조합. 각 hook은 순서대로 위임."""

    def __init__(self, modules: list, seed=None):
        """
        Args:
            modules: StochasticityModule 인스턴스 리스트.
        """
        super().__init__(seed)
        self.modules = modules

    def apply_damage_variance(self, damage: float, ctx=None) -> float:
        for m in self.modules:
            damage = m.apply_damage_variance(damage, ctx)
        return damage

    def roll_critical(self, attacker, target, ctx=None) -> tuple:
        # 첫 번째 크리티컬 발생하는 모듈의 결과 사용
        for m in self.modules:
            is_crit, mult = m.roll_critical(attacker, target, ctx)
            if is_crit:
                return (True, mult)
        return (False, 1.0)

    def roll_hit(self, attacker, target, ctx=None) -> bool:
        # 모든 모듈이 적중이라고 해야 적중 (AND 조합)
        for m in self.modules:
            if not m.roll_hit(attacker, target, ctx):
                return False
        return True

    def shuffle_tie_order(self, participants_with_same_speed: list) -> list:
        # 첫 번째 모듈에만 위임
        if self.modules:
            return self.modules[0].shuffle_tie_order(participants_with_same_speed)
        return participants_with_same_speed
