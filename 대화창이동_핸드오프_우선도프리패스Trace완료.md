# 대화창 이동 핸드오프 — 우선도 결정 프리패스(P3a~P4) + Trace·진입타이밍(S6~S8) 완료, 해저드 설계 진입

새 대화창에 이 문서를 붙여넣고, 직전 핸드오프(`대화창이동_핸드오프_교체우선도phase완료.md`)와 함께 읽어라. 본 문서는 그 위에서 진행된 무브 우선도 결정 프리패스 + Trace/진입 즉시 타이밍 phase의 결과를 기록하고, 다음 갈래(해저드)의 설계까지 올려둔다. 역할·제약·방법론은 직전 핸드오프 그대로다(코드 직접 수정 금지·Antigravity 프롬프트 산출·검증 의무·시간 추정 금지·시연 언급 금지·도구 위치 과대표현 금지·말투 prose 우선·갈래는 항상 최종목표 기준으로 사용자에게 묻고 결정받기).

## 0. 이번 phase에서 한 일 — 설계안 3건 + PR 6건(전부 적용·검증)

직전 핸드오프 §5의 두 갈래를 둘 다 닫았다. 갈래 1(무브 우선도 결정 프리패스)로 P-트랙을 살리고, 갈래 2(Trace + 진입 즉시 타이밍)로 S-트랙을 닫았다. 그다음 갈래(해저드)는 설계안까지 올리고 사용자 결정 대기.

설계안 세 건이 워크스페이스 루트에 있다. `우선도결정프리패스_설계안.md`(잠복했던 무브 우선도를 살리는 결정 프리패스 — 선택 로직을 공유 순수 코어 1벌로 만들어 예측=실행 보장), `Trace진입타이밍_설계안.md`(ON_SWITCH 위 첫 진입 메커니즘 Trace + 진입 hook을 "다음 턴"→"진입 즉시"로 교정), `해저드_설계안.md`(진입 데미지; 정적 H1 vs 무브-설치 동적 H2, H1 권고).

납품·적용·검증된 Antigravity 프롬프트(워크스페이스 루트):
`우선도결정프리패스_PR-P3a_프롬프트.md`(engine: 공유 순수 코어 `_candidate_targets`·`_select_move_pure` 추출 + `_act_target_select`·`_act_move_select`를 그 코어 호출로 리팩터 — 행동 byte-동일·회귀 0).
`우선도결정프리패스_PR-P3b_프롬프트.md`(engine: 정렬 클로저 `_switch_action_priority`→`_predict_action_priority` 교체 — 비-교체 유닛이 예측된 무브 priority 반환 + manager kwarg; turn_manager 무변경).
`우선도결정프리패스_PR-P4_UI_프롬프트.md`(step2: 무브 우선도 컬럼 명시 매핑 셀렉트박스 `st.columns(4)`→`5` + switch_priority number_input + `_gc` 저장; 2곳).
`Trace진입타이밍_PR-S6_프롬프트.md`(engine: `_apply_switch_in_effects`(Trace) 추가 + `_act_on_switch` 배선; 타이밍은 "다음 턴" 유지).
`Trace진입타이밍_PR-S7_프롬프트.md`(engine 3 + turn_manager 3: `_fire_switch_in` 통합 함수 + `_maybe_voluntary_switch` 즉시 호출 + turn_manager `on_switch_in` 콜백 배선 + `_resolve_faint`에서 즉시 호출; `just_switched_in` 소비로 이중 발화 방지).
`Trace진입타이밍_PR-S8_UI_프롬프트.md`(step2: Trace 부착 UI, Protean 양식, `_mech_cfg["trace"]`; 저장은 기존 배선 재사용).

## 1. 엔진/턴매니저/step2에 생긴 인프라 (현재 상태)

engine.py(~1265줄).
- `_candidate_targets(char, participants, target_val, spatial_module, attack_range)` — 부작용 없는 타겟 후보 결정(상대 on_field→사거리→태그). `_select_move_pure(char, target, sys_stats, game_config, formula_str)` — 부작용 없는 그리디+setup_first 무브 선택. 둘 다 `_act_target_select`/`_act_move_select`(셸)와 행동순서 예측기가 공유 → 예측=실행 보장.
- `_predict_action_priority(unit)`(run_simulation 클로저, manager에 `action_priority=`로 전달) — 교체 예정이면 switch_priority 티어, 아니면 `build_ctx`+공유 코어로 예측한 무브의 priority 반환. **turn_manager의 스칼라 안정정렬이 (교체 티어 ≫ 무브 우선도) 한 숫자로 "교체 먼저→우선도 무브→속도순"을 처리하므로 turn_manager는 무변경.** 전원 우선도 0 + 교체 미설정이면 정렬 키가 속도만 남아 회귀 0.
- `_apply_switch_in_effects(char, participants, game_config, add_log)`(Trace) — 부착 캐릭터(`mechanisms['trace']`의 gimmick_col/match_value 일치)가 진입하면 상대 on_field 유닛의 타입(상대 current_type 우선, 없으면 `type_col` 기믹)을 `char['current_type']`에 복사 → `_move_stab_multiplier`가 읽어 STAB 되먹임.
- `_fire_switch_in(char, participants, game_config, add_log)` — 진입 즉시 처리 통합: Trace 효과 + ON_SWITCH 이벤트(`_notify_event`에 `{"add_log": add_log}` 전달) + 진입 로그. ctx 비의존이라 자발/강제 교체 양쪽이 호출.
- `_maybe_voluntary_switch`는 진입 직후 `_fire_switch_in(incoming, participants, gc, ...)` 즉시 호출(구 `just_switched_in=True` 제거). `_act_on_switch`는 이제 다음-턴 fallback(즉시 처리를 놓친 진입용).
- run_simulation manager 생성부에 `on_switch_in=lambda _char,_parts,_alog: _fire_switch_in(_char,_parts,game_config,_alog)` 전달.

turn_manager.py.
- `SequentialTurnManager.__init__`에 `on_switch_in=None` 파라미터 + `self._on_switch_in`. `_resolve_faint`의 예비 승급 루프가 `self._on_switch_in is not None`이면 즉시 콜백 호출 + `just_switched_in=False`, 미전달이면 `just_switched_in=True`(다음-턴 fallback, 회귀 0). action_priority 정렬(스칼라 안정정렬)은 그대로.

step2_system_definition.py.
- 무브 컬럼 매핑에 "우선도 컬럼" 셀렉트박스(`ui_move_priority_col`, 기본=자동 탐지값) — `extract_moves`에 명시 전달. 교체 모델 UI에 "교체 행동 우선도 티어"(`ui_switch_priority`, 기본 6, ≠6일 때만 `_gc["switch_priority"]` 저장). 메커니즘 부착 expander에 Trace 체크박스+기준 기믹 컬럼+값+복사할 타입 컬럼(`_mech_cfg["trace"]`={gimmick_col, match_value, type_col}).

game_config 키 흐름: 무브 dict의 priority(P1, 기존 필드)가 이제 정렬에 실제 반영됨(P3b). 신규 `switch_priority`(P4 UI), `mechanisms.trace`(S8 UI).

## 2. 정직한 위치 (갱신)

직전까지 "정적 모델 + 동적 메커니즘 3종 + 무브 효과 + 교체 모델 + 우선도 일부(P1 필드·P2 교체-순서, 무브 우선도는 잠복) + 부분 전략"이었다. 지금은 **무브 우선도가 실제로 작동한다**(P3b 예측 프리패스로 느린 유닛이 우선도 무브로 선행) — 싱글에서 예측=실행 구조 보장. 그리고 **첫 진입형 동적 메커니즘 Trace + 진입 즉시 타이밍**이 라이브로 작동한다(교체 진입 그 시점에 상대 타입 복사→STAB 변화). 교체 모델은 라이브로 사망→예비 등장→진입 효과→정상 종결까지 돈다.

여전히 부분 구현이다. 무브 우선도 **역전 자체의 라이브 실증**은 아직(priority 컬럼 든 데이터로 느린 유닛 선행을 직접 봐야 — 회귀 0 경로만 라이브 확인). 멀티 액티브(더블+)에서는 우선도 예측·Trace "어느 상대 복사" 모두 싱글 가정이라 미보장(검증·외부 PS replay 모두 싱글이라 현재 무관). 해저드는 설계만(미착수). 메가 진화·Substitute·외부 PS replay 어댑터·교체-인식 백테스트 데이터는 미착수. "Pokemon 복제"가 아니라 "Pokemon 정적 모델 + 동적 메커니즘 일부 + 교체 모델 + 작동하는 우선도 + Trace/진입타이밍 + 부분 전략" 수준임을 흐리지 마라.

## 3. 검증 상태

6개 PR 전부 적용 후 Read(진실 출처)로 변경 구역 byte-exact 확인 + Grep 신·구 마커 확인 + 하니스 단위검증(P3a 구·신 15케이스 동일성, P3b 정렬 5케이스, S6 Trace 8케이스, S7 즉시-타이밍 7케이스) + 클린룸 컴파일 + 라운드트립 MD5(또는 .md 직접 write 후 되읽기 대조). 곁가지 수정 0건.

**S-트랙은 라이브 end-to-end 실증 완료** — 사용자 전투 로그에서: 강제 교체(replace_from_reserve)로 예비 등장 시 진입 그 시점에 "타입이 Bug으로 복사됨 (Trace ← E1)" 발화(다음 턴 아님), config 게이팅(부착 유닛만 복사, 미부착은 진입 로그만), 이중 발화 없음, 교착 해소(정상 종결). **P-트랙은 회귀 0 경로만 라이브 확인**(우선도 0→속도순 보존); 우선도 역전 라이브는 priority 컬럼 든 전투 필요(미실증). P4·S8 UI는 라이브 렌더 확인.

주의: P3a 적용 시 `_act_target_select` 주석 한 줄에서 글자 하나("를") 누락 — 주석이라 동작 무관(결함 아님).

## 4. 방법론 — 이번 phase 확인·추가 사항

bash mount silent truncation이 더 심해졌다. engine.py(~1265줄)는 L1175~1187 부근(build_ctx 딕셔너리)에서, turn_manager는 L184 f-string 중간에서 잘려 거짓 SyntaxError(`'{' was never closed`, `unterminated string`)를 낸다. **심지어 outputs/에 갓 쓴 검증 스크립트도 Write→bash 동기화 지연으로 잘려 실행된다.** Read·Grep 도구가 유일한 진실 출처다. 검증은 Grep 마커 + 변경 구역 Read 정독 + outputs 하니스 + 클린룸 컴파일(파편 wrap) + 라운드트립으로 하고, 갓 쓴 모듈/스크립트의 샌드박스 전체 실행에 의존하지 마라.

**새로 굳힌 패턴 — 한글 프롬프트는 .md 직접 작성.** 빌더가 find/replace 블록을 Python 문자열 리터럴로 들고 한글 f-string 삼중따옴표를 만들면 escaping이 반복해서 깨졌다(`'unterminated triple-quoted string'`). 그래서 **프롬프트 .md를 Write 도구로 raw하게 직접 쓰고, 검증은 그 .md를 되읽어 ```python 코드블록(FIND/REPLACE 쌍)을 추출해 실제 소스에 대조**(앵커 유일성 count==1·클린룸 컴파일·치환 후 컴파일)하는 방식으로 전환했다. outputs 스크립트가 잘리면 bash heredoc 인라인 실행으로 우회. S6~S8·P4가 이 방식(verify_*_delivery.py)을 쓴다. P3a/P3b는 구식 빌더(build_priority_p3a/p3b_prompt.py, find/replace string 상수)였고 그건 잘 돌았다 — 한글이 적은 코드 블록은 빌더도 OK, 한글 docstring 많은 블록은 .md 직접 쓰기가 안전.

기존 제약 재확인: turn_manager는 engine을 import 못 한다(순환) → engine이 콜백으로 넘긴다(`action_priority`, `on_switch_in`, `broadcast_phase_event`가 그 사례). 정규식 검증 함정: `spec.get("key")`와 `spec.get("key", default)`를 둘 다 잡게(후자 놓치면 거짓 불일치).

outputs/에 이번 phase 하니스·빌더·검증이 다 있다 — verify_priority_p3a·p3b, verify_trace_s6·s7, build_priority_p3a·p3b·p4_prompt, verify_s6·s7·s8_delivery.

## 5. 다음 단계 — 사용자 결정 대기 중

`해저드_설계안.md`가 올라가 있고 **H1(정적 진입 데미지) vs H2(무브-설치 동적) 사용자 결정 대기**다. 정찰 확인: 데미지는 `apply_delta`/percent-of-max(`_act_status_tick` 패턴)로 진입 유닛에 적용 가능; `_fire_switch_in`은 교체에서만 호출돼 리드는 자연히 면제(Pokemon과 동일); 핵심 난점은 필드(팀) 레벨 상태 substrate 부재(현재 모든 상태가 participant active_states에 산다) — H2(무브 설치)는 그 저장 방식(game_config 런타임 sub-dict vs 별도 battle-state, 병렬 sim 공유 주의)을 새로 정해야 한다. 권고: H1(정적, `_apply_entry_hazard` 헬퍼 + `_fire_switch_in` 호출, engine 한 파일, 회귀 0) 먼저 → 라이브 → H3(부착 UI). H2는 필드-상태 결정과 함께 후속.

그 외 더 뒤 후보: 무브 우선도 역전 라이브 실증(priority 컬럼 든 합성 전투), 멀티 액티브(더블+) 충실도(우선도·Trace의 싱글 가정 해소 — 설계안 §7의 결정-후-해결 깊은 재구조화 자리), 메가 진화·Substitute(APPLY_DAMAGE 흡수, resource.py 라우팅 정찰), 교체-인식 백테스트 데이터(합성 ref 확장 — 순환 주의), 외부 PS replay 어댑터.

## 6. 파일 위치 (이번 phase 추가분)

워크스페이스 루트에 설계안 3건(우선도결정프리패스_설계안·Trace진입타이밍_설계안·해저드_설계안) + 프롬프트 6건(우선도결정프리패스_PR-P3a·P3b·P4_UI, Trace진입타이밍_PR-S6·S7·S8_UI) + 본 핸드오프. modules/engine.py(~1265줄)·turn_manager.py·step2_system_definition.py가 P3a~S8로 수정됨. outputs/에 하니스·빌더·검증. 나머지 위치는 직전 핸드오프 §6 그대로.

상태 요약. 무브 우선도 결정 프리패스(P3a 순수 코어·P3b 예측기·P4 UI)와 Trace+진입 즉시 타이밍(S6 효과·S7 타이밍·S8 UI) 납품·적용·검증 완료. S-트랙은 라이브 end-to-end 실증, P-트랙은 회귀 0 라이브 확인(우선도 역전 미실증). 현재 위치는 해저드 설계안의 H1(정적)/H2(동적) 사용자 결정 대기. 시간 추정 던지지 마라. 시연 언급 금지. 도구 위치 과대표현 금지. Read/Grep이 진실 출처(bash truncation 주의), 한글 프롬프트는 .md 직접 작성. 단계별 보고 + 사용자 결정 받기.
