# Phase 8a — 무브/어빌리티 1급 엔티티화 (엔진 레이어)

## 목표

전투 엔진에 **무브(어빌리티)** 개념을 도입한다. 지금까지 캐릭터는 단일 `global_damage_formula`
하나로만 공격했다. 8a 이후 캐릭터는 `movepool`(무브 목록)을 가질 수 있고, 매 턴 타겟별로
그리디(기대 데미지 최대)하게 무브를 선택하며, 데미지 공식이 그 무브의 위력/카테고리를
참조할 수 있다.

이 변경은 **순수 가산적(default=identity)**이다 — `movepool`이 없거나 `game_config`가
없으면 엔진은 현행과 100% 동일하게 동작한다. 회귀 베이스라인(1v1 `phys_power -
target_armor_class`, lopsided 620.0 / near-even 1026.0)은 반드시 불변이어야 한다.

## 대상 파일

**`modules/engine.py` 단 하나만 수정한다.** 다른 어떤 파일도 건드리지 마라.
`_act_element_mult`(속성 상성)는 이번 단계에서 **수정하지 마라** — Phase 8b 영역이다.

## 새 데이터 계약 (엔진은 소비만, 생산은 UI 단계에서)

1. **인스턴스 dict의 선택적 `"movepool"` 키** — 무브 dict의 리스트:
   ```python
   inst["movepool"] = [
       {"name": str, "power": float, "type": str, "category": str},
       ...
   ]
   ```
   `run_simulation`의 `p = {**inst, ...}` 가 이 키를 자동 보존하므로 별도 복사 코드는 불필요하다.

2. **`run_simulation` / `run_monte_carlo`의 선택적 `game_config` 파라미터** — dict:
   ```python
   game_config = {
       "categories": {category_name: {"offense": stat_name, "defense": stat_name}},
   }
   ```
   무브의 `category`로 어떤 공격/방어 스탯을 쓸지 라우팅한다 (Physical/Special 분리 등).

3. **데미지 공식 namespace 확장** — 무브가 활성일 때 공식이 `move_power`, `offense`,
   `defense` 변수를 추가로 참조할 수 있다. 기존 공식(원시 스탯 참조)은 그대로 동작한다.

---

## 변경 사항 — 아래 14개를 하나도 빠짐없이 적용하라

각 변경은 **정확한 찾기-바꾸기**다. 들여쓰기·공백·줄바꿈을 그대로 유지하라.
re-indent 하지 마라. 14개 중 하나라도 누락하면 `NameError`가 발생한다.

### 변경 1a — `_KOREAN_TO_KEY`에 무브 선택 키 추가

**찾기:**
```python
    "이동": "MOVE",
}
```
**바꾸기:**
```python
    "이동": "MOVE",
    "무브 선택": "MOVE_SELECT",
}
```

### 변경 1b — `_ENGLISH_HINTS`에 영문 폴백 추가

**찾기:**
```python
    ("move", "MOVE"),
]
```
**바꾸기:**
```python
    ("move", "MOVE"),
    ("select move", "MOVE_SELECT"),
]
```

### 변경 1c — `_TARGET_LEVEL_KEYS`에 `MOVE_SELECT` 추가

**찾기:**
```python
_TARGET_LEVEL_KEYS = {"DAMAGE_CALC", "ELEMENT_MULT", "CRIT_CALC", "APPLY_DAMAGE", "ON_HIT", "DEATH_CHECK"}
```
**바꾸기:**
```python
_TARGET_LEVEL_KEYS = {"MOVE_SELECT", "DAMAGE_CALC", "ELEMENT_MULT", "CRIT_CALC", "APPLY_DAMAGE", "ON_HIT", "DEATH_CHECK"}
```

### 변경 2 — 신규 액션 함수 `_act_move_select` 추가

`def _act_damage_calc(ctx):` 줄을 찾아, **그 줄 바로 위에** 아래 함수 정의 전체를
삽입하라 (함수 끝과 `def _act_damage_calc` 사이에 빈 줄 2개).

**`def _act_damage_calc(ctx):` 직전에 삽입:**
```python
def _act_move_select(ctx):
    """무브 선택 Phase (Phase 8a) — movepool에서 그리디(기대 데미지 최대)로 무브 선택.
    movepool 미보유 시 current_move=None → 단일 global 공식 경로 유지(default=identity)."""
    char = ctx["active_char"]
    movepool = char.get("movepool")
    if not movepool:
        ctx["current_move"] = None
        return
    t = ctx.get("current_target")
    if t is None:
        ctx["current_move"] = movepool[0]
        return
    import math
    sys_stats = ctx["sys_stats"]
    game_config = ctx.get("game_config") or {}
    formula_eval = str(ctx["formula_str"]).lower() if ctx.get("formula_str") else "0"
    base_env = {s: get_effective_stat(char, s) for s in sys_stats}
    base_env.update({"target_" + s: get_effective_stat(t, s) for s in sys_stats})
    base_env["current_health"] = get_current(char)
    base_env["max_health"] = get_max(char)
    base_env["target_current_health"] = get_current(t)
    base_env["target_max_health"] = get_max(t)
    best, best_dmg = movepool[0], -1.0
    for _mv in movepool:
        env = dict(base_env)
        env["move_power"] = float(_mv.get("power", 0))
        _cat = game_config.get("categories", {}).get(_mv.get("category"))
        if _cat:
            env["offense"] = get_effective_stat(char, _cat["offense"])
            env["defense"] = get_effective_stat(t, _cat["defense"])
        env = {str(k).lower(): float(v) for k, v in env.items()}
        try:
            _d = max(0, int(float(eval(formula_eval, {"__builtins__": None, "math": math}, env))))
        except Exception:
            _d = 0.0
        if _d > best_dmg:
            best, best_dmg = _mv, _d
    ctx["current_move"] = best
```

### 변경 3 — `_act_damage_calc`에 무브 변수 주입

**찾기:**
```python
    eval_env_raw["target_max_health"] = get_max(t)

    eval_env = {str(k).lower(): float(v) for k, v in eval_env_raw.items()}
```
**바꾸기:**
```python
    eval_env_raw["target_max_health"] = get_max(t)

    # ── Phase 8a: 무브 활성 시 move_power / offense / defense 주입 ──
    _move = ctx.get("current_move")
    if _move:
        _gc = ctx.get("game_config") or {}
        eval_env_raw["move_power"] = float(_move.get("power", 0))
        _cat = _gc.get("categories", {}).get(_move.get("category"))
        if _cat:
            eval_env_raw["offense"] = get_effective_stat(char, _cat["offense"])
            eval_env_raw["defense"] = get_effective_stat(t, _cat["defense"])

    eval_env = {str(k).lower(): float(v) for k, v in eval_env_raw.items()}
```

### 변경 4 — `MOVE_SELECT` 액션을 디폴트 레지스트리에 등록

`register("MOVE", ... _act_move)` 줄을 찾아, **그 줄 바로 아래에** 새 줄을 추가하라.

**찾기:**
```python
DEFAULT_ACTION_REGISTRY.register("MOVE",          _act_move)
```
**바꾸기:**
```python
DEFAULT_ACTION_REGISTRY.register("MOVE",          _act_move)
DEFAULT_ACTION_REGISTRY.register("MOVE_SELECT",   _act_move_select)
```

### 변경 5 — `MOVE_SELECT` 자동 삽입 로직 추가

기존 "MOVE 자동 삽입" 블록을 찾아, **그 블록 아래에** MOVE_SELECT 자동 삽입 블록을 추가하라.

**찾기:**
```python
    # MOVE 자동 삽입 — TARGET_SELECT 직전 (Phase 4b)
    if "MOVE" not in [k for k, _ in all_actions]:
        _ts_idx = next((i for i, (k, _) in enumerate(all_actions) if k == _PIVOT_KEY), 0)
        all_actions.insert(_ts_idx, ("MOVE", "Move Toward Target (이동)"))
```
**바꾸기:**
```python
    # MOVE 자동 삽입 — TARGET_SELECT 직전 (Phase 4b)
    if "MOVE" not in [k for k, _ in all_actions]:
        _ts_idx = next((i for i, (k, _) in enumerate(all_actions) if k == _PIVOT_KEY), 0)
        all_actions.insert(_ts_idx, ("MOVE", "Move Toward Target (이동)"))

    # MOVE_SELECT 자동 삽입 — TARGET_SELECT 직후, per-target 첫 액션 (Phase 8a)
    if "MOVE_SELECT" not in [k for k, _ in all_actions]:
        _ms_idx = next((i for i, (k, _) in enumerate(all_actions) if k == _PIVOT_KEY), -1)
        all_actions.insert(_ms_idx + 1, ("MOVE_SELECT", "Select Move (무브 선택)"))
```

### 변경 6a — `run_simulation` 시그니처에 `game_config` 파라미터 추가

**찾기:**
```python
                   move_stat=None, deck_module=None):
```
**바꾸기:**
```python
                   move_stat=None, deck_module=None, game_config=None):
```

### 변경 6b — `run_simulation` 내부에서 `game_config` 정규화

**찾기:**
```python
    if not global_damage_formula: global_damage_formula = "0"
```
**바꾸기:**
```python
    if not global_damage_formula: global_damage_formula = "0"
    if game_config is None: game_config = {}
```

### 변경 6c — `build_ctx`의 ctx dict에 `current_move`·`game_config` 추가

**찾기:**
```python
            "current_target": None,
            "raw_dmg":       0,
```
**바꾸기:**
```python
            "current_target": None,
            "current_move":  None,
            "game_config":   game_config,
            "raw_dmg":       0,
```

### 변경 7a — `_worker_simulate_match`의 args 언패킹에 `game_config` 추가

**찾기:**
```python
         spatial_module, range_stat, move_stat, deck_module, worker_seed) = args
```
**바꾸기:**
```python
         spatial_module, range_stat, move_stat, deck_module, game_config, worker_seed) = args
```

### 변경 7b — `_worker_simulate_match`의 `run_simulation` 호출에 `game_config` 전달

**찾기:**
```python
            spatial_module=spatial_module, range_stat=range_stat, move_stat=move_stat,
            deck_module=deck_module
        )
```
**바꾸기:**
```python
            spatial_module=spatial_module, range_stat=range_stat, move_stat=move_stat,
            deck_module=deck_module, game_config=game_config
        )
```

### 변경 7c — `run_monte_carlo` 시그니처에 `game_config` 파라미터 추가

**찾기:**
```python
                    spatial_module=None, range_stat=None, move_stat=None,
                    deck_module=None):
```
**바꾸기:**
```python
                    spatial_module=None, range_stat=None, move_stat=None,
                    deck_module=None, game_config=None):
```

### 변경 7d — `run_monte_carlo`의 `tasks.append` 튜플에 `game_config` 추가

**찾기:**
```python
                      spatial_module, range_stat, move_stat, deck_module, worker_seed))
```
**바꾸기:**
```python
                      spatial_module, range_stat, move_stat, deck_module, game_config, worker_seed))
```

---

## 검증 체크리스트 (적용 후 직접 확인하라)

- [ ] `modules/engine.py` **단 하나만** 수정됐다. 다른 파일은 그대로다.
- [ ] `_act_element_mult` 함수는 **수정하지 않았다** (8b 영역).
- [ ] `python -m py_compile modules/engine.py` 가 에러 없이 통과한다.
- [ ] 신규 함수 `_act_move_select` 가 `_act_damage_calc` 바로 위에 존재한다.
- [ ] `DEFAULT_ACTION_REGISTRY.register("MOVE_SELECT", ...)` 줄이 존재한다.
- [ ] `_KOREAN_TO_KEY`·`_ENGLISH_HINTS`·`_TARGET_LEVEL_KEYS` 세 곳 모두 `MOVE_SELECT`를 포함한다.
- [ ] `run_simulation`·`run_monte_carlo`·`_worker_simulate_match` 세 곳 모두 `game_config`를 처리한다.
- [ ] 14개 변경이 **전부** 적용됐다 (부분 적용 시 `NameError` 발생).

## 회귀 불변 조건

`movepool` 없는 인스턴스 + `game_config` 미지정 시 — `_act_move_select`는 `current_move=None`을
설정하고, `_act_damage_calc`의 `if _move:` 블록은 건너뛰며, 데미지 공식 eval 환경은 현행과
완전히 동일하다. 즉 기존 전투 시뮬레이션 결과는 비트 단위로 불변이어야 한다.
