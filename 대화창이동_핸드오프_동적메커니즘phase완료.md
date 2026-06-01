# 대화창 이동 핸드오프 — 동적 메커니즘 phase (PR-A~G) 완료

새 대화창에 이 문서를 붙여넣고, 직전 핸드오프(`대화창이동_핸드오프_D5완료_표현력보강진입.md`)와 함께 읽어라. 본 문서는 그 위에서 진행된 동적 메커니즘 phase의 결과를 기록한다. 역할·제약·방법론은 직전 핸드오프 그대로다(코드 직접 수정 금지·Antigravity 프롬프트 산출·검증 의무·시간 추정 금지·시연 언급 금지·도구 위치 과대표현 금지·말투 prose 우선).

## 0. 이번 phase에서 한 일 — 7개 PR + 2개 설계안

동적 차원의 "자리"를 만들고 그 위에 메커니즘 3종 + 전략 결정 1종을 얹었다. 모두 납품·검증 완료.

설계안 두 건이 워크스페이스 루트에 있다. `동적메커니즘_hook인프라_설계안.md`(hook 인프라 + Leftovers 첫 PoC 결정), `전략의사결정_무브효과_설계안.md`(전략 모델은 무브 효과 경로가 선행이라는 정찰 결론 + PR-E/F 범위).

납품된 Antigravity 프롬프트(워크스페이스 루트)와 각 내용은 다음과 같다. `동적메커니즘1_Leftovers_프롬프트.md`(PR-A: executor pre/per/post 3슬롯 일반화 + ON_TURN_END 회복 액션, turn_manager 2곳·engine 6곳). `동적메커니즘1_Leftovers_PR-B_부착UI_프롬프트.md`(PR-B: step2 메커니즘 부착 expander, 기믹 컬럼 값 기반 부착). `동적메커니즘2_상태이상_프롬프트.md`(PR-C: ON_STATUS_TICK 턴 종료 데미지, ON_TURN_END 슬롯 재사용 증명). `동적메커니즘3_Protean_프롬프트.md`(PR-D: 새 per-target hook ON_MOVE_USE + current_type + STAB 리더 current_type 우선). `동적메커니즘4_무브효과_프롬프트.md`(PR-E: ON_MOVE_EFFECT + game_config['move_effects']로 active_states boost 부여). `동적메커니즘5_전략정책_프롬프트.md`(PR-F: _act_move_select에 setup_first 정책 분기). `동적메커니즘6_무브효과정책UI_프롬프트.md`(PR-G: step2에 무브 효과 + 정책 입력 UI, _gc에 move_effects·move_policy 저장).

## 1. 엔진에 생긴 동적 인프라 (현재 상태)

engine.py 액션 파이프라인에 hook이 늘었다. 기존 11개 + 신규: post-target 슬롯(executor 3슬롯 일반화, turn_manager.StandardTurnExecutor), ON_TURN_END(_act_turn_end_heal·_act_status_tick), per-target ON_MOVE_USE(_act_move_use, Protean), ON_MOVE_EFFECT(_act_move_effect, 무브 효과). `_POST_LEVEL_KEYS = {"ON_TURN_END", "ON_STATUS_TICK"}`, `_TARGET_LEVEL_KEYS`에 ON_MOVE_USE·ON_MOVE_EFFECT 추가됨. 각 hook은 run_simulation 흐름에 자동 삽입된다.

game_config에 새 키가 늘었다 — `mechanisms`(leftovers·status·protean 부착 spec, 기믹 컬럼 값 기반), `move_effects`(무브이름→boost 리스트), `move_policy`("setup_first"). 모두 미설정 시 no-op이라 기존 동작 회귀 0.

`_act_move_select`에 setup_first 정책 분기가 붙었다(movepool 가드 직후·타겟 결정 직전). 기본은 그리디 유지.

current_type는 instance 필드(Protean이 set, STAB 리더가 read). 별도 초기화 불필요(.get 사용).

## 2. 정직한 위치 (갱신)

직전까지 "시뮬레이터의 뼈대 + 정적 데미지 계산기 수준의 채움 + 동적 차원 자리 부재"였다. 지금은 동적 차원의 자리가 생겼고 메커니즘 3종 + 무브 효과 + 첫 전략 결정(setup_first)이 작동한다. hook 아키텍처가 두 종류의 삽입점(턴 종료 post, 무브 사용 per-target)에서 작동하고 동적 상태가 정적 데미지 모델(STAB)로 되먹임됨이 실증됐다.

그러나 여전히 부분 구현이다. 교체(switch) 모델은 자리 자체가 부재다(per_battle_backtest가 전원 동시 필드, 트레이너-벤치 개념 없음). Protean은 공격 STAB만 동적화하고 방어 타입 변경은 미구현. 전략 정책은 룰 기반 단일 패턴(setup 1회 후 데미지)이고 다회 스택·HP 조건·ML은 미구현. 우선도 무브·메가·Substitute·Trace는 미착수. 메커니즘이 정확도(합성 데이터 62~67% 권역)에 주는 영향은 통제 A/B 미측정. 외부 실제 PS replay 수치는 여전히 미측정. "Pokemon 복제"가 아니라 "Pokemon 정적 모델 일부 + 동적 메커니즘 3종 + 부분 전략" 수준임을 흐리지 마라.

## 3. 검증 상태

7개 PR 전부 Read(진실 출처)로 byte-exact 적용 확인, Grep 마커 확인, 하니스 단위검증(각 PR마다 4~8개 케이스), 라운드트립 MD5, replace 블록 컴파일을 통과했다. Leftovers(PR-A)는 라이브 단일 전투에서 회복 로그 발화 + 산술(172×0.0625=10.75→10) 확인까지 마쳤다.

PR-B UI도 라이브 렌더 확인됨. 나머지 메커니즘의 라이브 발화는 부착 대상 캐릭터가 살아서 해당 hook을 맞아야 보인다(Leftovers 확인 시 부착 캐릭터가 1턴에 죽으면 회복 로그가 안 보였던 사례 참고 — 결함 아님).

## 4. 방법론 — 이번 phase에서 강화된 함정

bash mount silent truncation이 이번에 심했다. Antigravity가 수정한 직후 파일(engine.py·turn_manager.py·step2)을 bash가 tail-truncate해서 서빙했다(OneDrive→mount 동기화 지연). 그 결과: bash로 현재 파일 전체 읽기 불가, import 시 거짓 SyntaxError, 클린룸 전체 컴파일·실제 run_simulation 통합 실행 모두 샌드박스에서 막힘. Read 도구와 Grep 도구는 진짜 현재 파일을 보므로 검증은 그 둘로 했다.

대응 패턴(다음에도 그대로): find 앵커 유일성은 Grep으로 확인(진짜 파일). 새 코드 로직은 outputs/ 하니스에서 단위검증 + py_compile. replace 블록은 최소 컨텍스트로 컴파일. .md 전사 무결성은 라운드트립 MD5. 납품 후엔 Read로 변경 구역 정독 + Grep 마커. 클린룸 전체 컴파일은 mount가 동기화되면 가능하나 의존하지 마라.

outputs/에 이번 phase 하니스·빌더가 다 있다 — verify_leftovers/status/protean/moveeffect/policy.py, build_*_prompt.py, verify_delivery.py.

## 5. 다음 단계 — 최종목표 기준

최종목표(턴제 게임을 사용자 개입으로 복제)의 남은 최대 구조적 격차는 교체(switch) 모델이다. 현재 per_battle_backtest는 한 전투를 N행으로 잘라 전원을 동시에 필드에 올리므로 트레이너-벤치(active/bench) 구분이 없다. 교체가 없으면 Pokemon 전투 흐름 전체가 재현되지 않고, Trace(진입 시 특성 복사)·교체 전략·메가 타이밍 결정도 substrate가 없다. 이건 전투 모델 재설계라 큰 작업이고 새 대화에서 깨끗이 착수하는 게 좋다.

그 전 더 작은 후속들: 전략 정책 다회 스택(Calm Mind N회)·조건 확장, Protean 방어 타입, Substitute(APPLY_DAMAGE 흡수 — resource.py 라우팅 활용 정찰 필요), 우선도 무브(turn_manager 2단계 턴 모델 — 정렬-후-행동 구조 변경 필요), 메커니즘 정확도 통제 A/B 측정(같은 설정에서 부착 on/off 백테스트). 외부 데이터 어댑터(PS replay HTML→wide CSV, §4-4)도 미착수.

## 6. 파일 위치 (이번 phase 추가분)

워크스페이스 루트에 위 7개 프롬프트 .md + 2개 설계안 + 본 핸드오프. modules/engine.py·turn_manager.py·step2_system_definition.py가 PR-A~G로 수정됨. outputs/에 하니스·빌더. 나머지 위치는 직전 핸드오프 §7 그대로.
