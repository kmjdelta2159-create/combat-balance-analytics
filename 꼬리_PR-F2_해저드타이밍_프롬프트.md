# 꼬리 PR-F2 — 진입 해저드 타이밍 (하니스-통일 적용 + T-1 윈도우)

> 점근 꼬리 두 번째 PR. F1(Seismic Toss)에 이어, held-out 분류에서 **최대 버킷(7셀)**으로
> 확인된 진입 해저드 타이밍을 닫는다. 이 프롬프트는 *추정이 아니라* 런타임 계측
> (`run_f2diag.py`)으로 확정된 두 버그를 고친다.

---

## 0. 무엇을, 왜 (확정 진단)

`run_f2diag.py`의 [D] 대조표가 진입 해저드 경로를 런타임으로 갈라, **별개의 두 버그**를
확정했다(정적 Read만으론 평결의 "forced 미적용" 모델로 오진했을 지점 — 계측이 교정):

### 버그 A — 미발화(under-application). 5셀.
`T6 Clefable · T9 Abomasnow · T11 Gliscor · T14 Reuniclus · T27 Reuniclus`
- 다섯 진입 모두 **T-1 해저드가 있는데 `_fire_switch_in` 콜백이 한 번도 안 불림**
  (`콜백X 발화X`). resync(`_make_resync`)가 `on_field`을 직접 세팅하면서 그 진입의 switch
  액션/콜백을 건너뛰어, 진입 해저드가 통째로 누락된다.
- 결과: 엔진이 진입 데미지 0 → log<eng(엔진 과소). 예: T9 Abomasnow log=63 eng=100(gap 37).
- **주의**: 같은 자발 교체라도 `T8/T10 Jirachi · T11 Scrafty · T12 Skarmory · T15 Clefable ·
  T21 Scrafty · T23 Gliscor`는 `콜백O 발화O`로 정상이다. 즉 엔진의 진입-해저드 *계산*은 옳고,
  문제는 **특정 진입이 콜백 경로를 우회**하는 것뿐이다. 8/13 정상, 5건만 샌다.

### 버그 B — 과적용(over-application, 윈도우 오프바이원). 2셀.
`T4 Gliscor · T5 Skarmory`
- `T-1해저드={}`(진입 직전엔 해저드 없음)인데도 `발화O`. 엔진이
  `engine.py` L1484-1486에서 `field_state["hazard"] = hazard_by_turn[turn]`로 **현재 턴(T)**의
  해저드를 읽어, *그 턴에 깔린* SR을 진입 유닛에 잘못 적용한다.
- 정답 윈도우 = **`hazard_by_turn[T-1]`**(진입 시점 = 턴 시작 = 직전 턴 끝의 해저드).
- 지속 해저드라 정상 8건은 `[T]==[T-1]`로 무해, 해저드가 *그 턴에 바뀐* T4/T5에서만 갈린다.
- 결과: log=100 eng=87(엔진 과데미지, gap 13).

근거 산출물: `run_f2diag.py` [A]기대진입+T-1/T해저드 · [B]콜백관찰 · [C]발화관찰 · [D]대조.

---

## 1. 설계 결정 — 하니스-통일 진입 해저드 (권장)

두 버그 모두 **resync 타이밍**에 얽혀 있다. 엔진 콜백 경로(`_fire_switch_in`→
`_apply_entry_hazard`)는 8건엔 맞지만 (A)에서 일부 진입을 우회하고 (B)에서 윈도우가 한 칸
밀려 있다. 적용 지점이 두 군데(엔진 콜백 8건 + 누락 5건)로 갈리면 윈도우/중복을 양쪽에서
맞춰야 해 취약하다.

→ **트레이스-리플레이의 진입 해저드를 하니스(`fullbattle_run`)가 단일 책임으로 적용한다.**
트레이스가 진입 시점을 정확히 알고(onfield 타임라인) 해저드 타임라인(`hazard_by_turn`)도
하니스가 만든다. 진입 해저드는 트레이스의 시계에 속하므로 하니스가 적용하는 게 정합적이고,
**엔진 무관 → 클린룸 검증 가능**하다.

핵심 규칙(전부 하니스 한 곳):
1. 트레이스의 **모든** 진입 유닛에 진입 해저드를 **정확히 1회** 적용.
2. 윈도우 = **`hazard_by_turn[진입턴 - 1]`** (버그 B 해소).
3. 진입턴에 적용해 그 턴 끝 스냅샷(divergence 측정면)에 반영(버그 A 해소 — 콜백 우회와 무관).
4. 타입 스케일은 기존 `engine._hazard_entry_pct`를 재사용(SR 0.125×Rock타입곱, Spikes 층/접지,
   Flying·Levitate 면제) — gen5 정합 검증된 식. 중복 구현 금지.

### 1-A. 중복 적용(double-count) 차단 — 필수
하니스가 모든 진입을 처리하므로, **엔진의 트레이스-동적 진입 해저드가 같은 진입에 또 적용되면
안 된다.** 따라서 트레이스-리플레이 경로에서 엔진의 `hazard_by_turn → field_state["hazard"]`
주입을 끈다:
- `engine.py` L1484-1486의 `field_state["hazard"] = _hz` 주입은 **진입 해저드용으로만** 존재한다
  (X7에서 추가). 이를 제거/가드해 트레이스 모드에서 엔진이 동적 진입 해저드를 적용하지 않게 한다.
- **반드시 보존**: `_apply_entry_hazard`의 **정적 경로**(`game_config['mechanisms']['hazard']`,
  임의 게임용)와 `set_hazard` 무브 경로(`field_state["hazard"]`를 인-엔진 시뮬레이션이 쓰는 길)는
  손대지 않는다. 끄는 건 *트레이스 hazard_by_turn 주입* 한 줄뿐.

### 1-B. 인덱싱(정확히) — `_make_resync` 기준
`_make_resync`의 훅은 `on_round_start(turn=R, participants)`이고 `on_field`을
`onfield_tl[R-1]`(직전 턴 끝 상태)에서 세팅한다. 따라서:
- 라운드 R 시작에 **새로 on-field이 된 유닛** = `onfield_tl[R-1] \ onfield_tl[R-2]`
  = **턴 (R-1)에 진입한 유닛**.
- 그 유닛의 진입 해저드 윈도우 = `hazard_by_turn[(R-1) - 1] = hazard_by_turn[R-2]`.
- resync는 HP를 `log[R-1]`(이미 진입 해저드가 반영된 *관측* HP)로 덮으므로, 진입 해저드를
  **HP 덮어쓰기와 별개로 빼면 이중 차감**이다. → **하니스 적용은 "엔진이 그 진입턴(R-1)에
  스스로 적용했어야 할 데미지"를 엔진 내부 HP에 반영하는 것**이지, resync가 주입하는 관측 HP에
  더 빼는 게 아니다. 적용 지점을 정확히 잡아라(아래 2 참고): 진입턴 R-1의 엔진 처리 중에
  적용되어야 `on_turn_end[R-1]` 스냅샷이 log[R-1]과 맞는다.

> 인덱싱이 까다로우니 **구현 전 `run_f2diag.py`로 현재 동작을 재현**하고, 수정 후 [D]가 전부
> `OK`가 되는지로 검증하라(아래 4). 숫자(예: T9 Abomasnow eng 100→63)가 곧 정답지다.

---

## 2. 적용 표면 (코드 진실은 Read/Grep — mnt 절단 주의)

> bash 샌드박스는 최근수정 .py를 끝부분 절단할 수 있다. 적용 전후 대조는 **Read/Grep**으로,
> 무결성은 적용 후 `wc -l`/`tail`로 확인한다.

대상 파일·함수(라인은 Read로 재확인 후 수정):
- `modules/fullbattle_run.py`
  - `_make_resync(log_snaps, onfield_tl, hp_mode)` — 진입 해저드 적용 로직을 여기에 추가
    하거나, `run_and_diff`에서 `_make_resync`에 `hazard_by_turn`·`type_table`·`participants`
    접근을 넘겨라. 진입턴(R-1) 처리 시점에 `hbt[R-2]` 기반으로 `engine._hazard_entry_pct`를
    호출해 해당 유닛 엔진 HP에 1회 적용.
  - `run_and_diff` / `setup_for_engine` — 이미 `gc["hazard_by_turn"]`·`gc["type_table"]`이
    있으니 하니스가 재사용. (현 build_hazard_by_turn·build_onfield_timeline 그대로.)
- `modules/engine.py`
  - L1484-1486: 트레이스 `hazard_by_turn → field_state["hazard"]` 주입 제거/가드(1-A).
  - `_hazard_entry_pct`(L944)·`_apply_entry_hazard`(L962)의 **정적 경로는 불변**.

> 적용 위치가 `_make_resync`만으로 깔끔히 안 되면(진입턴 R-1에 직접 적용이 필요),
> `run_simulation`의 `on_round_start` 외에 진입턴 처리 훅을 쓰는 안도 검토하되, **단일 적용·
> T-1 윈도우·정적경로 보존**의 세 불변만 지키면 된다.

---

## 3. 불변 (회귀 0 보장)

- **정적 진입 해저드**(임의 게임, `mechanisms.hazard`)와 `set_hazard` 무브 경로는 동작 불변.
- `_hazard_entry_pct`의 식(SR 타입곱·Spikes 층/접지·Flying/Levitate 면제) 불변 — 재사용만.
- 진입 해저드는 **진입 유닛에만, 진입턴에, 1회**. 비진입·재진입 아닌 잔류 유닛엔 무적용.
- 골든 `run_b4` divergence가 **악화되지 않아야** 한다(평결은 오히려 switch-in-turn 동반개선 예측).

---

## 4. 검증 (전부 앱사이드 — 사용자 실행 후 출력 붙임)

순서대로, 셋 다 통과해야 F2 종료:
1. **`python run_f2diag.py`** — [D] 대조표가 **전 행 `OK`**(현재 미발화 5 + 과적용 2가 사라짐).
   [C] 발화 기록이 **진입당 정확히 1회**(중복 없음), 윈도우가 T-1과 일치.
2. **`python run_cellclass.py`** — `[요약]`의 **F2(해저드 타이밍) 버킷이 0(또는 닫힌 셀만큼
   감소)**. 다른 버킷(NEW 스탯스테이지·F3) 수가 늘지 않음(부작용 없음).
3. **`python run_b4.py`** — 골든 **회귀 0**(divergence 불변 또는 개선). 악화 시 즉시 롤백.

추가: 클린룸(/tmp)에서 하니스의 진입집합·윈도우 계산(순수부)을 엔진 없이 검증 가능
(`run_f2diag` [A]가 이미 트레이스 측 기대값을 산출 — 이와 일치 확인).

---

## 5. 적용 후 보고
- 수정 파일·라인, `wc -l`/`tail` 무결성.
- 위 1~3 출력 전체(특히 run_f2diag [D] 전OK, run_cellclass F2 버킷, run_b4 회귀0).
- 닫힌 셀 귀속(7셀 중 몇이 닫혔나) — 점근 꼬리 갱신용.
