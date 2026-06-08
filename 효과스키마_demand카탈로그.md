# 효과-스키마 demand 카탈로그 — 코퍼스 2전투에서 추출

> 트레이스-리플레이 코퍼스 확장 산출. 효과-스키마를 *단일 전투가 아니라 실 demand에서
> 결정화*하기 위한 입력. 출처: gen6 Kecleon전 + gen5 OU전. env([from])·start/activate·
> cant·move→status 스트림 파싱. 엔진 현재 커버리지에 겹쳐 분류한다.

## 0. 한 줄

코퍼스가 요구하는 메커니즘을 셋으로 가른다 — **이미 엔진이 하는 것**(검증만 하면 됨),
**부분/Tier-3 갭**(작은 수정), **미구현 발동형 클러스터**(효과-스키마 본체). 발동형 ~10개가
*공통 shape(트리거×조건×효과×스코프)*를 보여 — 이제 스키마 결정화가 데이터로 정당화됨.

## 1. 엔진이 이미 커버 (gen5 로그 env 스트림으로 *검증 완료* — 38/38 정합 ±1)

복제가 생각보다 가깝다 — 로그가 요구하는 상당수를 엔진이 이미 1급으로 하고, **실 수치로
확정됐다**: sandstorm chip **9/9**(1/16), Leftovers **20/20**·Black Sludge **4/4**·Rain Dish
**2/2**(1/16 회복), 화상 틱 **3/3**(1/8). 아래 항목별:

- **Leftovers/Black Sludge 회복** (env: Leftovers ×26, Black Sludge ×4) — regen-class. 엔진 보유.
- **typechange/Protean** (start: typechange ×10) — `current_type`. 엔진 보유.
- **sandstorm 날씨 chip** (env: sandstorm ×9) — 엔진 F3(weather_defs: chip_percent +
  immune_types). gen5 모래 = chip 1/16 + Rock/Ground/Steel 면역. **직접 검증 가능.**
- **독/화상 틱** (env: psn ×3, brn ×3) — 엔진 상태 틱(`_act_status_tick`). 보유.
- **상태 부여 + 행동 게이팅** (move→status: Spore→잠듦, Scald→화상, Body Slam→마비,
  Toxic→맹독) — 엔진 G1(inflict_status + status_gates). 보유.

→ 다음 단계 후보: 이 커버분을 트레이스 env/status 스트림으로 *검증*해 "이미 되는 것"을
숫자로 확정(저비용, 1차목표 진척 가시화).

## 2. 엔진 부분 / Tier-3 갭 (작은 수정)

- **Stealth Rock** (env ×13) — 엔진 해저드 substrate(F2) 있으나 *평탄 percent*. 로그는
  타입 스케일(Rock약점 2배…). → 진입 데미지를 타입 상성으로 스케일하는 작은 PR.
- **맹독(Toxic) 누진** (env: psn 일부가 tox) — 틱은 있으나 평탄. 로그는 1/16→2/16… 누진.
  → 누진 틱 작은 PR.

## 3. 엔진 미구현 — 발동형 클러스터 (효과-스키마 본체)

공통 shape가 또렷하다: **트리거 × (조건) × 효과(자원/스탯) × 스코프**. ~10 예시:

| 메커니즘 | 트리거 | 효과 | 스코프 |
|---|---|---|---|
| flinch (Fake Out) | on-hit(우선) | 대상 이번 턴 행동불가 | 대상 |
| Rough Skin / Rocky Helmet | on-contact(피격) | 공격자 maxHP 1/8 데미지 | 공격자 |
| Life Orb | on-attack | 공격자 maxHP 1/10 반동 | 자신 |
| Rain Dish | on-turn-end(비) | 자신 maxHP 1/16 회복 | 자신 |
| Wish | 지연(2턴 후) | 대상 슬롯 HP 1/2 회복 | 슬롯 |
| Protect | on-action | 이번 턴 피격 무효 | 자신 |
| Substitute | on-action | maxHP 1/4로 대체 자원 생성(흡수) | 자신 |
| Trick | on-hit | 도구 교환 | 양자 |

이들은 *서로 다른 게임 메커니즘*이지만 표현 형태가 같다 — 트리거(on-hit/on-contact/
on-turn-end/on-action/지연) × 효과(자원 델타/자원 생성/행동 차단/속성 교환) × 스코프
(자신/대상/공격자/슬롯). **단일 전투에선 안 보였을 이 공통 shape가 2전투·2세대에서 반복
확인됨** → 스키마를 이 형태로 결정화할 근거.

## 4. 결론 / 다음 갈래

- **결정화 정당화됨**: 발동형 ~10개가 공통 shape를 반복 → 효과-스키마(트리거×조건×효과×
  스코프 over 자원/스탯)를 이제 설계해도 "성급한 추상화"가 아니다. (1 battle이 아니라
  2 battle/2 gen에서 결정화.)
- 동시에 **엔진이 §1을 이미 커버** → 1차목표가 생각보다 가깝다. 발동형 클러스터(§3) +
  Tier-3 갭(§2)이 실질 잔여.
- 권고 순서:
  1. **(저비용 선검증)** §1 커버분을 트레이스 env/status 스트림으로 검증 — sandstorm chip·
     status 틱·regen이 로그 수치와 맞는지. "이미 되는 것"을 숫자로 확정.
  2. **(본체) 효과-스키마 설계안** — §3 카탈로그에서 트리거×조건×효과×스코프 결정화. 발동형
     클러스터를 *데이터*로 표현(엔진 효과 hook + 스키마). 첫 인코딩 후보: flinch·Rough Skin
     (단순·자원 델타).
  3. Tier-3 갭(SR 타입스케일·맹독 누진)은 작은 PR로 사이사이.
- **교차-게임 가드**: §3 shape가 *비-포켓몬* 스탯턴제 로그에서도 성립하는지는 굳히기 전
  점검(로드맵). 지금은 2 모두 포켓몬(다른 세대)이라 *세대* 일반성까진 확인, *게임* 일반성은
  비-포켓몬 로그 확보 후.
