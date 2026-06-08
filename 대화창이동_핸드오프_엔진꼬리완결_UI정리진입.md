# 대화창 이동 핸드오프 — 엔진 메커니즘 꼬리 완결(F1~F3r) / UI 정리 진입·적용대기 2건

새 대화창에 이 문서를 붙여넣고, 직전 핸드오프들(`대화창이동_핸드오프_F1완료_꼬리진단진입.md`·
`대화창이동_핸드오프_UI재설계완료.md`)과 함께 읽어라. 본 문서는 그 위에서 점근 꼬리 F2·F2b·
F3s·F3r를 적용→실측검증으로 닫고, T10을 진단 후 보류했으며, UI 정리(가)에 진입해 카피/레이아웃
프롬프트까지 낸 결과를 기록한다.

## 역할·제약·방법론 (불변)
코드 직접 수정 금지·Antigravity 프롬프트(.md) 산출·클린룸/실측 검증 의무·시간 추정 금지·시연
언급 금지·도구 위치 과대표현 금지·말투 prose 우선·갈래는 최종목표 기준으로 사용자에게 묻고 결정.
**mnt가 최근수정 .py를 끝부분 절단**(이번에도 bash `py_compile`이 절단 라인에서 `unterminated
string`로 실패 재확인) → **Read/Grep이 진실 출처**, 풀런·진단은 앱사이드(사용자가 run_*.py 실행
후 출력/캡처 붙여줌), 클린룸은 /tmp(순수부만).

## 0. 한 줄 요약 (현재 위치)
"쓸 수 있을 정도 = 포켓몬 복제 기능 + 가독 UI" 목표에서, **엔진 메커니즘 꼬리를 전부 닫았다**
(F1·F2·F2b·F3s·F3r, 매 단계 골든 회귀0). held-out 구조적 divergence는 6셀로 줄었고 **전부
비-메커니즘 잔여**(리드 아티팩트·크리·롤·보류한 T10). UI는 (가) 홀리스틱 재설계로 진입 —
requirements·Step2 expander·attack_log이동은 이미 코드에 있었고, U3b(섹션3·4 평면복원)는 적용·
검증됨. **적용 대기 2건: PR-CLEAN(목업/데드 제거)·U4(카피·언어통일·레이아웃).**

## 1. 이번 세션 완료물 — 엔진 꼬리 (전부 적용·실측검증)
각 PR은 "진단 스크립트로 원인 확정 → 코드 프롬프트 → 적용 → run_cellclass 셀 귀속 + run_b4
회귀0"의 규율로 닫았다. F1의 "출력 불변=미발동" 오판을 반복하지 않으려 **항상 진단 먼저**.

- **F2 해저드 타이밍** (`꼬리_PR-F2_해저드타이밍_프롬프트.md`). 진단(`run_f2diag.py`)이 두 버그를
  확정: (a)미발화 5셀 — resync가 on_field 직접세팅으로 `_fire_switch_in` 콜백 우회, (b)과적용
  2셀 — `hazard_by_turn[T]` 윈도우 오프바이원. 해법 = **하니스(`fullbattle_run`)가 진입 해저드를
  단일 책임으로 `hazard_by_turn[T-1]` 윈도우로 1회 적용**(엔진 트레이스-주입은 끔, 정적/move
  경로는 보존). 닫음: T9 Abomasnow·T11 Gliscor(진입)·T4 Gliscor·T5 Skarmory(과적용).
- **F2b Magic Guard 진입 면제** (`꼬리_PR-F2b_MagicGuard진입면제_프롬프트.md`). F2 후 over-damage
  4셀(T6·T15 Clefable·T14·T27 Reuniclus)이 드러남 — Magic Guard는 진입 해저드 면역인데
  `_hazard_entry_pct`가 미체크. 데이터엔 이미 ability=Magic Guard 있음(L138·142). 엔진 한 줄
  추가(우박칩 면제와 동형). 골든 무Magic Guard라 회귀0 구조적 보장. 4셀 닫음.
- **F3s 스탯 스테이지** (`꼬리_PR-F3s_스탯스테이지_프롬프트.md`). 진단(`run_boostdiag.py`):
  트레이스-리플레이 game_config의 `move_effects` 키=0 → 부스트 무브(Bulk Up·Swords Dance·Calm
  Mind·Amnesia)가 엔진 stat-stage에 미반영. 엔진엔 stat-stage 기계(`get_effective_stat` percent
  배율) 이미 있음. 해법 = **하니스가 `boosts_by_turn`(누적·교체 리셋) 타임라인을 매 라운드
  on-field 유닛 active_states로 주입**. 결정 디테일: **엔진 방어스탯 키는 `df`(def 아님)**, value=
  stage_mult(n)-1, **[R-1] 윈도우**(T29 Reuniclus def-1은 그 턴 Crunch 2차효과라 그 타격엔
  미적용). 닫음: T24·T25 Scrafty(방어)·T29 Reuniclus(공격자 Atk+2) + T11 Jirachi hp 동반.
- **F3r 반동무브** (`꼬리_PR-F3r_반동무브_프롬프트.md`). F1과 동형 무브-속성 레이어 — `RECOIL_MOVES`
  (reference_gen5)·battle_setup 부착·`_act_apply_damage`에서 타겟 데미지 후 사용자에 int(dmg×분수).
  recoil 속성 없으면 no-op→회귀0. 닫음: T16·T18 Skarmory(Brave Bird).
- **T10 Garchomp(gap=61) — 진단 후 보류**. `run_t10diag.py`로 확정: **타입버그 아님**(type_columns
  =[t1,t2,t3], Ice→Dragon/Ground=4× 정확) ·**raw_dmg 아님**. 엔진이 **Abomasnow Ice Shard(우선도+1)를
  실행조차 안 함** — 공격자가 그 턴 공격 후 곧 필드를 떠나는(기절/교체) 케이스의 트레이스-리플레이
  액션 스케줄링 엣지. 1셀·좁은 엣지·레버리지 낮음 → known-residual로 문서화·보류(F3r 프롬프트 부기).
  엔진엔 locked-move 처리 자체가 없음(평결의 "Outrage-locked" 가설은 빗나감).

### 남은 6셀 (작업 대상 아님 — 비-메커니즘 잔여)
T0 Magnezone·Abomasnow(턴0 리드 하니스 아티팩트), T27 Scrafty(U-turn 크리), T11 Jirachi(기절
임계 롤), T10 Garchomp(보류), T6 Gliscor(롤). 메커니즘 부채 0.

## 2. 이번 세션 완료물 — UI 정리 (가: 홀리스틱 재설계)
- **현황 확인(Read/Grep)**: requirements.txt 정상(손상 아님)·Step2 5섹션 expander 적용됨·
  attack_log→Step1 이동 완료(Step1 소유, Step2는 session_state 읽기). 즉 설계안의 PR-HOTFIX·U2·
  S1은 이미 코드에 반영돼 있었음.
- **U3b 적용·검증됨** (`UI정리_PR-U3b_섹션34평면복원_프롬프트.md`): Step2 섹션3(태그 정규화·내부
  중첩 expander 불법)·섹션4(실행 순서·streamlit-sortables 커스텀 컴포넌트가 expander 안에서 높이0)
  를 평면 헤더로 복원. 앱 캡처로 드래그 블록(Phase1/2/3) 정상 렌더 확인. (섹션2/5/6 expander 유지.)
- **사용자 UI 검수에서 두 기능 판정**:
  - "🎛️ 가중치 기반 동적 Dashboard(D5)" = `build_mock_state_from_log` 목업·"시연용(실제 통합
    D7~8 미완)" → **역할 없는 가짜 → 제거 결정**.
  - "🔬 전투별 백테스트(Per-Battle Backtest)" = 실제 엔진 재시뮬·복제 충실도 측정(클린룸 harness의
    인앱판) → **유지**.
  - 동적 메커니즘 8종은 코드상 **기본 OFF**(value=False) — 버그 아님(스샷의 켜짐은 세션 잔존).

## 3. 적용 대기 — UI 프롬프트 2건 (다음 액션)
순서: **PR-CLEAN → U4**, 적용 후 Step1·2·5 캡처로 검증.
- **`UI정리_PR-CLEAN_목업데드제거_프롬프트.md`**: step6_dashboard.py에서 D5 목업 import(L27-32)+
  블록(L1327-1346) 제거(`return True, ""` 유지), `modules/ui_registry.py`(목업 전용 고아)·
  `step3_flow_auditor.py`·`step4_role_definition.py`(데드, import 0) 삭제. 검증 ast.parse+Step5 캡처.
- **`UI정리_PR-U4_카피언어통일_프롬프트.md`**: (A)카피 find→replace 제로리스크 — 영한혼용 헤더
  한국어화·업로더 라벨 한국어·**어택로그→무브로그**(내부키 attack_log_df 유지)·ML 과장문구
  평이화. (B)타입 상성표 `height=320` 박스화+카피 완화(expander 중첩 불가라 높이 고정). (C)데미지
  공식 자동추정 섹션을 데미지 컬럼 있을 때만 노출(중위험·들여쓰기 주의, 안전대안=문구만 변경).

## 4. 운영 (불변)
- 적용분 대조·코드 진실 = Read/Grep. bash 샌드박스는 최근수정 .py 절단으로 import/실행 실패 가능.
- 풀런·진단 앱사이드: `run_b4`(골든 회귀0 게이트)·`run_cellclass`(분류·셀 귀속)·`run_xval`(held-out
  divergence)·일회용 진단(`run_f2diag`·`run_boostdiag`·`run_t10diag`·`run_f1diag`·`run_dmg_diag`,
  지워도 무방).
- 엔진 PR 검증 = run_cellclass 버킷 감소 + run_b4 불변. UI PR 검증 = `ast.parse` + 앱 캡처(Streamlit
  렌더는 클린룸 불가). 프롬프트 .md 직접 작성, 적용 후 wc/tail 무결성. 단계별 보고 + 사용자 결정.

## 5. 파일 위치 (이번 세션, 워크스페이스 루트)
- 코드 프롬프트(적용·검증): `꼬리_PR-F2_*`·`_PR-F2b_*`·`_PR-F3s_*`·`_PR-F3r_*`·`UI정리_PR-U3b_*`.
- 코드 프롬프트(작성·미적용): `UI정리_PR-CLEAN_목업데드제거_*`·`UI정리_PR-U4_카피언어통일_*`.
- 진단 도구(신규·일회용): `run_cellclass.py`·`run_f2diag.py`·`run_boostdiag.py`·`run_t10diag.py`.
- 코드(적용분): `modules/fullbattle_run.py`(하니스 진입해저드·boosts_by_turn)·`engine.py`(Magic
  Guard 면제·recoil·해저드 윈도우)·`reference_gen5.py`(RECOIL_MOVES)·`battle_setup.py`(recoil 부착)·
  `step2_system_definition.py`(U3b 평면).
- 코퍼스: `Gen5OU-2026-newatmons-bantyranitar.html`(held-out, 퍼센트HP)·골든 gen5(reymedy-leftiez).
- 상위 맥락: `교차검증_평결_2가드통과.md`·`UI_홀리스틱_재설계안.md`·`전체로드맵_데드라인_및_최종목표.md`.

## 6. 다음 단계 (사용자가 고름)
- (권장·바로) PR-CLEAN·U4 적용 → Step1·2·5 캡처 검증 → (가) UI 정리 완료 = "쓸 수 있을 정도" 도달.
- (정리 연장) Step1/3/4도 캡처로 훑어 숨은 거슬림(영한혼용·과장문구·안 되는 기능 노출) 추가 정리.
- (피처·나중) (나) 피처셋: 트레이스-리플레이 앱뷰·복제 일치율 헤드라인 — 더 큰 단계.
- (최종목표) 임의 게임 슬라이더 복제 — 별개 대단계(목업 D5가 그 미완 흔적이었음, 설계는
  `WeightDrivenUI_설계안.md`에 보존). 진짜 시뮬 통합으로 재구축.

## 상태 요약
엔진 메커니즘 꼬리 완결(F1·F2·F2b·F3s·F3r, 골든 회귀0, held-out 6셀 전부 비-메커니즘 잔여, T10
보류). UI (가) 진입 — 기존 적용분 확인 + U3b 적용·검증, 목업 D5 제거 결정·백테스트 유지 판정.
적용 대기 = PR-CLEAN·U4. 다음 = 둘 적용+캡처로 "쓸 수 있을 정도" 마무리. 코드 직접수정 금지·
프롬프트 .md·회귀0 게이트·Read/Grep 진실출처·풀런 앱사이드·진단 먼저·갈래 사용자 결정.
