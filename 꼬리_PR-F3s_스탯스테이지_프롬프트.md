# 꼬리 PR-F3s — 스탯 스테이지 (트레이스 boosts → 엔진 stat-stage)

> 점근 꼬리의 신규 메커니즘 버킷. held-out 분류의 NEW(스탯스테이지) 3셀을 닫는다. F1·F2와
> 동일 규율: 추정 아닌 **실측 확정**(`run_boostdiag.py`) 위에서 고친다. 이 메커니즘은 임의
> 턴제 게임 일반성에도 근본적(부스트/디버프는 보편 메커니즘)이다.

---

## 0. 무엇을, 왜 (실측 확정)

분류 NEW 셀 3건 — 트레이스가 명시한 스탯 부스트가 엔진 데미지에 반영 안 됨:

| 셀 | log | eng | 방향 | 원인(트레이스 stage) |
|---|---|---|---|---|
| T24 Scrafty | 81 | 67 | over(엔진 과) | Scrafty **Def+1**(Bulk Up) 미반영 → 물리타 과데미지 |
| T25 Scrafty | 63 | 49 | over | Scrafty **Def+1**(누적) 미반영 |
| T29 Reuniclus | 34 | 67 | under(엔진 소) | 공격자 Scrafty **Atk+2**(×2.0) 미반영 → 정확히 ½ 데미지 |

`run_boostdiag.py` 확정:
- **[A] 트레이스-리플레이 game_config의 `move_effects` 키 = 0.** 부스트 무브(Bulk Up·Swords
  Dance·Calm Mind·Amnesia)는 `reference_gen5` MOVES엔 `(0,'status',None)`로 존재하나 *효과
  스펙이 없다*(move_effects는 step2/UI 경로에서만 생성 → 트레이스 경로엔 없음). 따라서
  `_act_move_effect`가 no-op → 부스트가 엔진 stat-stage로 안 들어간다.
- **[B] 트레이스 `boosts_by_turn`(누적·교체 시 리셋)** 이 ground truth로 검증됨(아래 산식 포함).
- 엔진엔 stat-stage 기계가 **이미 있다**: `get_effective_stat`(active_states의 percent 배율,
  L162)·데미지 계산이 공/방 모두 `get_effective_stat` 사용(L587-602). **빠진 건 데이터(부스트
  상태)를 그 기계에 공급하는 것뿐.**

→ 트레이스의 관측 boosts를 ground truth로 삼아, **하니스가 `boosts_by_turn`을 매 라운드
on-field 유닛의 active_states로 주입**한다(weather_by_turn·hazard_by_turn 타임라인과 동형).
move_effects 스펙을 무브명마다 역설계하는 것보다, 트레이스가 이미 기록한 (who,stat,stages)를
직접 쓰는 게 정합적이고 견고하다.

---

## 1. 설계 — 하니스 공급 boosts 타임라인

### 1-A. 타임라인 빌더 (검증 완료, `run_boostdiag.build_boosts_by_turn`와 동일 규칙)
`fullbattle_run.py`에 `build_boosts_by_turn(trace)` 추가:
- 반환 `{turn: {nick: {stat: net_stages}}}`. 턴 경계마다 on-field 유닛의 누적 stage.
- `move` 이벤트의 `boosts: [{who, stat, stages}]`를 해당 nick에 누적.
- **교체(switch/drag) 시 리셋**(gen5 룰): 떠난 유닛 stage=0, 진입 유닛 stage=0으로 시작.
- 스탯 정규화: `attack→atk, defense→def`(소문자). (저장은 트레이스 표기 `def`로, 매핑은 1-C.)

### 1-B. stage → 배율 (gen5 일반스탯)
```
stage_mult(n) = (2+n)/2   (n>=0)        # +1=1.5 +2=2.0 +3=2.5 ...
              = 2/(2-n)    (n<0)         # -1=0.667 -2=0.5 ...
```
active_states는 percent 배율이므로 **value = stage_mult(n) - 1** (예: +2 → 1.0, -1 → -0.333).
(`get_effective_stat`이 `(base+flat)*∏(1+value)`로 곱하므로 정확히 일치.)

### 1-C. ★ 스탯명 매핑 — 엔진은 방어를 `df`로 쓴다
엔진 `sys_stats = ["atk","df","spa","spd","spe"]`(fullbattle_run의 run_simulation 호출).
`get_effective_stat(char, "df")`로 방어를 읽으므로, 트레이스 `def`는 **`df`로 매핑**해
active_states의 `target_stat`에 넣어야 한다. 매핑: `atk→atk, def→df, spa→spa, spd→spd, spe→spe`.
(이 한 글자 누락 시 방어 부스트가 영원히 무시됨 — 반드시 확인.)

### 1-D. 적용 지점·윈도우 — resync 라운드훅, [R-1] 창
per-unit 상태라 `_make_resync`의 라운드훅(`on_round_start(turn=R, participants)`)이 자연스럽다
(이미 HP/status/on_field를 라운드별로 세팅). 거기서:
1. 각 participant의 기존 **트레이스 부스트 active_states 제거**(id 접두사 `trace_boost_`로 식별).
   (매 라운드 새로 세팅하므로 누적 방지 — 필수.)
2. `boosts_by_turn[R-1]`(직전 턴 끝 상태)에서 그 유닛의 stage를 읽어 active_states 추가:
   ```
   {"id": f"trace_boost_{eng_stat}", "target_stat": eng_stat, "mod_type": "percent",
    "value": stage_mult(n) - 1, "expire_trigger": "PERMANENT", "expire_count": 9999,
    "source_id": "trace_boost"}
   ```
   (`eng_stat`은 1-C 매핑 적용값.)

**윈도우가 [R-1]인 이유(F2와 동일 규율)**: 라운드 R 진입 상태 = 직전 턴 끝. 특히 **T29 Reuniclus의
`def-1`은 그 턴 Scrafty Crunch의 2차효과**라 그 Crunch 데미지 계산엔 적용되면 안 된다(stat 변화는
타격 *후*). `boosts_by_turn[28]`(def-1 없음)이 T29 타격에 정확. → [R-1] 창이 정답.
> 만약 어떤 셀이 [R-1]로 안 닫히면 그 셀만 [R] 창이 맞는지 진단으로 가린다(F2 교훈: 창은 진단이
> 중재). 기본은 [R-1].

### 1-E. 공급 배관
`setup_for_engine`에서 `gc["boosts_by_turn"] = build_boosts_by_turn(trace)` (weather/hazard와
나란히). `run_and_diff`가 resync 훅에 넘겨 1-D가 소비.

---

## 2. 적용 표면 (Read/Grep로 라인 재확인 — mnt 절단 주의)

- `modules/fullbattle_run.py`
  - `build_boosts_by_turn(trace)` 신규(1-A) + `stage_mult` 헬퍼(1-B).
  - `setup_for_engine`: `gc["boosts_by_turn"]` 공급(1-E).
  - `_make_resync`: 라운드훅에 트레이스 부스트 active_states 주입(1-C·1-D). resync HP/status
    세팅 로직은 불변, 부스트 세팅만 추가.
- `modules/engine.py` — **무변경 예상**. `get_effective_stat`·데미지 계산이 이미 active_states를
  읽는다(L162·L587-602). 손대지 말 것(확인만).

---

## 3. 불변 (회귀 0)

- 엔진 stat-stage 기계(`get_effective_stat`·`_act_move_effect`·move_effects)는 불변 — 트레이스
  타임라인이 active_states를 *추가 공급*할 뿐, in-engine(UI) 게임의 move_effects 경로 그대로.
- 트레이스 부스트 active_states는 **id 접두사 `trace_boost_`로 격리**, 매 라운드 교체(누적·잔류 0).
- **골든 `run_b4` 회귀0**: 골든에 부스트 무브가 없으면 타임라인이 비어 무영향. 있으면 오히려
  정확도 개선(현재 무시 중). 악화 시 즉시 롤백.
- **범위 밖(이번 PR 아님)**: 크리티컬이 방어 부스트를 무시하는 규칙(T27 Scrafty 크리, 잔여 버킷).

---

## 4. 검증 (앱사이드, 셋 다 통과)

1. **`python run_boostdiag.py`** — [C]에서 부스트 무브 사용 시 또는 라운드 주입으로 해당 유닛
   active_states가 채워짐(현재 +0에서 변화). [B] 타임라인과 일치.
2. **`python run_cellclass.py`** — `[요약]`에서 **NEW(스탯스테이지) 버킷 0**(T24·T25 Scrafty·
   T29 Reuniclus 닫힘). 다른 버킷 무증가(특히 새 over/under 미발생).
3. **`python run_b4.py`** — 골든 회귀0(불변 또는 개선).

---

## 5. 적용 후 보고
- 수정 파일·라인 + `wc -l`/`tail` 무결성(특히 `def→df` 매핑 라인).
- 위 1~3 출력(run_cellclass [요약]에서 NEW 버킷 닫힘, run_b4 회귀0).
- 꼬리 갱신: F1·F2·F2b·F3s 누적 닫힌 셀, 남은 버킷(F3 단건·잔여).
