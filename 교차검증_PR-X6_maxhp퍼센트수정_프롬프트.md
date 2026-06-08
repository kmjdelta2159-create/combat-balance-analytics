# 교차검증 PR-X6 — 퍼센트모드 maxhp 수정 (과데미지 유령기절 근본 해결)

> X5 진단이 원인을 한 줄로 못박았다. 세 과데미지 셀의 엔진 덤프가 클린룸과 **완전 일치**:
> off/def/raw/elem 전부 정확, final도 정확(163·109·165) — 단 **maxhp=100**. 데미지 공식은
> 실스탯 절대값을 내는데 수비수 HP풀 max가 100이라 직격이 즉사한다.
>
> 근본: `battle_setup.build_participants`가 maxhp를 *트레이스 관측 max HP*(`_observed_maxhp`)로
> 덮는다. 골든(절대 HP)에선 관측 max가 진짜 maxhp(ground truth)라 옳지만, **이 전투는 퍼센트
> 로그(HP Percentage Mod)라 관측 max=100** → 계산 maxhp(394/334/424)를 100으로 깨뜨린다. HP EV
> 역산도 `ev4 = 100 − 2·base − 141 < 0`으로 불법.
>
> **수정**: 퍼센트 로그에선 관측-max 보정을 건너뛰고 `make_char` 계산 maxhp(BASE+SET EV)를 쓴다.
> 절대 HP 로그(골든)는 현행 그대로 = 회귀0. 래더 퍼센트 로그(임의 싱글의 다수)에 필요한 일반 수정.

## 변경 — `battle_setup.build_participants`에 퍼센트 가드 (한 곳)

함수 상단에서 퍼센트 모드 판정(run_xval과 동일 기준) 후, 관측-max 보정 분기에 `not pct` 가드:

```python
def build_participants(trace, ref, set_override=None):
    mh = _observed_maxhp(trace)
    side = _nick_side(trace)
    # HP Percentage Mod: 관측 max=100은 실 maxhp가 아님 → 보정 생략, make_char 계산값 사용.
    pct = any("Percentage" in str(r) for r in (trace.get("meta") or {}).get("rules", []))
    parts = []
    for nick, species in trace["nick2species"].items():
        if species not in ref.BASE:
            parts.append({"id": nick, "_species": species, "_missing_ref": True,
                          "side": side.get(nick)})
            continue
        set_data = (set_override or {}).get(species) or ref.SETS.get(species)
        ch = ref.make_char(nick, species, set_data=set_data)
        om = mh.get(nick)
        if om is not None and not pct:          # ← 절대 HP 로그에서만 관측값으로 보정
            B = ref.BASE[species]
            ev4 = om - 2 * B[0] - 141
            ch["maxhp"] = om
            ch["_hp_ev"] = max(0, ev4) * 4
            ch["_hp_ev_legal"] = 0 <= ev4 <= 63
        ch["hp"] = ch["maxhp"]                   # 퍼센트면 make_char 계산 maxhp 그대로
        ch["side"] = side.get(nick)
        ch["set"] = set_data or {}
        ch["ability"] = (set_data or {}).get("ability")
        ch["item"] = (set_data or {}).get("item")
        parts.append(ch)
    return parts
```

> 유일한 변경은 `if om is not None:` → `if om is not None and not pct:`(+ pct 한 줄 정의).
> 절대 HP 로그(골든)는 `pct=False` → 분기 그대로 = **바이트 동일 회귀0**.

## 왜 이게 전부를 맞추나 (퍼센트 정합 체인)

maxhp가 실값(예: Clefable 394)으로 돌아오면:
- **resync**(percent): `current = round(log_pct/100 · 394)` → 진입 HP 정확.
- **데미지**: 163 절대 / 394 = 41% 적용 → Clefable 생존(로그 32% 부합).
- **snapshot**(percent): `round(231/394·100)=59%` → 로그 퍼센트와 같은 공간.
- **env frac**(Leftovers 1/16 등): 퍼센트 불변(1/16은 maxhp 무관 6%) → 기존 정합 유지.

즉 X5에서 "정확"했던 off/def/raw/elem은 그대로, 깨졌던 maxhp만 복구 → 과타 유령기절(Clefable
T16·18·Scrafty T24–26·Reuniclus T29)이 닫힌다.

## 검증 (적용 후, 순서대로)

1. **골든 회귀0**: `python run_b4.py` 출력이 PR-X6 전과 완전 동일(절대 HP → `pct=False` → 분기 무변).
2. **클린룸 maxhp 확인**(엔진 무관): Clefable hp_stat(95,252)=394·Scrafty(65,252)=334·
   Reuniclus(110,252)=424. 진단 재실행 시 `maxhp=`가 100→이 값들로 바뀌어야.
3. **run_dmg_diag 재확인**: `python run_dmg_diag.py` → T16/T24/T29 줄의 `maxhp=`가 394/334/424,
   `hp후=`가 0이 아닌 생존값(예: T16 Clefable hp후≈59%).
4. **run_xval 재실행**: `python run_xval.py` → 과타 유령기절(Clefable·Scrafty·Reuniclus faint ★)
   소거. ★가 21에서 추가 감소. 남는 ★를 붙여달라.

## 예상 잔여 (X6 후)

- **진입 해저드 스위치인**(SR/Spikes, Jirachi/Abomasnow/Skarmory 진입): 골든 잔차 #1과 공유 구조.
- **Ice Shard 과소**(Garchomp T10, Outrage lockedmove 중 피격): 별도 — 단 maxhp 복구로
  Garchomp HP 양상이 바뀔 수 있어 재확인.
- **Seismic Toss 고정데미지**(T20·T22): 카탈로그된 유일한 언어확장.
- 턴0 리드 아티팩트·롤.

이 수정으로 교차검증 잔여가 *구조(진입 해저드) + 언어확장 1(Seismic Toss) + 진단(Ice Shard) 꼬리*로
좁혀진다 — 2-가드 통과가 거의 완결된다.
