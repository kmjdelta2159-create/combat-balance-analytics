# Phase 8c-α — 종결 보고서

검증 인프라 도입(per-battle backtest)을 통한 두 잔여 갭 정리. 2026-05-26 종결.

---

## 한 줄 요약

검증 패널의 misleading 3% 점수를 의미 있는 충실도 지표로 대체했고, **외부 클린룸 harness 의존을 종결했다** — 앱 안 측정이 외부 측정과 정량적으로 align(66.2% ↔ 채점표 65.5~67.2%)함을 확인했다.

---

## 1. 무엇이 풀렸나

### 풀린 두 갭

| 갭 | Before | After |
|---|---|---|
| 사용자 게임 검증 "승률" | **3%** (misleading) | **66.2%** (의미 있음) |
| Pokemon 충실도 측정 | 외부 클린룸 harness 필요 | **앱 안에서 직접** |

두 문제 모두 **공통 뿌리 = "앱 내부에 per-battle backtest가 없음"** 으로 환원됐다. 새 모듈 `modules/per_battle_backtest.py` + step6 백테스트 섹션 1회 삽입으로 둘 다 해결.

### 의미 없던 3%의 원인

기존 `calculate_validation_score`는 "GM Mode 1개 매치업의 MC 승률"과 "로그 전체의 target_col 평균"을 빼서 점수화했다. 시뮬레이터가 아무리 정확해도 매치업이 균형이 아니면 자동으로 0~3%로 떨어지는 구조. `검증_Run결과_채점표.md` §1-1이 이 결함을 이미 기록해뒀음(*"overall 점수는 'MC 1매치업 승률이 0.5에 얼마나 가까운가' 단일 수치로 붕괴"*).

Phase 8c-α는 기존 `calculate_validation_score`를 건드리지 않고 새 backtest 섹션을 추가했다 — 기존 검증의 damage_formula/element_chart/buff_duration 같은 보조 지표는 그대로(매핑되면 의미 있음), 결정적인 "전체 일치율"만 backtest의 진짜 충실도 지표로 대체됨.

---

## 2. 정량 align 증거 — 결정적 양성 컨트롤

`pkmn_battle_log.csv` 5000행 (Pokemon 검증 정답지) 업로드 → Step 2 매핑(HP/Attack/Defense/SpAtk/SpDef/Speed + Type1/Type2, target Is_Victorious) → 데미지 공식 `22 * 90 * (attack + spatk) / (target_defense + target_spdef) / 50 + 2` → 백테스트 실행.

| 측정 | 값 |
|---|---|
| 우리 in-app (avg P/S formula, no type table) | **66.2%** |
| 채점표 §2 D — phys 라우팅 단독 | 65.5% |
| 채점표 §2 D — spec 라우팅 단독 | 67.2% |
| 채점표 §2 D — 평균 P/S 라우팅 | ~66.4% |

**우리 66.2%가 채점표의 단일 라우팅 결과와 ±1pp 안에서 일치**. 외부 클린룸 harness가 측정한 충실도를 앱 안에서 정량 재현. backtest 인프라가 의미 있는 측정을 한다는 결정적 증거.

부수 양성 컨트롤:
- 클래스 분포 257:243 (51.4%:48.6%) — 완벽 균형 → battle_size=2 + 앞1=Ally 가정 정확
- 양쪽 정확도 65.0% / 67.5% — 한쪽 편향 없음
- 500전투 6초 완료 — 멀티코어 병렬 정상

---

## 3. 발견된 한계 — ML-format 로그

도구 검증용 합성 로그 `universal_test_log.csv` 분석 결과:
- 5000행, Is_Victorious 분포 51.3% (정상 균형)
- battle_size=8 가정 시 합계 분포가 **Binomial(8, 0.5) 종 모양** (peak at sum=4, 합=0/8 거의 0)
- 이는 8행 안에서 Is_Victorious 8개가 거의 독립적이라는 신호 → **paired battle log가 아니라 ML 학습용 형식**

이런 형식의 로그는 per-battle backtest의 입력으로 부적절하다 — 행 순서가 전투 그룹화를 의미하지 않아 측정값이 noisy해진다. universal_test_log로 측정한 56.8%(battle_size=2) / 60.4%(battle_size=8)는 엔진 충실도가 아니라 형식 미스매치 노이즈.

→ 이는 사용자가 실제 paired 로그(Pokemon 형식 또는 자체 생성)를 쓸 때만 충실도가 의미 있게 측정된다는 뜻. 인프라는 정확하다 — 입력 데이터의 구조가 중요할 뿐.

---

## 4. 현재 도구 상태 (Phase 1~9b + 8c-α 통합)

| Phase | 영역 | 상태 |
|---|---|---|
| 1~7 | 업로드·매핑·SR·LR 프로파일링·결측치·검증 프레임 | 완료 |
| 8a | 무브 시스템 (MOVE_SELECT, move_power/offense/defense 주입) | 완료 |
| 8b | N-type 상성표 + STAB (game_config 기반) | 완료 |
| 9 | 엔진-인-더-루프 스탯 배분 최적화 (`optimize_allocation`) | 완료 |
| 9b | 멀티코어 병렬 핫픽스 (영속 풀 + 평가단위 진행바) | 완료 |
| **8c-α** | **Per-battle backtest 검증 모드 (앱 내부 충실도 측정)** | **완료** |

핵심 모듈 (`engine.py` · `optimizer.py` · `per_battle_backtest.py`)은 전부 검증 통과, 외부 의존성 최소(stdlib + pandas + scipy). step6_dashboard.py는 Phase 8c-α 후 1321줄.

도구가 다루는 게임 도메인: **스탯 기반 턴제 게임(JRPG · 가챠 · SRPG · 덱빌더)**. 연속 슬라이더 원리상 대중적 형태일수록 자동 역설계 비중이, 비대중적일수록 사용자 개입 비중이 크다.

---

## 5. 종결 후 갈래 (사용자 선택)

도구는 기능 측면에서 성숙 단계에 들어섰다. 다음 사이클의 자연스러운 후보:

### A. 사용자 본인 게임 실사용
- 본인 게임의 paired 로그 한 개 만들기 (예: 매 전투의 승리 4명 + 패배 4명을 행 순서로 출력) → backtest로 시뮬레이터 충실도 정확 측정
- 충실도가 70%대면 typeless 권역, 90%대면 완벽 권역
- 그 결과를 Phase 9 옵티마이저·MC 분석에 활용해 진짜 밸런스 분석 시작

### B. 도구 폴리시 (작은 사이클)
- backtest 모듈에 "ML-format mode" 추가 — 행이 그룹화되지 않은 로그도 측정 가능하게 (per-row outcome prediction 방식)
- 결과 패널에 채점표 권역 비교 자동 표시 (66.2% 옆에 "Pokemon avg P/S 라우팅 권역" 자동 라벨)
- 옵티마이저 정밀도 슬라이더 UX (빠름·표준·정밀)

### C. Pokemon 천장 도전 (선택적 학습)
- step2 Phase 8b UI(type_table editor + STAB)에 18타입 표 입력 → ~84% 권역
- 무브풀 수동 입력 → ~92% 권역
- 학습 가치는 있지만 사용자 본인 게임과는 무관

### D. 새 도메인 확장
- 팀 빌드 최적화 (한 캐릭터가 아니라 슬롯 1~3까지 같이 흔드는 다중 ES)
- 메타 분석 (무작위 매치업 분포에서 빌드의 평균 승률·분산)
- 9b 인프라(영속 풀 + 엔진 워커) 그대로 재사용 가능

---

## 6. 산출물 일람

신규 또는 변경된 파일:
- `modules/per_battle_backtest.py` (신규, 129줄, MD5 `98b457fdd7cf40ed9101a86d89d90bdf`)
- `modules/step6_dashboard.py` (1321줄, 8c-α 삽입 156줄, MD5 `01339f2adf20cd5f13e3aee1cfb0f61c`)

문서 산출물 (워크스페이스):
- `Phase8c-alpha_백테스트_프롬프트.md` — Antigravity 납품용 프롬프트
- `Phase8c-alpha_종결보고서.md` — 본 문서

검증 자산 (그대로 유지):
- `검증_포켓몬/pkmn_ref.py` · `pkmn_battle_log.csv` · `pkmn_attack_log.csv`
- `검증_포켓몬/검증_Run결과_채점표.md` · `검증_정답지_측정계획.md`

---

*Phase 8c-α 종결. 도구는 기능 측면에서 성숙 단계에 들어섰다. 다음 사이클 결정은 사용자 본인 게임의 실사용 데이터가 확보되는 시점, 또는 새로운 도구 갈증이 생기는 시점에.*
