# Phase 4b (엔진) — Spatial Module: 이동

## 배경
Phase 4a(좌표 + 사거리 타겟팅)는 엔진·UI 모두 완료·검증됨. **4b는 이동(movement)**.
이 프롬프트는 **4b의 엔진 부분**. Step 6 UI(이동력 스탯 선언)는 Phase 4b-UI에서 별도.

목표: `MOVE` 액션을 신설해, 각 캐릭터가 자기 턴에 가장 가까운 적을 향해 격자를
이동하도록 한다. 이로써 4a의 사거리 타겟팅이 실제 게임플레이가 된다 — 사거리 밖
캐릭터가 더 이상 영원히 교착하지 않고 적에게 접근한다.

## 변경 파일 (정확히 2개)
- **수정**: `modules/spatial.py` — `SpatialModule`에 이동 메서드 추가
- **수정**: `modules/engine.py` — `MOVE` 액션 + 파이프라인 + 스레딩
- `step6_dashboard.py` 등 그 외 무수정 (UI는 4b-UI 단계)

## 설계 원칙 — default = identity
4b-engine 단독은 **현행과 100% 동일**해야 한다. Step 6는 아직 `move_stat`을 넘기지
않으므로 `move_stat=None` → `move_range=None` → `_act_move`가 즉시 no-op. `MOVE`는
파이프라인에 자동 삽입되어 매 턴 실행되지만 이동력이 없으면 아무 일도 하지 않는다.
(4a의 `_act_target_select` 사거리 필터가 `attack_range=None`일 때 skip되는 것과 동일 패턴.)

## 이동 AI 규칙 (4b 범위)
- 가장 가까운 적(`SpatialModule.distance` 기준)을 향해 직선 접근한다. 격자에 장애물이
  없으므로 경로탐색 불필요 — 좌표 차이를 좁히기만 한다.
- 한 턴에 최대 `move_range` 타일 이동.
- `attack_range`(4a)가 있으면 그 거리에서 멈추고, 없으면 인접(거리 1)에서 멈춘다 —
  적 위로 겹쳐 올라가지 않는다.
- **범위 밖(향후 정제 대상)**: 카이팅·최적 사거리 유지·후퇴 AI는 4b 범위 아님.
  4b는 "접근(approach)" 단일 정책.

---

## 1. `modules/spatial.py` — `SpatialModule`에 이동 메서드 추가

기존 `SpatialModule` 클래스에 메서드 2개를 추가한다 (`__init__`/`distance`/`in_range`는
그대로 둔다). 순수 데이터 속성은 그대로이므로 pickle 안전성 유지.

```python
    def clamp(self, pos):
        """위치를 격자 경계 [0, width-1] x [0, height-1] 안으로 클램프.
        width/height가 None이면 해당 축은 무제한."""
        x, y = int(pos['x']), int(pos['y'])
        if self.width is not None:
            x = max(0, min(self.width - 1, x))
        if self.height is not None:
            y = max(0, min(self.height - 1, y))
        return {'x': x, 'y': y}

    def step_toward(self, src, dst, steps):
        """src에서 dst 방향으로 정확히 steps 타일 이동한 새 위치를 반환한다.
        장애물 없음 가정. distance_metric에 따라 이동 방식이 다르다:
        - manhattan: 한 스텝에 한 축만 1칸
        - chebyshev: 한 스텝에 x,y 동시 1칸씩(대각 허용)
        결과는 격자 경계로 클램프된다."""
        x, y = int(src['x']), int(src['y'])
        tx, ty = int(dst['x']), int(dst['y'])
        for _ in range(max(0, int(steps))):
            if x == tx and y == ty:
                break
            if self.distance_metric == "chebyshev":
                if x < tx: x += 1
                elif x > tx: x -= 1
                if y < ty: y += 1
                elif y > ty: y -= 1
            else:  # manhattan
                if x != tx:
                    x += 1 if x < tx else -1
                elif y != ty:
                    y += 1 if y < ty else -1
        return self.clamp({'x': x, 'y': y})
```

---

## 2. `modules/engine.py` 수정

### 2-1. 액션 키 매핑에 MOVE 추가
- `_KOREAN_TO_KEY` dict (현재 51~61행)에 항목 추가: `"이동": "MOVE",`
- `_ENGLISH_HINTS` 리스트 (현재 64~75행)에 항목 추가: `("move", "MOVE"),`
- `_CHAR_LEVEL_KEYS` (현재 92행)에 `"MOVE"` 추가 (문서용 — MOVE는 캐릭터 단위 액션)

### 2-2. `_act_move` 액션 함수 신설
`_act_target_select` 정의 끝(현재 321행) 다음, `_act_damage_calc`(현재 323행) 앞에 추가:

```python
def _act_move(ctx):
    """이동 (Phase 4b) — 가장 가까운 적을 향해 move_range 타일 접근.
    attack_range가 있으면 그 거리에서, 없으면 인접(거리 1)에서 멈춘다.
    이동 비활성(move_range 없음/위치 없음/spatial 없음)이면 no-op → 현행 동일."""
    char = ctx["active_char"]
    spatial = ctx.get("spatial_module")
    move_range = ctx.get("move_range")
    if spatial is None or not move_range or char.get('position') is None:
        return
    enemies = [p for p in ctx["participants"]
               if p['team'] != char['team'] and get_current(p) > 0
               and p.get('position') is not None]
    if not enemies:
        return
    my_pos = char['position']
    nearest = min(enemies, key=lambda e: spatial.distance(my_pos, e['position']))
    dist = spatial.distance(my_pos, nearest['position'])
    attack_range = ctx.get("attack_range")
    stop_dist = max(int(attack_range), 1) if attack_range is not None else 1
    steps = min(int(move_range), dist - stop_dist)
    if steps <= 0:
        return  # 이미 사거리/인접 안 — 이동 불필요
    new_pos = spatial.step_toward(my_pos, nearest['position'], steps)
    if new_pos != my_pos:
        char['position'] = new_pos
        ctx["add_log"](
            f"[Turn {ctx['turn']}] {char['id']} ({char['name']}) "
            f"이동 → ({new_pos['x']},{new_pos['y']})"
        )
```

### 2-3. MOVE 액션 레지스트리 등록
디폴트 액션 등록 블록(현재 460~469행)에 한 줄 추가 (예: `TARGET_SELECT` 등록 다음):
```python
DEFAULT_ACTION_REGISTRY.register("MOVE",          _act_move)
```

### 2-4. `run_simulation` 시그니처
끝에 옵셔널 파라미터 추가 (현재 568~574행, `spatial_module=None, range_stat=None` 다음):
```python
def run_simulation(ally_instances, enemy_instances, max_turns=100,
                   combat_flow=None, speed_stat=None, sys_stats=None, global_damage_formula=None, silent=False,
                   action_registry=None, turn_manager_cls=None,
                   win_condition=None,
                   stochasticity: StochasticityModule = None,
                   resource_module=None,
                   spatial_module=None, range_stat=None,
                   move_stat=None):
```

### 2-5. MOVE 파이프라인 자동 삽입
`run_simulation` 본문에서 TARGET_SELECT 자동삽입 블록(현재 637~645행, `all_actions`에
`_PIVOT_KEY` 보장) **직후**, 피벗 분리 루프(현재 647행 `# 피벗 기준으로...`) **직전**에 추가:

```python
    # MOVE 자동 삽입 — TARGET_SELECT 직전 (Phase 4b)
    if "MOVE" not in [k for k, _ in all_actions]:
        _ts_idx = next((i for i, (k, _) in enumerate(all_actions) if k == _PIVOT_KEY), 0)
        all_actions.insert(_ts_idx, ("MOVE", "Move Toward Target (이동)"))
```

이로써 `MOVE`는 항상 `TARGET_SELECT` 직전에 위치 → 피벗 분리에서 `pre_target_actions`에
들어가 타겟 선택 전에 실행된다. (사용자 combat_flow에 이미 "이동"이 있으면 중복 삽입 안 함.)

### 2-6. `build_ctx` — move_range 계산 + ctx 주입
`build_ctx` 안, `attack_range = ...`(현재 688행) 다음에 추가:
```python
        move_range = get_effective_stat(active_char, move_stat) if move_stat else None
```
ctx dict에 키 추가 (`"attack_range": attack_range,` 다음):
```python
            "move_range":     move_range,
```
(`move_stat`은 `run_simulation` 파라미터 → `build_ctx` 클로저로 접근. `get_effective_stat`로
읽으므로 이동력 버프/디버프도 자동 반영.)

### 2-7. `run_monte_carlo` — 파라미터 + 태스크 튜플
시그니처(현재 509~512행)에 `move_stat=None` 추가:
```python
def run_monte_carlo(ally_party, enemy_party, combat_flow, speed_stat, sys_stats, global_formula,
                    num_simulations=10000, max_turns=100, progress_callback=None,
                    stochasticity_factory=None, resource_module=None,
                    spatial_module=None, range_stat=None, move_stat=None):
```
태스크 튜플(현재 518~520행)에서 `worker_seed` **직전**에 `move_stat` 삽입:
```python
        tasks.append((ally_party, enemy_party, combat_flow, speed_stat, sys_stats, global_formula,
                      max_turns, stochasticity_factory, resource_module,
                      spatial_module, range_stat, move_stat, worker_seed))
```

### 2-8. `_worker_simulate_match` — 언팩 + 전달
args 언팩(현재 488~490행)을 태스크 튜플과 같은 순서로:
```python
        (ally_party, enemy_party, combat_flow, speed_stat, sys_stats, global_formula,
         max_turns, stochasticity_factory, resource_module,
         spatial_module, range_stat, move_stat, worker_seed) = args
```
`run_simulation(...)` 호출(현재 497~504행)에 `move_stat=move_stat` 추가:
```python
        winner, _, sim_metrics = run_simulation(
            ally_copy, enemy_copy, max_turns=max_turns,
            combat_flow=combat_flow, speed_stat=speed_stat, sys_stats=sys_stats,
            global_damage_formula=global_formula, silent=True,
            stochasticity=stoch_instance,
            resource_module=resource_module,
            spatial_module=spatial_module, range_stat=range_stat, move_stat=move_stat
        )
```

---

## 핵심 제약
- `SpatialModule`은 메서드만 추가 — 데이터 속성(width/height/distance_metric)은 그대로 →
  pickle 안전성 유지, MC 워커에 인스턴스 직접 전달 OK.
- `move_stat`은 문자열(스탯 이름) → pickle 안전.
- 신규 파라미터 `move_stat`는 default=None.
- **`battle_over`를 건드리지 말 것** — `_act_move`는 전투 종료와 무관.
- `_act_move`는 `_broadcast_phase_event`를 호출하지 않는다 (이동은 4b에서 버프 만료
  트리거가 아님).
- 로직을 "개선"하지 말 것 — 사양대로만. `element_chart` 등 기존 하드코딩 손대지 않는다.

## 동작 동일성 — 회귀 검증
4b-engine 단독은 순수 identity여야 한다. Step 6가 `move_stat`을 넘기지 않으므로
`move_stat=None` → `build_ctx`의 `move_range=None` → `_act_move`가 즉시 return.
`MOVE`가 파이프라인에 들어가 매 턴 실행되어도 완전한 no-op.

베이스라인 (1v1, 공격자 Vit500/Phys100/Arm30/Spd50, 공식 `phys_power - target_armor_class`,
`DEFAULT_COMBAT_FLOW`, 전원 `Active_Cast`/`Single_Target`):
- NoVariance lopsided(적 Vit400/Phys70/Arm30/Spd40) 데미지총량 **620.0**
- NoVariance near-even(적 Vit500/Phys100/Arm33/Spd49) 데미지총량 **1026.0**

**추가 — 이동 동작 확인 하니스**:
- `step_toward` 단위 검증: manhattan (0,0)→(10,0) steps 3 = (3,0) / chebyshev
  (0,0)→(10,10) steps 3 = (3,3)
- **교착 해소 검증**: 4a에서 무승부였던 시나리오(A·E 모두 사거리 1, 좌표 거리 10,
  상호 사거리 밖)에 `move_stat`(이동력 1)을 추가 → 양측이 접근해 인접 후 교전 →
  **winner Ally, 데미지총량 620.0** (이동 턴은 0 데미지, 교전 시작 후엔 lopsided와 동일).
- Monte Carlo(spawn 강제) 정상 동작 — `move_stat` 스레딩 + Pickling 확인.

## 완료 기준 체크리스트
- [ ] `modules/spatial.py`: `SpatialModule`에 `clamp` + `step_toward` 추가 (기존 메서드 보존)
- [ ] `engine.py`: `_KOREAN_TO_KEY`·`_ENGLISH_HINTS`·`_CHAR_LEVEL_KEYS`에 MOVE 추가
- [ ] `engine.py`: `_act_move` 함수 신설 + `DEFAULT_ACTION_REGISTRY.register("MOVE", _act_move)`
- [ ] `run_simulation`에 `move_stat=None` 파라미터
- [ ] MOVE 자동 삽입 — `TARGET_SELECT` 직전, 중복 시 미삽입
- [ ] `build_ctx`가 `move_range` 계산 + ctx에 주입
- [ ] `run_monte_carlo`/`_worker_simulate_match`에 `move_stat` 스레딩 (튜플 순서 일치)
- [ ] 변경 파일 정확히 2개 (spatial.py, engine.py), step6 등 무수정
- [ ] `python -c "import modules.engine"` 통과
- [ ] 회귀 베이스라인 불변: NoVariance 620.0 / 1026.0
- [ ] 이동 검증: 4a 교착 시나리오 + `move_stat` → winner Ally, 데미지총량 620.0
- [ ] `step_toward` manhattan/chebyshev 단위 검증 통과
