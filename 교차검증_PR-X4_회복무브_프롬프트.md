# 교차검증 PR-X4 — 회복무브 (Roost·Soft-Boiled·Rest, ON_MOVE_USE 무브-소스 heal_frac)

> PR-X3이 held-out ★를 55→21로 떨궜다. 남은 최대 버킷은 **회복무브** — Skarmory Roost(T14·17)·
> Clefable Soft-Boiled(T19)·Scrafty Rest(T23·26)의 자가회복을 엔진이 안 줘서 해당 유닛이 낮게
> 유지되고 *유령 기절 연쇄*(Scrafty T24–26·Clefable T16–18·Reuniclus T29)를 낳았다. 이 PR은
> 그걸 **기존 `heal_frac` 효과타입의 무브-소스 버전**으로 닫는다 — 언어확장 아님, 한 패턴.
>
> **게이트**: 골든 회귀 ≤ 0. 골든이 Roost/Soft-Boiled/Rest를 *안 쓰면* 무영향. 쓰면 일반
> 메커니즘이라 옳게 적용돼야 함(★ 증가 없음). Wish(지연회복)는 별개 — 이 PR 미포함.

## 메커니즘 자리 — 왜 ON_HIT이 아니라 ON_MOVE_USE인가

`_act_on_hit`은 `current_target`(피격자)을 요구해 *데미지 없는 status 무브*(Roost 등)엔 발동하지
않는다. 모든 무브 사용 시 도는 hook은 **`_act_move_use`(ON_MOVE_USE)**. 회복무브는 자기 자신을
회복(scope=self)하므로 여기서 무브-소스로 발동시킨다.

## 변경 1 — `engine._act_move_use` 끝에 디스패처 ON_MOVE_USE 구동 (한 줄)

`_act_move_use`(Protean hook) 함수 **맨 끝**에 추가:

```python
    _act_effect_dispatch(ctx, "ON_MOVE_USE")   # 무브-소스 효과(회복무브 등) — effects 미설정/미매칭 시 no-op
```

## 변경 2 — `engine._act_effect_dispatch` 무브명 키를 ON_MOVE_USE에도 (한 줄 조건 확장)

현재 무브명은 ON_HIT에서만 키에 들어간다(line ~833). ON_MOVE_USE에서도 사용자가 쓴 무브명을
키로 넣도록 조건만 넓힌다:

```python
        # before:
        if phase == "ON_HIT" and owner is ctx.get("active_char"):
            keys.append((ctx.get("current_move") or {}).get("name"))
        # after:
        if phase in ("ON_HIT", "ON_MOVE_USE") and owner is ctx.get("active_char"):
            keys.append((ctx.get("current_move") or {}).get("name"))
```

> owner 로직(line ~829)은 비-ON_HIT이면 `(active_char,)` → ON_MOVE_USE의 owner는 무브 사용자뿐.
> 무브-소스 가드(line ~839 `source=='move' and nm != current_move.name → skip`)가 ability/item
> 동명 오발동을 막는다. heal_frac/damage_frac 처리부는 그대로 재사용.

## 변경 3 — `reference_gen5.EFFECTS`에 회복무브 3줄

```python
    'Roost':       {'trigger': 'ON_MOVE_USE', 'source': 'move',
                    'effect': {'type': 'heal_frac', 'frac': 1/2, 'of': 'maxhp'}, 'scope': 'self'},
    'Soft-Boiled': {'trigger': 'ON_MOVE_USE', 'source': 'move',
                    'effect': {'type': 'heal_frac', 'frac': 1/2, 'of': 'maxhp'}, 'scope': 'self'},
    'Rest':        {'trigger': 'ON_MOVE_USE', 'source': 'move',
                    'effect': {'type': 'heal_frac', 'frac': 1.0, 'of': 'maxhp'}, 'scope': 'self'},  # 풀회복(+slp는 주입 status)
```

> heal_frac은 `min(max, current+amt)`로 캡 → Rest frac=1.0이면 current=max(풀회복). Roost·
> Soft-Boiled는 1/2. Rest의 수면(slp)은 관측 status라 resync가 이미 주입(별개).

## 검증 (적용 후, 순서대로)

1. **클린룸 산수(엔진 무관)**: Skarmory maxhp=hp_stat(65,252)=334 → Roost 1/2=167(50%): T14 72%
   +50%→cap 100(로그 100). Clefable maxhp=394 → Soft-Boiled 197(50%): T19 48%+50%→98(로그 98).
   Scrafty maxhp=334 → Rest 1.0→풀(로그 T23 100). 3셀 대조 일치.
2. **골든 회귀 ≤ 0**: `python run_b4.py` → 첫 divergence·마지막 캡처 27 유지, ★ 증가 없음.
   (골든이 이 3무브를 쓰면 회복이 옳게 적용돼 닫히거나 동일.) 늘면 중단·진단.
3. **run_xval 재실행**: `python run_xval.py` → ★가 21에서 추가 감소. 특히 회복 유닛(Skarmory·
   Clefable·Scrafty)과 그 *유령 기절 연쇄*가 소거되는지. 남는 ★를 붙여달라.
4. **스키마 무파손**: 기존 EFFECTS·디스패처 로직 diff 없음(ON_MOVE_USE 호출 1줄 + 키 조건 1줄 +
   EFFECTS 3줄 추가만). ON_MOVE_USE 매칭 없으면 no-op(회귀0).

## 예상 잔여 (X4 후 — 함께 triage)

- **Seismic Toss 고정데미지**(T20·T22): 카탈로그된 *유일한 언어확장* — 다음 PR 후보.
- **진입 해저드 스위치인**(SR/Spikes): 골든 잔차 #1과 공유 구조.
- **Ice Shard 과소**(T10 Garchomp, Outrage lockedmove 중 피격): 진단 필요.
- **Clefable 과데미지**(Brave Bird가 과도): 세트(Def) 정밀화 (ㄱ) 또는 별도.
- 턴0 리드 아티팩트·롤.

이 PR이 회복 연쇄를 닫으면, 교차검증 잔여는 *언어확장 1(Seismic Toss) + 구조적 1(진입 해저드) +
진단/세트 꼬리*로 좁혀진다 — 2-가드 통과가 더 또렷해진다.
