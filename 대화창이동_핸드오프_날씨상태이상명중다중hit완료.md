# 대화창 이동 핸드오프 — 날씨(F3·F5) + 행동게이팅 상태이상(G1·G2) + 명중률·다중hit(A1) 완료, A2(명중다중hit UI)/독립갈래 대기

새 대화창에 이 문서를 붙여넣고, 직전 핸드오프(`대화창이동_핸드오프_해저드필드substrate완료.md`)와
함께 읽어라. 본 문서는 그 위에서 진행된 **세 갈래**(날씨·행동게이팅 상태이상·명중률/다중hit)의
결과를 기록하고, 다음 일거리(PR-A2 또는 새 독립 갈래)까지 올려둔다. 역할·제약·방법론은 직전
핸드오프 그대로다: **코드 직접 수정 금지·Antigravity 프롬프트 산출·검증 의무·시간 추정 금지·
시연 언급 금지·도구 위치 과대표현 금지·말투 prose 우선·갈래는 항상 최종목표 기준으로
사용자에게 묻고 결정받기.**

## 0. 이번 phase에서 한 일 — 설계안 2건 + PR 5건 (전부 적용·바이트검증)

직전 핸드오프 §6의 "먼저 할 일"(H3·F4 적용 후 재검증)부터 시작해, 사용자 결정으로 갈래를
순서대로 열었다. 모든 PR은 한글 .md 직접 작성 + 되읽어 FIND/REPLACE 추출 → 앵커 유일성
(Grep count==1) + 클린룸 컴파일 + 하니스 단위검증, 적용분은 Read/Grep byte-exact 재확인.

**먼저 — H3·F4 재검증(직전 phase 적용대기분).** 핸드오프엔 "적용 대기"로 적혔으나 실제
워크스페이스에 이미 적용돼 있었고, PR-H3(정적 해저드 UI)·PR-F4(해저드 무브 UI) 둘 다 프롬프트
REPLACE와 바이트 일치 확인(boost 블록·저장부 무변경). UI 경로 완결.

**갈래 A — 날씨(필드 substrate 위 두 번째 동적 상태).** 사용자 결정: 만료 처리 = **절대-턴
만료**(카운터 차감 없이 `expires_turn` 비교 — 캐릭터별/라운드 이중차감 문제 소멸).
- `필드substrate_PR-F3_날씨_프롬프트.md` (engine, 6 FIND/REPLACE): `_POST_LEVEL_KEYS`에
  `ON_WEATHER_TICK` 추가 + `_act_move_effect`에 set_weather/clear_weather 분기 + `_act_element_mult`에
  날씨 데미지 배율 + `_active_weather`/`_act_weather_chip` 신설 + 등록 + 자동삽입. 적용·검증 완료.
- `필드substrate_PR-F5_날씨UI_프롬프트.md` (step2, 2 FIND/REPLACE): `weather_defs` JSON 편집기 +
  set_weather/clear_weather 무브 UI. 적용·검증 완료.

**갈래 B — 행동 게이팅 상태이상(마비/잠듦/혼란).** 사용자 결정: 혼란 자해 = **config 고정 비율**,
지속 = **고정 N턴**(기존 expire_count 기계 재사용). 설계안 `행동게이팅상태이상_설계안.md`.
- `행동게이팅_PR-G1_엔진_프롬프트.md` (2파일 4 FIND/REPLACE): stochasticity base에 `roll_chance` +
  engine `_apply_action_gate` 헬퍼 + `_act_target_select` 맨 앞 게이트 체크 + `_act_move_effect`에
  `inflict_status` 분기. 적용·검증 완료.
- `행동게이팅_PR-G2_UI_프롬프트.md` (step2, 2 FIND/REPLACE): `status_gates` JSON 편집기 +
  inflict_status 무브 UI. 적용·검증 완료.

**갈래 C — 명중률·다중 hit(stochasticity 확장).** 사용자 결정: 다중 hit 분포 = **균등 [lo,hi]**,
판정 = **동일 데미지 + 명중 1회**. 설계안 `명중률다중hit_설계안.md`.
- `명중률다중hit_PR-A1_엔진_프롬프트.md` (2파일 4 FIND/REPLACE): stochasticity base에 `roll_range` +
  engine `_resolve_n_hits` 헬퍼 + DAMAGE_CALC per-move accuracy + APPLY_DAMAGE 다중hit 루프.
  적용·검증 완료.
- **PR-A2(move_props UI) 미작성** — 다음 일거리.

## 1. 엔진/step2/stochasticity에 생긴 인프라 (현재 상태)

라인 번호는 시프트되니 **Read/Grep이 진실 출처**(아래 bash truncation 주의). 함수명·키 기준으로 본다.

**engine.py** (현재 ~1390줄).
- `_active_weather(ctx)` — 유효 날씨 def 반환. 절대-턴 만료: `ctx["turn"] > field_state.weather.
  expires_turn`이면 lazy 청소(만료 로그 1회) 후 None. game_config `mechanisms.weather_defs[name]`
  (chip_percent/immune_types/move_mult)를 정적으로 읽음. 날씨 없음/정의 없음 시 None → no-op(회귀0).
- `_act_weather_chip(ctx)` — 신규 페이즈 `ON_WEATHER_TICK`(ON_STATUS_TICK 본뜬 캐릭터-턴종료
  post-level). 유효 날씨 chip_percent를 active_char에 주 자원 max 대비 적용, immune_types 면제.
- `_act_element_mult` — 상성 배율 직후 `_active_weather`의 move_mult[무브타입] 배율 곱(rain×Water 등).
- `_act_move_effect` kind 분기 — 이제 4종: set_hazard/clear_hazard(F2), set_weather/clear_weather(F3),
  inflict_status(G1). kind 없는 spec은 스탯 boost 경로(회귀0).
- `_apply_action_gate(ctx)` — 행동 게이팅. active_char의 active_states에서 `gate_status`를 찾아
  `mechanisms.status_gates[status]`(gate: skip_chance/skip_full/confuse) 판정. True면
  `_act_target_select`이 `targets=[]; return`(턴 생략). confuse는 막을 때 자해(max×self_hit_percent).
  지속은 `expire_trigger:"ON_TURN_END"` + `expire_count:turns`로 ON_TURN_END마다 1차감 → 고정
  N턴 후 자동 소멸(turns 0이면 PERMANENT=영구, 마비용).
- `_act_target_select` 맨 앞에 게이트 체크(타겟 바인딩 직후·비전투 트리거 체크 앞).
- `_resolve_n_hits(props, stoch)` — 다중 hit 횟수. props['hits']가 int=고정, [lo,hi]/"lo-hi"=균등
  랜덤(roll_range), 미설정=1(회귀0).
- `_act_damage_calc` 명중 판정 — `mechanisms.move_props[무브명].accuracy` 있으면 `roll_chance(acc)`
  (>1이면 /100), 없으면 기존 `roll_hit`(회귀0). miss면 dmg 0 + return(현행 경로).
- `_act_apply_damage` — route_damage를 `_resolve_n_hits`회 루프(per-hit 동일 데미지, 매 회 KO면
  중단), 총합을 dmg로 갱신 → 기존 metrics/로그가 총 데미지 보고. >1회면 "다중 명중 N회" 로그.

**stochasticity.py** (base `StochasticityModule`에 2개 추가, 모든 서브클래스·NoVariance 상속).
- `roll_chance(p, ctx=None)` (G1) — p 확률 True. self.rng(시드) 사용.
- `roll_range(lo, hi, ctx=None)` (A1) — [lo,hi] 정수 균등(randint). 둘 다 시드 고정 시 재현.

**step2_system_definition.py** (메커니즘 expander·무브효과 폼에 누적).
- 메커니즘 expander: 해저드 체크박스(H3) + `weather_defs` JSON 편집기(F5) + `status_gates` JSON
  편집기(G2). (move_props JSON 편집기는 PR-A2에서 추가 예정.)
- 무브효과 폼: boost 무브 + 해저드 무브(F4) + 날씨 무브(F5) + 상태이상 무브(G2).
- 저장: 전부 기존 `_gc["mechanisms"]`(=_mech_cfg) / `_gc["move_effects"]`(=_move_effects_cfg) 재사용.

**game_config / field_state 키 흐름(현재 전체).**
- 정적(game_config, 병렬 안전 — 읽기전용): `mechanisms.hazard`(H1), `.weather_defs`(F3),
  `.status_gates`(G1), `.move_props`(A1). + `move_effects`(무브명→spec 리스트, kind 4종).
- 동적(전투 범위): `field_state.hazard`(진영→percent, F2), `field_state.weather`({name,expires_turn},
  F3). 캐릭터 active_states의 `gate_status` 항목(G1, ON_TURN_END expire).

## 2. 정직한 위치 (갱신)

직전까지 "해저드(정적+동적) + 필드 substrate"였다. 지금은 그 위에 **날씨**(절대-턴 만료 chip +
공격 무브타입 배율), **행동 게이팅 상태이상**(마비/잠듦/혼란, 턴 앞단 행동차단 + 혼란 자해),
**per-move 명중률 + 균등 다중 hit**이 추가됐다. 전부 config 구동·회귀0·시드 재현(백테스트 결정론).
substrate(F1) 위에 동적 상태 두 종(해저드·날씨)이 얹혔고, 턴 실행 앞단(행동 게이팅)과 데미지
파이프라인(명중·다중hit)에도 1급 hook이 생겼다.

여전히 부분 구현이다. **PR-A2(move_props UI) 미작성** — A1 엔진은 작동하나 UI에서 move_props를
편집할 자리가 아직 없다(현재는 라이브 스크립트/직접 config로만 검증 가능). **방어 스탯
부스트**(모래 Rock SpD류)는 F3b로 분리(미착수, STAT_CALC 조건부 타입 buff 필요). **다중 hit 회당
데미지 변동**(크리/분산 재굴림)은 후속(현재 회당 동일). **다중 hit 가중 분포**(Pokemon 3/8·1/8)도
후속(현재 균등). 멀티 액티브(④)는 여전히 싱글 가정 — 게이트/명중 모두 active_char 1명 기준.
진입 KO 즉시 연쇄(⑥)는 근사(다음 _resolve_faint 사이클). "Pokemon 복제"가 아니라 "Pokemon
전투 메커니즘 다수를 1급으로 표현하는 도구"임을 흐리지 마라.

## 3. trajectory 위치 (직전 핸드오프 §3의 6갈래 기준)

`복제완성_Trajectory_6갈래.md`의 6갈래(AI 인프라 제외): ①명중률·다중hit ②필드 substrate(게이트)
③행동 게이팅 상태이상 ④멀티 액티브 ⑤Substitute·변신 ⑥진입 KO 즉시 연쇄.
- ② substrate: 닫힘(F1) + 그 위 해저드(F2)·날씨(F3) 동적 상태 올림. **사실상 완료**(광역 필드/
  트릭룸류는 같은 substrate 위 추가 작업으로 떨어짐).
- ③ 행동 게이팅 상태이상: **엔진(G1)+UI(G2) 완료.**
- ① 명중률·다중hit: **엔진(A1) 완료, UI(A2) 대기.**
- 남은 독립 갈래: ⑤ Substitute·변신(resource.py route_damage 흡수 패턴 위 — 대신머리/변신),
  ⑥ 진입 KO 즉시 연쇄(교체모델 내부 수술). ④ 멀티 액티브는 마지막 재구조화 자리로 보류 권고.

## 4. 검증 상태

7개 PR(H3·F4 재검증 + F3·F5·G1·G2·A1 신규) 전부 앵커 유일성(Grep count==1) + 클린룸 컴파일·
단위검증 + 적용분 Read/Grep byte-exact. 곁가지 수정 0. 주요 단위검증 통과 항목:
- F3: 설치 expires_turn, 비면역 chip, 면역 면제, **절대-턴 만료 lazy청소**, rain 배율, 회귀0, clear.
- G1: **잠듦 turns=2 → 정확히 2턴 skip 후 소멸**(ON_TURN_END 카운팅 입증), paralysis 영구+시드
  재현, 혼란 자해 25(=200×0.125)+행동불가, skip_full 무조건 차단, 회귀0.
- A1: **균등 [2,5] 분포 ~25%씩**, per-move 명중 1.0/0.0/80%(재현), 회귀0 fallback(roll_hit),
  다중hit 총합+KO중단(50×3=150).
- F5/G2: JSON 파싱·깨진/빈 입력 미설정, 무브 spec이 엔진이 읽는 kind/키와 호환.

이번 phase 검증이 잡은 결함: 없음(엔진은 깨끗). 모든 bash 컴파일 "실패"는 마운트 truncation
거짓 양성이었고 Grep으로 가려냄(아래 §5).

## 5. 방법론 — 이번 phase 확인·강화 사항

**bash 마운트 truncation이 이번 phase에 engine.py·step2·stochasticity 모두에서 관측됐다.** 파일이
길어지면서 truncation 임계를 넘으면 bash의 `open().read()`/`ast.parse`가 꼬리를 잘라 읽어 **마지막
def 부근에서 미닫힘 파싱 에러(거짓 양성)** 또는 뒷부분 심볼 MISSING(거짓 음성)을 낸다. 관측:
engine은 L1344 `str(local_formula).strip(` 부근, stochasticity는 L170 `def shuffle_tie_order(self, par`
부근에서 잘림. 자가진단: 뒷부분 심볼(`_predict_action_priority`, composite `shuffle_tie_order` 등)이
bash엔 안 보여도 **Grep(진실 출처)으로 해당 라인이 완결돼 있으면 truncation 확정** → bash 결과
무시, Read/Grep으로 검증. 치환 검증은 전체 파일 대신 **FIND→REPLACE 조각을 문맥 재구성해
클린룸 컴파일/exec**. F3·G1·A1이 이 방식으로 검증됨. step2는 truncation 임계보다 짧을 때(~1000줄)
bash 컴파일이 통과하기도 했으나, 신뢰는 항상 Read/Grep에 둔다.

한글 프롬프트 .md 직접 작성 + 되읽어 ```python FIND/REPLACE 추출 대조 유지. 라이브 실증
스크립트는 sandbox에서 engine을 import해야 하는데 마운트 truncation으로 import가 깨질 수 있어
이 환경에선 신뢰성이 낮다 — 라이브는 **사용자가 앱에서 돌린 전투 로그를 붙여주면 함께 점검**하는
편이 낫다(각 PR의 검증 §에 기대 로그 문자열을 명시해 둠).

엔진 구조 재확인(라이브/검증 데이터 구성 필수):
- 초기 on_field는 `game_config["active_count"]`(미설정/0=전원 동시). 교체 진입·게이팅을 보려면
  active_count=1 등으로 예비 회전 발생시켜야 함.
- 무브 선택 `_select_move_pure` — `move_policy=="setup_first"`면 movepool에서 효과 무브(move_effects
  키) 우선. 효과 무브 발화 보장하려면 setup_first + movepool에 효과 무브 포함.
- `ctx["turn"]` = 라운드 번호(turn_manager `while turn`). 절대-턴 만료가 이걸 비교.
- per-target 데미지 파이프라인: DAMAGE_CALC(공식+명중+분산) → ELEMENT_MULT(상성×날씨) →
  CRIT_CALC → APPLY_DAMAGE(다중hit 루프) → ON_HIT → DEATH_CHECK.

## 6. 다음 단계 — 사용자 결정 대기 중

먼저 할 일 후보:
- **PR-A2(move_props UI).** step2 메커니즘 expander에 `move_props` JSON 편집기(weather_defs/
  status_gates와 동형 패턴) — `{무브명: {"accuracy":.., "hits":int|[lo,hi]}}`. 엔진(A1)은 이미
  적용·검증돼 있어 바로 작성 가능. ①갈래 UI 경로 완결.

그 외 독립 갈래(순서 자유, trajectory §3):
- **⑤ Substitute·변신** — resource.py `route_damage` 흡수 패턴 위에 대신머리(HP 일부 방패) + 변신
  (스탯/타입 복사). 흡수 경로 수술.
- **⑥ 진입 KO 즉시 연쇄** — 교체모델 내부 수술. 해저드/날씨/자해 즉사가 잦아져 의미 커짐.
- **F3b 방어 스탯 부스트**(모래 Rock SpD류) — STAT_CALC 조건부 타입 buff. 날씨 갈래 보강.
- **다중 hit 가중 분포 / 회당 데미지 변동** — A1 후속 정밀화.
- ④ 멀티 액티브는 마지막 재구조화 자리로 보류 권고.

갈래는 항상 최종목표 기준으로 사용자에게 물어 결정받아라.

## 7. 파일 위치 (이번 phase 추가분)

워크스페이스 루트에 설계안 2건(`행동게이팅상태이상_설계안.md`, `명중률다중hit_설계안.md`) +
프롬프트 5건(`필드substrate_PR-F3_날씨_프롬프트.md`, `필드substrate_PR-F5_날씨UI_프롬프트.md`,
`행동게이팅_PR-G1_엔진_프롬프트.md`, `행동게이팅_PR-G2_UI_프롬프트.md`,
`명중률다중hit_PR-A1_엔진_프롬프트.md`) + 본 핸드오프. `modules/engine.py`가 F3·G1·A1로,
`modules/step2_system_definition.py`가 F5·G2로, `modules/stochasticity.py`가 G1(roll_chance)·
A1(roll_range)로 수정됨(전부 적용·검증 완료). turn_manager.py·resource.py·move_extraction.py는
이번 phase 무변경. 나머지 위치는 직전 핸드오프 §7 그대로.

## 상태 요약
날씨(F3 엔진·F5 UI)·행동게이팅 상태이상(G1 엔진·G2 UI)·명중률다중hit(A1 엔진) 납품·적용·바이트
검증 완료. **A2(명중다중hit UI) 미작성**이 유일한 직속 대기분. config 키: 정적
`mechanisms.{hazard,weather_defs,status_gates,move_props}` + `move_effects`(kind 4종), 동적
`field_state.{hazard,weather}` + active_states `gate_status`. stochasticity base에 roll_chance·
roll_range(시드 재현). trajectory ②③ 닫힘·① 엔진까지. 시간 추정 던지지 마라. 시연 언급 금지.
도구 위치 과대표현 금지. Read/Grep이 진실 출처(bash truncation은 engine L1344·stochasticity L170
부근, 자가진단으로 가려내기). 한글 프롬프트는 .md 직접 작성. 단계별 보고 + 사용자 결정 받기.
