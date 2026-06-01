# Phase 5.1 (엔진) — 덱 엔진 (DeckModule + CardTurnExecutor)

## 배경
Phase 5.0(턴 스케줄러/실행기 분리)은 완료. 5.1은 **덱빌더 전투 턴**을 엔진에 추가한다.
유닛의 한 턴 = 드로우 → 핸드에서 카드 여러 장 플레이(에너지 예산 내) → 핸드 버림.

논의 합의 사항:
- **카드 = 액터** — 카드 플레이 = 카드를 `active_char`로 표준 액션 파이프라인 실행.
  새 "카드 효과 시스템" 불필요, 기존 파이프라인(공식 eval·타겟팅·데미지·상태머신) 재사용.
- 카드는 `participants`에 넣지 **않는다** — 덱/핸드/버림 존에 산다.
- 턴 스케줄링은 그대로(`SequentialTurnManager`). 바뀌는 건 턴 실행기뿐 → 5.0에서 만든
  `TurnExecutor` 슬롯에 `CardTurnExecutor`를 끼운다.

## 범위 (5.1)
- 양 진영 모두 덱 사용(대칭 카드 전투). 비-덱 적과의 혼합전은 5.1 범위 밖.
- 카드 플레이 AI = 단순 그리디(핸드 순서대로 에너지 되는 카드 플레이). 숙련 플레이 학습은 향후.
- 에너지 = 턴당 정수 예산(executor 로컬). 자원화(에너지 획득/환급 카드)는 향후.
- 콤보 전투 외(맵·상점·전투 사이 덱 구성)는 엔진 범위 아님.

## 변경 파일 (정확히 2개)
- **신규**: `modules/deck.py`
- **수정**: `modules/engine.py`
- 그 외 모든 파일 무수정. (`turn_manager.py`도 무수정 — 5.0의 `TurnExecutor` 그대로 사용.)

## 설계 원칙 — default = identity
`run_simulation`에 `deck_module`이 전달되지 않으면 `StandardTurnExecutor`(5.0) 사용 →
**현행 100% 동일**. Step 6는 아직 `deck_module`을 넘기지 않는다(5.2 UI 단계). 테스트
CSV엔 덱 데이터가 없다.

## 카드 데이터 형태
카드 = 캐릭터와 동형 구조의 dict. 캐릭터 인스턴스의 `deck` 키에 카드 리스트로 저장:
```python
{"name": "Strike", "cost": 1,
 "gimmicks": {"Target_Logic": "Single_Target", "Formula": "6"}}
```
- `gimmicks`는 캐릭터 gimmicks와 동형 → `build_ctx`가 그대로 읽음.
- 공격 카드: `Formula`(데미지 공식) + `Target_Logic`.
- 효과 카드: `Formula`를 `"0"`으로 두고 `passive` 슬롯에 효과 스크립트(`add_state` 등).
  (효과 카드는 0 데미지 + 패시브 효과로 처리 — 카드-액터가 소유자 자원/상태를 공유하므로
  소유자에게 효과가 적용된다.)

---

## 1. 신규 파일 — `modules/deck.py`

```python
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
```

**참고**: `card_ctx["battle_over"]`(적 진영 궤멸)는 카드 ctx에만 설정된다 — 유닛 ctx로
전파하지 않는다. 루프만 중단하고, 스케줄러가 `execute()` 직후 `win_condition.check()`로
승자를 정상 판정한다 (battle_over로 전파하면 "None"이 되어 승자 판정이 어긋남).

---

## 2. `modules/engine.py` 수정

### 2-1. import (현재 6행 근처)
`from modules.turn_manager import SequentialTurnManager, StandardTurnExecutor` 아래에 추가:
```python
from modules.deck import CardTurnExecutor
```

### 2-2. `run_simulation` 시그니처
끝에 `deck_module=None` 추가 (현재 `...spatial_module=None, range_stat=None, move_stat=None):`):
```python
                   spatial_module=None, range_stat=None,
                   move_stat=None, deck_module=None):
```

### 2-3. 참가자 초기화 — 카드 존 deepcopy
참가자 초기화 루프에서 ally·enemy **양쪽** 모두, `p['position'] = copy.deepcopy(...)`
다음 줄에 추가:
```python
            p['deck'] = copy.deepcopy(inst.get('deck', []))
            p['hand'] = []
            p['discard'] = []
```
전투는 항상 덱이 가득 찬 상태에서 시작 (hand/discard 빈 상태). 덱 미보유 인스턴스는
`p['deck']`이 `[]` → `CardTurnExecutor`가 자연히 no-op.

### 2-4. 턴 실행기 선택 (현재 759행 `turn_executor = StandardTurnExecutor(...)`)
현재:
```python
    turn_executor = StandardTurnExecutor(pre_target_actions, per_target_actions)
```
교체:
```python
    if deck_module is not None:
        turn_executor = CardTurnExecutor(deck_module, build_ctx, sys_stats,
                                         pre_target_actions, per_target_actions)
    else:
        turn_executor = StandardTurnExecutor(pre_target_actions, per_target_actions)
```
(`build_ctx`는 바로 위에서 정의된 중첩 함수 — 이 시점에 접근 가능. `sys_stats`는
`run_simulation` 지역 변수.)

### 2-5. `run_monte_carlo` — 파라미터 + 태스크 튜플
시그니처 끝에 `deck_module=None` 추가. 태스크 튜플에서 `worker_seed` **직전**에
`deck_module` 삽입:
```python
        tasks.append((ally_party, enemy_party, combat_flow, speed_stat, sys_stats, global_formula,
                      max_turns, stochasticity_factory, resource_module,
                      spatial_module, range_stat, move_stat, deck_module, worker_seed))
```

### 2-6. `_worker_simulate_match` — 언팩 + 전달
args 언팩을 태스크 튜플과 동일 순서로 (`worker_seed` 직전에 `deck_module` 추가):
```python
        (ally_party, enemy_party, combat_flow, speed_stat, sys_stats, global_formula,
         max_turns, stochasticity_factory, resource_module,
         spatial_module, range_stat, move_stat, deck_module, worker_seed) = args
```
`run_simulation(...)` 호출에 `deck_module=deck_module` 추가:
```python
            spatial_module=spatial_module, range_stat=range_stat, move_stat=move_stat,
            deck_module=deck_module
```

---

## 핵심 제약
- 변경 파일 2개 한정 (`deck.py` 신규, `engine.py` 수정). `turn_manager.py` 무수정.
- `DeckModule`은 순수 데이터(int 설정값) → pickle 안전 → MC 워커 직접 전달 OK.
- 셔플 RNG는 `DeckModule`이 보유하지 않는다 — `StochasticityModule.rng`를 받아 씀
  (RNG를 모듈에 넣으면 Pickling/MC 시드 문제 발생 — 과거 `default_stochasticity_factory`
  교훈과 동일).
- 카드 존(`deck`/`hand`/`discard`)은 순수 리스트, 카드는 순수 dict → deepcopy/pickle 안전.
- `CardTurnExecutor`는 `run_simulation` 내부에서 생성되어 워커로 pickle되지 않음 — `build_ctx`
  클로저를 들고 있어도 무방 (현행 `build_ctx`와 동일).
- 카드를 `participants`에 절대 넣지 말 것 — 존에만 존재.
- `card_ctx["battle_over"]`를 유닛 ctx로 전파하지 말 것 (위 참고 박스).
- 로직을 "개선"하지 말 것 — 사양대로만.

## 동작 동일성 — 회귀 검증
`deck_module`이 None이면 `StandardTurnExecutor`(5.0)가 쓰여 현행과 100% 동일.
참가자에 `deck`/`hand`/`discard` 키가 추가되지만 비-덱 경로에서 아무도 읽지 않는다.

베이스라인: NoVariance 1v1 lopsided 데미지총량 **620.0** / near-even **1026.0** 불변.

**추가 — 덱 동작 확인 하니스**:
- 양 진영에 `deck`(공격 카드 리스트)을 부여하고 `DeckModule`을 전달
- 드로우 → 카드 플레이(파이프라인 경유 데미지) → 핸드 버림 → 덱 소진 시 재셔플이
  순환하는지 확인
- 단일 공격 카드 덱으로 1v1 → 승자 판정 + 데미지 누적 확인
- Monte Carlo(spawn 강제) — `deck_module` 스레딩 + Pickling 정상

## 완료 기준 체크리스트
- [ ] `modules/deck.py` 신규 — `DeckModule`(draw/discard/discard_hand/reshuffle) + `CardTurnExecutor`
- [ ] `DeckModule`은 순수 데이터, 셔플 RNG 외부 주입
- [ ] `CardTurnExecutor`가 드로우 → 카드 플레이 루프(에너지 예산) → 핸드 버림
- [ ] 카드 플레이 = `_make_card_actor` + `build_ctx` + `StandardTurnExecutor` 실행
- [ ] 카드-액터가 소유자 `resources`/`active_states`를 참조 공유, 스탯은 복사
- [ ] `engine.py`: `CardTurnExecutor` import
- [ ] `run_simulation`에 `deck_module=None` 파라미터
- [ ] 참가자 초기화에 ally·enemy 양쪽 `deck`/`hand`/`discard` 설정
- [ ] `deck_module`이 있으면 `CardTurnExecutor`, 없으면 `StandardTurnExecutor`
- [ ] `run_monte_carlo`/`_worker_simulate_match`에 `deck_module` 스레딩 (튜플 순서 일치)
- [ ] 변경 파일 정확히 2개, 그 외 무수정
- [ ] `python -c "import modules.engine"` 통과
- [ ] 회귀 베이스라인 불변: NoVariance 620.0 / 1026.0
- [ ] 덱 전투 동작 확인: 카드 드로우·플레이·버림·재셔플, 승자 판정
