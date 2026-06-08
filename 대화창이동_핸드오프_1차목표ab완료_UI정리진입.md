# 대화창 이동 핸드오프 — 1차목표 두 기둥(a 일반화·b 도구화) 실측 완료 / 남은 건 UI 정리 + 점근 꼬리

새 대화창에 이 문서를 붙여넣고, 직전 핸드오프(`대화창이동_핸드오프_타입특성_환경레이어_무브효과완료.md`)와
함께 읽어라. 본 문서는 그 위에서 **교차검증(2-가드)·교차-게임(FF7)·역설계→수정 루프 도구화**를
완료해 1차목표의 두 엔지니어링 기둥을 실측으로 닫은 결과를 기록한다.

역할·제약·방법론은 그대로다: **코드 직접 수정 금지·Antigravity 프롬프트(.md) 산출·클린룸 검증
의무·시간 추정 금지·시연 언급 금지·도구 위치 과대표현 금지·말투 prose 우선·갈래는 최종목표
기준으로 사용자에게 묻고 결정.** mnt가 최근수정 .py를 끝부분 절단 → **Read/Grep이 진실 출처·풀런은
앱사이드(사용자가 run_*.py 실행 후 출력/캡처 붙여줌)·클린룸은 /tmp 재구성.**

## 0. 한 줄 요약 (현재 위치)

1차목표 = *임의 싱글 전투를 트레이스-리플레이로 수치까지 재현하는 검증된 루프 + 그 루프의 도구*.
**두 기둥이 실측으로 섰다**: (a) 일반화 — gen5 교차-전투(★55→14, 언어확장 1) + FF7 교차-게임
(데미지코어 100%·흡수 무료·엔진 0줄). (b) 도구화 — 메커니즘 RE 검출기 + 수정 surface + Streamlit
패널로 역설계→수정 루프가 수작업에서 도구로. **남은 건 본질이 아니라 완성도**: UI 정리(설계안 존재)
+ 점근 꼬리. 그래서 이 시점에 가벼운 모델로 대화창을 옮긴다.

## 1. 이번 phase 완료물 (전부 적용·검증)

### (a) 교차검증 2-가드 — `교차검증_평결_2가드통과.md`
never-fit held-out gen5(`Gen5OU-2026-newatmons-bantyranitar.html`, 퍼센트 HP)에 일반 스키마를
던져 **구조적 ★ 55→14**. 닫은 갭은 전부 *기존 언어 한 줄/데이터/버그수정*. 진짜 언어확장 부채 =
**Seismic Toss(고정데미지) 1건**. PR-X1~X7(데이터채움·Hail/PoisonHeal/U-turn one-liner·회복무브·
maxhp퍼센트버그·진입해저드). 골든 잔차 #1·#4 동반 개선.

### (a) 교차-게임 FF7 — `교차게임_FF7_트레이스리플레이_설계안.md`·`교차게임_PR-G1_FF7하니스_프롬프트.md`
키스톤(트레이스-리플레이 + 설정가능 데미지엔진 + 디스패처)을 JRPG에 던짐. **12턴 24무브 100% 일치**
— Physical/Magic 라우팅(`categories`)·통합 데미지식(`global_damage_formula`)·9속성(`weak:`/`absorb:`
의사-타입 `type_table`)·**흡수(-1)까지 무료**(엔진이 음수 elem_mult를 apply_delta 회복으로 라우팅).
**엔진 0줄 수정, ff7_reference 설정만.** 파일: `검증_FF7/ff7_reference.py`·`ff7_trace_gen.py`·
`run_ff7.py`. (정직 범위: 데미지 코어 일반화 측정. Limit Break 게이지·MP·상태이상은 ff7_ref
단순화로 스코프 밖.)

### (b) 도구화 — RE→수정 루프
- **PR-T1 검출기**(`툴화_PR-T1_*`): `modules/mechanism_detect.py` — 트레이스 `[from]` env 스트림
  마이닝 → 메커니즘 쇼핑리스트(class·name·kind·frac·modeled·EFFECTS 후보). `run_mechdetect.py`.
  gen5 held-out에서 손으로 닫은 메커니즘(Hail·PoisonHeal·Leftovers·RockyHelmet·회복무브·SR·Spikes·
  Recoil) **자동 재발견**.
- **PR-T2 수정 surface**(`툴화_PR-T2_*`): `modules/mechanism_commit.py` — 조건 자동추론
  (영향군 vs 면제 on-field 대조 → not_ability/not_types 힌트, **Magic Guard 자동발견**) + 사용자
  결정 → EFFECTS 커밋. `run_mechcommit.py`. 커밋된 `'hail'`이 손작성과 동일.
- **PR-T3 Streamlit**(`툴화_PR-T3_*`): `modules/step_mechanism_re.py`(render_mechanism_re) +
  step2 expander. 트레이스 업로드→검출 테이블→확정 위젯→EFFECTS 블록. **앱에서 종단 작동 확인.**

## 2. 남은 것 (본질 아님 — 완성도·꼬리)

1. **★UI 정리(다음 작업)** — 설계안 `UI정리_step2탭구조_설계안.md` 존재. step2(`render_system_
   definition`) 6섹션을 **`st.tabs` 4탭**(📊데이터·공식 / 🎯무브·타입 / ⚙️메커니즘·태그 / 🔄실행순서)
   으로 묶어 끝없는 스크롤 해소. **핵심 안전점**: `st.tabs`는 레이아웃 컨테이너지 파이썬 스코프가
   아니라 탭 안 변수(is_valid·매핑)가 하단 버튼에서 그대로 쓰임 → 하단 버튼·return 안 깨짐. 제어흐름
   확인됨(가드 상단 125·return 하단 913/1072, 중간 return 없음). 리스크 = ~700줄 한단계 재들여쓰기
   (기능 무변·레이아웃만). Streamlit이라 **앱 캡처로만 검증**. 가벼운 대안 = 무거운 섹션만 expander.
   → *적용 프롬프트(.md) 작성만 하면 됨.* 사용자가 "탭 vs expander" 선택.
2. **검출기 정련(1줄)** — `mechanism_detect._norm`에 별칭(sandstorm→sand) + modeled 별칭 반영.
   골든 업로드서 sandstorm/psn/Life Orb/Wish 미모델 오판 본 것. UI와 분리.
3. **점근 꼬리(선택)** — Seismic Toss(언어확장 fixed_damage 1건)·해저드 타이밍(진입 [T-1]·forced
   교체)·Brave Bird recoil·Ice Shard lockedmove. 전부 롤/단건 수준. `교차검증_평결_2가드통과.md` §6.

## 3. 운영 (이번에도 동일)

- mnt가 최근수정 .py 끝부분 절단 → **적용분 대조는 Read/Grep**(bash 정규식이 truncation에 None
  반환한 사례 다수). 풀 엔진 실행은 **앱사이드**(run_b4·run_xval·run_dmg_diag·run_mechdetect·
  run_mechcommit·run_ff7). 클린룸은 /tmp 재구성(showdown_trace·mechanism_detect 등 미수정/소형은 cp 가능).
- **회귀0 게이트** 모든 PR 유지(`run_b4.py` 골든 무변). UI PR은 Streamlit이라 앱 로드+캡처로.
- 프롬프트 작성 후 wc/tail 무결성. 한글 프롬프트 .md 직접 작성. 단계별 보고 + 사용자 결정.

## 4. 파일 위치 (이번 phase, 워크스페이스 루트)

- 평결/설계: `교차검증_평결_2가드통과.md`(§8 교차-게임 포함)·`교차검증_설계안.md`·`교차게임_FF7_*
  설계안.md`·`UI정리_step2탭구조_설계안.md`.
- 프롬프트(적용됨): `교차검증_PR-X1~X7_*`·`교차게임_PR-G1_FF7하니스_*`·`툴화_PR-T1~T3_*`.
- 로드맵: `복제완성_재정리_1차목표로드맵.md`(§5″ 교차검증·교차-게임 통과 반영됨).
- 코드(적용분): `modules/mechanism_detect.py`·`mechanism_commit.py`·`step_mechanism_re.py`(신규
  도구) + X1~X7 적용분(engine·reference_gen5·battle_setup·fullbattle_run·showdown_trace) +
  `검증_FF7/ff7_reference.py`·`ff7_trace_gen.py`·`run_ff7.py`.
- 도구: `run_xval.py`·`run_dmg_diag.py`·`run_mechdetect.py`·`run_mechcommit.py`(앱 실행).
- 코퍼스(영속): `Gen5OU-2026-newatmons-bantyranitar.html`(held-out)·`Gen5OU-2015-...-leftiez.html`
  (골든)·`검증_FF7/`(FF7 합성 known-answer).

## 5. 다음 단계 (사용자가 고름)

- **(주) UI 정리 적용** — `UI정리_step2탭구조_설계안.md`대로 step2 탭화 프롬프트(.md) 작성. 사용자가
  탭(권장) vs 경량 expander 선택. 앱 캡처로 검증.
- (부) 검출기 정련 1줄 / 점근 꼬리(Seismic Toss 등) — 원하면.
- (축 전환) 1차목표 본질은 닫혔으니, 데이터층 자동시드·더블(갈래④)·제품 폴리시 등 *다음 목표*는
  로드맵·데드라인 문서(`전체로드맵_데드라인_및_최종목표.md`) 기준으로 사용자 결정.

## 상태 요약
교차검증(2-가드 ★55→14·언어확장 1)·교차-게임(FF7 데미지코어 100%·흡수 무료·엔진 0줄)·도구화
(검출기 T1·수정 surface T2·Streamlit T3)로 1차목표 두 기둥을 실측 완료. 남은 건 UI 정리(step2 4탭,
설계안 존재·적용만)·검출기 1줄 정련·점근 꼬리. mnt 절단→Read/Grep 진실출처·풀런 앱사이드·클린룸
/tmp. 코드 직접수정 금지·프롬프트 .md 산출·회귀0 게이트·시간추정/시연언급 금지·갈래는 사용자 결정.
