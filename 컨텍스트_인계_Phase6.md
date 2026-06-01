# Combat Balance Analytics — 프로젝트 컨텍스트 인계 (Phase 6 착수 시점)

## 프로젝트 정의
**프로젝트명**: Combat Balance Analytics — 전투로그 기반 범용 턴제 시뮬레이터
**기술 스택**: Python 3, Streamlit (SPA 마법사), Pandas, Scikit-learn, Plotly/ECharts
**최종 목표**: 전투로그 디테일 + 사용자 개입 정도로 **모든 턴제 게임을 담아내는 범용 메타 엔진**
(정직한 범위: "스탯 기반 턴제 전투 게임군" — JRPG·가챠·SRPG/택틱스·덱빌더 전투. 체스·바둑·4X
내정 등은 플러그인 SDK로 별도 구현 영역.)

## 너의 역할
사용자(프로젝트 리드)의 지시를 **안티그래비티(코드 생성기)에 전달할 마크다운 프롬프트**로
변환한다. 직접 코딩은 하지 않는다. 연결된 폴더 안에 모든 코드가 있으므로, 코드 확인이
필요하면 직접 읽어서 검증한다. 안티그래비티 납품물은 **항상 코드를 직접 읽어 검증**한다
(설명만 신뢰 X — 과거 하드코딩 납품 사례 있음).

## 시스템 아키텍처 (Streamlit SPA 마법사)
라우터: `main.py`
- **Step 1** `modules/step1_upload.py` — Data Upload
- **Step 2** `modules/step2_system_definition.py` — System Definition (Schema-Agnostic Mapping,
  Live Formula Validator(eval), Tag Normalization, Logic Execution Order(D&D), ML 파이프라인 LR+RF+KMeans)
- `modules/step2_profiling.py` — System Profiling (Feature Importance + Coefficient 대시보드)
- `modules/step3_flow_auditor.py`, `modules/step4_role_definition.py`
- **Step 5** `modules/step5_discrepancy.py` — Discrepancy (ML 예측 vs 실제 괴리)
- **Step 6** `modules/step6_dashboard.py` — Dashboard & Simulation. GM Mode, Monte Carlo 멀티프로세싱(1만회).

## 엔진/인프라 모듈 (현재 구조 — 이번 세션에 크게 바뀜)
- **`modules/engine.py`** — **신규(엔진 추출 Phase)**. 전투 엔진 코어. `run_simulation`,
  `run_monte_carlo`, `_worker_simulate_match`, `default_stochasticity_factory`, 액션 함수
  `_act_*` 9종 + `_act_move`, 중첩 `build_ctx`, `DEFAULT_ACTION_REGISTRY` 등록, `DEFAULT_COMBAT_FLOW`,
  `element_chart`/`get_element_multiplier`, `_parse_action_key`/`_KOREAN_TO_KEY`/`_ENGLISH_HINTS`,
  `_PHASE_TO_EVENT`, `get_effective_stat`, `_notify_event`/`_broadcast_phase_event`(이벤트 상태머신).
  **UI 독립 — streamlit/pandas import 안 함.** (이전엔 step6_dashboard.py 안에 박혀 있었음.)
- **`modules/turn_manager.py`** — **Phase 5.0에서 스케줄러/실행기 분리**.
  - `TurnManager`(추상) / `SequentialTurnManager`(순차 스케줄러 — 라운드 루프·속도 정렬·승리 판정)
  - `TurnExecutor`(추상) / `StandardTurnExecutor`(턴 바디 — pre/per-target 액션 실행)
  - `SequentialTurnManager.__init__`은 이제 `turn_executor`를 받음 (pre/per_target_actions 아님).
- `modules/action_registry.py` — `ActionRegistry`, `DEFAULT_ACTION_REGISTRY` (동적 액션 디스패치, 실제 사용 중).
- `modules/resource.py` — 자원 시스템. `ResourceModule(specs, damage_type_map)` — 턴 재생/실드 흡수/
  damage_type 라우팅. `PRIMARY_RESOURCE`, `get_current`/`get_max`/`apply_delta`/`is_alive`.
- `modules/win_condition.py` — `WinCondition` 추상 + `ResourceDepletion`/`HPDepletion`/`TurnLimit`/`CompositeWinCondition`.
- `modules/stochasticity.py` — `StochasticityModule` 추상 + `NoVariance`/`DamageVariance`/`CritSystem`/
  `HitChance`/`CompositeStochasticity`. RNG 보유 → MC는 팩토리 패턴.
- **`modules/spatial.py`** — **신규(Phase 4)**. `SpatialModule(width, height, distance_metric)` —
  `distance`(manhattan/chebyshev), `in_range`, `clamp`, `step_toward`. 순수 데이터.
- **`modules/deck.py`** — **신규(Phase 5)**. `DeckModule(hand_size, energy_per_turn)` —
  draw/discard_card/discard_hand/reshuffle(셔플 RNG 외부 주입). `CardTurnExecutor` — 덱빌더 턴 실행기.
- `modules/validation.py` — Validation Loop (시뮬 vs 로그 대조).

### `run_simulation` 현재 시그니처
```python
run_simulation(ally_instances, enemy_instances, max_turns=100,
               combat_flow=None, speed_stat=None, sys_stats=None, global_damage_formula=None,
               silent=False, action_registry=None, turn_manager_cls=None, win_condition=None,
               stochasticity=None, resource_module=None,
               spatial_module=None, range_stat=None, move_stat=None, deck_module=None)
```
`run_monte_carlo`도 `spatial_module/range_stat/move_stat/deck_module` 동일하게 받아 워커로 스레딩.

### 엔진 액션 파이프라인
액션 키: `PASSIVE_START → STAT_CALC → MOVE → TARGET_SELECT`(피벗) → `DAMAGE_CALC → ELEMENT_MULT
→ CRIT_CALC → APPLY_DAMAGE → ON_HIT → DEATH_CHECK`. `MOVE`/`TARGET_SELECT`는 누락 시 자동 삽입.
`build_ctx`가 만드는 ctx 키: active_char, participants, add_log, turn, sys_stats, passive_logic,
trigger_val, target_val, formula_str, atk_elem, damage_type, sim_metrics, stochasticity,
resource_module, spatial_module, attack_range, move_range, targets, current_target, raw_dmg,
dmg, elem_mult, battle_over.

## 핵심 설계 패턴 (이번 세션 확립)
1. **턴 스케줄러 / 턴 실행기 분리** — `TurnManager`(누가/어떤 순서) vs `TurnExecutor`(턴 안에서
   무엇을). 덱빌더는 스케줄러 그대로, 실행기만 `CardTurnExecutor`로 교체.
2. **카드 = 액터** — 카드는 `participants`에 안 넣음. 덱/핸드/버림 존에 삶. 카드 플레이 =
   `CardTurnExecutor._make_card_actor`로 카드-액터(소유자 스탯 복사 + resources/active_states
   참조 공유 + 카드 gimmicks) 생성 → `build_ctx` → `StandardTurnExecutor`로 표준 파이프라인 실행.
3. **모듈은 직교 조합형, default = identity** — 자원/공간/확률/덱은 독립 축. 미선언 시 현행
   동작과 100% 동일. (`range_stat`/`move_stat`/`deck_module` 등이 None이면 해당 기능 skip.)

## 개발 규칙
1. `copy.deepcopy()` 사용, Worker 함수 내 `st.session_state` 금지 (멀티프로세싱 안전성).
2. UI/백엔드 분리. 엔진(engine.py)은 streamlit 의존 0.
3. `try-except` + Fallback (eval 에러, 타입 캐스팅 방어).
4. **Pickling 안전성** — MC 워커에 인스턴스 직접 전달 시 순수 데이터만. `ResourceModule`/
   `SpatialModule`/`DeckModule`은 순수 데이터라 직접 전달 OK. `StochasticityModule`은 RNG 때문에
   팩토리 패턴. RNG를 모듈에 넣지 말 것 — 셔플 등은 외부(StochasticityModule.rng)에서 주입.
   `TurnManager`/`TurnExecutor`는 `run_simulation` 내부 생성 → pickle 안 됨, 신경 X.
5. 새 기능은 **default 경로가 현행과 100% 동일**하도록 설계.
6. 프롬프트엔 항상 명시: 동작 동일성 / 옵셔널 파라미터 default=None / Worker 내 st.session_state
   금지 / 완료 기준 체크리스트 / 변경 파일 한정 / "로직 개선 금지, 사양대로만".
7. 큰 Phase는 엔진/UI 분할 납품. 단, 분할은 자동 규칙이 아님 — 엔진 파트가 크고 위험할 때만.
   inert(아무도 안 쓰는) 납품물이 생기면 묶을 것.

## 하드코딩 제약사항 (현황)
- `element_chart` 딕셔너리 + `1.5/0.5` 상성 배율 — **미해결** (engine.py에 잔존).
- `_KOREAN_TO_KEY`/`_ENGLISH_HINTS` 한글/영문 액션 파싱 사전 — 미해결 (engine.py).
- `_PHASE_TO_EVENT` 매핑 — 미해결.
- 파티 슬롯 `range(4)` 고정 (step6 get_default_df 등) — 미해결.
- ML 휴리스틱 (타겟 컬럼 추론, 이상치 5%, LR 샘플링 5000) — 미해결.
- `ENGINE_STANDARD_TAGS` (step2) — 잔존하나 엔진은 비표준 태그 fail-safe 처리.
- ~~트리거 화이트리스트~~, ~~Vitality/Mana_Shield 가중치 예외~~ — 해결됨.

## 완료된 작업 (이번 세션)
검증은 전부 **클린룸 회귀 실행 + 코드 직접 읽기** 통과.
1. **Phase 3.5b-ii UI** — step6에 damage_type → 자원 라우팅 매핑 테이블.
2. **엔진 추출 리팩토링** — step6_dashboard.py의 엔진 블록(L22~710)을 `modules/engine.py` 신규
   파일로 순수 relocation. step6는 `from modules.engine import ...`.
3. **Phase 4a** — Spatial 좌표 + 사거리 타겟팅. engine: `SpatialModule`, `run_simulation`에
   `spatial_module`/`range_stat`, `_act_target_select` 사거리 필터(battle_over는 적 궤멸 시만).
   UI: step6 격자 선언 + 사거리 스탯 + 좌표 배치.
3. **Phase 4b** — 이동. engine: `_act_move`/`MOVE` 액션(TARGET_SELECT 직전 자동삽입),
   `step_toward`, `move_stat`. UI: step6 이동력 스탯.
4. **Phase 5.0** — 턴 실행기 추출 리팩토링 (turn_manager.py 스케줄러/실행기 분리).
5. **Phase 5.1** — 덱 엔진 (`modules/deck.py`: `DeckModule` + `CardTurnExecutor`, 카드=액터).
6. **Phase 5.2** — step6 덱 전투 UI (덱 모드 토글, hand_size/energy, Ally/Enemy 덱 에디터).

## 현재 상태
**Phase 5(Deck Module) 완료.** 엔진이 스탯전투 + 공간(좌표/사거리/이동) + 덱빌더 전투를
시뮬레이션한다. 다음 = **Phase 6**.

## 다음 작업: Phase 6 — Auto Game-Type Detection (재정의됨)
로드맵 원안은 "장르 탐지 → 플러그인 추천"이었으나, 논의 결과 **재정의**:

> **문제**: Phase 3~5가 각자 UI 섹션(자원 선언·damage_type 맵·공간 expander·덱 expander)을
> 무조건 렌더한다. 토글로 identity는 지켰지만 모든 장르의 컨트롤이 한 화면에 겹쳐 쌓였다.

Phase 6 = **탐지가 UI를 구동**한다. 구조:
1. **탐지** — Step 2 스키마 매핑 직후, 매핑된 컬럼 분석 → **활성 모듈 집합** 제안
   (장르 하나가 아니라 모듈 셋 — 자원/공간/확률/덱은 직교 조합 축, 혼합 장르 존재).
2. **게임 프로파일** — 활성 모듈 셋을 session_state에 저장 + 수동 오버라이드 패널.
3. **UI 게이팅** — Step 6의 각 모듈 UI 섹션이 프로파일에 따라 렌더/숨김.
- 탐지 강도: 공간(좌표 컬럼)·damage_type·다중자원은 CSV에서 잘 잡힘. **덱은 약함**(평면
  전투로그가 카드 데이터를 잘 안 담음) → 탐지는 "제안", **수동 오버라이드 필수**.

## 향후 로드맵
- **Phase 6** (다음) — 위 재정의 버전.
- **Phase 7** — Plugin별 Symbolic Regression (데미지 공식 자동 추측).
- **보류** — ability cost(자원 소비), 자원 역할 아키타입 확장, 캐릭터별 개별 덱,
  효과 카드 작성 UI, 카드 플레이 AI 고도화(현재 그리디), 비대칭 덱/비-덱 혼합전.

## 검증 방법론 (필독 — 이번 세션 핵심 교훈)
- **검증 샌드박스(bash) 마운트 불안정**: 큰 파일(`step6_dashboard.py` ~74KB+, `engine.py` ~30KB)을
  **잘라서/널바이트로 서빙**한다. `wc -l`·`py_compile`이 truncation 지점에서 가짜 SyntaxError를
  낸다 (에러 줄 번호가 파일 끝 너머면 truncation 아티팩트 확정). **사용자 실제 파일은 정상.**
- **신뢰 가능 경로**: `Read`/`Grep` 툴(파일 툴)은 실제 파일을 정확히 읽는다. bash는 작은·신규
  파일엔 OK지만 큰·수정된 파일엔 불안정.
- **클린룸 검증 절차** (리팩토링·엔진 변경 시 필수):
  1. 검증 대상 + 의존 모듈을 `Read` 툴로 읽어 `프로젝트폴더/regtest/modules/`에 `Write`로 사본
     작성 (engine.py는 로직 verbatim, 로그 이모지만 단순화 가능 — 데미지/승자 무관).
  2. `regtest/harness.py`에서 streamlit 없이 `run_simulation`/`run_monte_carlo` 직접 호출.
  3. bash로 `regtest`에서 harness 실행, 회귀 베이스라인 대조.
  4. 끝나면 `regtest/` 삭제 (`mcp__cowork__allow_cowork_file_delete`로 삭제 권한 필요).
- UI(step6)는 Streamlit 런타임이라 헤드리스 실행 불가 → 정적 코드 정독 + py_compile(가능하면).

## 검증 회귀 베이스라인 (클린룸 하니스 재구성용)
공통: 1v1, 공식 `phys_power - target_armor_class`, `DEFAULT_COMBAT_FLOW`, 전원 `Active_Cast`/`Single_Target`.
공격자 Vit500/Phys100/Arm30/Spd50.
- **NoVariance**: lopsided(적 Vit400/Phys70/Arm30/Spd40) 데미지총량 **620.0** /
  near-even(적 Vit500/Phys100/Arm33/Spd49) **1026.0**.
- **공간(4a)**: 양측 사거리 내 → 620 / 상호 사거리 밖(이동 없음) → winner None, 데미지 0 /
  비대칭(A 사거리20, E 사거리1, 거리5) → Ally, 데미지 **420** (E가 한 대도 못 침).
- **`step_toward`**: manhattan (0,0)→(10,0) steps 3 = (3,0) / chebyshev (0,0)→(10,10) steps 3 = (3,3).
- **이동(4b)**: 위 "상호 사거리 밖" 시나리오 + `move_stat`(이동력 1) → 접근 후 교전 → Ally, **620**.
- **덱(5.1)**: A덱(10×코스트1/공식"70"), E덱(10×"40"), `DeckModule(hand_size=1, energy_per_turn=1)`
  → 턴당 1장 플레이 = 표준 lopsided와 동일 → Ally, **620**.
- MC는 `spawn` 강제로 Windows Pickling 경로 검증.

## 사용자 선호
- 짧고 직접적인 답변 (불필요한 호들갑/사과 X).
- 마크다운 헤더 적당히, 코드/표 활용.
- 단계적 진행 (Phase 단위 분할 후 검증).
- 정직한 평가 (이론적 한계, 안티그래비티 품질 문제, 설계 약점 솔직하게).
- 큰 Phase 착수 전 설계 논의를 선호. 사용자가 아키텍처 통찰을 자주 제시함 — 진지하게 반영할 것.

## 작업 패턴 / 교훈
- 안티그래비티 납품물은 항상 코드 직접 읽어 검증 → 변경 지점 grep → 핵심 섹션 정독 → 클린룸 회귀.
- Streamlit `key` 달린 위젯은 `value=`/`index=` 인자를 첫 렌더링 때만 반영. 동적 기본값/옵션
  변경 시 stale-value 크래시 가능 → key에 상태 시그니처 포함하거나, 옵션 의존 셀렉트박스는 key 생략.
- 좌표 number_input에 `max_value` 금지 (격자 크기 변경 시 저장값 초과 크래시).
- 리팩토링 프롬프트는 "순수 relocation, 로직 0줄 변경" 명시 + 동작 동일성 논거 포함.

## 테스트 CSV
프로젝트 폴더 내 `universal_test_log.csv` (5000행). 컬럼: Vitality, Phys_Power, Armor_Class,
Action_Speed, Mana_Shield, Cast_Trigger, Target_Logic, Is_Victorious.
(공간/덱 컬럼 없음 → 모든 신규 모듈에 대해 default=identity 경로 → 회귀 안전.)

---
위 컨텍스트를 숙지하고, 다음 지시(Phase 6 설계/프롬프트)를 기다린다.
