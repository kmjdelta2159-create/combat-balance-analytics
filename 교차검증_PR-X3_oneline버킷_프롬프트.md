# 교차검증 PR-X3 — one-line 버킷 닫기 (Hail·Poison Heal 회복·U-turn 접촉·status 리포팅)

> 교차검증 평결: held-out gen5 한 판은 *스키마 언어로 한 줄씩* 표현되는 일반 메커니즘 갭과,
> *유일한 언어확장 1건(Seismic Toss 고정데미지)*으로 갈렸다. 이 PR은 **"한 줄로 표현된다"를
> 주장이 아니라 실측으로 증명** — 트레이스로 확정된 빈도순 버킷(Hail 25·Poison Heal 6·U-turn
> 접촉 2 + status 리포팅)을 각 한 줄로 닫고 run_xval 재실행해 ★ 감소를 본다. Seismic Toss(언어
> 확장)는 의도적으로 미포함(다음 PR).
>
> **게이트**: 골든 회귀 ≤ 0. Hail·U-turn은 골든 미등장이라 무영향. **Poison Heal은 골든 Breloom도
> 보유** → 일반 메커니즘이라 양쪽에 옳게 적용돼야 한다. 골든 run_b4 ★가 *늘지 않아야* 하고(이상적
> 으론 Breloom이 더 닫힘), 늘면 진단.

## 트레이스 근거 (각 버킷의 로그 빈도)

`Gen5OU-2026-...` 의 `[from]` 부수-데미지 스트림 집계: **Hail 25 · item:Leftovers 14 ·
Stealth Rock 10 · ability:Poison Heal 6 · Spikes 3 · item:Rocky Helmet 2 · Recoil 2**. 이 PR은
*기존 스키마에 없던* Hail·Poison Heal회복·U-turn접촉(Rocky Helmet)을 닫는다. (Leftovers는 이미
있음·SR/Spikes는 해저드 꼬리·Recoil은 다음.)

## 변경 1 — `reference_gen5.EFFECTS`에 Hail 한 줄 (sand 복제)

`sand`와 동형. 날씨 토큰 `'hail'`(=`build_weather_by_turn`이 'Hail'을 lower로 정규화)이 ON_TURN_END
self 키로 디스패처에 들어온다. Hail은 **Ice 타입만** 면제(모래의 Rock/Ground/Steel과 다름) +
Magic Guard 보유자(이 전투 Clefable·Reuniclus) 면제.

```python
    'hail': {'trigger': 'ON_TURN_END',
             'condition': {'not_types': ['Ice'], 'not_ability': ['Magic Guard']},
             'effect': {'type': 'damage_frac', 'frac': 1/16, 'of': 'maxhp'},
             'scope': 'self', 'source': 'weather'},   # 우박 칩 1/16 (Ice·Magic Guard 면제)
```

## 변경 2 — `reference_gen5.EFFECTS`에 Poison Heal 회복 한 줄 + `of_status` 조건

골든에선 Poison Heal을 *맹독 데미지 억제*(`tox`의 `not_ability`)로만 모델했다. 회복(+1/8)은 미모델
이라 Gliscor가 20턴 버티며 드러났다. ability-키 `'Poison Heal'` 엔트리 + 보유자가 독상태일 때만
발동하는 `of_status` 조건:

```python
    'Poison Heal': {'trigger': 'ON_TURN_END', 'condition': {'of_status': ['tox', 'psn']},
                    'effect': {'type': 'heal_frac', 'frac': 1/8, 'of': 'maxhp'},
                    'scope': 'self', 'source': 'ability'},   # 독일 때 1/8 회복(데미지 대신)
```

`engine._eff_cond_ok`에 `of_status` 조건 연산자 추가(`not_ability` 바로 아래, 동형 2줄):

```python
    os_ = cond.get("of_status")
    if os_ and (owner or {}).get("status") not in os_:
        return False
```

> 동작 확인(디스패처 keys): Gliscor 턴엔드 keys=[ability 'Poison Heal', item 'Toxic Orb', status
> 'tox', weather 'hail']. → `Poison Heal`(heal +1/8, of_status tox 통과) + `tox`(damage, not_ability
> Poison Heal로 skip) + `hail`(damage −1/16) 동시. 순효과 ≈ +1/8 −1/16 = +1/16. 로그 Gliscor 순증과
> 일치. **골든 Breloom**도 동일 발동(Toxic Orb tox + Poison Heal) → 양쪽 일반.

## 변경 3 — `reference_gen5.CONTACT_MOVES`에 U-turn 추가 (데이터 한 줄)

```python
CONTACT_MOVES = {'Body Slam', 'Ice Fang', 'Iron Head', 'Superpower', 'Rapid Spin', 'U-turn'}
```
U-turn은 접촉 → Gliscor가 Skarmory(Rocky Helmet) 치며 사용자 반동 1/6. (로그 Rocky Helmet 2건.)

## 변경 4 — `fullbattle_run` status 리포팅 폴백 (하니스, 회귀0-안전)

`engine_snapshot`/`_status_of`가 `active_states`만 읽어, resync가 주입한 `p["status"]`(frz/tox/slp)를
못 보고 전 status를 엔진=None으로 오보 → status ★ 과다. **트레이스-리플레이에서 status는 관측
입력(답안지)** 이므로 주입값을 그대로 리포트해야 한다. `active_states`에 없으면 `p["status"]`로
폴백:

```python
def _status_of(p):
    for s in p.get("active_states", []):
        st = s.get("gate_status") or s.get("status")
        if st:
            return st
    return p.get("status")    # resync 주입 status 폴백(없으면 None — 회귀0)
```

> 회귀0: 골든이 `active_states`를 채웠다면 폴백 미발동 → 무변. 채우지 않았다면 골든도 주입 status가
> 올바로 리포트(개선). 둘 다 ★ 증가 없음.

## 검증 (적용 후, 순서대로)

1. **클린룸 산수(엔진 무관)**: Gliscor maxhp=hp_stat(75,ev252)=354 → hail int(354/16)=22(≈6%),
   PH int(354/8)=44(≈12%), 순 +22(+6%p). 로그 Gliscor T11→T12: 71→(hail)65→(PH)78 ≈ 모델 71−6+12=77.
   Garchomp maxhp≈357 → hail 22(6%): 로그 T11 Garchomp 2→0 faint(2%<6%) 정합. 표로 3~4셀 대조.
2. **골든 회귀 ≤ 0**: `python run_b4.py` → 첫 divergence·마지막 캡처 27 유지, ★ 수 *증가 없음*.
   Breloom 관련 셀이 닫히거나 동일(Poison Heal 회복이 골든에도 옳게). 늘면 중단·진단.
3. **run_xval 재실행**: `python run_xval.py` → ★ 수가 55에서 *크게 감소*(Hail 25 + PH/status 다수
   소거). 남는 구조적 ★를 붙여달라 — 예상 잔여: Seismic Toss(언어확장·다음 PR)·Ice Shard 과소/
   Brave Bird 과다(세트 정밀화 (ㄱ))·SR 타입스케일/Spikes(해저드 꼬리)·Brave Bird Recoil.
4. **스키마 무파손**: 기존 EFFECTS 12·디스패처 로직 diff 없음(추가만). `of_status`는 신규 조건
   연산자(미설정 시 통과 → 회귀0).

## 의미

이 PR이 ★를 예측대로 떨구면 — Hail·Poison Heal·U-turn이 *각 한 줄*로 닫히면 — 교차검증의
"스키마가 임의 gen5를 한 줄로 표현한다"가 **실측으로 증명**된다. 그러면 남는 진짜 표현력 부채는
Seismic Toss(고정데미지) 단 하나로 좁혀지고, 그게 1차목표 천장의 정직한 측정이다.
