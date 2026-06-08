# 꼬리 PR-F3r — 반동무브 (recoil) 자기 데미지

> 점근 꼬리의 마지막 일반 메커니즘. 반동무브(Brave Bird 등)가 사용자에게 입히는 자기 데미지를
> 추가한다. F1(fixed_damage)과 **완전히 동일한 무브-속성 레이어 패턴** — 검증된 길이라 저위험.

---

## 0. 무엇을, 왜 (확정)

분류 F3(recoil) 2셀:

| 셀 | log | eng | 정체 |
|---|---|---|---|
| T16 Skarmory | 69 | 82 | Brave Bird 자기반동 미적용 → 엔진 HP 높음(under) |
| T18 Skarmory | 45 | 57 | Brave Bird 자기반동 미적용 |

확인(Read/Grep):
- 엔진에 **반동 메커니즘이 전혀 없다**(`recoil` 무검색). `_act_apply_damage`(engine.py L716)는
  타겟에만 데미지를 입히고 사용자에겐 아무것도 안 한다.
- reference_gen5엔 무브-속성 레이어 패턴이 이미 있다: `CONTACT_MOVES`(set, L206)·
  `FIXED_DAMAGE_MOVES`(dict, L210). battle_setup이 이를 무브 dict에 부착한다
  (L126 `contact`, L127 `fixed_damage`).

→ 같은 패턴으로 `RECOIL_MOVES`(무브→반동 분수)를 추가하고, battle_setup이 부착, 엔진이 데미지
적용 후 사용자에게 반동을 입힌다. gen5 반동: Brave Bird·Double-Edge·Flare Blitz·Wood Hammer·
Volt Tackle = 1/3, Head Smash = 1/2, Take Down·Submission·Wild Charge·Head Charge = 1/4.

---

## 1. 변경 (3파일, F1과 동형)

### 1-A. `modules/reference_gen5.py` — RECOIL_MOVES 추가
`FIXED_DAMAGE_MOVES`(L210) 근처에:
```python
# 반동무브 — 사용자가 '입힌 데미지'의 분수만큼 자기 피해(gen5).
RECOIL_MOVES = {
    'Brave Bird': 1/3, 'Double-Edge': 1/3, 'Flare Blitz': 1/3, 'Wood Hammer': 1/3,
    'Volt Tackle': 1/3, 'Head Smash': 1/2,
    'Take Down': 1/4, 'Submission': 1/4, 'Wild Charge': 1/4, 'Head Charge': 1/4,
}
```
(코퍼스엔 Brave Bird만 등장하나 일가 전부 커버 — F1과 동일 일반화.)

### 1-B. `modules/battle_setup.py` — 무브 dict에 recoil 부착
L126-127(contact·fixed_damage 부착)와 나란히:
```python
"recoil": getattr(ref, "RECOIL_MOVES", {}).get(e["move"]),
```

### 1-C. `modules/engine.py` `_act_apply_damage`(L716) — 사용자 반동 적용
타겟 데미지 적용 후(절대 그 전 아님), 무브에 `recoil`이 있으면 **입힌 데미지(`dmg`)** 기준으로
사용자(`active_char`)에게 반동:
```python
    # ── 반동무브: 사용자가 입힌 데미지의 분수만큼 자기 피해(PR-F3r) ──
    move = ctx.get("current_move") or {}
    _rec = move.get("recoil")
    if _rec and dmg > 0:
        char = ctx.get("active_char")
        if char is not None and get_current(char) > 0:
            recoil_dmg = max(1, int(dmg * _rec))
            before = get_current(char)
            apply_delta(char, -recoil_dmg)
            ctx["add_log"](f"  -> [Phase: APPLY_DAMAGE] {char.get('id','?')} "
                           f"반동 데미지 {before - get_current(char)} (recoil)")
```
- 위치: `_broadcast_phase_event("APPLY_DAMAGE", ...)` 직전(L749 위).
- **반동 기준 = 타겟에 입힌 `dmg`**(쉴드 흡수 무시한 산출 데미지 — gen5는 입힌 데미지 기준).
- `recoil` 속성 없으면(=대다수 무브·임의 게임) no-op → **회귀 0**.

---

## 2. 불변 (회귀 0)

- `_act_apply_damage`의 타겟 데미지·실드·sim_metrics·로그 경로 불변 — 반동 블록만 *추가*.
- `recoil` 속성은 RECOIL_MOVES에 든 무브에만 붙음. 그 외 전부 no-op.
- **골든 `run_b4` 회귀0**: 골든 무브셋(Hidden Power·Scald·Draco Meteor·Explosion·Earthquake·
  Body Slam·Iron Head·Superpower 등)에 반동무브 없음 → 무영향. (있더라도 정확도 개선 방향.)
- Rough Skin·Rocky Helmet(방어자→공격자 반사, env 스트림)과는 **별개** — 손대지 않음.

---

## 3. 검증 (앱사이드)

1. **`python run_cellclass.py`** — `[요약]`에서 **F3(recoil) 버킷 0**(T16·T18 Skarmory 닫힘).
   다른 버킷 무증가.
2. **`python run_b4.py`** — 골든 회귀0(불변).

---

## 4. 적용 후 보고
- 수정 파일·라인 + `wc -l`/`tail` 무결성(특히 engine 반동 블록 위치).
- 위 1~2 출력(run_cellclass F3recoil 닫힘, run_b4 회귀0).
- 꼬리 갱신: F1·F2·F2b·F3s·F3r 누적 닫힌 셀. 남은 = T10(보류·known-residual) + 잔여(크리/롤/
  리드 아티팩트). → 메커니즘 부채 사실상 종료, UI 배칭 단계로.

---

## 부기 — T10은 이번 PR 범위 밖(보류)
T10 Garchomp(gap=61)은 `run_t10diag`로 **타입버그 아님·raw_dmg 아님**이 확정됐다: 엔진이
Abomasnow의 Ice Shard(우선도+1)를 **실행조차 안 함**(공격자가 그 턴 공격 후 곧 필드를 떠나는
케이스의 트레이스-리플레이 액션 스케줄링 엣지). 1셀·좁은 엣지케이스라 비용 대비 레버리지가 낮아
known-residual로 문서화하고 보류한다(타입 시스템은 4×까지 정확함을 진단이 확증).
