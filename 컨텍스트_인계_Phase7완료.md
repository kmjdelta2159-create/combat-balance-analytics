Combat Balance Analytics — 프로젝트 컨텍스트 인계 (Phase 6·7 완료, 검증 마일스톤 진행 중)

# 프로젝트 정의

프로젝트명: Combat Balance Analytics — 전투로그 기반 범용 턴제 시뮬레이터
기술 스택: Python 3, Streamlit(SPA 마법사), Pandas, Scikit-learn, gplearn, Plotly/ECharts

최종 목표 (이번 세션에 정밀화됨):
전투로그 **역설계** + 해당 게임 시스템을 전부 파악한 **전문가의 개입**으로 → 그 게임의
전투 시스템을 **복제** → 복제된 시뮬레이터를 그 게임에 **최적화**(밸런스 분석)하는 도구.
- 개입은 흠이 아니라 설계 전제다. 보편적 턴제일수록 개입 ↓, 비보편적일수록 개입 ↑
  (슬라이딩 스케일).
- 정직한 범위: 스탯 기반 턴제 전투 게임군(JRPG·가챠·SRPG/택틱스·덱빌더). 체스·바둑·
  4X 내정 등은 플러그인 SDK 별도 영역.
- 이론적 도달성: 전제("시스템을 전부 아는 사용자") 안에서 이론적으로 달성 가능. 단
  하이브리드 플러그인 모델(흔한 건 config, 희귀한 건 코드 escape-hatch)이 성립해야
  하고, 닫힌 상용 게임은 "정확 복제"가 아닌 "고충실도 근사"가 한계(인식론적 한계,
  설계 결함 아님).

# 너의 역할

사용자(프로젝트 리드)의 지시를 안티그래비티(코드 생성기)에 전달할 마크다운 프롬프트로
변환한다. 직접 코딩은 하지 않는다(검증용 test harness·참조 구현은 예외 — 프로젝트
코드가 아님). 연결된 폴더 안에 모든 코드가 있으므로 코드 확인이 필요하면 직접 읽어
검증한다. 안티그래비티 납품물은 항상 코드를 직접 읽어 검증한다(설명만 신뢰 X — 과거
하드코딩 납품 + 불완전 납품 사례 있음. 이번 세션 Phase 6 step6는 6개 변경 중 1개만
적용돼 NameError까지 유발 → 교정 프롬프트로 바로잡음).

# 시스템 아키텍처 (Streamlit SPA 마법사)

라우터: `main.py`. 실제 표시 단계 5개:
1. `modules/step1_upload.py` — Data Upload
2. `modules/step2_system_definition.py` — System Definition (Schema-Agnostic Mapping,
   Live Formula Validator(eval), Tag Normalization, Logic Execution Order(D&D),
   ML 파이프라인 LR+RF+KMeans, **Phase 6 Game Profile 패널**, **Phase 7 SR 버튼**)
3. `modules/step5_discrepancy.py` — Discrepancy (ML 예측 vs 실제 괴리)
4. `modules/step2_profiling.py` — System Profiling (Feature Importance + Coefficient)
5. `modules/step6_dashboard.py` — Dashboard & Simulation. GM Mode, Monte Carlo
   멀티프로세싱(1만회), SLSQP 스탯 최적화.
(`step3_flow_auditor.py`/`step4_role_definition.py`는 모듈은 존재하나 라우터 미연결.)

## 엔진/인프라 모듈

* `modules/engine.py` — 전투 엔진 코어. `run_simulation`, `run_monte_carlo`,
  `_worker_simulate_match`, `default_stochasticity_factory`, 액션 함수 `_act_*` +
  `_act_move`, `build_ctx`, `DEFAULT_ACTION_REGISTRY`, `DEFAULT_COMBAT_FLOW`,
  `element_chart`/`get_element_multiplier`, 액션 파싱 사전, `_PHASE_TO_EVENT`,
  `get_effective_stat`, 이벤트 상태머신. UI 독립(streamlit/pandas import 안 함).
* `modules/turn_manager.py` — `TurnManager`/`SequentialTurnManager`(스케줄러),
  `TurnExecutor`/`StandardTurnExecutor`(턴 바디).
* `modules/action_registry.py` — `ActionRegistry`, `DEFAULT_ACTION_REGISTRY`.
* `modules/resource.py` — `ResourceModule(specs, damage_type_map)`. 턴 재생/실드 흡수/
  damage_type 라우팅. **자원 선언만 되고 소비(ability cost)는 미구현.**
* `modules/win_condition.py` — `WinCondition` + `ResourceDepletion`/`HPDepletion`/
  `TurnLimit`/`CompositeWinCondition`.
* `modules/stochasticity.py` — `StochasticityModule` + `NoVariance`/`DamageVariance`/
  `CritSystem`/`HitChance`/`CompositeStochasticity`. RNG 보유 → MC는 팩토리 패턴.
* `modules/spatial.py` — `SpatialModule(width, height, distance_metric)`. 순수 데이터.
* `modules/deck.py` — `DeckModule(hand_size, energy_per_turn)` + `CardTurnExecutor`.
  카드=액터. **공격 카드만 — 효과 카드(버프/드로우/블록) 미구현.**
* `modules/validation.py` — Validation Loop (시뮬 vs 로그 대조).
* `modules/detection.py` — **신규(Phase 6).** 순수(streamlit 의존 0).
  `detect_modules(df, stat_cols, gimmick_cols, target_col)` → 모듈 탐지 dict,
  `module_active(game_profile, key)` → bool, `MODULE_KEYS`, `GATED_MODULES`.
* `modules/symbolic_regression.py` — **신규(Phase 7).** 순수(gplearn+pandas, streamlit/
  엔진 의존 0). `detect_damage_column`, `select_feature_cols`, `infer_formula`,
  `gplearn_available`, `_program_to_infix`(gplearn prefix 트리 → infix).

## run_simulation 시그니처 (Phase 6·7에서 무변경)

```python
run_simulation(ally_instances, enemy_instances, max_turns=100,
               combat_flow=None, speed_stat=None, sys_stats=None,
               global_damage_formula=None, silent=False, action_registry=None,
               turn_manager_cls=None, win_condition=None, stochasticity=None,
               resource_module=None, spatial_module=None, range_stat=None,
               move_stat=None, deck_module=None)
```
`run_monte_carlo`도 spatial/range/move/deck 동일 수용. 엔진은 Phase 6·7에서 전혀
수정되지 않음.

## 엔진 액션 파이프라인

키: `PASSIVE_START → STAT_CALC → MOVE → TARGET_SELECT`(피벗) → `DAMAGE_CALC →
ELEMENT_MULT → CRIT_CALC → APPLY_DAMAGE → ON_HIT → DEATH_CHECK`. `MOVE`/`TARGET_SELECT`
누락 시 자동 삽입. 모듈은 직교 조합형, default=identity(미선언 시 현행 100% 동일).

# 완료된 작업

## 이전 세션 (Phase 1~5)
Action Registry 분리, Win Condition 추상화, Resource System(다중자원·실드·damage_type
라우팅), 엔진 추출(step6 → engine.py), Spatial(좌표·사거리·이동), 턴 실행기 추출,
Deck 엔진. 전부 클린룸 회귀 통과.

## 이번 세션 — Phase 6 (Auto Game-Type Detection) — 완료·검증
탐지가 UI를 구동: Step 2 매핑 직후 컬럼 분석 → 활성 모듈 셋 제안 → `game_profile`
저장 → Step 6의 자원/공간/덱 UI 섹션 게이팅.
- `game_profile` 구조: `{'signature':..., 'detection':{module:{detected,confidence,
  evidence,hints}}, 'overrides':{resource/spatial/deck:'auto'|'on'|'off'}}`.
- `module_active`: override on/off, 아니면 detection.detected. game_profile None이면
  True(전체 표시 폴백).
- 탐지 모델: 구조적 강신호(좌표쌍·범주형 damage_type)만 detected=True. 약신호는
  hints만. 덱/확률은 detected 항상 False.
- step2: `_render_game_profile_panel` + 탐지 블록(else 분기 끝). step6: 게이팅 불리언
  + 자원/공간/덱 `if`/`else` 게이팅 + `spatial_module_val` 조건부.
- 1차 납품에서 step6 변경 5/6 누락(→NameError) → 앵커-구간 통째교체식 교정 프롬프트로
  바로잡음. 클린룸 회귀 detection.py 24/24, 라이브 확인 완료.

## 이번 세션 — Phase 7 (Damage Formula Symbolic Regression) — 완료·검증
전투로그에 데미지 컬럼이 있으면 gplearn 기호 회귀로 `damage ≈ f(스탯)` 자동 추측.
- `symbolic_regression.py` 신규. function_set는 add/sub/mul/div 한정(엔진 eval 호환).
  gplearn prefix 트리 → infix 변환, 변수명 소문자화, 후보별 eval_safe 플래그.
- step2 Live Formula Validator 옆 "🔮 공식 자동 추측" 버튼(하이브리드: 데미지 컬럼
  탐지 시 활성, gplearn 미설치/컬럼 없음 시 안내). 공식 적용은 `_sr_apply` on_click
  콜백(위젯 키 인라인 수정 시 Streamlit 예외 → 콜백 필수).
- `requirements.txt`에 `gplearn` 추가. `n_jobs=1` 고정.
- 클린룸 회귀 21/21(gplearn 비의존 로직 + prefix→infix mock). gplearn 실연동은
  샌드박스 PyPI 차단으로 미검증 → 사용자 로컬에서 라이브 확인 완료(작동).

# 현재 상태 — 검증 마일스톤 진행 중

로드맵 번호 Phase(1~7)는 전부 끝남. 그러나 이번 세션에 **초기 3-Layer 설계도** 대비
중대한 공백이 드러남:

## 3-Layer 설계도 vs 현 상태
- L1 Universal Core (Turn Manager/Participant Registry/Event Broadcaster/State
  Container/Log Emitter) — ~80%. Participant 4슬롯 고정, State Container 임의
  key-value 미완.
- L2 Pluggable Modules (Resource/Targeting/Action Registry/Win Condition/Phase
  Sequence) — ~75%. Targeting 분산, `_PHASE_TO_EVENT` 하드코딩.
- **L3 Game Plugins (RPG/TCG/SRPG 플러그인, 사용자 추가 가능) — ~5%, 사실상 부재.**
  `game_profile`은 "모듈 on/off dict"일 뿐 Plugin 추상화가 아님.
- 결과: Phase 6·7은 설계도상 "플러그인 조합 추천"·"플러그인별 SR"이었으나 L3가 없어
  모듈 레이어로 떨어짐. Phase 7도 RPG 데미지 공식만(TCG/SRPG SR 미구현).
- 하드코딩(element_chart 6속성·4슬롯 파티·액션 파싱 사전)이 안 없어진 이유: 그 설정이
  살 집(L3 Plugin)이 없어서 엔진 코어에 잔존.

## 검증 마일스톤 — 포켓몬式 known-answer 실험
실제 게임으로 도구를 처음 검증 중. 워크스페이스 `검증_포켓몬/` 폴더:
- `pkmn_ref.py` — 포켓몬 Gen6+ 전투 참조 구현(정답). 데미지 공식·18타입표·크리/난수·
  속도턴순·HP승패. 오리지널 크리처 + 정식 메커니즘. 검증 11/11 통과.
- `pkmn_battle_log.csv` (5000행) — 크리처-per-전투, ML/시뮬/Validation용.
- `pkmn_attack_log.csv` (8000행) — per-attack(Damage 컬럼), Phase 7 SR용.
- `검증_정답지_측정계획.md` — 정답·실행절차·채점표·사전예측.

### 1차 검증 결과 (사용자 라이브 실행)
- **Run A — Phase 7 SR: 실패.** 후보 R² 0.20/0.13/0.09, 공식 비대(복잡도 313).
  base 공식 구조 미회수. 원인: 포켓몬 데미지 분산은 범주형 곱셈 modifier(타입상성
  0~4×·STAB·크리·난수)가 지배 → 숫자전용 gplearn이 ~20%만 설명. (사전 예측 R² 0.5~0.8
  은 빗나감 — 실제가 더 심함.) → confound 없는 깨끗한 결과.
- **Run B — Validation 26%:** 낮으나 confounded — 공식란에 자리표시 `attack`만 입력된
  상태로 측정됨. best-effort 공식으로 재측정 필요.
- 부수: 로그의 단일타입 Type2에 `"None"` 문자열을 썼는데 pandas가 `"None"`을 기본
  NA로 취급 → 가짜 결측치 경고(imputation이 되채워 분석엔 무해). 재실행 시 안전
  토큰(`Mono`)으로 로그 재생성 필요.

# 다음 작업 — 미결정 (사용자 선택 대기)

검증 1차 데이터는 "표현력/L3 보강 필요"를 강하게 가리킴(실제 JRPG 핵심인 타입상성·
STAB을 도구가 역설계도 복제도 못 함). 둘 중 택1:
- (a) Run B를 깨끗하게 마저 — 안전토큰 로그 재생성 + best-effort 공식 Validation
  재측정 + ML 프로파일링 확인 → 채점표 완성, 슬라이딩 스케일 개입량 실측.
- (b) Run A로 충분(SR 0.20이 결정적) → 바로 L3/표현력 설계 논의.
(이전 어시스턴트는 (a) 권장.)

이후 큰 방향: L3 Plugin 레이어 구축(블루프린트 키스톤) vs L2 표현력 보강(자원 소비·
효과 카드) vs descope(모듈 도구 착지). 검증 결과로 결정.

# 향후 로드맵 / 보류

L3 Plugin 추상화 + 코드 escape-hatch + Phase 6·7 플러그인 인지형 retrofit. 표현력:
ability cost(자원 소비), 효과 카드 + 작성 UI, 자원 역할 아키타입 확장, 캐릭터별
개별 덱, 카드 플레이 AI 고도화(현재 그리디), 비대칭/혼합전. Phase 7 확장: 범주형
modifier(타입·STAB)를 다루는 SR.

# 하드코딩 제약사항 (현황)
* `element_chart` 6속성 + 1.5/0.5 배율 — 미해결(engine.py). 검증서 포켓몬 18타입에
  명백히 부딪힘.
* 액션 파싱 사전(한/영) — 미해결. `_PHASE_TO_EVENT` — 미해결.
* 파티 슬롯 `range(4)` 고정 — 미해결.
* ML 휴리스틱(타겟 추론·이상치 5%·LR 샘플링 5000) — 미해결.
* 무브별 위력 — 엔진의 단일 `global_damage_formula`는 캐릭터 스탯 식이라 "무브마다
  다른 위력/타입"을 한 식에 못 담음(검증서 드러난 표현력 구멍).

# 검증 방법론 (필독)

* 검증 샌드박스(bash) 마운트 불안정 — 이번 세션에 악화. 큰·수정된 파일을 truncation
  하거나 **stale 서빙**(옛 버전). `wc`·`py_compile`이 가짜 에러를 냄(에러 줄이 파일
  끝 너머면 truncation 확정). step6 전체 py_compile은 stale로 불가능했음.
* 신뢰 가능 경로: `Read`/`Grep` 파일 툴은 실제 파일을 정확히 읽음. bash는 작은·신규
  파일엔 OK.
* 우회법(이번 세션 확립): 검증 코드/참조 구현을 bash heredoc으로 샌드박스 로컬
  `/tmp`에 직접 작성하면 마운트를 안 거쳐 안정적. 클린룸 회귀는 `/tmp`에서 실행.
* gplearn은 샌드박스 PyPI 차단(403)으로 설치 불가 → SR 실연동은 사용자 로컬 검증.
* UI(step2/step6)는 Streamlit 런타임이라 헤드리스 불가 → 정적 코드 정독 + (가능하면)
  py_compile + 사용자 라이브 스크린샷.
* 안티그래비티 re-indent 지시는 신뢰도 낮음 → 큰 블록은 "앵커 2줄로 구간 식별 후
  통째 교체" 방식 + 교체 블록을 미리 격리 py_compile.

# 검증 회귀 베이스라인 (엔진용 — Phase 6·7에서 무변경)
1v1, 공식 `phys_power - target_armor_class`, `DEFAULT_COMBAT_FLOW`, 전원 `Active_Cast`/
`Single_Target`. 공격자 Vit500/Phys100/Arm30/Spd50. NoVariance: lopsided(적 Vit400/
Phys70/Arm30/Spd40) 데미지총량 620.0 / near-even(적 Vit500/Phys100/Arm33/Spd49)
1026.0. 공간/덱/SR 미사용 시 불변.

# 사용자 선호
* 짧고 직접적인 답변(불필요한 호들갑/사과 X). 마크다운 헤더 적당히, 코드/표 활용.
* 단계적 진행(Phase 단위 분할 후 검증). 큰 작업 착수 전 설계 논의 선호.
* 정직한 평가(이론적 한계·안티그래비티 품질 문제·설계 약점·예측 빗나감 솔직하게).
* 사용자가 아키텍처 통찰을 자주 제시함 — 진지하게 반영할 것.

# 작업 패턴 / 교훈
* 안티그래비티 납품물은 항상 코드 직접 읽어 검증 → 변경 지점 grep → 정독 → 클린룸 회귀.
* 신규 순수 모듈은 프롬프트 작성 전 미리 작성·클린룸 검증한 뒤 검증된 코드를 프롬프트에
  verbatim 임베드(detection.py·symbolic_regression.py 둘 다 이 방식 — 성공적).
* Streamlit 위젯 키는 콜백에서만 안전하게 수정(인라인 대입 시 예외).
* 검증 마일스톤(known-answer 통제 실험): 룰 공개 게임을 참조 구현 → 로그 생성 → 도구가
  로그만 보고 역설계 → 정답과 대조. 정답을 알므로 충실도 정밀 측정.

# 이번 세션 생성 파일 (워크스페이스)
`Phase6_AutoDetection_프롬프트.md`, `Phase6_교정_step6게이팅_프롬프트.md`,
`Phase7_SymbolicRegression_프롬프트.md`, `검증_포켓몬/`(pkmn_ref.py, 2 CSV, 정답지).

# 테스트 CSV
`universal_test_log.csv`(5000행, 공간/덱/데미지 컬럼 없음 → 신규 모듈 default=identity)
+ `검증_포켓몬/`의 포켓몬 로그 2종.

---
위 컨텍스트를 숙지하고, 다음 지시(검증 Run B 마무리, 또는 L3/표현력 설계 논의)를 기다린다.
