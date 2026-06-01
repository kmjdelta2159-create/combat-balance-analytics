# 대화창 이동 핸드오프 — 교체 모델(S1~S5) + 우선도(P1~P2) phase 완료

새 대화창에 이 문서를 붙여넣고, 직전 핸드오프(`대화창이동_핸드오프_동적메커니즘phase완료.md`)와
함께 읽어라. 본 문서는 그 위에서 진행된 교체 모델 + 우선도/행동순서 phase의 결과를 기록한다.
역할·제약·방법론은 직전 핸드오프 그대로다(코드 직접 수정 금지·Antigravity 프롬프트 산출·검증
의무·시간 추정 금지·시연 언급 금지·도구 위치 과대표현 금지·말투 prose 우선).

## 0. 이번 phase에서 한 일 — 설계안 2건 + PR 7건

핸드오프 §5가 "최종목표 기준 남은 최대 구조적 격차"로 지목한 교체(switch) 모델에 착수했고,
이어 다음 구조 격차인 우선도/행동순서 일부를 처리했다. 사용자가 갈래 선택 시 "항상 최종목표를
기준으로" 결정하라고 위임했고, 그 기준으로 진행했다. 모두 납품·검증 완료.

설계안 두 건이 워크스페이스 루트에 있다. `교체모델_설계안.md`(액티브/예비 회전을 게임 중립
프리미티브로 — game_config 구동, 게임명 하드코딩 0, 미설정 시 전원-동시 회귀 0), `우선도턴모델_
설계안.md`(결정-후-해결의 위험을 사용자 개입 주도 프리소트로 우회 — 우선도는 사용자가 공급하는
무브 데이터, 엔진은 정렬만).

납품·검증된 Antigravity 프롬프트(워크스페이스 루트). `교체모델_PR-S1_프롬프트.md`(active_count
설정 + on_field/roster_idx 부여 + 턴 루프 on_field 게이팅 + `on_active_faint="replace_from_reserve"`
강제 교체 + `_resolve_faint`; engine 참가자 초기화·turn_manager 4곳). `교체모델_PR-S2_프롬프트.md`
(타겟팅을 상대 on_field로 제한 + "예비 포함 전멸일 때만 종료"로 종료 판정 교정; engine
`_act_target_select`·`_act_move`). `교체모델_PR-S3_프롬프트.md`(ON_SWITCH 진입 hook 인프라 +
`just_switched_in` 플래그; engine 3곳·turn_manager 1곳). `교체모델_PR-S4_프롬프트.md`(자발적 교체
액션 + `hp_threshold` 룰 정책 + 라운드 행동자 스냅샷; engine 2곳·turn_manager 1곳). `교체모델_
PR-S5_UI_프롬프트.md`(step2에 active_count·on_active_faint·switch_policy 입력 UI + _gc 저장; step2
2곳). `우선도턴모델_PR-P1_프롬프트.md`(move_extraction에 무브 priority 필드 탐지·추출, 기본 0 +
step2 배선; move_extraction 5곳·step2 1곳). `우선도턴모델_PR-P2_프롬프트.md`(교체-우선 행동순서 —
`_will_voluntary_switch` read-only 예측기 + `action_priority` 콜백 + acting_units 안정 재정렬;
engine 2곳·turn_manager 3곳).

## 1. 엔진에 생긴 인프라 (현재 상태)

game_config에 새 키가 늘었다 — `active_count`(팀별 액티브 수, 미설정=팀 크기=전원-동시),
`on_active_faint`("replace_from_reserve"=예비 자동 등장 / 미설정·기타=무동작; "team_loss"는 미구현
후속), `switch_policy`({"type":"hp_threshold","threshold":0.25} 형태), `switch_priority`(교체 우선
티어, 기본 6). 모두 미설정 시 no-op이라 회귀 0.

participant(엔진 인스턴스)에 새 필드 — `on_field`(bool), `roster_idx`(팀 내 순서), `just_switched_in`
(교체 진입 1회 hook 플래그). engine run_simulation의 "1b" 블록이 active_count 기준으로 on_field를
부여한다.

`SequentialTurnManager`(turn_manager.py)에 `on_active_faint`·`action_priority` 파라미터가 추가됐다.
`run()`은 라운드마다 (1) participants 속도 정렬, (2) 라운드 시작 on_field 스냅샷 `acting_units`,
(3) `action_priority` 콜백으로 안정 재정렬(교체 예정 유닛을 앞으로; 동순위는 속도순 유지),
(4) 유닛별 실행, (5) 각 행동 후 `_resolve_faint`(on_active_faint 규칙)로 죽은 액티브를 예비로 교체,
(6) win_condition 판정. `_resolve_faint` 메서드가 추가됐다.

engine 액션/함수 신규·변경 — `_will_voluntary_switch`(read-only 교체 예측, 정렬용),
`_maybe_voluntary_switch`(자발적 교체 수행, `_act_target_select` 안에서 호출 — 교체 시 targets 비워
공격 생략·턴 소모), `_act_on_switch`(ON_SWITCH hook, just_switched_in 소비 + 진입 이벤트 브로드캐스트,
현재 무동작 슬롯; 레지스트리 등록 + 흐름 맨 앞 자동삽입), `_act_target_select`(타겟을 상대 on_field로
제한 + team_alive 종료 판정 + 자발적 교체 분기), `_act_move`(이동 대상 on_field 제한). run_simulation
manager 생성부에 `_switch_action_priority` 클로저 + `action_priority` kwarg.

move_extraction — `_PRIORITY_HINTS` + `detect_move_columns` 반환에 priority + `extract_moves`에
priority_col 파라미터·무브 dict의 priority 필드(기본 0). step2가 감지된 우선도 컬럼을 전달.

step2_system_definition — 메커니즘 expander에 교체 설정 위젯 4개(액티브 수·사망 처리·교체 정책·HP
임계) + 시작 버튼 핸들러에서 _gc로 저장.

## 2. 정직한 위치 (갱신)

직전까지 "시뮬레이터의 뼈대 + 정적 데미지 계산기 + 동적 메커니즘 3종(Leftovers·상태이상·Protean)
+ 무브 효과 + 부분 전략(setup_first)"이었다. 지금은 거기에 **교체 모델이 사용자 개입(step2 폼)으로
켜져 turn-by-turn으로 작동**한다 — 액티브/예비 구분, 강제 교체(사망→예비 등장), 자발적 교체(HP 임계),
교체 진입 hook(ON_SWITCH), 그리고 교체가 공격보다 먼저 해결되는 순서까지. 라이브 단일 전투 로그로
S1~S5 전체가 실증됐다(액티브 사망→예비 등장→진입 hook→스냅샷으로 진입 유닛 다음 라운드 행동→
자발적 교체→예비 포함 전멸 시 종료). 핸드오프가 짚은 "최대 구조 격차"인 교체가 메워졌다.

그러나 여전히 부분 구현이다. 무브 우선도 필드(P1)는 들어갔지만 **잠복 상태**다 — 그리디 AI가
우선도 무브를 거의 안 골라(우선도 무브는 보통 저위력), 선택 무브 우선도가 거의 0이라 정렬에 영향이
없다. 무브 우선도가 *행동 순서*에 반영되려면 라운드 시작에 각 유닛의 타겟·무브 선택을 미리 돌리는
"결정 프리패스"(연기한 결정-후-해결의 경량판)가 필요하다 — 저위험 지름길이 없다. ON_SWITCH 진입
효과는 "진입 유닛의 다음 턴 시작"에 발화하는 근사이고(진입 즉시 아님), 진입 유닛이 자기 턴 전에
죽으면 hook이 안 뜬다. Trace·메가·Substitute·우선도 무브의 실제 순서 효과·멀티 액티브(더블+)
충실도는 미착수. "Pokemon 복제"가 아니라 "Pokemon 정적 모델 + 동적 메커니즘 일부 + 교체 모델 +
부분 전략" 수준임을 흐리지 마라.

## 3. 검증 상태

7개 PR 전부 Antigravity 적용 후 Read(진실 출처)로 변경 구역 byte-exact 확인, Grep 신·구 마커 확인,
하니스 단위검증(각 PR 4~5케이스), 라운드트립 MD5, 클린룸 컴파일(파편을 def/while 컨텍스트로 감싸)
통과. 곁가지 수정 0건. S1~S5는 사용자가 실제 앱에서 돌린 라이브 전투 로그로 end-to-end 발화까지
확인했다(P1~P2는 라이브 미확인 — P2 교체-우선 정렬은 switch_policy 설정 전투에서 확인 권장).

## 4. 방법론 — 이번 phase 확인·추가 사항

bash mount silent truncation이 이번에도 나왔다. engine.py가 ~1186줄로 커져 bash로 읽으면 L908
부근에서 `"Enem`처럼 중간에 끊겨 거짓 SyntaxError를 낸다. Antigravity가 방금 쓴 직후엔 mount 동기화
지연으로 모듈 import가 hang하기도 한다. **Read 도구가 유일한 진실 출처**고, 검증은 Grep 마커 +
변경 구역 Read 정독 + outputs/ 하니스 + 라운드트립 MD5 + 클린룸 컴파일(파편 wrap)로 한다. 갓 쓴
모듈의 샌드박스 실행에 의존하지 마라 — 라이브 발화 확인은 사용자가 앱에서 한다.

새로 확인한 제약: **turn_manager는 engine을 import할 수 없다**(engine.py L6가 turn_manager를 import →
순환). 그래서 turn_manager가 engine 로직(무브 선택·교체 판정 등)을 써야 하면 engine이 *콜백으로*
넘긴다(P2의 `action_priority` 예측기가 그 사례; build_ctx도 같은 패턴).

빌더 양식은 그대로다 — outputs/에 verify_*.py 하니스 + build_*_prompt.py. find/replace를 string 상수로
박고, .md 쓰기→되읽기→블록 재추출→MD5 대조, 클린룸 컴파일은 함수-본문 파편을 `def _w(...):` 또는
`while True:` 컨텍스트로 들여쓰기 맞춰 감싼다. FIND 앵커는 Grep으로 유일성 확인(중복 라인은 더 넓은
컨텍스트로 좁힘 — 예: `resource_module=resource_module,`가 2곳이라 `broadcast_phase_event=...` 포함
블록으로 구분).

outputs/에 이번 phase 하니스·빌더가 다 있다 — verify_switch_s1~s4·s5ui, verify_priority_p1~p2,
build_switch_s1~s5ui_prompt, build_priority_p1~p2_prompt.

## 5. 다음 단계 — 사용자 결정 대기 중인 갈래

직전에 사용자가 "니 판단대로"라 했고, 보조자가 정정 보고를 한 직후에서 멈췄다. 정정 내용: "우선도-
인지 무브 정책"은 단독으로 무의미하다 — P2 예측기가 교체 여부만 정렬에 반영하고 무브 우선도는 안
넣으므로, 정책이 우선도 무브를 골라도 순서가 안 바뀌어 효과가 없다. 무브 우선도를 진짜 작동시키려면
결정 프리패스가 필요하고, 저위험 지름길이 없다.

그래서 사용자 앞에 놓인 갈래는 둘이다.

(1) **무브 우선도 결정 프리패스** — 라운드 시작에 각 on_field 유닛의 타겟·무브 선택을 read-only로 미리
돌려 선택 무브의 우선도를 뽑고 P2 정렬에 합친다. P-트랙(P1 잠복 필드)을 살린다. 중위험(그리디 선택
로직을 공유 순수 함수로 추출, 회귀 0을 하니스 + 합성 백테스트로 증명; 싱글에서 정확). turn_manager는
engine을 import 못 하니 예측기는 engine 콜백으로.

(2) **Trace + 진입 타이밍 교정** — ON_SWITCH 위에 첫 실제 동적 메커니즘(진입 시 상대 액티브의 속성
복사)을 얹고, 진입 hook을 "진입 즉시"(해결 시점)로 당겨 현재 "다음 턴" 근사를 해소한다. S-트랙을
닫는다. 자기완결적, 중위험.

둘 다 중위험이고 "저위험 빠른 승리"는 없다. 최종목표(충실도) 기준으로 사용자가 고른다. 그 외 더 뒤의
후보: 우선도 입력 UI(switch_priority·priority 컬럼 매핑, S5와 동일 양식), 멀티 액티브(더블+) 충실도,
메가 진화·Substitute, 교체-인식 백테스트 데이터(합성 ref 확장 — §직전 핸드오프대로 순환 주의),
외부 PS replay 어댑터(미착수).

## 6. 파일 위치 (이번 phase 추가분)

워크스페이스 루트에 위 7개 프롬프트 .md + 2개 설계안 + 본 핸드오프. modules/engine.py(~1186줄)·
turn_manager.py·move_extraction.py·step2_system_definition.py가 S1~P2로 수정됨. outputs/에 하니스·빌더.
나머지 위치는 직전 핸드오프 §6 그대로.

상태 요약. 교체 모델(S1~S5) + 우선도 일부(P1 필드·P2 교체-순서) 납품·검증 완료. 교체는 사용자 개입으로
켜져 라이브로 작동한다. 무브 우선도는 잠복(결정 프리패스 필요), ON_SWITCH 진입 타이밍은 근사, Trace·
메가·멀티액티브는 미착수. 현재 위치는 §5의 두 갈래(무브 우선도 결정 프리패스 / Trace+진입 타이밍)
사용자 결정 대기. 시간 추정 던지지 마라. 시연 언급 금지. 도구 위치 과대표현 금지. 단계별 보고 +
사용자 결정 받기.
