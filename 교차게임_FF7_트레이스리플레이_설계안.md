# 교차-게임 FF7 키스톤 검증 설계안 — 트레이스-리플레이가 JRPG에 일반화되나

> 1차목표 = 트레이스-리플레이 충실도(이벤트별 수치 재현). gen5 *교차-전투*는 통과(★ 55→14).
> 이 설계는 그 키스톤(효과 디스패처 + 설정 가능한 데미지 엔진 + 트레이스-리플레이)을 **구조가
> 다른 게임(FF7=classic JRPG)**에 던져 *교차-게임* 2-가드를 잰다. "스키마가 포켓몬 모양으로
> 굳었는가"의 직접 측정.
>
> 주의: `검증_FF7`의 CSV(battle_log·attack_log)는 *옛 집계 파이프라인*(ML/SR/per-battle backtest,
> 이미 66% 채점)용이다. 이 설계는 **다른 축** — `ff7_ref.py`의 규칙으로 *단일 전투 이벤트
> 트레이스*를 새로 생성해 트레이스-리플레이 하니스로 이벤트별 divergence를 잰다.

## 0. 왜 FF7인가 (HS 제외)

FF7은 *엔티티 스탯 전투*(HP·공방 스탯·턴·데미지식) — gen5와 같은 골격이라 키스톤이 곧장
적용된다. HS(덱빌더)는 *시퀀스 결정 게임*(핸드·보드·덱 상태머신)이라 entity-HP-트레이스 모델
자체가 안 맞고, 옛 실험이 이미 47%로 그 경계를 확정(= X6/다음목표 영역). 따라서 키스톤 교차-게임
대상은 **FF7**.

## 1. FF7 → 엔진 매핑 (클린룸 검증 완료)

**핵심 검증**: FF7 phys·magic이 *하나의* 엔진 공식 + categories 라우팅으로 정확 재현(6/6 셀 OK):

```
통합식:  damage = floor( floor(offense*(offense+50)/64) * (512-defense)/512 ) * power/16
categories:  Physical → offense=Strength+WeaponAttack, defense=Vitality+ArmorDefense
             Magic    → offense=Magic+WeaponMagic,     defense=Spirit+ArmorSpirit
element:  Magic만 elem_mult(type_table) 적용. Physical은 무속성(1.0).
```

즉 엔진의 *설정 가능한 `global_damage_formula` + `categories`(phys/spec) + `type_table`*가 FF7
데미지 코어를 그대로 담는다. gen5 매핑(atk/df, spa/spd)을 FF7 스탯합으로 재배선만 하면 된다.

| FF7 요소 | 엔진 표현 | 판정 |
|---|---|---|
| phys/magic 라우팅 | `categories` phys→atk/df·spec→spa/spd (스탯=합산) | **표현 가능** |
| 통합 데미지식 | `global_damage_formula` 문자열 | **표현 가능**(검증) |
| 9속성 약점/저항(2.0·0.5·0·1.0) | `type_table`(양의 배율) | **표현 가능** |
| 크리(Luck/64 ×2) | 미관측 롤(gen5 크리와 동일 취급) | 롤 노이즈 |
| Limit Break 게이지 | **AI 결정** — 트레이스가 `Limit_Break` 사용을 *관측* → 엔진은 Power-32 phys로 정상 계산 | **스코프 밖**(데미지 갭 아님) |
| 속성 **흡수(-1 = 회복)** | `type_table`는 양의 배율만 → 표현 불가 | **(ㄴ) 언어확장 후보** |

## 2. 예측 평결

트레이스-리플레이에서 FF7의 데미지 충실도는 **흡수(-1) 단 하나**의 언어확장으로 닫힐 전망. 나머지
(라우팅·식·9속성·Limit Break 데미지)는 기존 엔진 설정으로 표현된다. → 예측: **키스톤이 JRPG에
일반화**(gen5와 동형 결과), (ㄴ) = 흡수 1건. 흡수는 `type_table` 음수 허용 + APPLY_DAMAGE가 음수
elem_mult를 회복으로 라우팅하는 *효과타입 1개*(gen5 heal_frac 친척)로 표현 가능할 것 — 즉
언어확장이지만 *작고 일반적*. 이게 교차-게임 2-가드의 핵심 측정.

## 3. 산출물 (빌드 단계 — 각 단계 클린룸 게이트)

1. **`ff7_trace_gen.py`** — `ff7_ref.py` 규칙으로 *단일 전투*를 돌려 이벤트 트레이스 생성. 결정론
   시드 + `expected=True`(롤·크리 제거)로 *데미지 갭을 롤 노이즈와 분리*. 출력 = 하니스가 먹는
   정규화 트레이스 IR(showdown_trace.parse_replay 출력과 동형): `{events, nick2species, meta}`.
   - 1v1·교체 없음. 매 턴 actor가 상대에게 move. event: `{action:'move', actor, actor_side,
     target, move:{name}, turn, context:{}}` + 데미지 결과는 `-damage` 상당 env/hp로.
   - HP는 *절대*(1500~4500) → 골든과 동일 경로(퍼센트 가드 무관).
2. **`ff7_reference.py`** — reference_gen5와 *같은 인터페이스*: `BASE`(두 캐릭터 스탯), `MOVES`
   (name→power/category/element), `SPECIES_TYPES`(캐릭터 종족 약점/흡수), `TYPE`(9속성), `SETS`
   (없음/None), `make_char`(atk=STR+WA·df=VIT+AD·spa=MAG+WM·spd=SPR+AS·maxhp=HP), `build_game_config`
   (categories·type_table·formula=FF7식·stab_factor=1.0·crit 없음), `EFFECTS`/`CONTACT_MOVES`(빈).
3. **`run_ff7.py`** — FF7 트레이스 + `ff7_reference`로 `run_and_diff` → 이벤트별 divergence +
   분류(데이터 / **흡수 (ㄴ)** / 롤). run_xval 패턴 복제(앱사이드).

## 4. 하니스 적응 (IR/인터페이스 매칭이 빌드의 주 작업)

`run_and_diff(trace, ref)` → `setup_for_engine` → `prepare_run`(build_participants +
build_trace_actions) → `run_simulation`. FF7가 닿으려면:
- 트레이스 IR이 prepare_run이 읽는 필드(nick2species·move 이벤트·관측 HP/max·turn)를 갖출 것.
- `ff7_reference`가 prepare_run·make_char·build_game_config·run_simulation이 호출하는 심볼을 구현.
- 대부분 gen5 인터페이스의 *부분집합*(abilities/items/natures/weather/hazard 불필요) → ff7
  reference는 작게. 막히는 지점(IR 필드 누락 등)은 *진단 후* 최소 보강.

회귀0: ff7_reference·트레이스·run_ff7은 **신규 파일**. 엔진/기존 reference 무수정(흡수 표현이
필요해지면 그때 *효과타입 1개* 추가를 별도 PR로, gen5 회귀0 게이트와 함께).

## 5. 측정 항목

- **닫힘**: phys/magic 라우팅·통합식·9속성(흡수 제외)·Limit Break 데미지가 롤 노이즈 내로.
- **(ㄴ) 흡수**: 흡수 속성 공격이 회복(음수)인데 엔진이 못 내면 ★ → 효과타입 1개로 닫히는지.
- **결론**: (ㄴ) 수가 0~1이면 키스톤이 JRPG에 일반화(교차-게임 2-가드 통과). 다수·다양하면
  포켓몬 모양으로 굳은 것.
