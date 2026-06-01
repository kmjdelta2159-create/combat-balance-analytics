# Trace + ON_SWITCH 진입 타이밍 설계안 — S-트랙 닫기

## 0. 이 문서의 위치

우선도 트랙(P3a 순수 코어 + P3b 예측기 + P4 UI) 완료 후, "다음" 지침으로 핸드오프 §5의
**갈래 2**에 착수한다. 두 개의 결합된 격차를 닫는다 — (1) ON_SWITCH 위에 첫 *실제* 진입형
동적 메커니즘(Trace: 진입 시 상대 속성 복사), (2) 진입 hook을 현재의 "다음 턴" 근사에서
"진입 즉시"로 당겨 타이밍을 교정. 본 보조자는 코드를 직접 수정하지 않는다 — 정찰 → 설계안
→ 사용자 검토 → 작은 PR 분할 → Antigravity 프롬프트 → 검증 순으로 간다.

## 1. 현재 구조 (정찰 결과, Read 기준)

ON_SWITCH 인프라(S3에서 깔림).
- `_act_on_switch`(engine L837): 이번 턴 행동 캐릭터가 `just_switched_in`이면 진입 이벤트를
  브로드캐스트하고 플래그를 소비하는 **무동작 슬롯**(실제 진입 효과 없음). 게임 중립.
- ON_SWITCH는 흐름 맨 앞에 자동 삽입(engine L1099~1101)돼 매 턴 각 유닛의 pre-target 첫
  액션으로 실행된다. 따라서 진입 효과는 **진입 유닛의 다음 턴 시작**에 발화한다(근사).

`just_switched_in = True`로 세팅되는 교체 수행 2지점.
- `_maybe_voluntary_switch`(engine L318~354): 자발적 교체. `incoming['on_field']=True` +
  `incoming['just_switched_in']=True`. ctx에 participants·game_config·add_log 모두 있음.
- `SequentialTurnManager._resolve_faint`(turn_manager L159~183): 강제 교체(사망→예비).
  예비를 on_field로 올리고 `just_switched_in=True`. **여기엔 game_config·engine 함수가 없다.**

동적 타입(current_type)과 STAB 되먹임.
- `_move_stab_multiplier`(engine L598~611): `char.get("current_type")`가 있으면 그것을
  공격자 타입으로 우선 사용해 STAB 판정. Protean(`_act_move_use`)이 이 필드를 set한다.
  → Trace가 상대 타입을 진입 유닛의 `current_type`에 복사하면 **기존 STAB 기계장치로
  가시적 효과**가 난다(새 경로 불필요, 게임 중립).

메커니즘 설정 패턴(Protean 사례, `_act_move_use` L778). `game_config['mechanisms']['protean']`
spec = `{gimmick_col, match_value}`. 부착 캐릭터의 기믹 컬럼 값이 match_value와 일치할 때만
발동. Trace도 동일 패턴(`mechanisms['trace']`)으로 게임 중립·config 구동.

제약 재확인. turn_manager는 engine을 import할 수 없다(순환). engine 로직을 turn_manager가
써야 하면 engine이 콜백으로 넘긴다(P2의 action_priority, broadcast_phase_event가 그 사례).

## 2. 목표 구조

(2-a) Trace 메커니즘. 진입 효과 핸들러 `_apply_switch_in_effects(char, participants,
game_config, add_log)`를 새로 만든다 — 부작용은 char['current_type'] 설정 + 로그뿐.
`mechanisms['trace']` spec(gimmick_col/match_value)으로 부착 여부를 판정하고, 부착 시
**상대 팀 on_field 유닛의 타입**(상대의 current_type, 없으면 지정 type_col 기믹 값)을 복사해
char['current_type']에 넣는다. 미설정/미부착/상대 없음 시 no-op(회귀 0).

(2-b) 진입 즉시 타이밍. 진입 효과를 교체 수행 시점에 바로 발화시킨다.
- 자발적 교체(engine): `_maybe_voluntary_switch`에서 `incoming['on_field']=True` 직후
  `_apply_switch_in_effects(incoming, ...)` 직접 호출 + `just_switched_in` 소비(즉시 처리됨
  표시).
- 강제 교체(turn_manager): `_resolve_faint`가 engine이 넘긴 `on_switch_in` 콜백을 호출.
  콜백은 game_config를 클로저로 잡아 `_apply_switch_in_effects`를 부른다. 콜백 미전달 시
  no-op(회귀 0).

타이밍이 즉시로 당겨지면 `_act_on_switch`(다음 턴 슬롯)는 이미 처리된 진입에 대해 재발화하면
안 된다 — 두 수행 지점에서 진입 효과를 적용한 뒤 `just_switched_in`을 소비하므로, 다음 턴
`_act_on_switch`는 플래그가 꺼져 있어 자동으로 no-op이 된다(이중 발화 방지). 진입 이벤트
브로드캐스트(상태 만료 trigger)는 즉시 시점으로 함께 옮긴다.

## 3. 핵심 난점

(a) **진입 즉시 ↔ 진행 중 라운드.** 자발적 교체는 한 유닛의 턴 도중 일어난다. 진입 유닛의
Trace는 그 시점 상대 on_field를 본다 — 싱글에선 상대 액티브가 1마리라 결정적. 멀티 액티브는
"어느 상대를 복사하나"가 모호(설계안 한계 §6).

(b) **강제 교체 콜백.** `_resolve_faint`는 라운드 중 매 행동 후 호출돼 죽은 액티브를 교체한다.
콜백으로 engine 핸들러를 부르는 건 broadcast_phase_event와 동형이라 패턴은 검증됨. 다만
turn_manager 시그니처에 파라미터 1개 추가(기본 None)라 회귀 0.

(c) **current_type 영속성.** Trace로 set된 current_type은 이후 Protean(`_act_move_use`)이
무브 사용 시 덮어쓸 수 있다. 이는 자연스러운 상호작용(나중 효과가 우선)이고 의도된 동작.
교체로 다시 나갔다 들어오면 재진입 시 다시 복사. 별도 클린업 불필요(.get 기반).

## 4. 회귀 0 전략

- `mechanisms['trace']` 미설정 → `_apply_switch_in_effects` 즉시 return → current_type 불변
  → STAB·전투 동일.
- `on_switch_in` 콜백 미전달(turn_manager 단독 테스트) → _resolve_faint 기존과 동일.
- 자발적 교체 경로: 진입 효과 호출은 trace 미설정 시 no-op, just_switched_in 소비는 어차피
  다음 턴 _act_on_switch도 소비하던 것이라 관측 차이 없음(로그 시점만 당겨짐).
- 하니스: ① trace 미설정 시 current_type 불변 ② 부착+상대 타입 복사 정확 ③ 미부착 캐릭터
  불변 ④ 상대 on_field 없을 때 no-op ⑤ 즉시 발화 후 다음 턴 _act_on_switch 재발화 안 함.
- 라운드트립 MD5 + 클린룸 컴파일 + 납품 후 Read·Grep. bash mount truncation은 Read로 우회.

## 5. PR 분할

PR-S6. **Trace 메커니즘 (기존 다음-턴 hook 위).** `_apply_switch_in_effects` 추가 +
`_act_on_switch`가 그것을 호출하도록 변경. **타이밍은 현행 "다음 턴" 유지** — 첫 실제 진입
메커니즘만 얹는다. engine 한 파일. 자기완결적, 낮은 위험(회귀 0: trace 미설정 시 no-op).

PR-S7. **진입 즉시 타이밍.** 진입 효과 호출을 교체 수행 2지점으로 이동 — engine
`_maybe_voluntary_switch`에서 직접 호출, turn_manager `_resolve_faint`에서 engine 콜백
(`on_switch_in`) 호출. turn_manager 시그니처에 콜백 파라미터 추가(기본 None) + engine
manager 생성부에서 클로저 전달. `_act_on_switch`는 플래그 소비 순서로 이중 발화 방지.
engine + turn_manager 두 파일. 중위험(switch 수행 경로 + 콜백 배선).

PR-S8. **Trace 부착 UI.** step2 메커니즘 부착 expander에 Trace 체크박스 + 기믹 컬럼/매치값 +
타입 출처 컬럼 매핑(Protean·Leftovers와 동일 양식). step2 한 파일.

분할 근거: S6는 "효과는 있으나 타이밍은 근사"인 안전한 첫 수순, S7이 타이밍 위험을 따로
떠안고, S8이 사용자 개입 경로를 연다. 우선도 트랙의 P3a(순수)/P3b(동작) 분리와 같은 철학.

## 6. 정직한 한계

(a) 멀티 액티브(더블+)에서 "어느 상대를 복사하나"는 미해결 — 싱글에서만 결정적. 검증
범위·외부 PS replay 모두 싱글이라 현재 무관.
(b) Trace를 "타입 복사"로 모델링한다(상대 current_type/type 기믹 → 진입 유닛 current_type).
실제 Pokemon Trace는 특성 복사지만, 본 엔진엔 특성 substrate가 없고 current_type+STAB가
가시 효과를 주는 가장 가까운 게임 중립 프리미티브다. "특성 복사 일반"은 특성 시스템이
생길 때의 후속.
(c) 해저드(Stealth Rock류, 진입 시 데미지)는 본 PR 범위 밖 — 같은 진입 hook 위에 후속으로
얹을 수 있다(APPLY_DAMAGE 라우팅 정찰 필요).

## 7. 사용자 결정 대기 항목

권고: PR-S6(Trace 메커니즘, 안전) 먼저 → 라이브 확인 후 PR-S7(진입 즉시 타이밍, 중위험)
→ PR-S8(UI). 승인하면 PR-S6 빌더로 진입한다(find/replace 자동 추출·라운드트립 MD5·클린룸
컴파일·하니스·납품 후 Read·Grep). S6/S7을 한 번에 갈지, 분리할지는 사용자 선호.
