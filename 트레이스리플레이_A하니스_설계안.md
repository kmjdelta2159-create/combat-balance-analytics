# A 하니스 설계안 — 쇼다운 파서 + 트레이스 모드 + diff

> 로드맵(`복제완성_재정리_1차목표로드맵.md`) §4-A의 정식 설계. 1차목표(트레이스-리플레이
> 충실도)의 *첫 발*. 측정 토대이자 역설계→사용자수정 루프의 계기(diff)를 세운다.
> 본 설계는 실 데이터(업로드된 Kecleon전)로 파서를 프로토타입해 IR 스키마를 *검증한 뒤* 작성됨.

## 0. 목적·범위

쇼다운 리플레이를 넣으면 엔진이 *로그에 찍힌 행동을 그대로 먹고* 결과를 재현하는지
*이벤트별로 대조*한다. 세 조각: **파서**(HTML→정규화 트레이스 IR), **트레이스 모드**(AI 대신
관측 행동 주입), **diff**(엔진 산출 vs 로그 관측). AI 의사결정 복제는 스코프 밖 — 로그가 무엇을
했는지 이미 알려주므로 행동을 *주입*하고 *해결*만 대조한다.

범위: 싱글. 더블 보류. 첫 마일스톤은 *구현된 메커니즘만 쓰는 단순 전투*로 데미지 코어를 못박음.

## 1. 입력 형식 (검증됨)

쇼다운 리플레이 HTML 안 `<script type="text/plain" class="battle-log-data">…</script>`에
`|`-구분 프로토콜이 통째로 있다. 파서: ① 그 script 블록 추출 → ② `\/`→`/` 이스케이프 복원
→ ③ `|`로 시작하는 줄만 → ④ 첫 토큰으로 이벤트 분기. (라이브 프로토콜·`.log` 텍스트도 같은
줄 형식이라 ①만 우회하면 동일 경로.)

## 2. 정규화 트레이스 IR (실 데이터로 추출 검증)

```
{
  "meta":   { gen, tier, gametype, rules[], players{p1,p2}, teams{p1[종족…], p2[종족…]} },
  "nick2species": { 닉네임: 종족 },          # switch/drag/replace에서 누적
  "events": [ {turn, actor_side, actor(닉네임), species, action, …}, … ]
}
```

**데미지 귀속 — `[from]` 태그가 열쇠 (PR1에서 검증·구현됨).** `-damage`에 `[from]`이 없으면
*무브 직격*(공식 검증 타깃 → move 이벤트 `hits[]`에 부착), 있으면 *부수 데미지*(날씨/해저드/
상태/도구 → 별도 `env` 스트림). 실측 Gen5전: `-damage` 54개 중 직격 23·부수 31(Stealth
Rock·sandstorm·psn·brn·Life Orb…). 이 분리 덕에 "무브 데미지"와 "환경 칩"이 안 섞인다.

`action` 종류:
- `move` — {move, target, hits[], flags[], boosts[], faints[], context}. `hits[]`=직격
  `{who,prev,cur,max,delta}`. `flags`=crit/supereffective/resisted/immune/status:X.
  **`context`={weather(발효 날씨), attacker_status}** — "깨끗한 이벤트" 필터의 근거.
- `switch` — {actor, species, hp, max, status, forced(=drag면 강제), weather}.
- `env` — {kind:damage|heal, src([from] 내용), who, prev, cur, max, delta}. 부수 스트림.
- `cant` — {actor, reason} (flinch 등) · `start`/`end`/`activate` — {actor, what}
  (typechange/Substitute…) · `faint` — {who} · `win` — {who}.
- HP 필드 상태 접미사(`60/420 tox`)·기절(`0 fnt`) 파싱.

검증 결과(Kecleon전, 38 이벤트): 메타·팀프리뷰·닉네임→종족(6) 정확, 정확 HP delta 추출
(T1 Fake Out −79, T2 Sucker Punch 크리+SE −213 KO, T10 resisted −27, T11 SE −296 …),
boost·crit·immune·faint 플래그 부착 정상. **답안지 = 로그의 관측값**(데미지 delta·상성플래그·
크리·기절)이고, 엔진은 이를 *독립 계산*해 대조한다.

## 3. 트레이스 모드 — 엔진 시ーム만 갈아끼움 (회귀 0)

엔진 결정·RNG가 전부 두 시ーム으로 돈다(확인): **ActionRegistry**(`MOVE_SELECT`=
`_act_move_select`, `TARGET_SELECT`=`_act_target_select`) + **StochasticityModule**(명중
`roll_hit`/`roll_chance`, 크리 `_act_crit_calc`, 다중hit `roll_range`). 해결 코드(데미지·상성·
적용)는 *안 건드린다.*

- **행동 주입**: 트레이스 구동 selector를 `MOVE_SELECT`/`TARGET_SELECT`에 등록 오버라이드 —
  계산 대신 *현재 트레이스 이벤트의 move/target*을 반환. 교체 행동(자발 `switch`)은 신규
  trace 액션으로 주입(현재 엔진 교체는 기절 구동 `replace_from_reserve`뿐 → *자발 교체 주입*은
  신규 표면, §6 미지수).
- **RNG 재생**: 트레이스 구동 StochasticityModule — 로그가 보여준 결과를 그대로 반환:
  명중=miss 이벤트 없으면 hit, 크리=`-crit` 있으면 True. 데미지 롤(0.85~1.0)은 로그에 없음 →
  back-solve 또는 스윕(§5).
- **스텝 드라이버**: 트레이스를 턴·행동 순으로 전진시키며 엔진 한 스텝씩 구동, 각 스텝 후 diff.

이 구조라서 엔진 *해결 로직 회귀 0* — 결정·RNG 시ーム만 교체.

## 4. diff 기준

스텝(=move 이벤트)별 대조:
- **데미지**: 엔진 산출 dmg vs 로그 delta(절댓값). 데미지 롤 미지(§5) 때문에 *허용 구간*
  [0.85R, 1.00R]에 드는지로 1차 판정(R=롤 제거 기준 데미지). 크리는 `-crit` 반영.
- **상성**: 엔진 elem_mult 부호(>1/<1/=1/=0) vs 로그 `supereffective`/`resisted`/`immune`.
  (이중타입 곱은 이미 정확 — 0배·4배 자연.)
- **기절 타이밍**: 엔진 KO vs 로그 `faint` 동일 스텝.
- **부가**: boost·heal·status 발생 일치(있는 범위에서).
잔차(불일치) = RE/수정이 채워야 할 신호 → D 루프로.

## 5. 숨은 스탯 역산 (1급 서브시스템)

로그에 EV/IV/성격 없음 → 정확 데미지 재현 불가. 관측 데미지 + 종족값(등장분) + 데미지식에서
공격자 유효 스탯을 *back-solve*. 단일 히트는 미정(유효공격 × 롤 × 크리가 한 식) → ① 같은
공격자의 여러 히트로 구속, ② 표준세트(쇼다운 usage) prior, ③ max HP가 HP 스탯 일부 노출
(예: 252/252, 424). 이게 슬라이더의 역설계 끝이 실 데이터에서 도는 자리 — A의 산출이 D의
입력이 된다.

## 6. 정직한 미지수·경계

- **자발 교체**: 로그의 비-기절 `switch`는 *선택된 행동*인데 현재 엔진엔 자발 교체 액션이
  없다(기절 구동만). 트레이스 모드가 이를 주입하려면 작은 신규 표면 필요. 첫 마일스톤(단순
  전투, 교체 적음)에선 회피 가능.
- **이 Kecleon전은 코어 검증용 아님**: 전체 파싱이 확인 — **Substitute(⑤, 대타 흡수로 HP
  무변동), U-turn(피벗 교체), Fake Out(flinch), Recover(50% 자힐), 이중 Protean**을 끌어옴.
  → D의 *초기 코퍼스 한 건*. 코어 검증(데미지 diff≈0)은 대타·피벗·회복무브·변신 없는 단순
  싱글전으로.
- **데미지 롤**: 0.85~1.0 미관측 → 허용구간 판정 + 역산으로 좁힘.

## 7. 코어 검증 단위 = 이벤트 (단순 전투 불필요)

실 사다리 전투는 거의 다 메커니즘 밀집(업로드 2건: Gen6=대타/피벗/Protean, Gen5=날씨/SR/
잠듦/맹독)이라 *깨끗한 전투*를 찾는 건 비현실적. 그래서 **코어 검증의 단위를 전투가 아니라
*데미지 이벤트*로 내린다.** `clean_damage_events`(발효 날씨 없음 + 공격자 화상 없음 + 자가
데미지 제외)로 깨끗한 직격만 뽑으면 밀집 전투에서도 타깃 충분(Gen6 9·Gen5 3). 단순 전투를
*기다릴 필요 없이* 이미 받은 실 로그로 코어 검증 가능 — **이 결정거리는 해소됨.**

- **마일스톤**: 깨끗한 직격 이벤트의 엔진 산출 vs 관측 데미지가 롤 허용구간 [0.85R,1.00R]
  내 + 공격자 유효스탯 역산. 파서·트레이스모드·diff end-to-end 1회 닫힘.
- **PR 분할**: (1) **파서 모듈** — `트레이스리플레이_PR1_파서_프롬프트.md`로 *작성·검증 완료*
  (신규 `modules/showdown_trace.py`, 기존 무변경). → (2) 트레이스 구동 selector +
  StochasticityModule(시ーム 오버라이드, 해결코드 무변경). → (3) diff 하니스 + 역산 v0.

## 8. 사용자 결정거리

- ~~코어 검증용 단순 황금표준~~ — **불필요로 해소**(이벤트 단위 검증, §7).
- **PR1 적용 승인** — `modules/showdown_trace.py` 생성. 이후 PR2(트레이스 모드) 진입.
- (뒤로) 교차-게임 일반성 점검용 *비-포켓몬* 로그 — 스키마(B) 굳히기 전.
