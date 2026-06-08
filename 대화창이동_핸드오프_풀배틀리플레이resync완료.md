# 대화창 이동 핸드오프 — 풀배틀 트레이스 리플레이(B1~B4) + 세트(C1) + 라운드별 resync(C2) 완료

새 대화창에 이 문서를 붙여넣고, 직전 핸드오프(`대화창이동_핸드오프_트레이스리플레이하니스구축.md`)와
함께 읽어라. 본 문서는 그 위에서 **풀배틀 트레이스 리플레이를 끝까지 구축·작동시키고, 역설계→수정
루프를 전투 스케일로 처음 돌린 결과**를 기록한다. 역할·제약·방법론은 직전 핸드오프 그대로다:
코드 직접 수정 금지·Antigravity 프롬프트(.md) 산출·검증 의무·시간 추정 금지·시연 언급 금지·도구
위치 과대표현 금지·말투 prose 우선·갈래는 항상 최종목표 기준으로 사용자에게 묻고 결정받기.

## 0. 한 줄 요약 (현재 위치)
**임의의 실 gen5 싱글 전투를 넣으면 엔진이 27턴 전부를 로그대로 재생하고, 라운드별로 divergence를
연쇄 없이 격리한다.** 하니스가 완성·작동한다(엔진 마지막 턴 27 = 로그 27). 남은 일은 메커니즘 잔차를
하나씩 인코딩하는 것뿐 — 하니스 결함이 아니라 데이터/메커니즘 채움이다.

## 1. 이번 phase에 구축한 것 — 풀배틀 리플레이 B 시리즈 + 수정 루프 C 시리즈
전부 한글 프롬프트 .md 직접 작성 + 클린룸/앱사이드 검증. 사용자 적용 완료분:

* **PR-B1 — `modules/fullbattle_diff.py`(신규)**: 비교 인프라(엔진 무관). `build_action_queue`(로그
  순서 행위자 액션)·`build_snapshots`(턴 경계 {nick:{hp,status,fainted}})·`divergence`(라운드별
  expected vs actual). 클린룸 검증: gen5 행동큐 60(move 36+자발 24)·스냅샷 28(turn 0~27)·self-diff 0·
  모의오차 정확 포착. 교차게임 gen6 25/13.
* **PR-B2 — `modules/battle_setup.py`(신규, 세대중립) + `modules/reference_gen5.py`(신규)**:
  `build_participants(trace,ref)`/`build_battle_spec(trace,ref)` — ref 주입으로 세대중립. gen5 레퍼런스
  12종족값·타입·무브·타입표·CRIT_MULT=2.0 시드. **관측 max HP로 종족값 자가검증(12종 전부 합법
  HP EV)**. maxhp는 관측 ground truth로 보정, 비-HP는 prior. gen6 교차로 세대중립 입증(Huge Power 적용).
* **PR-B3a — `battle_setup`에 `build_trace_actions`+`prepare_run` 추가**: switch를 **정밀 분류**(핵심
  난점) — 리드 2(셋업)·기절교체 7(엔진 faint 경로)·피벗 1(Volt Switch, 무브효과)·자발 14. move 36.
  prepare_run이 team(Ally/Enemy)·on_field(리드)·roster_idx + game_config(trace_actions·
  trace_faint_incoming·switch_policy=trace) 조립. 클린룸: dangling 참조 0.
* **PR-B3b — engine.py selector 트레이스 분기(FIND/REPLACE)**: `_maybe_voluntary_switch`(트레이스
  자발교체)·`_act_target_select`(move/target 오버라이드)·`_act_move_select`(로그 무브 사용).
  `game_config['trace_actions']` 없으면 no-op(회귀0). 앱사이드.
* **PR-B3c — `turn_manager._resolve_faint` 기절-교체 incoming 트레이스 교정**: 엔진 기본
  roster_idx[0] 대신 로그 지정 incoming(outgoing→incoming) 진입. + `__init__` param·engine 매니저
  생성 전달. + `prepare_run`에 `on_active_faint="replace_from_reserve"` 보강. standalone 3시나리오 검증.
* **PR-B4 — `modules/fullbattle_run.py`(신규) + engine 게이트 훅 2개**: 통합 run.
  `setup_for_engine`(닉 보존·HP 자원 초기화·진영 정렬)·`engine_snapshot`·`run_and_diff`·`format_report`.
  engine `run_simulation`에 `preserve_ids`(닉 id 보존; 엔진은 A1/E1 재할당) + `on_turn_end`(TURN_END
  브로드캐스터 합성으로 라운드 상태 캡처). 순수조각 클린룸: perfect-engine self-diff 0·오차주입 포착.
* **PR-C1 — `reference_gen5` 세트/EV 메커니즘 + 표준세트 시드**: `NATURES` + set-aware `make_char`
  (EV/nature/item/ability). 표준 gen5 OU 12세트 시드(잔차 역설계 확정분 반영: Tentacruel 물리방어·
  Latios Choice Specs·Politoed 물리방어). 세트 없으면 prior 폴백(회귀0). **per-event 과다데미지 잔차
  대거 닫힘**(Hydro Pump→Jirachi 0.68→0.93, Scald→Hippowdon 0.65→0.95, Body Slam→Latios 0.62→0.86).
* **PR-C2 — 라운드별 resync(turn_manager round-start 훅 + engine + fullbattle_run)**: 매 라운드 시작에
  엔진 상태(HP·on_field)를 log[T-1]로 재동기화 → **누적 desync 차단**. divergence가 라운드별 순수
  예측오차가 됨(설계안 "첫 divergence 격리" 구현). 클린룸: on_field 타임라인·resync 콜백 검증.
  `run_and_diff(resync=True)` 기본.

## 2. 핵심 진단 — 역설계→수정 루프가 전투 스케일로 작동
* **풀배틀이 처음엔 100턴 표류**(승부 못 냄). per-event 잔차(연쇄 없음, 로그 def HP 사용)로 근원 확정:
  **세트/EV prior 오차 → 엔진 과다데미지 → 유닛 조기 사망 → 로그에 없는 기절 → faint incoming
  미스매치 → on_field 영구 desync → 무브조회 실패 → 데미지 멈춤 → 표류.**
* **잔차가 세트를 역설계**: `Body Slam→Hippowdon 0.09`(물리벽), `Draco Meteor→Tentacruel`(Choice
  Specs Latios 적용 시 R≈321≈관측 327 → Tentacruel은 SpD형 아닌 물리방어형), Latios `Trick`=Choice
  도구. C1 시드가 이를 반영해 과다데미지를 닫음.
* **C2 resync로 desync 해소**: 엔진 마지막 턴 100→**27**(=로그). 여러 라운드 near-exact —
  T3 −60/**−59**, T13 −238/**−222**, T15 Explosion −108/**−108**.
* 결론: **하니스는 멀쩡. 풀배틀 충실도는 데미지/메커니즘 정확도에 달렸고, 그건 per-event(run_resid)로
  연쇄 없이 하나씩 닫는다 → resync 풀배틀(run_b4)로 흐름 통합 확인.** 두 도구가 상보적 루프.

## 3. 남은 잔차 (전부 라운드별로 격리됨 — 다음 타깃 목록, 우선순위 미정)
메커니즘 채움이지 하니스 결함 아님. 버킷:
1. **타입/특성** — Hidden Power 숨김타입(T1 −238 SE vs 엔진 −129, T22), Levitate 등 특성 면역(T16
   Latios가 Garchomp Earthquake에 엔진 −253 — 땅 ×0 면역 누락). reference_gen5에 추가, 데이터 역설계
   가능. **추천 1순위**(새 인프라 0, 단일 최대 과다데미지 T16 닫음).
2. **날씨 데미지 배율** — Politoed Drizzle=비 → Water ×1.5(T8 Scald −145/엔진 −45 과소). 엔진 날씨
   인프라(F3) 있음.
3. **무브효과** — Draco Meteor 2연타 −2 SpA 자기디버프, Explosion 자폭(T19 −323/엔진 −21). 효과-스키마
   (ON_MOVE_USE).
4. **해저드** — Stealth Rock 진입 데미지(타입스케일 = Tier-3 갭; T5 Hippowdon −96/엔진 0).
5. **(점검 — 메커니즘 아닐 수 있음)** T12 Latios Draco Meteor −283/엔진 **−1**: per-event에선 0.87로
   맞는데 풀배틀선 거의 0 → 그 턴 무브 발동 누락 의심. 다음 run에서 **엔진이 각 턴 실제 쓴 무브를
   한 줄씩 찍는 진단**을 run_b4/on_turn_end 캡처에 넣어 확인 권고(발동누락이면 하니스 점검).

## 4. 루프 도구 (앱에서 실행 — engine truncation으로 내 샌드박스 풀런 불가)
* **`run_resid.py`** — per-event 데미지 잔차(연쇄 없음, 로그 def HP 사용). reference_gen5 make_char +
  식(base×STAB×타입×크리) + Draco/Leaf Storm −2 SpA 추적. 세트 고칠 때마다 돌려 obs/R이 [0.85,1.0]로
  닫히는지 본다. **엔진 안 부름 → 내 샌드박스에서도 돔**(reference_gen5 등 작은 모듈만 사용).
* **`run_b4.py`** — 풀배틀 resync 통합 run + 라운드별 데미지 delta 진단(데미지 난 셀만, carry-forward
  노이즈 제거). `run_and_diff(resync=True)`. 엔진 전체 필요 → **앱사이드**.
* 실행: 프로젝트 루트에서 `python run_resid.py` / `python run_b4.py`. (둘 다 스크립트 폴더 기준 경로.)

## 5. ★운영 — engine truncation 여전
engine.py ~1398줄(이번 패치 적용 과정에서 일부 정리됨). 샌드박스가 큰 파일을 잘라 읽는 위험 상존 →
**Read/Grep이 진실 출처**, 엔진 전체 실행 검증은 앱사이드. **작은 모듈은 샌드박스 정상**:
showdown_trace·fullbattle_diff·battle_setup·reference_gen5·fullbattle_run·turn_manager·trace_replay·
stochasticity (전부 <11KB). per-event(run_resid)·순수조각은 내가 직접 검증, 풀런은 사용자 앱 로그로 대조.

## 6. 파일 위치 (이번 phase 산출, 워크스페이스 루트)
* 설계: `풀배틀리플레이_설계안.md`(B1~B4 분할), `효과스키마_설계안.md`(잔차 버킷 3 관련).
* 프롬프트: `풀배틀리플레이_PR-B1_비교인프라_프롬프트.md`, `..._PR-B2_셋업빌더_..md`,
  `..._PR-B3a_행동표_..md`, `..._PR-B3b_엔진selector_..md`, `..._PR-B3c_기절교체_..md`,
  `..._PR-B4_통합run_..md`, `..._PR-C1_세트EV메커니즘_..md`, `..._PR-C2_resync모드_..md`.
* 코드(사용자 적용분): `modules/fullbattle_diff.py`·`battle_setup.py`·`reference_gen5.py`·
  `fullbattle_run.py`(신규), `modules/engine.py`(B3b selector·B3c faint param·B4 preserve_ids/
  on_turn_end·C2 on_round_start), `modules/turn_manager.py`(B3c _resolve_faint·C2 round-start 훅).
* 루프 도구: `run_resid.py`·`run_b4.py`.
* 황금표준 코퍼스(이제 워크스페이스에 영속화 — 재제공 불필요): `Gen5OU-2015-05-11-reymedy-leftiez.html`
  (gen5 골든 풀배틀), `OUMonotype-2014-01-29-kdarewolf-onox.html`(gen6 교차).

## 7. 방법론 — 이번 phase 확인·강화
* **데이터 먼저**: per-event 잔차표가 "세트가 틀렸다"를 정량으로 지목하고 세트를 역설계(Tentacruel
  물리방어·Latios Choice)했다. 표준세트는 prior, 잔차가 교정 타깃을 데이터로 정한다.
* **resync = 트레이스 충실도 검증의 표준 기법**: 순수 시뮬은 누적오차로 desync한다 → 매 스텝 관측
  ground truth로 재anchor해 "그 라운드 예측오차"만 잰다(설계안의 라운드별 격리 = resync 사고).
* **회귀0 게이트 패턴**: 모든 엔진/turn_manager 분기는 config·param 게이트(미설정 시 기존 경로).
  preserve_ids·trace_actions·trace_faint_incoming·on_round_start 전부 그렇다.
* **switch 정밀 분류**가 결정적이었다(리드/기절/피벗/자발 — 경로가 다름). "자발교체 24"는 틀린
  뭉뚱그림이었고, 실제는 자발 14 + 기절 7 + 피벗 1 + 리드 2.
* 갈래는 최종목표 기준으로 사용자에게 묻고 결정. 시간 추정·시연 언급·도구 위치 과대표현 금지.

## 8. 다음 단계
사용자가 잔차 버킷 중 시작점을 고른다(§3). **추천: #1 타입/특성**(Hidden Power 숨김타입 + Levitate
면역) — 새 인프라 0, 데이터 역설계 가능, 단일 최대 과다데미지(T16) 닫음. 또는 #5 T12 발동 진단 먼저
(메커니즘 아닐 수 있으니 안전). 각 타깃은 동일 루프: run_resid/run_b4로 잔차 지목 → reference_gen5
또는 효과-스키마에 인코딩 → 재run으로 닫힘 확인. 로드맵(`복제완성_재정리_1차목표로드맵.md`)도 이
마일스톤(풀배틀 하니스 작동) 반영해 갱신 권고.

## 상태 요약
풀배틀 트레이스 리플레이 하니스를 끝까지 구축(B1 비교인프라·B2 세대중립셋업+gen5레퍼런스·B3a 행동표·
B3b 엔진selector·B3c 기절교체·B4 통합run) + 세트/EV 메커니즘(C1) + 라운드별 resync(C2)로 **desync를
없애 27턴 전체를 라운드별 격리 재생**. per-event 잔차가 세트를 역설계하고 C1이 과다데미지를 닫고 C2가
표류를 해소 = 역설계→수정 루프가 전투 스케일로 작동. 남은 건 메커니즘 잔차(타입/특성·날씨배율·무브
효과·해저드)를 하나씩 인코딩. 도구: run_resid(per-event)·run_b4(resync 풀배틀), 둘 다 앱 실행. engine
truncation 상존 → Read/Grep 진실 출처, 풀런 앱사이드. 시간 추정 던지지 마라. 시연 언급 금지. 도구
위치 과대표현 금지. 한글 프롬프트는 .md 직접 작성. 단계별 보고 + 사용자 결정 받기.
