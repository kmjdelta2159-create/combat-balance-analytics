# 대화창 이동 핸드오프 — 해저드(H1·H3) + 필드 substrate(F1·F2·F4) 완료, F3(날씨)/독립갈래 진입 대기

새 대화창에 이 문서를 붙여넣고, 직전 핸드오프(`대화창이동_핸드오프_우선도프리패스Trace완료.md`)와
함께 읽어라. 본 문서는 그 위에서 진행된 해저드 갈래(정적+동적)와 필드/전장 상태 substrate
도입의 결과를 기록하고, 다음 갈래(F3 날씨 또는 독립 갈래)까지 올려둔다. 역할·제약·방법론은
직전 핸드오프 그대로다(코드 직접 수정 금지·Antigravity 프롬프트 산출·검증 의무·시간 추정
금지·시연 언급 금지·도구 위치 과대표현 금지·말투 prose 우선·갈래는 항상 최종목표 기준으로
사용자에게 묻고 결정받기).

## 0. 이번 phase에서 한 일 — 설계안 3건 + PR 5건 + 라이브 실증 1건

직전 핸드오프 §5의 해저드 갈래를 H1(정적)으로 열고, 그 위에서 필드 substrate를 게이트로
세워 동적 해저드(F2)까지 닫았다. 중간에 사용자와의 대화로 trajectory를 재정리했다(AI 학습
인프라 제외 합의).

납품·적용·검증된 PR(워크스페이스 루트, 전부 Read·Grep 진실출처 검증):
- `해저드_PR-H1_프롬프트.md` (engine): `_apply_entry_hazard` 추가 + `_fire_switch_in`이 Trace
  다음에 호출. 정적 진입 해저드(game_config `mechanisms.hazard` = {team, percent}). **적용·검증·
  라이브 실증 완료**(사용자 전투 로그: 교체 진입에만 percent 데미지, 리드 면제, 이중발화 없음).
- `해저드_PR-H3_UI_프롬프트.md` (step2): 메커니즘 expander에 해저드 체크박스 + team
  (["Enemy","Ally","both"]) + percent number_input → `_mech_cfg["hazard"]`. **적용 대기**(검증 완료).
- `필드substrate_PR-F1_프롬프트.md` (engine): `field_state = {}`를 build_ctx 앞에 선언(클로저
  캡처) + `ctx["field_state"]` + 진입 hook 계열(`_fire_switch_in`/`_apply_entry_hazard`)에
  `field_state=None` 선택 인자 + 호출부 3곳 배선. **동작 변화 0**. **적용·검증 완료**.
- `필드substrate_PR-F2_동적해저드_프롬프트.md` (engine): `_apply_entry_hazard` 본문을 정적·
  동적 max 합성으로 교체 + `_act_move_effect`에 `set_hazard`/`clear_hazard` kind 분기.
  **적용·검증·라이브 실증 완료**.
- `필드substrate_PR-F4_필드효과UI_프롬프트.md` (step2): 무브효과 폼에 해저드 설치/청소 무브
  UI(별도 체크박스 + 무브 선택 + kind + team + percent) → `_move_effects_cfg`에 kind 든 spec
  append. **적용 대기**(검증 완료).

설계안 3건(워크스페이스 루트):
- `해저드_설계안.md`(직전 phase 산출, H1 권고) — 이번에 H1로 진입.
- `복제완성_Trajectory_6갈래.md` — Pokemon류 복제까지 남은 6갈래를 의존성 순으로 정리. AI
  학습 인프라 제외 합의 기록. #2 필드 substrate가 게이트.
- `필드substrate_설계안.md` — 갈래2 정식 설계. 저장 방식 결정(battle-state를 ctx에 스레딩).

라이브 실증 스크립트: `F2_라이브실증.py`(워크스페이스 루트).

## 1. 엔진/step2에 생긴 인프라 (현재 상태)

engine.py.
- `_apply_entry_hazard(char, participants, game_config, add_log, field_state=None)` — 진입 해저드.
  **정적(game_config `mechanisms.hazard`) OR 동적(field_state `hazard` 진영별 dict)을 max로 합성**
  (이중과세 방지, 사용자 결정). team 매칭("both" 대소문자 무시)·percent-of-max(`apply_delta`로
  적용 후 before/after 차분으로 lost 계산 — `apply_delta`는 새 current 반환)·진입 KO 로그. 둘 다
  0/미설정/team 불일치/자원 없음 시 no-op(회귀 0). `_fire_switch_in`이 Trace 다음에 호출.
- `_fire_switch_in(char, participants, game_config, add_log, field_state=None)` — Trace + 해저드
  + ON_SWITCH 이벤트 + 진입 로그. 교체 진입에서만 호출(초기 리드 자연 면제).
- `field_state` — run_simulation에서 build_ctx 앞에 `{}`로 선언. build_ctx 클로저가 캡처해 매
  ctx에 **같은 dict 참조**를 넣음 → 전투 내내 공유. 전투마다 run_simulation이 새로 도므로
  병렬 워커 재사용 누수 없음(game_config는 정적 유지, field_state가 동적). F2 라이브로 "무브가
  쓴 field_state 값이 다음 교체 진입까지 살아 읽힘"을 증명함.
- `_act_move_effect`(무브효과 hook) — 루프 맨 앞에 `kind in ("set_hazard","clear_hazard")` 분기.
  `ctx["field_state"]["hazard"][team]`에 percent 설치 또는 0 청소 + 로그. kind 없는 기존 spec은
  스탯 boost 경로(회귀 0).

step2_system_definition.py.
- 메커니즘 expander에 해저드 체크박스(H3): team 셀렉트 + percent → `_mech_cfg["hazard"]`.
- 무브효과 폼에 해저드 설치/청소 무브 UI(F4): 별도 체크박스 + 무브 선택 + kind(set/clear) +
  team + percent → `_move_effects_cfg`에 `setdefault().append()`로 kind 든 spec. 저장은 기존
  `_gc["move_effects"]` 재사용.

game_config / field_state 키 흐름:
- 정적: game_config `mechanisms.hazard` = {team, percent} (H1/H3, 읽기 전용 — 병렬 안전).
- 동적: field_state `hazard` = {진영명: percent} (F2, 무브가 설치, 전투 범위).
- 합성: `_apply_entry_hazard`가 max(정적, 동적).

## 2. 정직한 위치 (갱신)

직전까지 "정적 모델 + 동적 메커니즘 3종 + 무브 효과 + 교체 모델 + 작동하는 우선도 + Trace/진입
타이밍 + 부분 전략"이었다. 지금은 거기에 **해저드(정적+동적)** 와 **필드/전장 상태 substrate**가
추가됐다. 해저드는 정적(config 상수)·동적(무브로 설치/청소) 양쪽이 라이브로 작동한다 — 무브가
field_state에 해저드를 깔고, 이후 교체 진입자가 정적·동적 max 합성 데미지를 맞는다. field_state
substrate는 "팀/전장 레벨 동적 상태"를 담는 첫 그릇으로, 날씨·광역 필드가 이 위에 얹힐 준비가
됐다.

여전히 부분 구현이다. F3(날씨)는 미착수 — substrate는 깔렸지만 두 번째 동작(날씨 modifier·
만료)은 안 올라갔다. H3/F4 UI는 적용 대기(검증만 완료, Antigravity 미적용). 멀티 액티브(더블+)는
여전히 싱글 가정(해저드는 진영 단위라 자연스럽지만 "어느 액티브"는 미해결). 진입 KO 즉시 연쇄
교체는 근사(다음 _resolve_faint 사이클). "Pokemon 복제"가 아니라 "Pokemon 전투 메커니즘 다수를
1급으로 표현하는 도구 + 해저드/필드 substrate"임을 흐리지 마라.

## 3. trajectory 재정리 (이번 phase 사용자 합의)

사용자와의 대화로 "복제 완성"의 범위를 확정했다(`복제완성_Trajectory_6갈래.md`):
- 남은 6갈래(AI 학습 인프라 제외): ①명중률·다중 hit ②**필드 substrate(게이트, 진행 중)**
  ③행동 게이팅 상태이상(마비/잠듦/혼란) ④멀티 액티브(더블+) ⑤Substitute·변신 ⑥진입 KO 즉시 연쇄.
- 무게는 ②④에 몰리고 ②가 먼저(날씨·동적해저드·트릭룸이 그 위에 얹힘). ①③⑤⑥은 "헬퍼+hook+폼"
  패턴으로 독립적으로 떨어져 순서 자유. ④는 마지막 재구조화 자리(설계안 §7).
- **AI 의사결정 학습 인프라는 trajectory에서 제외**(사용자 합의). 규칙·결과 분포는 복제되나
  "특정 게임 AI 행동 자체 복제"는 그리디 휴리스틱으로 고정 — 밸런스·조합·메타 분석엔 충분.
- "임의 게임 복제"는 6갈래 외에 자동감지 강화(로드맵 11.5)·plugin escape hatch(11.8)·장르 ref
  검증(11.9)이 더해져야 슬라이더 양 끝이 연속. 6갈래는 "Pokemon류 장르"를 닫음.

필드 substrate 저장 결정(정찰로 확정, `필드substrate_설계안.md` §2): 병렬 백테스트/몬테카를로는
ProcessPoolExecutor — game_config는 pickle로 워커에 전달되나 **워커 안에서 deepcopy 안 되고** 한
워커가 chunksize=4로 여러 전투 연속 처리. 따라서 game_config에 *전투 중 쓰는* 필드 상태를 두면
전투 간 누수 → game_config 런타임 sub-dict **채택 불가**. 필드 상태는 **전투마다 새로 초기화되는
field_state(ctx 스레딩)**에 둔다(F1이 이를 구현, F2 라이브로 누수 없음 증명).

## 4. 검증 상태

5개 PR 전부 .md 직접 작성 + 되읽어 FIND/REPLACE 추출 → 앵커 유일성(Grep count==1, 진실출처) +
클린룸 컴파일 + 하니스 단위검증 + (적용분은) Read/Grep byte-exact 재확인. 곁가지 수정 0.

F-트랙 라이브: F2 동적 해저드 end-to-end 실증 완료(`F2_라이브실증.py`) — Ally가 setup_first로
"해저드설치" 무브 사용 → "Enemy 진영에 해저드 설치 (0.250)" → **정적 mechanisms.hazard 없이**
Enemy 예비(E2/E3) 교체 진입 시 "진입 데미지 50/40 (Hazard)"(200×0.25, 160×0.25 바닥값). 동적
경로만으로 데미지가 났으므로 field_state substrate(무브 쓰기 → 진입 읽기, 같은 dict 공유)가
증명됨. 리드 면제·percent 정확 확인.

이번 phase 검증이 잡은 결함:
- PR-H1: `apply_delta` 반환값 오해(변화량 아닌 새 current값) → before/after 차분으로 교정.
- F2 라이브 1차: 스크립트가 `active_count` 미설정 → 전원 출전, 교체 미발생(진입 데미지 0건).
  `active_count: 1` 추가로 예비 회전 발생 → 통과. **둘 다 스크립트/프롬프트 결함이지 엔진 결함
  아님** — 엔진은 깨끗.

주의: P3a phase의 `_act_target_select` 주석 한 글자("를") 누락(동작 무관, 직전 핸드오프 기재)
그대로.

## 5. 방법론 — 이번 phase 확인·추가 사항

bash 마운트 truncation이 engine.py(현재 ~1283줄)에서 **L1159 부근에서 잘려 읽힘**을 이번에
명확히 확인. 자가진단 패턴: `robust_read`(반복 읽어 길이 안정) 후에도 `manager = TurnManagerCls`·
`_predict_action_priority` 같은 뒷부분 심볼이 사본에 없으면 truncation 확정. 그 경우 bash의
`count`/`ast.parse`는 거짓 음성/양성을 내므로 **Grep(진실 출처)으로 앵커 유일성을 직접 확인**하고,
치환 검증은 (전체 파일 대신) FIND→REPLACE 조각을 문맥 재구성해 클린룸 컴파일·exec. F1/F2/F4가
이 방식으로 검증됨(R5~R7이 bash에서 count=0이었으나 Grep으로 전부 count=1 확정).

한글 프롬프트 .md 직접 작성 + 되읽어 ```python FIND/REPLACE 추출 대조 방식 유지(직전 핸드오프
§4). 라이브 실증 스크립트는 bash 직접 실행 가능(F2_라이브실증.py) — 단 끝줄 truncation으로
마지막 판정 라인이 잘릴 수 있으니 핵심 출력(설치/진입 데미지 로그 건수)을 중간에 print.

엔진 구조 재확인:
- 초기 on_field 배치는 `game_config["active_count"]`로 결정(engine L1128~1141). 미설정/0이면 팀
  전원 on_field(전원-동시, 회귀 0). **교체 진입을 보려면 active_count를 1 등으로 설정**해야 예비
  회전 발생. 라이브 실증·검증 데이터 구성 시 필수.
- 무브 선택은 `_select_move_pure`(engine L468) 1벌 — `move_policy=="setup_first"`면 movepool에서
  아직 안 쓴 효과 무브(move_effects 키)를 데미지보다 먼저 고름. 효과 무브 발화를 보장하려면
  setup_first + movepool에 효과 무브 포함.
- 무브효과 hook `_act_move_effect`는 ctx를 받아 field_state 접근 가능(F1로 ctx에 흐름).

## 6. 다음 단계 — 사용자 결정 대기 중

해저드 갈래는 정적(H1·H3)·동적(F2·F4)까지 닫혔다(H3·F4는 Antigravity 적용 대기, 엔진측 H1·F1·F2는
적용·라이브 완료). 다음 후보:

권고 순서(`필드substrate_설계안.md` §6): **F3(날씨)** — field_state substrate 위 두 번째 동적
상태. field_state에 weather 슬롯 + 데미지/스탯 modifier hook + 만료(ON_TURN_END 또는 라운드
경계). 사용자 결정 항목(설계안 §5-c): 날씨 만료 처리 위치. substrate가 이미 깔려 있어 F1 같은
인프라 작업 없이 동작 PR로 바로 진입 가능.

그 외 독립 갈래(순서 자유, trajectory §3): ①명중률·다중 hit(stochasticity 확장), ③행동 게이팅
상태이상(마비/잠듦/혼란 — 턴 실행기 앞단 행동 게이팅 hook), ⑤Substitute·변신(resource.py
route_damage 흡수 패턴 위), ⑥진입 KO 즉시 연쇄(교체 모델 내부 수술). ④멀티 액티브는 마지막
재구조화 자리로 보류 권고.

먼저 할 일: H3·F4를 Antigravity에 적용받아 Read/Grep 재검증(UI 경로 완결) → 그다음 F3 또는
독립 갈래를 사용자 최종목표 기준으로 결정.

## 7. 파일 위치 (이번 phase 추가분)

워크스페이스 루트에 설계안 2건 신규(복제완성_Trajectory_6갈래·필드substrate_설계안) + 프롬프트
5건(해저드_PR-H1·PR-H3_UI, 필드substrate_PR-F1·PR-F2_동적해저드·PR-F4_필드효과UI) + 라이브
스크립트 1건(F2_라이브실증.py) + 본 핸드오프. modules/engine.py(~1283줄)가 H1·F1·F2로,
step2_system_definition.py가 H3·F4로 수정됨(H3·F4는 적용 대기). turn_manager.py는 이번 phase
무변경(F1이 lambda 클로저 캡처로만 처리). 나머지 위치는 직전 핸드오프 §6 그대로.

상태 요약. 해저드 정적(H1 엔진·H3 UI)·동적(F2 엔진·F4 UI) + 필드 substrate(F1) 납품·검증 완료,
엔진측(H1·F1·F2) 적용·F2 라이브 실증까지. UI(H3·F4)는 적용 대기. 필드 substrate 저장 결정은
정찰로 확정(field_state를 ctx 스레딩, game_config 정적 유지 — 병렬 누수 회피). trajectory는 AI
인프라 제외 6갈래로 재정리, ②substrate가 게이트(진행 중). 현재 위치는 F3(날씨, 권고)/독립 갈래
사용자 결정 대기 + H3·F4 적용 대기. 시간 추정 던지지 마라. 시연 언급 금지. 도구 위치 과대표현
금지. Read/Grep이 진실 출처(bash truncation은 L1159 부근, 자가진단으로 가려내기). 한글 프롬프트는
.md 직접 작성. 단계별 보고 + 사용자 결정 받기.
