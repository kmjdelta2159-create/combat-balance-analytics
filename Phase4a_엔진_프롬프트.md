# Phase 4a (엔진) — Spatial Module: 좌표 + 사거리 타겟팅

## 배경
Phase 4 = 공간 시스템(격자 타일 모델). **4a = 좌표 데이터 모델 + 사거리 기반 타겟팅**,
4b = 이동. 이 프롬프트는 **4a의 엔진 부분**만 다룬다. Step 6 UI(격자 선언·캐릭터 배치)는
Phase 4a-UI에서 별도로 진행한다.

목표: `SpatialModule`(격자 + 거리 계산)을 신설하고, `_act_target_select`가
공격자의 사거리 안에 있는 적만 타겟하도록 일반화한다.

## 변경 파일 (정확히 2개)
- **신규**: `modules/spatial.py`
- **수정**: `modules/engine.py`
- `modules/step6_dashboard.py` 등 그 외 모든 파일 무수정. (UI는 4a-UI 단계)

## 설계 원칙 — default = identity
4a-engine 단독으로는 **동작이 현행과 100% 동일**해야 한다. Step 6는 아직 spatial
파라미터를 넘기지 않으므로(`spatial_module`/`range_stat` 미전달 → 엔진 내부 None),
사거리 필터가 건너뛰어진다. 테스트 CSV(`universal_test_log.csv`)엔 좌표 데이터도 없다.

캐릭터 위치는 `char['position'] = {'x': int, 'y': int}` 중첩 dict, 없으면 `None`
(`char['resources']`와 동일한 패턴).

---

## 1. 신규 파일 — `modules/spatial.py`

`ResourceModule`과 동일한 **순수 데이터 모듈**이다 (width/height/거리메트릭만 보유 →
pickle/deepcopy 안전 → MC 워커에 인스턴스 직접 전달 가능, 팩토리 불필요).

```python
"""Spatial System — 격자 좌표 + 거리/사거리 계산. (Phase 4a)

캐릭터 위치는 char['position'] = {'x': int, 'y': int} 또는 None.
순수 데이터 속성(int/str)만 가지므로 pickle/deepcopy 안전 (멀티프로세싱 호환).
4a는 좌표 + 사거리만. 이동/경계 클램프는 4b에서 추가.
"""


class SpatialModule:
    def __init__(self, width=None, height=None, distance_metric="manhattan"):
        # width/height: 격자 크기. 4a 엔진은 미사용 (4a-UI 격자 선언 / 4b 이동 경계용).
        self.width = width
        self.height = height
        # "manhattan" (4방향 거리) | "chebyshev" (8방향 거리)
        self.distance_metric = distance_metric

    def distance(self, pos_a, pos_b):
        """두 위치 dict 간 격자 거리."""
        dx = abs(int(pos_a['x']) - int(pos_b['x']))
        dy = abs(int(pos_a['y']) - int(pos_b['y']))
        if self.distance_metric == "chebyshev":
            return max(dx, dy)
        return dx + dy  # manhattan (기본)

    def in_range(self, attacker, target, attack_range):
        """attacker가 target을 attack_range 내에서 칠 수 있는지 판정.
        attack_range가 None이거나 둘 중 한쪽이라도 위치 미지정이면 True
        (사거리 무제한 = 현행 동작 보존)."""
        if attack_range is None:
            return True
        pa = attacker.get('position')
        pt = target.get('position')
        if not pa or not pt:
            return True
        return self.distance(pa, pt) <= attack_range
```

---

## 2. `modules/engine.py` 수정

### 2-1. import 추가
파일 상단 import 구역(`from modules.win_condition import ResourceDepletion` 근처)에:
```python
from modules.spatial import SpatialModule
```

### 2-2. `run_simulation` 시그니처 (현재 539~544행)
끝에 옵셔널 파라미터 2개 추가 (default None):
```python
def run_simulation(ally_instances, enemy_instances, max_turns=100,
                   combat_flow=None, speed_stat=None, sys_stats=None, global_damage_formula=None, silent=False,
                   action_registry=None, turn_manager_cls=None,
                   win_condition=None,
                   stochasticity: StochasticityModule = None,
                   resource_module=None,
                   spatial_module=None, range_stat=None):
```

### 2-3. `run_simulation` 본문 — spatial 기본값
`resource_module = resource_module or ResourceModule()` 다음 줄에 추가:
```python
spatial_module = spatial_module or SpatialModule()
```

### 2-4. 참가자 초기화 — position 딥카피
참가자 초기화 루프(현재 568~580행)에서 ally·enemy **양쪽** 모두,
`p['resources'] = copy.deepcopy(inst.get('resources', {}))` 바로 다음 줄에 추가:
```python
p['position'] = copy.deepcopy(inst.get('position'))
```
inst에 position이 없으면 `None`이 저장된다. 중첩 dict 공유 차단 + 4b 이동 대비.

### 2-5. `build_ctx` — attack_range 계산 + ctx 주입 (현재 632~678행)
`build_ctx` 안, `ctx = { ... }` dict 생성 직전에 공격자 사거리 계산 추가:
```python
attack_range = get_effective_stat(active_char, range_stat) if range_stat else None
```
그리고 `ctx` dict에 키 2개 추가 (`"resource_module": resource_module` 줄 근처):
```python
"spatial_module": spatial_module,
"attack_range":   attack_range,
```
`range_stat`·`spatial_module`은 `run_simulation` 파라미터이므로 `build_ctx` 클로저로
접근된다. `get_effective_stat`로 읽으므로 사거리 버프/디버프도 자동 반영된다.

### 2-6. `_act_target_select` 일반화 — 사거리 필터 (핵심, 현재 269~300행)

**가장 중요한 지점**: `battle_over`는 적 진영이 **진짜 궤멸**했을 때만 True로 설정한다.
"적은 살아있는데 사거리 밖이라 타겟이 없음"은 `battle_over`가 **아니다** — 그 경우
공격자는 이번 턴 행동만 생략한다. 함수 전체를 아래로 교체:

```python
def _act_target_select(ctx):
    """트리거 조건 확인 후 사거리 내 타겟 선택"""
    char = ctx["active_char"]
    participants = ctx["participants"]
    trigger_val = ctx["trigger_val"]
    target_val = ctx["target_val"]

    # 비전투 트리거만 행동 생략. 미인식 트리거는 행동하도록 fail-safe.
    if str(trigger_val).strip() in NON_ACTING_TRIGGERS:
        ctx["targets"] = []
        return

    # 살아있는 적 진영 전체
    opponents_all = [p for p in participants
                     if p['team'] != char['team'] and get_current(p) > 0]
    if not opponents_all:
        # 적 진영 실제 궤멸 → 전투 종료
        ctx["add_log"](f"  [Phase: TARGET_SELECT] 🏆 {char['team']} 반대 진영 궤멸!")
        ctx["battle_over"] = True
        ctx["targets"] = []
        return

    # ── 사거리 필터 (SpatialModule + attack_range 둘 다 있을 때만) ──
    spatial = ctx.get("spatial_module")
    attack_range = ctx.get("attack_range")
    if spatial is not None and attack_range is not None:
        opponents = [o for o in opponents_all
                     if spatial.in_range(char, o, attack_range)]
    else:
        opponents = opponents_all

    if not opponents:
        # 적은 살아있으나 사거리 내 타겟 없음 → 이번 턴 행동 생략 (battle_over 아님)
        ctx["add_log"](
            f"[Turn {ctx['turn']}] {char['id']} ({char['name']}) "
            f"[Phase: TARGET_SELECT] 사거리 내 타겟 없음 — 행동 생략"
        )
        ctx["targets"] = []
        return

    norm_target = _normalize_target_tag(target_val)
    if norm_target == "AoE_All":
        ctx["targets"] = opponents
    elif norm_target == "Lowest_HP":
        ctx["targets"] = [min(opponents, key=lambda x: get_current(x))]
    else:  # Single_Target
        ctx["targets"] = [opponents[0]]

    ctx["add_log"](
        f"[Turn {ctx['turn']}] {char['id']} ({char['name']}) 행동! "
        f"[Phase: TARGET_SELECT] 타겟: {', '.join(t['id'] for t in ctx['targets'])}"
    )
```

### 2-7. `run_monte_carlo` — 파라미터 + 태스크 튜플 (현재 485~491행)
시그니처 끝에 `spatial_module=None, range_stat=None` 추가:
```python
def run_monte_carlo(ally_party, enemy_party, combat_flow, speed_stat, sys_stats, global_formula,
                    num_simulations=10000, max_turns=100, progress_callback=None,
                    stochasticity_factory=None, resource_module=None,
                    spatial_module=None, range_stat=None):
```
태스크 튜플(`tasks.append((...))`)에서 `worker_seed` **직전**에 `spatial_module, range_stat` 삽입:
```python
tasks.append((ally_party, enemy_party, combat_flow, speed_stat, sys_stats, global_formula,
              max_turns, stochasticity_factory, resource_module,
              spatial_module, range_stat, worker_seed))
```

### 2-8. `_worker_simulate_match` — 언팩 + 전달 (현재 461~483행)
args 언팩 튜플을 태스크 튜플과 똑같은 순서로 맞춘다 (`worker_seed` 직전에 2개 추가):
```python
(ally_party, enemy_party, combat_flow, speed_stat, sys_stats, global_formula,
 max_turns, stochasticity_factory, resource_module,
 spatial_module, range_stat, worker_seed) = args
```
`run_simulation(...)` 호출에 인자 추가:
```python
        winner, _, sim_metrics = run_simulation(
            ally_copy, enemy_copy, max_turns=max_turns,
            combat_flow=combat_flow, speed_stat=speed_stat, sys_stats=sys_stats,
            global_damage_formula=global_formula, silent=True,
            stochasticity=stoch_instance,
            resource_module=resource_module,
            spatial_module=spatial_module, range_stat=range_stat
        )
```

---

## 핵심 제약
- `SpatialModule`은 순수 데이터(int/str) → pickle 안전 → MC 워커에 인스턴스 직접 전달
  (팩토리 불필요, `ResourceModule`과 동일 패턴. `StochasticityModule`처럼 RNG가 없음).
- `char['position']`은 순수 dict 또는 None → pickle·deepcopy 안전.
- 신규 파라미터(`spatial_module`/`range_stat`)는 전부 default=None.
- **`battle_over`는 적 진영 실제 궤멸 시에만 True** — 사거리 밖 ≠ 궤멸.
- 4a 엔진은 `SpatialModule.width`/`height`를 사용하지 않는다 (4a-UI/4b용으로만 보유).
- 로직을 "개선"하지 말 것 — 사양대로만. `element_chart` 등 기존 하드코딩은 손대지 않는다.

## 동작 동일성 — 회귀 검증
4a-engine 단독은 순수 identity여야 한다. Step 6가 `spatial_module`/`range_stat`을
넘기지 않으므로 `range_stat=None` → `attack_range=None` → `_act_target_select`의
사거리 필터가 skip → `opponents = opponents_all` → 현행과 완전히 동일.

베이스라인 (1v1, 공격자 Vit500/Phys100/Arm30/Spd50, 공식 `phys_power - target_armor_class`,
`DEFAULT_COMBAT_FLOW`, 전원 `Active_Cast`/`Single_Target`):
- NoVariance lopsided(적 Vit400/Phys70/Arm30/Spd40) 데미지총량 **620.0**
- NoVariance near-even(적 Vit500/Phys100/Arm33/Spd49) 데미지총량 **1026.0**

**추가 — 사거리 동작 확인 하니스**:
- 두 캐릭터에 `position` 부여 + `range_stat` 지정한 `SpatialModule` 전달
- 사거리 내 배치 → 정상 공격
- 사거리 밖 배치 → 행동 생략, `battle_over` False 유지, 양측 모두 사거리 밖이면 max_turn 무승부
- `distance_metric` manhattan/chebyshev 각각 거리 계산 확인

## 완료 기준 체크리스트
- [ ] `modules/spatial.py` 신규 — `SpatialModule(width, height, distance_metric)` + `distance` + `in_range`
- [ ] `engine.py`: `SpatialModule` import 추가
- [ ] `run_simulation`에 `spatial_module=None, range_stat=None` 파라미터 + `spatial_module or SpatialModule()` 기본값
- [ ] 참가자 초기화에서 ally·enemy 양쪽 `p['position'] = copy.deepcopy(inst.get('position'))`
- [ ] `build_ctx`가 `attack_range` 계산 + ctx에 `spatial_module`·`attack_range` 주입
- [ ] `_act_target_select` 사거리 필터 — `battle_over`는 적 궤멸 시에만, 사거리 밖은 행동 생략
- [ ] `run_monte_carlo`/`_worker_simulate_match`에 `spatial_module`·`range_stat` 스레딩 (튜플 순서 일치)
- [ ] 변경 파일 정확히 2개 (spatial.py 신규, engine.py 수정), step6 등 무수정
- [ ] `python -c "import modules.engine"` 통과
- [ ] 회귀 베이스라인 불변: NoVariance 620.0 / 1026.0
- [ ] 사거리 필터 동작 확인: in-range 공격 / out-of-range 행동 생략(battle_over False)
