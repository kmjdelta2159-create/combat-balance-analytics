대화창 이동 핸드오프 — Combat Balance Analytics / Phase 8d 납품 대기 + Phase 11 진입 직전

새 대화창에 이 문서를 그대로 붙여넣어라. 아래 컨텍스트를 숙지하고, 곧바로 즉시 다음 스텝부터 이어서 진행한다.

# 0. 너의 역할 (불변 제약 — 절대 어기지 마라)

너는 프로젝트 "Combat Balance Analytics" 의 보조자다. 프로젝트 리드는 사용자(김민재)다.

- 너는 프로젝트 코드 파일을 직접 수정하지 않는다. 너의 산출물은 코드 생성기 "Antigravity" 에게 넘길 markdown 프롬프트다. 사용자가 그 프롬프트를 Antigravity에 전달하고, Antigravity가 실제 파일을 고친다.
- 예외: 검증용 테스트 하니스, 레퍼런스 구현(reference implementation)은 너가 직접 작성해도 된다. 이것들은 프로젝트 코드가 아니라 검증 도구다. 샌드박스(`~/...` 또는 `outputs/`)에서 작업한다.
- 검증 의무: Antigravity 산출물은 절대 설명만 믿지 마라. 항상 코드를 직접 읽어 검증한다 — Grep으로 마커 확인 → 변경 구역 Read 정독 → 라인 수 산술 → 바이트 동등성(MD5) → 클린룸 컴파일. Antigravity는 불완전·하드코딩 납품 전력이 있다.
- 프롬프트 스타일: 앵커 기반 통째 블록 find/replace (찾기 블록 / 바꾸기 블록). 이전 프롬프트들(`Phase8b_상성표STAB_프롬프트.md`·`Phase9_엔진최적화_프롬프트.md`·`Phase9b_병렬핫픽스_프롬프트.md`·`Phase8c-alpha_백테스트_프롬프트.md`·`Phase8d_채널매핑_프롬프트.md`)이 모범 양식이다.
- 프롬프트 작성 시: 검증된 하니스에서 find/replace 블록을 **프로그래매틱으로 추출·조립**하고 라운드트립(쓰기→되읽기→블록 재추출→MD5 대조)으로 전사 오류를 0으로 만든다.

# 1. 프로젝트 개요 — 최종 목표

Python 3 / Streamlit / Pandas / Scikit-learn / gplearn 기반 턴제 전투 시뮬레이터.

최종 목표 (3단계):

1. 전투 로그를 역설계한다.
2. 전문가(사용자) 개입을 받아 게임의 전투 시스템을 복제한다.
3. 복제본을 밸런스 분석용으로 최적화한다.

핵심 원리 — 연속 슬라이더: 대상은 턴제 구조 게임. 대중적인 형태일수록 시뮬레이터의 역설계 비중이 높고, 비대중적일수록 사용자 개입 비중이 높다. 역설계와 개입은 독립된 두 기둥이 아니라 하나의 연속 슬라이더의 양 끝이다.

정직한 스코프: 스탯 기반 턴제 게임 (JRPG / 가챠 / SRPG / 덱빌더).

# 2. 아키텍처 핵심

- Streamlit SPA 위저드: Step 1 업로드 → Step 2 시스템 정의 → Step 5 불일치 → Step 4 프로파일링 → Step 6 대시보드.
- 전투 엔진 `modules/engine.py` — UI 독립, 순수 Python. 액션 파이프라인: `PASSIVE_START → STAT_CALC → MOVE_SELECT → TARGET_SELECT → DAMAGE_CALC → ELEMENT_MULT → CRIT_CALC → APPLY_DAMAGE → ON_HIT → DEATH_CHECK`
- 3-Layer 설계: L1 Universal Core(~80%), L2 Pluggable Modules(~82%), L3 Game Plugins(~15%, 대부분 부재 — Phase 11이 잡을 영역).
- `game_config` dict = L3의 "데이터 척추". 현재 키: `{categories, type_table, type_columns, stab_factor, channels}`. Phase 8d로 `channels`가 추가됨(납품 대기 중).

# 3. 현재 진행 상황

## Phase 8 — 완료·검증 끝

- 8a (무브 시스템): `engine.py`에 MOVE_SELECT 단계·`_act_move_select`·무브 주입(`move_power`/`offense`/`defense`)·`game_config` 파라미터. 신규 순수 모듈 `modules/move_extraction.py`(71줄). UI는 `step2_system_definition.py`에 무브 패널.
- 8b (N-type 상성표 + STAB): `engine.py`에 `_move_type_multiplier`·`_move_stab_multiplier`·무브 인지 `_act_element_mult`·타입 인지 그리디. UI는 `step2_system_definition.py`에 타입 상성표 그리드(`st.data_editor` key `ui_type_table_editor`) + STAB `number_input`(key `ui_stab_factor`).

검증 결과 (포켓몬 known-answer 하니스, 클린룸): known-answer 충실도 71.6%(베이스) → 74.3%(8a) → 92.6%(8b), 천장 95.8%.

## Phase 9 — 완료·검증 끝

목적: Step 6 대시보드의 스탯 배분 최적화를 LR 대리모델에서 실제 엔진 MC 승률 목적함수로 교체.

- 신규 모듈 `modules/optimizer.py` — 미분 없는 노이즈 내성 (μ,λ)-진화 전략 + 예산 제약 초평면 투영(_project_budget · _feasible · optimize_allocation).
- step6의 `Global Character Builder` 탭 `Data-Driven Target Optimizer` 버튼 핸들러를 디스패치 구조로 변경:
  - `game_config` 또는 `move_library`가 있으면 → 엔진-인-더-루프 경로 (`run_simulation` 루프 ×N, 고정 시드 = 공통난수)
  - 둘 다 없으면 → 레거시 SLSQP 경로 (기존 코드 한 글자도 안 바뀜)

납품 검증 통과: optimizer.py verbatim 일치(MD5), step6 디스패치 블록 byte-identical, SLSQP 본문 불변, 라인 수 산술 정확.

## Phase 9b — 완료·검증 끝 (성능 핫픽스)

문제: Phase 9는 단일 코어에 108,300 시뮬을 직렬로 돌려 사용자 머신에서 수 분간 멈춘 듯 보임. 진행바가 세대 단위라 0%에서 안 움직이는 것처럼 보임.

수정 (`elif _use_engine_opt:` 블록 195줄 통째 교체):
- 엔진의 검증된 워커 `_worker_simulate_match` 재사용. ProcessPoolExecutor를 최적화 전체에 걸쳐 **한 번만** 띄우고 모든 평가에서 재사용 (영속 풀).
- 연산량 ~25배 축소: 평가 65회 × 내부 50시뮬 + 최종검증 1000 = 약 4,250 전투 (이전 108,300).
- 내부 전투 턴 상한 `_OPT_MAX_TURNS = min(_max_turns, 60)`. 최종 검증만 풀 턴.
- 평가 단위 진행바 — `objective` 호출마다(총 65회) `_prog_bar.progress(...)` 갱신.
- 엔진 에러 가시화 (`_opt_err` dict).

납품 검증 통과: 195줄 블록 MD5 일치, 라인 수 정확히 +18줄 시프트, Phase 9 마커 전부 +18 동일 시프트.

사용자 실측: 8코어 기준 63초, 양성 컨트롤(목표 100%) 정확 0.00%p, 음성 컨트롤(목표 50% Enemy 합류) 35.80%(매치업 한계 내 최선해).

## Phase 8c-α — 완료·검증 끝 (per-battle backtest 검증 모드)

문제 발견: `modules/validation.py`의 "승률" 점수가 **구조적으로 의미 없는 비교**를 하고 있었다 — GM Mode 1매치업의 MC 승률과 로그 전체의 target_col 평균을 빼서 점수화. 사용자가 본 misleading 3%의 원인. Pokemon 채점표 §1-1이 이미 이 결함을 기록(*"overall 점수는 'MC 1매치업 승률이 0.5에 얼마나 가까운가' 단일 수치로 붕괴"*).

해결: 신규 순수 모듈 `modules/per_battle_backtest.py` + step6 `시뮬레이션 로그` 탭 끝에 `🔬 전투별 백테스트` 섹션 1회 삽입(156줄). 로그의 각 전투를 엔진으로 재시뮬해 예측 승자 vs 실제 승자 1대1 비교. 영속 풀 패턴 9b 그대로 재사용.

납품 검증 통과: 신규 모듈 MD5 일치, 삽입 블록 MD5 일치, step6 1167→1321줄 정확히 +154 시프트, Phase 9b 마커 6개 전부 +154 동일 시프트.

사용자 실측: pkmn_battle_log.csv (Pokemon 검증 정답지) 500전투 6초 → **전체 일치율 66.2%** (Ally 65.0% / Enemy 67.5%, 클래스 균형 51.4% : 48.6%).

**결정적 양성 컨트롤**: 우리 in-app 66.2% ↔ 채점표 §2 D의 phys 라우팅 65.5% / spec 라우팅 67.2% / 평균 66.4% — ±1pp 내 정량 align. 외부 클린룸 harness 의존 종결. backtest 인프라가 의미 있는 측정을 한다는 결정적 증거.

발견된 한계: `universal_test_log.csv` (사용자가 보유한 도구 검증용 합성 로그)는 paired format이 아니라 **ML 학습용 형식** — 8행 분포가 Binomial(8, 0.5) 종 모양, 즉 행 그룹화 정보가 없음. per-battle backtest 입력으로는 부적절. 의미 있는 측정에는 paired log 필요.

종결 문서: `Phase8c-alpha_종결보고서.md` 워크스페이스에 보관.

## Phase 8d — 진행 중 (현재 위치 — 프롬프트 작성 끝, 납품 대기)

문제 발견: 엔진의 기믹 채널(`passive`·`trigger`·`target`·`formula`·`element`·`damage_type`)을 컬럼명에 영어 키워드가 들어있는지로 자동 탐지함(`engine.py` 다중 사이트). 사용자가 한국어/다국어 컬럼명을 쓰면 엔진이 그 채널을 **조용히 누락**하고 사용자는 알아채지 못함. 패시브 안 발동, 공식 폴백, 속성 1.0 배율 등.

해결: `game_config["channels"]` dict에 명시 매핑 슬롯 신설. 엔진은 명시 매핑 우선, 미설정 시 기존 이름 추측 폴백(회귀 불변).

5개 변경:
1. `engine.py`에 `_channel_col(gimmicks, channels, role, fallback_keywords)` 헬퍼 신규 (get_element_multiplier 직후).
2. `_act_on_hit`의 `t_passive_col` 라인 → `_channel_col` 사용.
3. `build_ctx`의 6개 채널 탐지 블록 → `_channel_col` 사용.
4. `step2_system_definition.py`에 `🧩 기믹 채널 매핑` expander 추가 (c_btn 직전, 3×2 selectbox 그리드).
5. `step2`의 game_config 조립 로직 수정 — 채널 매핑까지 포함 (채널만/무브만/둘 다 모든 경우 지원).

프롬프트 산출물: `Phase8d_채널매핑_프롬프트.md` (10,966자, 268줄). 작성 끝, 라운드트립 무결성 검증 통과 (10개 python 블록 MD5 대조 전부 일치).

사전 기능 검증 (6개 사례 통과):
- 한국어 컬럼 + 명시 매핑 → 정확히 풀림
- 영어 컬럼 + 채널 미설정 → 자동 디텍션 (회귀 불변)
- 한국어 컬럼 + 채널 미설정 → None (#1 landmine 재현)
- 명시 None → 채널 비활성
- 매핑이 존재하지 않는 컬럼 가리킬 때 → name 폴백 (robust)
- damage_type 듀얼 키워드 → 동작

상태: 사용자가 Antigravity에 전달 대기 중. 납품받으면 검증 사이클 들어가야 함.

## 도구 현재 위치 종합

| Phase | 영역 | 상태 |
|---|---|---|
| 1~7 | 업로드·매핑·SR·LR·결측치·검증 프레임 | 완료 |
| 8a/8b | 무브 시스템 + 타입표·STAB | 완료·검증 |
| 9 | 엔진-인-더-루프 스탯 배분 최적화 | 완료·검증 |
| 9b | 멀티코어 병렬 핫픽스 | 완료·검증 |
| 8c-α | Per-battle backtest 검증 모드 | 완료·검증 |
| **8d** | **기믹 채널 명시 매핑 (하드코딩 #1 정리)** | **납품 대기** |
| 11 | L3 Plugin 형식화 | 다음 |
| 10 | 팀 빌드/메타 분석 | 후순위 (사용자 결정) |

# 4. 핵심 방법론 주의사항 (반드시 지켜라)

bash 마운트 truncation (재발성·치명적): bash로 큰 워크스페이스 파일(engine.py ~890줄, step2 ~960줄, step6 1321줄)을 `cp`/`cat`하면 조용히 잘린다. `wc`/`py_compile`/`diff`가 거짓 에러를 낸다.

- → 워크스페이스 파일은 반드시 Read/Grep 파일 도구로 읽어라. bash 금지.
- 검증은 Grep 마커 + 변경 구역 Read 정독으로 한다.
- 샌드박스 자체 파일(`~/pkmn_regen/...`·`outputs/`)은 bash로 다뤄도 안전하다.
- 디렉터리 목록(`ls`)이나 작은 파일(<10KB)은 bash OK. 큰 파일 내용 읽기·복사는 금지.

검증 워크플로 (납품 후):

1. Glob/bash `ls` — 신규 파일 존재 확인.
2. Grep으로 새 마커 + 옛 마커(negative grep) 모두 확인.
3. 라인 수 산술 — `이전 라인 수 + (replace 줄수 - find 줄수) = 새 라인 수` 정확히 일치하는지. 어긋나면 곁가지 수정 의심.
4. Phase 마커들이 동일한 정수 시프트를 받았는지 → 곁가지 수정 0건 산술 증명.
5. 변경 블록 Read 정독 → 프롬프트의 바꾸기 블록과 바이트 동등성(MD5).
6. 클린룸 컨텍스트 py_compile (들여쓰기 정확 재현).

프롬프트 작성 워크플로:

1. 변경 사이트 Grep + Read로 정확한 컨텍스트 확정.
2. `outputs/verify_phaseN_xxx.py` 하니스 작성 — 새 코드를 실제 들여쓰기로 재현.
3. py_compile + 가능한 경우 기능 단위 테스트.
4. 빌더 스크립트 (Python heredoc)로 .md 조립 — find/replace 블록을 하니스에서 자동 추출, 직접 타이핑 금지.
5. 라운드트립 무결성 (.md 쓰기 → 되읽기 → python 블록 재추출 → MD5 대조 → 컨텍스트 py_compile).
6. `present_files`로 사용자에게 전달.

기타 함정:

- `run_simulation`은 3-튜플 반환 → `winner, logs, sim_metrics = run_simulation(...)`.
- `run_simulation`/`run_monte_carlo`는 `game_config` 파라미터를 받는다.
- `_worker_simulate_match` 시그니처: 15-튜플 인자 `(ally, enemy, combat_flow, speed_stat, sys_stats, global_formula, max_turns, stochasticity_factory, resource_module, spatial_module, range_stat, move_stat, deck_module, game_config, worker_seed)`. 반환 `(1 if winner=="Ally" else 0, sim_metrics)` 또는 `"ERROR: ..."`.
- 샌드박스 `/tmp`는 권한 문제 있음 → `outputs/` 디렉터리 사용.
- Glob 도구가 한국어 경로(`modules/optimizer.py` 같은) 검색 시 가끔 빈 결과 반환. 진실은 bash `ls`. bash `ls`는 디렉터리 목록이라 truncation 영향 없음.

# 5. 검증된 자산 — Phase 8d 프롬프트 (납품 대기)

워크스페이스: `Phase8d_채널매핑_프롬프트.md` (10,966 chars, 268 lines)
무결성: python 블록 10개(찾기/바꾸기 × 5쌍), 라운드트립 MD5 전부 일치
기능 검증: 6개 시나리오 단위 테스트 통과
컴파일 검증: engine.py + step2.py 변경 컨텍스트 양쪽 py_compile 통과

핵심 헬퍼 (verbatim, engine.py에 추가될 함수):

```python
def _channel_col(gimmicks, channels, role, fallback_keywords):
    """Phase 8d — 기믹 채널 명시 매핑 우선, 미설정 시 컬럼명 키워드 추측 폴백."""
    if channels and role in channels:
        mapped = channels[role]
        if mapped is None:
            return None
        if mapped in gimmicks:
            return mapped
    if isinstance(fallback_keywords, (tuple, list)):
        return next((c for c in gimmicks
                     if any(k in str(c).lower() for k in fallback_keywords)), None)
    return next((c for c in gimmicks
                 if str(fallback_keywords) in str(c).lower()), None)
```

# 6. 발견된 다른 하드코딩 (Phase 8d 이후 후순위 정리 대상)

🟡 Moderate — 명시적이지만 우회 가능
- element_chart 6원소·{1.5/0.5} (engine.py 13~24) — Phase 8b의 type_table로 우회 가능
- detection.py 키워드 hints — 거의 영어
- validation.py 검증 버킷 4종 고정
- per_battle_backtest 가정: "앞 절반=Ally" — 비대칭 전투, explicit team_col 미지원
- DEFAULT_COMBAT_FLOW — 정해진 액션 순서

🟢 Minor
- "비어 있음" 한국어 placeholder (step6)
- `char_col = df.columns[0]` (step1)
- DamageVariance variance_pct=0.1 default (Pokemon ±10%)

이 하드코딩들은 Phase 11(L3 형식화) 작업하면서 자연스럽게 정리되거나 별 사이클에서 다룸. Phase 8d가 닫히면 가장 시급한 silent landmine은 사라진 상태.

# 7. 다음 작업 — 즉시 다음 스텝

## Step 1 (사용자 행동 대기): Phase 8d 납품받기

사용자가 `Phase8d_채널매핑_프롬프트.md`를 Antigravity에 전달 → 납품받으면 사용자가 "받음"이라고 알려줄 것.

## Step 2: Phase 8d 납품 검증 (위 §4 방법론 따라)

1. Grep으로 새 마커 확인:
   - engine.py: `def _channel_col`, `_channel_col(t_gimmicks, _ch, "passive"`, `_channel_col(gimmicks, _ch,` 6번
   - step2_system_definition.py: `_channel_choices`, `ui_channel_passive`, `_channel_roles`, `🧩 기믹 채널 매핑`
2. Grep negative — 옛 코드가 사라졌는지: 
   - engine.py: `next((c for c in gimmicks if 'passive' in c.lower()` 같은 옛 패턴이 BUILD_CTX 안엔 없어야 함 (헬퍼 안에는 있음).
3. bash `ls` — 파일 크기 변화 확인.
4. Read로 변경 구역 정독 → 프롬프트 바꾸기 블록과 MD5 대조.
5. 라인 수 산술 — engine.py 이전 ~890줄, step2 이전 ~960줄. 변경 후 예상치 계산해서 일치 확인.
6. 클린룸 py_compile 컨텍스트 검증.

## Step 3: 사용자에게 Phase 11 진입 의사 확인 + 설계 시작

Phase 11 = **L3 Plugin 형식화**. 의미:
- 현재 `game_config` dict는 잡탕 — `{categories, type_table, type_columns, stab_factor, channels}` + 사실상 그 외 임의 키 허용.
- 이걸 정식 인터페이스로 추상화 (Pydantic schema? Protocol class? 또는 game_profile dict 구조 정형화).
- 상태이상/지속효과를 1급 엔티티화 (현재는 `exec(passive_logic)` raw Python).
- 다중 hit, 명중률 per 무브, 우선도, 날씨/필드 등 표현 — 현재 dict + raw Python으로 가능하지만 1급 시민 아님.
- 목표: 사용자가 자기 게임의 메커니즘을 형식적으로 기술하면 도구가 그걸 직접 실행 가능한 인프라.

Phase 11 시작 전 사용자와 합의할 것:
- 형식화의 깊이 (가벼운 schema vs 완전 plugin 시스템)
- 우선 대상 메커니즘 (상태이상? 우선도? 날씨? 무엇이 가장 갈증인가)
- 기존 game_config 호환성 (마이그레이션 vs 깔끔한 새 인터페이스)

## Phase 10 (팀 빌드/메타 분석)은 후순위

사용자가 명시했음 — 11이 우선. 10은 본인 게임의 실사용 데이터가 확보되거나 추가 갈증이 생긴 후. Phase 9b 인프라(영속 풀 + 엔진 워커)가 이미 있어서 10은 비교적 가벼운 추가 작업이지만, 우선순위는 11.

# 8. 파일 위치

- 워크스페이스(사용자 폴더): `C:\Users\kmjde\OneDrive\Desktop\턴제 시뮬레이션`
- 프로젝트 코드: `modules/engine.py`, `modules/optimizer.py`, `modules/per_battle_backtest.py`, `modules/move_extraction.py`, `modules/step2_system_definition.py`, `modules/step6_dashboard.py`, `modules/validation.py`, `modules/detection.py`, `modules/resource.py`, `modules/spatial.py`, `modules/deck.py`, `modules/stochasticity.py`, `modules/turn_manager.py`, `modules/win_condition.py`, `modules/action_registry.py`, `modules/step1_upload.py`, `modules/step2_profiling.py`, `modules/step3_flow_auditor.py`, `modules/step4_role_definition.py`, `modules/step5_discrepancy.py`, `modules/symbolic_regression.py`
- 메인 진입점: `main.py` · `app_backup.py`
- 검증 자산: `검증_포켓몬/pkmn_ref.py`, `검증_포켓몬/pkmn_battle_log.csv`(5000행 paired), `검증_포켓몬/pkmn_attack_log.csv`(8000행 per-attack), `검증_포켓몬/검증_정답지_측정계획.md`, `검증_포켓몬/검증_Run결과_채점표.md`
- 사용자 보유 합성 로그: `universal_test_log.csv`(5000행, ML 형식 — per-battle backtest 입력 부적절)
- 기존 Phase 프롬프트:
  - `Phase8a_무브엔티티_프롬프트.md`·`Phase8a-UI_무브UI_프롬프트.md`
  - `Phase8b_상성표STAB_프롬프트.md`·`Phase8b-UI_상성표UI_프롬프트.md`
  - `Phase9_엔진최적화_프롬프트.md`
  - `Phase9b_병렬핫픽스_프롬프트.md`
  - `Phase8c-alpha_백테스트_프롬프트.md`
  - **`Phase8d_채널매핑_프롬프트.md` ← 납품 대기**
- Phase 종결 문서: `Phase8c-alpha_종결보고서.md` (Phase 8c-α 종결, 도구 현재 상태 요약)
- 핸드오프 문서: `대화창이동_핸드오프_Phase8d직전.md` (본 문서)

---

상태 요약: Phase 8 / 9 / 9b / 8c-α 전부 완료·검증 끝. Phase 8d 프롬프트 작성·내부 검증 끝, 사용자가 Antigravity에 전달해서 납품받기를 대기 중. 납품받으면 §7 Step 2로 진행. 그 다음 Phase 11(L3 형식화) 설계 시작. Phase 10은 사용자 결정상 후순위.

위 §7 Step 1 — 사용자가 "받음" 또는 비슷한 시그널을 줄 때까지 대기하고, 그때 검증 사이클 시작하라.
