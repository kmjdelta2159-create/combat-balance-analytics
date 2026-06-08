# 명중률·다중 hit 설계안 — 갈래 ① (stochasticity 확장)

## 0. 위치
`복제완성_Trajectory_6갈래.md` §3의 독립 갈래 ①. 날씨(F)·행동게이팅(G) 완결 후 진입. 기존
stochasticity(roll_hit/roll_chance/apply_damage_variance) 위에 per-move 명중률 + 다중 hit을
얹는다. config 구동·병렬 안전·회귀 0.

## 1. 정찰로 확정한 지점
- **명중 판정**은 이미 `_act_damage_calc`(engine L627~633)에서 `stoch.roll_hit(char,t,ctx)`로
  호출되나 모듈 전역값(HitChance.base_hit_rate)만 본다. per-move 명중률이 없다.
- **데미지 적용**은 `_act_apply_damage`(L717~743)에서 route_damage 1회. 다중 hit(N회 반복)이 없다.
- **무브 dict**(extract_moves, move_extraction L74)는 name/power/type/category/priority/count
  고정 스키마 — accuracy/hits 컬럼 없음. → 무브 schema 변경 대신 **config 룩업**으로 단다
  (weather_defs/status_gates와 동형, 병렬 안전).
- **RNG**: base에 `roll_range(lo,hi)` 추가(시드 randint). roll_chance(G1 추가분)는 명중에 재사용.

## 2. config 스키마 (정적, 병렬 안전)
`game_config["mechanisms"]["move_props"]` = 무브명 → 속성. 엔진이 current_move 이름으로 룩업.
```
{
  "Thunderbolt": {"accuracy": 1.0},                 # 100% 명중
  "Hydro Pump":  {"accuracy": 0.8},                 # 80% (1 초과면 /100 자동: 80 → 0.8)
  "Fury Swipes": {"hits": [2, 5]},                  # 2~5회 균등(사용자 결정)
  "Double Kick": {"hits": 2},                       # 고정 2회
  "Rock Blast":  {"accuracy": 0.9, "hits": [2, 5]}  # 명중+다중 동시
}
```
- accuracy 미설정 → 기존 roll_hit(모듈 전역) 경로(회귀 0). 설정 시 per-move 우선.
- hits 미설정/1 → 단타(회귀 0). int=고정, [lo,hi]/"lo-hi"=균등 랜덤.

## 3. 사용자 결정 (확정)
- (a) **다중 hit 분포** = 균등 [lo,hi](roll_range). 가중(Pokemon 3/8·1/8)은 후속.
- (b) **다중 hit 판정** = 동일 데미지 + 명중 1회. DAMAGE_CALC에서 명중 1회 굴려 전체 게이팅
  (miss면 dmg 0 → 0회), 계산된 per-hit 데미지를 n_hits회 적용. hit마다 재굴림은 후속(데미지
  파이프라인 재진입 필요 — 보류).

## 4. 동작
- 명중(DAMAGE_CALC): current_move의 move_props.accuracy가 있으면 `roll_chance(acc)`(>1이면 /100),
  없으면 `roll_hit`(현행). miss → dmg 0 + 빗나감 로그 + return(현행 miss 경로 그대로).
- 다중 hit(APPLY_DAMAGE): `_resolve_n_hits(props, stoch)`로 횟수 결정(dmg>0일 때만; miss면 1).
  per-hit 동일 데미지를 route_damage로 n_hits회 적용, 매 회 KO면 중단(get_current<=0 break).
  총합을 dmg로 갱신 → 기존 metrics/로그가 총 데미지 보고. >1회면 "다중 명중 N회" 로그 추가.

## 5. PR 분할
- **PR-A1 — 엔진.** (1) stochasticity base `roll_range`. (2) `_resolve_n_hits` 헬퍼. (3)
  DAMAGE_CALC per-move accuracy. (4) APPLY_DAMAGE 다중 hit 루프. 2파일 4 FIND/REPLACE. 회귀 0
  (move_props 미설정 시 전부 현행).
- **PR-A2 — UI.** step2 메커니즘 expander에 `move_props` JSON 편집기(weather_defs/status_gates
  패턴). 엔진(A1) 적용·검증 후.

## 6. 정직한 한계
- 다중 hit 데미지는 회당 동일(크리/분산 재굴림 없음, 사용자 결정) — per-hit 변동은 후속.
- 명중 1회 굴림이라 "1·2번째만 맞고 나머지 빗나감" 같은 부분 명중 없음(Pokemon 다중 hit과 동일).
- accuracy/hits는 무브명 키 config — 무브 schema는 불변(컬럼 추가 시 detect/UI 손봐야 하므로
  config 룩업으로 격리). 무브명 오타 시 no-op(정의 우선).
- 다중 hit KO 중단은 즉시(루프 내 get_current 체크) — 진입 KO 연쇄(갈래 ⑥)와 별개.
