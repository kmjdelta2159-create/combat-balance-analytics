# PR-M2 — Trick 아이템 교환 (디스패처 swap_item + 스탯배율 조정)

## 목적
Trick(도구 교환)을 닫는다. 키스톤 디스패처에 **swap_item** 효과타입을 더해, 무브-소스로
양자(사용자↔대상) 아이템을 교환하고 정적 스탯배율(Choice Specs 등)을 보정한다.

근거(트레이스 실측): **T20 Latios Trick → Riou(Zapdos)**. 이후 Latios가 Leftovers를 받아 회복
(env T20~T23 Latios +19). 즉 Latios는 Choice Specs를 Zapdos에 주고 Leftovers를 받는다.
- Latios Choice Specs 상실 → spa ÷1.5 → **특수 데미지 강하**. T22 Latios HP→Nanami(Jirachi)
  로그 직격 −118인데 엔진은 −175(Specs 유지) 과다. 교환 후 spa 538→358 → 데미지 200→134(롤 내).
- Latios가 Leftovers 획득 → T20~T23 +19 회복(현재 미반영, item=Specs라). 교환으로 함께 닫힘.

이 PR은 **두 잔차를 동시에 닫는다**: Latios 후반 과다데미지 + Latios 후반 Leftovers 회복.

## 검증 제약
engine.py truncation으로 전체 실행은 앱사이드(run_b4). swap_item 로직은 클린룸 검증됨.
앵커는 Read 확인(_eff_cond_ok 788·디스패처 cond·Self-Destruct 147·build_game_config 231).

## 대상
`modules/engine.py`(2건: _eff_swap_item 헬퍼 + 디스패처 swap_item 분기) +
`modules/reference_gen5.py`(2건: build_game_config item_stat_mults + EFFECTS 'Trick').

## 설계 근거 (클린룸 검증됨)
- swap_item: active_char↔current_target item 교환 + `item_stat_mults`(game_config=ITEMS)의 정적
  배율을 각 측에서 old item ÷, new item × 로 보정. HP/scope 무관(양자 직접).
- 클린룸: Latios(Choice Specs, spa 538) ↔ Zapdos(Leftovers, spa 349) → 교환 후 Latios
  item=Leftovers·spa **358**(=538/1.5), Zapdos item=Choice Specs·spa **523**(×1.5). Latios HP
  Fire→Jirachi 데미지 **200→134**(로그 직격 118, 롤). ÷1.5 floor 오차 ±1(롤 내).
- status 무브에도 ON_HIT 발동(Explosion이 hits=[]에도 self_faint 발동한 것과 동일 — 트레이스
  target 지정 → per_target → ON_HIT). Trick은 target=Riou라 ON_HIT 발동.
- 회귀0: swap_item 효과 미설정·item_stat_mults 미설정 시 no-op. 기존 효과 경로 불변.

---

## FIND/REPLACE — modules/engine.py

### E1 — _eff_swap_item 헬퍼 추가 (_eff_cond_ok와 _act_effect_dispatch 사이)
**FIND**:
```python
    na = cond.get("not_ability")
    if na and (owner or {}).get("ability") in na:
        return False   # Poison Heal 등 — 해당 특성 보유자에겐 미발동(맹독/독 데미지 억제)
    return True


def _act_effect_dispatch(ctx, phase):
```
**REPLACE**:
```python
    na = cond.get("not_ability")
    if na and (owner or {}).get("ability") in na:
        return False   # Poison Heal 등 — 해당 특성 보유자에겐 미발동(맹독/독 데미지 억제)
    return True


def _eff_swap_item(ctx, add_log):
    """Trick류 — active_char와 current_target의 item을 교환하고, item_stat_mults
    (game_config)의 정적 스탯배율을 각 측에서 old item ÷, new item × 로 보정. HP/scope 무관."""
    a = ctx.get("active_char")
    t = ctx.get("current_target")
    if not a or not t:
        return
    mults = ((ctx.get("game_config") or {}).get("item_stat_mults")) or {}
    ia, it = a.get("item"), t.get("item")

    def _adj(ch, old_item, new_item):
        for itm, op in ((old_item, "div"), (new_item, "mul")):
            for st, mult in (mults.get(itm) or {}).items():
                if st in ch and mult:
                    ch[st] = int(ch[st] / mult) if op == "div" else int(ch[st] * mult)

    _adj(a, ia, it)
    _adj(t, it, ia)
    a["item"], t["item"] = it, ia
    add_log(f"  -> [Phase: ON_HIT] Trick: {a.get('id','?')}({it}) <-> {t.get('id','?')}({ia}) 도구 교환")


def _act_effect_dispatch(ctx, phase):
```

### E2 — 디스패처에 swap_item 분기 (cond 통과 후, scope/res 전에)
**FIND**:
```python
            if not _eff_cond_ok(ctx, spec.get("condition"), owner):
                continue
            tgt = _eff_scope(ctx, spec.get("scope", "self"))
```
**REPLACE**:
```python
            if not _eff_cond_ok(ctx, spec.get("condition"), owner):
                continue
            if (spec.get("effect") or {}).get("type") == "swap_item":
                _eff_swap_item(ctx, add_log)   # Trick류 — 양자 아이템 교환(+스탯배율), res/scope 무관
                continue
            tgt = _eff_scope(ctx, spec.get("scope", "self"))
```

---

## FIND/REPLACE — modules/reference_gen5.py

### R1 — build_game_config에 item_stat_mults 주입 (Trick 스탯조정용)
**FIND**:
```python
        'type_columns': ['t1', 't2', 't3'], 'stab_factor': 1.5, 'crit_mult': CRIT_MULT,
    }
```
**REPLACE**:
```python
        'type_columns': ['t1', 't2', 't3'], 'stab_factor': 1.5, 'crit_mult': CRIT_MULT,
        'item_stat_mults': {k: dict(v) for k, v in ITEMS.items()},   # Trick 도구교환 스탯배율 조정용
    }
```

### R2 — EFFECTS에 'Trick'(무브-소스 swap_item) 추가
**FIND**:
```python
    'Self-Destruct': {'trigger': 'ON_HIT', 'source': 'move',
                      'effect': {'type': 'self_faint'}, 'scope': 'self'},
}
```
**REPLACE**:
```python
    'Self-Destruct': {'trigger': 'ON_HIT', 'source': 'move',
                      'effect': {'type': 'self_faint'}, 'scope': 'self'},
    'Trick':         {'trigger': 'ON_HIT', 'source': 'move',
                      'effect': {'type': 'swap_item'}, 'scope': 'both'},   # 도구 교환(+스탯배율 조정)
}
```

---

## 검증 (적용 후)
1. **클린룸(이미 통과)** — 교환 후 Latios spa 358·item Leftovers, Zapdos spa 523·item Choice
   Specs. Latios HP Fire→Jirachi 200→134(로그 118). 회귀0(미설정 no-op).
2. **앱사이드 — 풀배틀**: 루트에서 `python run_b4.py`.
   - 기대(닫힘 근접): **T22 Nanami** Latios HP 데미지 강하(엔진 −175 → ~−134, 로그 직격 −118).
     **T23 Nanami** 동일 방향. **T20~T23 Latios** Leftovers +19 회복 반영(item이 Leftovers로 바뀜).
   - T12/T17 Latios Draco(Trick 前)는 Specs 유지라 불변.
   - 엔진 마지막 캡처 턴 = 27 유지. 회귀 없음.
   - 잔여 미세차(T22 134 vs 로그 118)는 Jirachi SpD 세트 정밀화 영역(별도).
   - 출력 붙여주면 함께 읽고 다음(switch-in-turn 잔류 또는 Psyshock/세트)으로.
3. **회귀0**: swap_item/item_stat_mults 미설정 게임 → no-op. ON_HIT 다른 효과·status 무브 경로 불변.

## 적용 메모
- ÷1.5 floor 오차(538→358, 참값 359)는 ±1, 롤 폭 내. 정밀이 필요하면 후속에 base 스탯 보존 방식.
- Trick은 ON_HIT(무브-소스)로 발동 — Explosion self_faint와 동일 경로(트레이스 target 지정 시
  status 무브도 per_target→ON_HIT). 만약 앱 로그에 교환이 안 보이면 status 무브 ON_HIT 발동
  여부를 점검(그 경우 ON_MOVE_USE 트리거로 대체).
- **표현력 확장**: 효과타입이 damage_frac·heal_frac·self_faint·swap_item 4종. 동적 아이템
  상태가 디스패처로 들어왔다.
