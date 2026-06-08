# PR-F1 — fixed_damage 효과타입 + Seismic Toss

> 대상 파일: `modules/reference_gen5.py`, `modules/battle_setup.py`, `modules/engine.py` (3개)
> 성격: 교차검증 평결이 1차목표 천장의 *유일한 진짜 언어확장 부채*로 못박은 건. 레벨/상수 고정 데미지(`(위력×스탯)` 산식으로 표현 불가)를 일반 효과로 추가한다.
> 검증: 클린룸 + `run_xval`(held-out) + `run_b4`(골든 회귀0). 새 엔진 패러다임 아님 — 데미지 경로에 분기 한 곳 + 무브 속성 1개.

---

## 0. 배경

`reference_gen5.MOVES`의 `'Seismic Toss': (0, 'status', None)`은 위력0 placeholder다(L69~71 주석 참고). 실제로는 **공격자 레벨만큼(gen5 OU=100) 고정 데미지**를 주며, 스탯·위력·상성 배율과 무관하다. 단 **타입 면역은 존중**한다 — Seismic Toss는 Fighting 타입이라 Ghost에겐 0이다. 현재는 위력0이라 엔진이 0을 내고, 그 divergence가 Skarmory/Scrafty 셀에 ★로 드러난다.

이 PR은 fixed_damage를 **무브 속성**으로 일반화한다(Seismic Toss·Night Shade=레벨, Dragon Rage=40, Sonic Boom=20 류 전부 커버). 데미지 경로(`_act_damage_calc`)에서 override하고, 상성 단계(`_act_element_mult`)에서 효과 배율은 무시하되 면역(×0)만 존중한다.

---

## 1. 변경 명세

### 1-A. `modules/reference_gen5.py` — 데이터 2곳

**(1) Seismic Toss 타입을 Fighting으로.** L71의 placeholder를 교체한다. 면역 판정(Ghost×0)이 작동하려면 타입이 있어야 한다. 위력은 0 유지(미사용), 카테고리는 gen5 정확성을 위해 'phys'로.

```python
# 변경 전 (L71)
    'Seismic Toss': (0, 'status', None),
# 변경 후
    'Seismic Toss': (0, 'phys', 'Fighting'),   # 고정데미지(FIXED_DAMAGE_MOVES). 타입은 면역 판정용
```

**(2) FIXED_DAMAGE_MOVES 사전 추가.** `CONTACT_MOVES = {...}`(L206 부근) **바로 다음 줄**에 신규 사전을 추가한다. CONTACT_MOVES와 동일한 "무브명 → 부가속성" 레이어 패턴이다.

```python
# 고정 데미지 무브 — {무브명: 고정 HP 데미지}. 산식/스탯/상성 배율 무관, 단 타입 면역(×0)은 존중.
# Seismic Toss·Night Shade = 레벨(gen5 OU=100). 확장: Dragon Rage=40, Sonic Boom=20.
FIXED_DAMAGE_MOVES = {'Seismic Toss': 100}
```

### 1-B. `modules/battle_setup.py` — 무브 dict에 fixed_damage 주입

`build_trace_actions`의 무브 dict 빌드(L124~126)에 한 키를 더한다.

```python
# 변경 전 (L124~126)
            mv = {"name": e["move"], "power": (md[0] if md else 0),
                  "category": (md[1] if md else None), "type": mtype,
                  "contact": e["move"] in getattr(ref, "CONTACT_MOVES", set())}
# 변경 후 (마지막 줄 끝 쉼표 + fixed_damage 한 줄 추가)
            mv = {"name": e["move"], "power": (md[0] if md else 0),
                  "category": (md[1] if md else None), "type": mtype,
                  "contact": e["move"] in getattr(ref, "CONTACT_MOVES", set()),
                  "fixed_damage": getattr(ref, "FIXED_DAMAGE_MOVES", {}).get(e["move"])}
```

`getattr(..., {})` 폴백이라 FIXED_DAMAGE_MOVES 없는 ref(gen6 등)에서도 안전(값 None).

### 1-C. `modules/engine.py` — 데미지 경로 분기 2곳

**(1) `_act_damage_calc` — 고정 데미지 override.** `ctx["dmg"] = ctx["raw_dmg"]`(L612) **바로 다음**에 블록 삽입. 산식 결과를 고정값으로 덮고 플래그를 세운다.

```python
# 변경 전 (L612)
    ctx["dmg"] = ctx["raw_dmg"]
# 변경 후 (아래 블록을 L612 다음에 추가)
    ctx["dmg"] = ctx["raw_dmg"]

    # ── fixed_damage 무브 (Seismic Toss/Night Shade 류) — 레벨/상수 고정, 산식·스탯 무관 ──
    _fd = (_move or {}).get("fixed_damage")
    if _fd is not None:
        ctx["raw_dmg"] = ctx["dmg"] = int(_fd)
        ctx["fixed_damage"] = True
```

여기서 `_move`는 같은 함수 L595에서 이미 `ctx.get("current_move")`로 잡혀 있다 — 재선언 불필요, 그대로 사용.

**(2) 데미지 분산이 고정값을 흔들지 않도록 가드.** L630의 분산 적용을 조건부로.

```python
# 변경 전 (L630)
        ctx["dmg"] = int(stoch.apply_damage_variance(ctx["dmg"], ctx))
# 변경 후
        if not ctx.get("fixed_damage"):
            ctx["dmg"] = int(stoch.apply_damage_variance(ctx["dmg"], ctx))
```

(결정적 리플레이는 NoVariance라 무해하지만, 고정데미지에 분산이 붙는 건 의미상 틀리므로 일반 가드.)

**(3) `_act_element_mult` — 상성 배율 무시·면역만 존중.** L686~687을 교체한다.

```python
# 변경 전 (L686~687)
    ctx["elem_mult"] = elem_mult
    ctx["dmg"] = int(ctx["dmg"] * elem_mult)
# 변경 후
    ctx["elem_mult"] = elem_mult
    if ctx.get("fixed_damage"):
        # 고정 데미지: 효과 배율(2x/0.5x)·STAB 무시, 단 면역(×0)은 존중
        if elem_mult == 0:
            ctx["dmg"] = 0
    else:
        ctx["dmg"] = int(ctx["dmg"] * elem_mult)
```

이로써 Seismic Toss는 일반 대상에 100 그대로, Ghost에겐 0(elem_mult=0)을 낸다.

---

## 2. 절대 건드리지 말 것 (회귀0)

- 다른 무브·다른 효과 경로. fixed_damage가 None이면 1-C의 분기는 전부 미발동 → 기존 동작 0% 변화.
- `_act_damage_calc`의 산식 eval·패시브·stoch 명중 판정 로직.
- 골든 코퍼스에는 Seismic Toss가 없다 → `run_b4` 출력 불변이어야 한다(회귀0 게이트).

---

## 3. 적용 후 검증

1. 구문/들여쓰기: 3파일 각각
   `python -c "import ast,sys; ast.parse(open(f).read())"` (f = reference_gen5.py·battle_setup.py·engine.py) — 통과 필수.
2. **회귀0**: `python run_b4.py` → 골든 출력이 PR 이전과 **완전 동일**(Seismic Toss 무관 코퍼스).
3. **갭 닫힘**: `python run_xval.py` → held-out(`Gen5OU-2026-newatmons-bantyranitar.html`)의 Seismic Toss 셀(Skarmory/Scrafty)이 엔진 0 → 100으로 수렴, 구조적 ★가 그만큼 감소. 평결 §6의 "Seismic Toss 1건" 항목이 닫힘.
4. **면역 스폿체크**(클린룸 /tmp 소형 스크립트): fixed_damage=100 무브를 ① 일반 대상 → dmg 100, ② type_table에서 elem_mult=0 나오는 대상 → dmg 0 확인.

`run_xval`·`run_b4`는 앱사이드 실행(출력/캡처 붙여주면 대조). 2번이 회귀 게이트, 3번이 목표 달성 증거다.

---

## 4. 산출/보고

- 변경 3파일의 적용분을 Read/Grep으로 대조(mnt 절단 대비). `wc -l` 변화 보고.
- 보고에 run_b4 회귀0 여부 + run_xval의 Seismic Toss 셀 전/후 수치 포함.
