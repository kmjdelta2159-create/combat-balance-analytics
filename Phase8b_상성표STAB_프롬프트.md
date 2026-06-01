# Phase 8b — N-type 상성표 + STAB (엔진 레이어)

## 목표

`ELEMENT_MULT` 단계를 **무브 인지 + 설정 기반**으로 만든다. Phase 8a로 무브 시스템이
들어왔고, 8b는 무브의 **타입**을 기반으로 N-type 상성표(임의 개수의 타입, 임의 배율)와
STAB(무브 타입 == 공격자 타입 시 추가 배율)을 적용한다. 그리디 무브 선택도 타입 상성을
반영해 super-effective 무브를 우선하게 한다.

검증 결과 — 이 변경으로 known-answer 충실도가 **74.3% → 92.6%** 로 도약한다(포켓몬
2500전투 harness 실측).

이 변경도 **순수 가산적**이다 — `game_config`에 `type_table`이 없으면 `ELEMENT_MULT`는
기존 `element_chart`(6속성) 레거시 경로로 동작하고 8a와 100% 동일하다.

## 대상 파일

**`modules/engine.py` 단 하나.** 다른 파일은 건드리지 마라.

## 새 데이터 계약 — `game_config`에 추가되는 키 (엔진은 소비만)

8a의 `game_config`(`categories`)에 아래 3개 키가 선택적으로 추가된다:

```python
game_config = {
    "categories":   {...},                          # 8a (기존)
    "type_table":   {atk_type: {def_type: float}},   # 8b — N-type 상성 배율표
    "type_columns": [gimmick_col, ...],              # 8b — 캐릭터 타입이 든 기믹 컬럼명들
    "stab_factor":  float,                           # 8b — STAB 배율 (1.0 = STAB 끔)
}
```

`type_table`/`type_columns`/`stab_factor`의 **생산은 UI 단계(8b-UI)**에서 한다. 8b 엔진은
이 값들을 받아 소비만 한다.

---

## 변경 사항 — 2개를 빠짐없이 적용하라

### 변경 1 — 헬퍼 2개 추가 + `_act_element_mult` 통째 교체

`_act_element_mult` 함수 **전체**를 찾아, 아래 내용으로 통째 교체하라 (헬퍼 함수 2개가
앞에 추가되고, `_act_element_mult`가 새 버전으로 바뀐다).

**찾기 (현재 `_act_element_mult` 함수 전체):**
```python
def _act_element_mult(ctx):
    """속성 상성 배율 적용"""
    t = ctx["current_target"]
    atk_elem = ctx["atk_elem"]

    t_gimmicks = t.get('gimmicks', {})
    t_element_col = next((c for c in t_gimmicks if 'element' in c.lower()), None)
    def_elem = t_gimmicks.get(t_element_col, "Neutral") if t_element_col else "Neutral"

    elem_mult = get_element_multiplier(atk_elem, def_elem)
    ctx["elem_mult"] = elem_mult
    ctx["dmg"] = int(ctx["dmg"] * elem_mult)
    _broadcast_phase_event("ELEMENT_MULT", ctx, targets=t)
```
**바꾸기:**
```python
def _move_type_multiplier(move, target, game_config):
    """무브 타입 vs 방어자 타입 상성 배율 — game_config['type_table'] 기반 (Phase 8b).
    type_table 미설정 시 1.0 (default=identity)."""
    table = (game_config or {}).get("type_table") or {}
    mtype = move.get("type") if move else None
    if not table or not mtype:
        return 1.0
    row = table.get(mtype, {})
    mult = 1.0
    for col in (game_config or {}).get("type_columns", []):
        dt = target.get("gimmicks", {}).get(col)
        if dt is not None and dt in row:
            mult *= float(row[dt])
    return mult


def _move_stab_multiplier(move, char, game_config):
    """STAB — 무브 타입이 공격자 타입 중 하나와 일치하면 stab_factor 배율 (Phase 8b).
    stab_factor 미설정/1.0 시 1.0 (default=identity)."""
    sf = float((game_config or {}).get("stab_factor", 1.0))
    mtype = move.get("type") if move else None
    if sf == 1.0 or not mtype:
        return 1.0
    atypes = [char.get("gimmicks", {}).get(c)
              for c in (game_config or {}).get("type_columns", [])]
    return sf if mtype in atypes else 1.0


def _act_element_mult(ctx):
    """속성 상성 배율 적용 — 무브+game_config 활성 시 N-type 상성표·STAB 사용,
    아니면 레거시 element_chart (default=identity)."""
    t = ctx["current_target"]
    move = ctx.get("current_move")
    game_config = ctx.get("game_config") or {}

    if move and game_config.get("type_table"):
        # Phase 8b — 무브 타입 기반 N-type 상성 + STAB
        char = ctx["active_char"]
        elem_mult = (_move_type_multiplier(move, t, game_config)
                     * _move_stab_multiplier(move, char, game_config))
    else:
        # 레거시 — element_chart 6속성
        atk_elem = ctx["atk_elem"]
        t_gimmicks = t.get('gimmicks', {})
        t_element_col = next((c for c in t_gimmicks if 'element' in c.lower()), None)
        def_elem = t_gimmicks.get(t_element_col, "Neutral") if t_element_col else "Neutral"
        elem_mult = get_element_multiplier(atk_elem, def_elem)

    ctx["elem_mult"] = elem_mult
    ctx["dmg"] = int(ctx["dmg"] * elem_mult)
    _broadcast_phase_event("ELEMENT_MULT", ctx, targets=t)
```

### 변경 2 — `_act_move_select` 그리디 랭킹을 타입 상성 인지로

무브 선택 AI가 base 데미지뿐 아니라 타입 상성·STAB까지 곱해 평가하게 한다.

**찾기:**
```python
        try:
            _d = max(0, int(float(eval(formula_eval, {"__builtins__": None, "math": math}, env))))
        except Exception:
            _d = 0.0
        if _d > best_dmg:
```
**바꾸기:**
```python
        try:
            _base = max(0, int(float(eval(formula_eval, {"__builtins__": None, "math": math}, env))))
        except Exception:
            _base = 0.0
        _d = _base * _move_type_multiplier(_mv, t, game_config) * _move_stab_multiplier(_mv, char, game_config)
        if _d > best_dmg:
```

---

## 검증 체크리스트 (적용 후 직접 확인하라)

- [ ] `modules/engine.py` **단 하나만** 수정됐다.
- [ ] `python -m py_compile modules/engine.py` 가 에러 없이 통과한다.
- [ ] 신규 함수 `_move_type_multiplier`, `_move_stab_multiplier` 가 `_act_element_mult` 바로 위에 존재한다.
- [ ] `_act_element_mult` 가 `if move and game_config.get("type_table"):` 분기를 가진다.
- [ ] `_act_move_select` 의 무브 평가가 `_base * _move_type_multiplier(...) * _move_stab_multiplier(...)` 를 쓴다.
- [ ] 변경 2개가 **전부** 적용됐다.

## 회귀 불변 조건

`game_config`에 `type_table`이 없으면 — `_act_element_mult`의 `if` 분기가 거짓 → 레거시
`element_chart` 경로로 진입 → Phase 8a 및 그 이전 동작과 100% 동일하다. `_act_move_select`도
`_move_type_multiplier`/`_move_stab_multiplier`가 1.0을 반환하므로 base 데미지 랭킹과 동일.
무브/`game_config` 미사용 시 엔진 회귀 베이스라인(620.0/1026.0) 불변.
