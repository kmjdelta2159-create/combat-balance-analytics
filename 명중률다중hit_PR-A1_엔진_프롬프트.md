# PR-A1 — 명중률(per-move) + 다중 hit 엔진

## 역할/맥락
너는 Antigravity 에이전트다. 아래 변경을 **두 파일**(`modules/stochasticity.py`,
`modules/engine.py`)에 정확히 적용하라. 기존 stochasticity 위에 (1) 무브별 명중률, (2) 다중 hit
(2~5회 등)을 얹는다. 둘 다 무브명 키 config 룩업이라 무브 schema는 불변(병렬 안전).

설계(`명중률다중hit_설계안.md`):
- config: `game_config['mechanisms']['move_props'][무브명] = {"accuracy": 0~1, "hits": int 또는 [lo,hi]}`.
  미설정 시 현행(회귀 0). accuracy 1 초과면 percent로 보고 /100.
- 명중(DAMAGE_CALC): move_props.accuracy 있으면 `roll_chance(acc)`, 없으면 기존 `roll_hit`. miss면
  현행 miss 경로 그대로(dmg 0 + return).
- 다중 hit(APPLY_DAMAGE): `_resolve_n_hits`로 횟수(균등 [lo,hi], 사용자 결정), per-hit 동일
  데미지를 n_hits회 route_damage. 명중은 DAMAGE_CALC에서 1회 굴려 전체 게이팅(사용자 결정).
  매 회 KO면 중단. 총합을 dmg로 갱신.
- RNG: base에 `roll_range(lo,hi)`(시드 randint). roll_chance(G1 추가분) 재사용.

## 제약
- 두 파일만. 아래 FIND/REPLACE **4건**(stochasticity 1 + engine 3). 각 FIND는 해당 파일에
  **정확히 1회**(검증 확인). 다른 함수·저장부 무변경.
- 들여쓰기 FIND 그대로(스페이스). 적용 후 두 파일 각각 `ast.parse`.
- **회귀 0**: move_props 미설정 시 명중은 기존 roll_hit, 다중 hit은 단타(n_hits 1) → 현행 동일.

---

## 변경 1/4 — `modules/stochasticity.py`: base에 `roll_range` 추가

`roll_chance`(G1에서 추가됨) 다음, `shuffle_tie_order` 앞에 정수 균등 추출을 넣는다(base만).

```python
# FIND
        return self.rng.random() < float(p)

    def shuffle_tie_order(self, participants_with_same_speed: list) -> list:
```

```python
# REPLACE
        return self.rng.random() < float(p)

    def roll_range(self, lo: int, hi: int, ctx=None) -> int:
        """범용 정수 균등 추출 — [lo,hi] 닫힌구간. 시드 제어 self.rng(재현). 다중 hit 횟수 등."""
        return self.rng.randint(int(lo), int(hi))

    def shuffle_tie_order(self, participants_with_same_speed: list) -> list:
```

---

## 변경 2/4 — `modules/engine.py`: DAMAGE_CALC per-move 명중률

명중 판정 블록에서 무브 accuracy(move_props)를 우선 보고, 없으면 기존 roll_hit. (`_move`는 이
함수 상단에서 이미 바인딩됨.)

```python
# FIND
    stoch = ctx.get("stochasticity")
    if stoch:
        if not stoch.roll_hit(char, t, ctx):
```

```python
# REPLACE
    stoch = ctx.get("stochasticity")
    if stoch:
        # 명중 판정 — 무브 accuracy(move_props) 우선(per-move), 없으면 모듈 roll_hit(현행).
        _props = (((ctx.get("game_config") or {}).get("mechanisms") or {})
                  .get("move_props") or {}).get((_move or {}).get("name")) or {}
        _acc = _props.get("accuracy")
        if _acc is not None and str(_acc) != "":
            try:
                _accf = float(_acc)
                if _accf > 1.0:
                    _accf /= 100.0
            except (ValueError, TypeError):
                _accf = 1.0
            _hit = stoch.roll_chance(_accf, ctx)
        else:
            _hit = stoch.roll_hit(char, t, ctx)
        if not _hit:
```

---

## 변경 3/4 — `modules/engine.py`: `_resolve_n_hits` 헬퍼 추가

`_act_apply_damage` 정의 바로 앞에 다중 hit 횟수 결정 헬퍼를 둔다.

```python
# FIND
def _act_apply_damage(ctx):
```

```python
# REPLACE
def _resolve_n_hits(props, stoch):
    """다중 hit 횟수 — props['hits']가 int면 그 수, [lo,hi]/"lo-hi"면 균등 랜덤(시드 roll_range),
    미설정이면 1(단타·회귀 0). 균등 분포(사용자 결정)."""
    h = (props or {}).get("hits")
    if h is None or h == "":
        return 1
    lo = hi = None
    if isinstance(h, (list, tuple)) and len(h) == 2:
        lo, hi = h[0], h[1]
    elif isinstance(h, str) and "-" in h:
        _p = h.split("-", 1)
        lo, hi = _p[0], _p[1]
    if lo is not None:
        try:
            lo, hi = int(lo), int(hi)
        except (ValueError, TypeError):
            return 1
        if hi < lo:
            lo, hi = hi, lo
        if lo < 1:
            lo = 1
        if hi < 1:
            hi = 1
        if lo == hi:
            return lo
        return stoch.roll_range(lo, hi) if stoch else lo
    try:
        n = int(h)
        return n if n >= 1 else 1
    except (ValueError, TypeError):
        return 1


def _act_apply_damage(ctx):
```

---

## 변경 4/4 — `modules/engine.py`: APPLY_DAMAGE 다중 hit 루프

route_damage 1회 적용부를 n_hits 루프로 교체한다. per-hit 동일 데미지, 매 회 KO면 중단, 총합을
dmg로 갱신(기존 metrics/로그가 총 데미지 보고).

```python
# FIND
    resource_module = ctx.get("resource_module")
    if resource_module is not None:
        absorbed = resource_module.route_damage(t, dmg, ctx.get("damage_type"))
    else:
        apply_delta(t, -dmg)
        absorbed = 0
    shield_text = f" (실드 {int(absorbed)} 흡수)" if absorbed else ""
```

```python
# REPLACE
    resource_module = ctx.get("resource_module")
    # ── 다중 hit (균등 [lo,hi], 사용자 결정) — per-hit 동일 데미지를 n_hits회 적용 ──
    #   미설정/1이면 단타(회귀 0). 명중은 DAMAGE_CALC에서 1회 굴려 전체 게이팅(miss면 dmg 0 → 0회).
    _per_hit = dmg
    _mv = ctx.get("current_move")
    _props = (((ctx.get("game_config") or {}).get("mechanisms") or {})
              .get("move_props") or {}).get((_mv or {}).get("name")) or {}
    n_hits = _resolve_n_hits(_props, ctx.get("stochasticity")) if _per_hit > 0 else 1
    absorbed = 0
    hits_done = 0
    for _h in range(n_hits):
        if get_current(t) <= 0:
            break
        if resource_module is not None:
            absorbed += resource_module.route_damage(t, _per_hit, ctx.get("damage_type"))
        else:
            apply_delta(t, -_per_hit)
        hits_done += 1
    dmg = _per_hit * hits_done
    ctx["dmg"] = dmg
    if hits_done > 1:
        ctx["add_log"](f"  -> [Phase: APPLY_DAMAGE] 다중 명중 {hits_done}회 (회당 {_per_hit})")
    shield_text = f" (실드 {int(absorbed)} 흡수)" if absorbed else ""
```

---

## 검증 (적용 후 수행)
1. `git diff`로 변경이 위 4지점뿐인지 확인(두 파일). 다른 함수·저장부 무변경.
2. 컴파일: 두 파일 각각 `ast.parse`.
3. 마커(각 1회): `def roll_range(self, lo: int, hi: int, ctx=None) -> int:`(stochasticity),
   `def _resolve_n_hits(props, stoch):`, `move_props`(DAMAGE_CALC·APPLY_DAMAGE 각 1 = 2회),
   `다중 명중`(engine).
4. 회귀 0 스모크: move_props 없이 기존 전투 1판 → 로그에 `다중 명중` 없음, 명중/데미지 동일.
5. 라이브(`A1_라이브실증.py`): 시드 고정 stochasticity, `mechanisms.move_props`에 accuracy<1
   무브와 hits=[2,5] 무브. 기대:
   - accuracy 0.8 무브 → 일부 턴 `❌ 공격이 빗나갔습니다!`(시드 재현).
   - hits=[2,5] 무브 → `다중 명중 N회 (회당 D)` (N∈[2,5] 균등), 총 데미지 = D×N.
   - hits=2 고정 무브 → 항상 2회.
   - KO 시 중단(잔여 hit 미적용).

## 회귀/한계 메모
- 다중 hit 데미지는 회당 동일(크리/분산 재굴림 없음, 사용자 결정). per-hit 변동은 후속.
- 명중 1회 굴림 — 부분 명중 없음(Pokemon 다중 hit과 동일).
- move_props는 무브명 키 — 무브 schema 불변. 무브명 오타 시 no-op(정의 우선).
- roll_range는 base 추가 → 모든 모듈(NoVariance 포함) 상속, 시드 고정 시 결정론.
- UI는 후속 **PR-A2**(step2: move_props JSON 편집기). 엔진(A1) 적용·검증 후.
