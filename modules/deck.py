"""Deck System — 카드 / 덱 / 핸드 (Phase 5.1).

캐릭터 카드 존: char['deck'] / char['hand'] / char['discard'] — 카드 dict 리스트.
카드 dict: {"name": str, "cost": int, "gimmicks": {...}}  (gimmicks는 캐릭터와 동형)

DeckModule은 순수 데이터(설정값)만 보유 → pickle 안전 (MC 워커 직접 전달 OK).
셔플 RNG는 보유하지 않고 외부(StochasticityModule의 rng)에서 받는다.
"""

from modules.turn_manager import TurnExecutor, StandardTurnExecutor


class DeckModule:
    """덱 시스템 — 존 관리(드로우/버림/재셔플) + 덱전투 설정."""

    def __init__(self, hand_size=5, energy_per_turn=3):
        # hand_size: 턴당 드로우 장수 / energy_per_turn: 턴당 에너지 예산
        self.hand_size = hand_size
        self.energy_per_turn = energy_per_turn

    def reshuffle(self, char, rng=None):
        """버림 더미를 덱으로 되돌려 섞는다."""
        deck = char.setdefault('deck', [])
        deck.extend(char.get('discard', []))
        char['discard'] = []
        if rng is not None:
            rng.shuffle(deck)

    def draw(self, char, n, rng=None):
        """덱 → 핸드 n장. 덱 부족 시 버림 더미를 재셔플해 보충, 그래도 없으면 중단."""
        hand = char.setdefault('hand', [])
        for _ in range(int(n)):
            deck = char.setdefault('deck', [])
            if not deck:
                self.reshuffle(char, rng)
                deck = char.get('deck', [])
                if not deck:
                    break
            hand.append(deck.pop(0))

    def discard_card(self, char, card):
        """카드 한 장: 핸드 → 버림."""
        hand = char.get('hand', [])
        if card in hand:
            hand.remove(card)
        char.setdefault('discard', []).append(card)

    def discard_hand(self, char):
        """핸드 전체 → 버림."""
        char.setdefault('discard', []).extend(char.get('hand', []))
        char['hand'] = []


class CardTurnExecutor(TurnExecutor):
    """덱빌더 턴 실행기 — 드로우 → 카드 플레이 루프 → 핸드 버림.
    카드 플레이 = 카드를 액터로 만들어 표준 파이프라인(StandardTurnExecutor) 실행."""

    def __init__(self, deck_module, build_ctx, sys_stats,
                 pre_target_actions, per_target_actions):
        self.deck_module = deck_module
        self.build_ctx = build_ctx
        self.sys_stats = sys_stats
        # 카드 플레이는 표준 파이프라인을 그대로 사용
        self.inner = StandardTurnExecutor(pre_target_actions, per_target_actions)

    def _make_card_actor(self, owner, card):
        """카드를 액터 dict로 변환.
        소유자 스탯은 복사, resources·active_states는 참조 공유(카드 효과가 소유자에게
        적용되도록), gimmicks는 카드 것을 사용."""
        actor = {s: owner.get(s) for s in self.sys_stats}
        actor["name"] = card.get("name", "Card")
        actor["id"] = f"{owner.get('id', '?')}:{card.get('name', 'Card')}"
        actor["team"] = owner["team"]
        actor["gimmicks"] = card.get("gimmicks", {})
        actor["resources"] = owner.setdefault("resources", {})          # 참조 공유
        actor["active_states"] = owner.setdefault("active_states", [])   # 참조 공유
        actor["position"] = owner.get("position")
        return actor

    def execute(self, ctx, registry):
        owner = ctx["active_char"]
        turn = ctx["turn"]
        participants = ctx["participants"]

        # 덱/핸드/버림이 전부 비었으면 덱 미사용 유닛 → 행동 없음
        if not owner.get('deck') and not owner.get('hand') and not owner.get('discard'):
            return

        # 셔플용 RNG — StochasticityModule의 rng 재사용 (없으면 None → 미셔플)
        stoch = ctx.get("stochasticity")
        rng = getattr(stoch, "rng", None)

        # 1) 드로우
        self.deck_module.draw(owner, self.deck_module.hand_size, rng)

        # 2) 카드 플레이 루프 — 핸드 순서대로, 에너지 예산 내 (그리디 AI)
        energy = self.deck_module.energy_per_turn
        for card in list(owner.get('hand', [])):
            cost = int(card.get("cost", 0))
            if cost > energy:
                continue
            energy -= cost
            card_actor = self._make_card_actor(owner, card)
            card_ctx = self.build_ctx(card_actor, turn, participants)
            self.inner.execute(card_ctx, registry)
            self.deck_module.discard_card(owner, card)
            if card_ctx.get("battle_over"):
                break

        # 3) 핸드 버림
        self.deck_module.discard_hand(owner)
