# 필드/전장 상태 substrate 설계안 — 갈래 2 (다음 게이트)

## 0. 이 문서의 위치

`복제완성_Trajectory_6갈래.md` §3이 박은 다음 게이트를 정식 설계로 끌어올린다. 동적 해저드
(H2)·날씨·광역 필드(트릭룸류)가 전부 이 substrate 위에 얹히므로, 저장 방식을 먼저 정한다.
보조자는 코드를 직접 수정하지 않는다 — 정찰 → 설계안 → 사용자 검토 → 작은 PR 분할 →
Antigravity 프롬프트 → 검증.

## 1. 문제 — 엔진에 팀/전장 레벨 동적 상태가 없다

현재 모든 상태가 participant의 active_states(캐릭터 단위)에 산다. "전장 전체에 깔린 조건"
(어느 진영에 해저드가 깔렸나, 지금 날씨가 비인가, 트릭룸이 켜졌나)을 담을 자리가 없다. H1
정적 해저드는 game_config의 *상수*로 우회했지만(상시 진입세), 무브로 설치/청소하는 동적화는
전투 중 변하는 전장 상태가 필요하다.

## 2. 저장 방식 결정 (정찰로 확정)

### 2-1. game_config 런타임 sub-dict는 불가 (누수 버그)

정찰: 병렬 백테스트/몬테카를로는 `ProcessPoolExecutor`(step6 `_worker_simulate_match`)로 돈다.
인자는 pickle되어 워커로 전달 → 각 워커는 game_config의 독립 사본을 받지만(프로세스 격리),
**워커 안에서 game_config를 deepcopy하지 않고** 한 워커가 chunksize=4로 여러 전투를 연속
처리한다. 따라서 game_config에 *전투 중 쓰는* 필드 상태를 두면 전투 A의 상태가 전투 B로 샌다.
→ game_config 런타임 sub-dict(설계안 구안 §2-B 옵션①) **채택 불가**.

### 2-2. 채택 — battle-state를 ctx에 스레딩

정찰: ctx는 `build_ctx(active_char, turn, participants_list)`(run_simulation 내부 클로저,
engine L1194)가 매 행동마다 만든다. game_config는 이미 `ctx["game_config"]`로 흐른다(L1245).

결정:
- run_simulation 본문에서 build_ctx 정의 **전에** `field_state = {}`를 한 번 선언한다. 클로저가
  이를 캡처 → 매 build_ctx 호출이 **같은 dict 참조**를 `ctx["field_state"]`로 넣는다. 전투 내내
  공유되고, 전투마다 run_simulation이 새로 도므로 **워커 재사용 누수 없음**(§2-1 문제 회피).
- game_config는 정적으로 유지한다 — 설치 가능한 해저드/날씨의 *정의*만 담는다(예:
  `mechanisms.hazard`는 H1의 정적 spec). field_state는 *현재 깔린 동적 상태*를 담는다.

field_state 형태(제안):
```
field_state = {
    "hazard": {"Ally": 0.125, "Enemy": 0.0},   # 진영별 진입 데미지 비율 (0이면 없음)
    "weather": None,                            # 예: "sand"/"rain"/"sun" (없으면 None)
    "weather_turns": 0,                         # 남은 턴(0이면 만료)
}
```
초기값은 `{}` 또는 위 기본 스키마. 비어 있으면 모든 체크가 no-op → **회귀 0**.

## 3. 진입 hook이 ctx를 안 받는 문제 (핵심 배선)

정찰: `_fire_switch_in`/`_apply_entry_hazard`는 `(char, participants, game_config, add_log)`
시그니처라 ctx·field_state를 못 본다(S7에서 ctx 비의존으로 설계 — 자발/강제 교체 양쪽 호출
위함). 동적 해저드는 진입 체크가 field_state를 읽어야 하므로 이 계열에 field_state를 인자로
더 넘겨야 한다.

배선 방안(시그니처 확장, 기본값으로 회귀 0):
- `_fire_switch_in(char, participants, game_config, add_log, field_state=None)`,
  `_apply_entry_hazard(..., field_state=None)`로 **선택 인자 추가**(기존 호출 다 호환).
- 호출부 3곳에 field_state 전달:
  1. `_maybe_voluntary_switch`(engine, ctx 있음) → `ctx.get("field_state")` 전달.
  2. `_act_on_switch`(engine, ctx 있음, 다음-턴 fallback) → `ctx.get("field_state")` 전달.
  3. turn_manager `on_switch_in` 콜백(강제 교체) → run_simulation의 lambda가 field_state
     클로저 캡처해 전달. (turn_manager는 engine import 불가 → 콜백으로만; field_state도 그
     경로로 넘긴다.)
- `_apply_entry_hazard`의 진입 데미지 = max(H1 정적, H2 동적). 즉 game_config의 정적 hazard
  **OR** field_state의 동적 hazard를 합쳐 percent 결정(둘 중 큰 값 또는 합 — §5에서 정책 확정).
  H1만 설정·H2 미설정이면 현행 H1과 동일(회귀 0).

## 4. 무브가 필드 상태를 설치/청소 (동적화)

무브 효과는 `_act_move_effect`(ctx 받음, engine L805)에서 처리된다. game_config의 `move_effects`
가 무브 이름→효과 리스트를 담는다. 여기에 필드 설치/청소 효과 타입을 추가:
- 설치: 효과 spec `{"kind":"set_hazard","team":"Enemy","percent":0.125}` →
  `ctx["field_state"]["hazard"]["Enemy"] = 0.125`.
- 청소: `{"kind":"clear_hazard","team":"self"}` → 해당 진영 0으로.
- 날씨: `{"kind":"set_weather","weather":"sand","turns":5}` → field_state 갱신.
무브 효과 미정의 무브는 no-op(현행). step2 무브효과 폼에 필드 효과 종류 추가(후속 UI PR).

## 5. 사용자 결정 항목

(a) **H1/H2 합성 정책.** 진입 데미지를 정적(game_config) OR 동적(field_state) 중 **큰 값**으로
    할지, **합산**할지. 권고: 큰 값(max) — 정적은 "기본 깔림", 동적은 "무브로 추가 설치"를
    같은 채널로 보되 이중과세 방지.
(b) **field_state 스키마 범위.** 1차로 hazard만(H2 닫기) vs 처음부터 weather 슬롯까지. 권고:
    substrate PR(F1)은 빈 dict + hazard만, weather는 F3에서 슬롯 추가(작게 격리).
(c) **날씨 만료 처리 위치.** weather_turns 감소를 ON_TURN_END에 둘지 라운드 경계에 둘지(F3에서).

## 6. PR 분할

- **PR-F1 — substrate 도입.** run_simulation에 `field_state = {}` + `ctx["field_state"]` 한 줄
  + 진입 hook 계열에 `field_state=None` 선택 인자 추가 + 호출부 3곳 배선. **동작 변화 0**
  (아무도 field_state에 쓰지 않으므로 전부 no-op). 엔진 한 파일(+turn_manager 콜백 시그니처
  한 줄). 회귀 0 검증: field_state 빈 채로 기존 전투 byte-동일.
- **PR-F2 — 동적 해저드(H2).** `_apply_entry_hazard`가 field_state.hazard를 읽어 정적과 합성
  (§5-a 정책) + `_act_move_effect`에 set/clear_hazard 효과. 라이브: 무브로 해저드 설치 →
  이후 교체 진입자가 데미지. H1 경로 불변(회귀 0).
- **PR-F3 — 날씨.** field_state.weather 슬롯 + 데미지/스탯 modifier hook + 만료. 로드맵 11.4.
- **PR-F4 — 필드 효과 UI.** step2 무브효과 폼에 필드 설치/청소·날씨 종류 추가.

권고 진입: PR-F1(substrate, 동작변화 0)부터 — 인프라를 회귀 0으로 깔고, 그 위에 F2(동적
해저드)로 H2를 닫는다. S6→S7, H1→H3와 같은 "인프라 먼저, 동작 나중" 분할.

## 7. 정직한 한계

- field_state는 단일 전투 범위(전투마다 새로 초기화). 메타 진행·연전 누적 없음(설계 의도).
- 멀티 액티브(갈래 4)에서 "진영 단위 필드"는 자연스럽지만 "어느 액티브에 적용"은 싱글 가정
  잔존 — 갈래 4 재구조화 때 함께 해소.
- 진입 KO 즉시 연쇄(갈래 6)는 별개 — F2로 동적 해저드가 즉사를 더 자주 유발할 수 있으나
  정리 타이밍 근사는 H1과 동일(다음 _resolve_faint 사이클).
