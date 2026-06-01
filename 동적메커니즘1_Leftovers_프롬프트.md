# 동적 메커니즘 PR-A — 엔진 hook 인프라 + Leftovers 액션

Antigravity 작업 지시서. 아래 find/replace를 **정확한 문자열 치환**으로 적용한다. 각 블록은 프로젝트 파일에 byte-exact 1회 등장함을 빌더가 검증했고, 모든 edit 적용 후 두 파일 전체가 py_compile을 통과함을 클린룸 컴파일로 확인했다.

## 목적

9단계 파이프라인에 동적 메커니즘이 작동할 첫 자리를 만든다. StandardTurnExecutor를 pre/per/post 3슬롯으로 일반화해 비어 있던 "캐릭터 턴 종료" 액션 슬롯을 신설하고, 거기에 Leftovers류 턴 종료 회복 액션(ON_TURN_END)을 얹는다. 회복 대상은 `game_config["mechanisms"]["leftovers"]`로 구동된다(부착 UI는 후속 PR-B). mechanisms 미설정 시 액션은 즉시 no-op이라 기존 시뮬레이션 동작에 회귀가 없다.

## 변경 범위

`modules/turn_manager.py` 2곳, `modules/engine.py` 6곳. **다른 파일·다른 영역은 건드리지 않는다.** 특히 CardTurnExecutor(deck.py)는 이번 PR에서 변경하지 않는다 — 덱 게임의 턴 종료 hook은 후속 과제다.

## 적용 규칙

- 아래 FIND를 찾아 REPLACE로 **그대로** 교체한다. 들여쓰기·공백·한글 주석 한 글자도 바꾸지 않는다.
- 임의 리팩터·이름 변경·추가 최적화·하드코딩 금지. 지시된 치환만 한다.
- 적용 후 `python -c "import modules.engine, modules.turn_manager"`가 에러 없이 통과해야 한다.

---

# 파일: `modules/turn_manager.py`

## TM-1 executor __init__ post 슬롯

**FIND:**

```python
    def __init__(self, pre_target_actions, per_target_actions):
        """
        Args:
            pre_target_actions: [(key, label), ...] 타겟 선택 이전 액션 리스트
            per_target_actions: [(key, label), ...] 타겟별 반복 액션 리스트
        """
        self.pre_target_actions = pre_target_actions
        self.per_target_actions = per_target_actions
```

**REPLACE:**

```python
    def __init__(self, pre_target_actions, per_target_actions, post_target_actions=None):
        """
        Args:
            pre_target_actions: [(key, label), ...] 타겟 선택 이전 액션 리스트
            per_target_actions: [(key, label), ...] 타겟별 반복 액션 리스트
            post_target_actions: [(key, label), ...] 타겟 처리 후 캐릭터 단위 1회 액션 (턴 종료 hook)
        """
        self.pre_target_actions = pre_target_actions
        self.per_target_actions = per_target_actions
        self.post_target_actions = post_target_actions or []
```

## TM-2 execute post 루프

**FIND:**

```python
        # ── B. per-target 액션 실행 ──
        if ctx["targets"]:
            for t in ctx["targets"]:
                ctx["current_target"] = t
                ctx["raw_dmg"] = 0
                ctx["dmg"] = 0
                ctx["elem_mult"] = 1.0
                for key, label in self.per_target_actions:
                    func = registry.get(key)
                    if func:
                        func(ctx)
```

**REPLACE:**

```python
        # ── B. per-target 액션 실행 ──
        if ctx["targets"]:
            for t in ctx["targets"]:
                ctx["current_target"] = t
                ctx["raw_dmg"] = 0
                ctx["dmg"] = 0
                ctx["elem_mult"] = 1.0
                for key, label in self.per_target_actions:
                    func = registry.get(key)
                    if func:
                        func(ctx)
        # ── C. post-target 액션 실행 (캐릭터 단위, 타겟 무관, 턴 종료 hook) ──
        for key, label in self.post_target_actions:
            func = registry.get(key)
            if func:
                func(ctx)
```

---

# 파일: `modules/engine.py`

## ENG-1 _POST_LEVEL_KEYS 분류

**FIND:**

```python
_CHAR_LEVEL_KEYS  = {"PASSIVE_START", "STAT_CALC", "TARGET_SELECT", "MOVE"}
_TARGET_LEVEL_KEYS = {"MOVE_SELECT", "DAMAGE_CALC", "ELEMENT_MULT", "CRIT_CALC", "APPLY_DAMAGE", "ON_HIT", "DEATH_CHECK"}
_PIVOT_KEY = "TARGET_SELECT"
```

**REPLACE:**

```python
_CHAR_LEVEL_KEYS  = {"PASSIVE_START", "STAT_CALC", "TARGET_SELECT", "MOVE"}
_TARGET_LEVEL_KEYS = {"MOVE_SELECT", "DAMAGE_CALC", "ELEMENT_MULT", "CRIT_CALC", "APPLY_DAMAGE", "ON_HIT", "DEATH_CHECK"}
# 캐릭터 턴 종료 후 1회 실행되는 동적 메커니즘 hook (타겟 무관)
_POST_LEVEL_KEYS = {"ON_TURN_END"}
_PIVOT_KEY = "TARGET_SELECT"
```

## ENG-2 _act_turn_end_heal 함수 삽입

**FIND:**

```python
# ── 디폴트 액션을 글로벌 레지스트리에 등록 ──
```

**REPLACE:**

```python
def _act_turn_end_heal(ctx):
    """턴 종료 회복 메커니즘 (Leftovers류) — game_config['mechanisms']['leftovers'] 기반.
    부착 캐릭터가 턴 종료 시 vital 자원의 percent만큼 회복한다. 사망(현재값 0)이면
    회복하지 않는다. max 상한으로 클램프. 미부착/미설정 시 no-op."""
    char = ctx["active_char"]
    mechs = (ctx.get("game_config") or {}).get("mechanisms") or {}
    spec = mechs.get("leftovers")
    if not spec:
        return
    col = spec.get("gimmick_col")
    want = str(spec.get("match_value", "")).strip().lower()
    have = str(char.get("gimmicks", {}).get(col, "")).strip().lower() if col else ""
    if not col or have != want:
        return
    percent = float(spec.get("percent", 0.0625))
    rm = ctx.get("resource_module")
    vitals = rm.vital_resources() if rm else ()
    rname = vitals[0] if vitals else "HP"
    res = char.get("resources", {}).get(rname)
    if not res or res.get("current", 0) <= 0:
        return
    before = res["current"]
    res["current"] = min(res["max"], res["current"] + res["max"] * percent)
    gained = res["current"] - before
    if gained > 0:
        ctx["add_log"](
            f"  -> [Phase: ON_TURN_END] {char.get('id','?')} {rname} {int(gained)} 회복 "
            f"({int(res['current'])}/{int(res['max'])})"
        )


# ── 디폴트 액션을 글로벌 레지스트리에 등록 ──
```

## ENG-3 ON_TURN_END 레지스트리 등록

**FIND:**

```python
DEFAULT_ACTION_REGISTRY.register("DEATH_CHECK",   _act_death_check)
```

**REPLACE:**

```python
DEFAULT_ACTION_REGISTRY.register("DEATH_CHECK",   _act_death_check)
DEFAULT_ACTION_REGISTRY.register("ON_TURN_END",   _act_turn_end_heal)
```

## ENG-4 ON_TURN_END 자동 삽입

**FIND:**

```python
    # MOVE_SELECT 자동 삽입 — TARGET_SELECT 직후, per-target 첫 액션 (Phase 8a)
    if "MOVE_SELECT" not in [k for k, _ in all_actions]:
        _ms_idx = next((i for i, (k, _) in enumerate(all_actions) if k == _PIVOT_KEY), -1)
        all_actions.insert(_ms_idx + 1, ("MOVE_SELECT", "Select Move (무브 선택)"))
```

**REPLACE:**

```python
    # MOVE_SELECT 자동 삽입 — TARGET_SELECT 직후, per-target 첫 액션 (Phase 8a)
    if "MOVE_SELECT" not in [k for k, _ in all_actions]:
        _ms_idx = next((i for i, (k, _) in enumerate(all_actions) if k == _PIVOT_KEY), -1)
        all_actions.insert(_ms_idx + 1, ("MOVE_SELECT", "Select Move (무브 선택)"))

    # ON_TURN_END 자동 삽입 — 흐름 끝, 캐릭터 턴 종료 동적 메커니즘 hook
    if "ON_TURN_END" not in [k for k, _ in all_actions]:
        all_actions.append(("ON_TURN_END", "Turn End Effects (턴 종료 효과)"))
```

## ENG-5 흐름 분리에 post_target_actions 추가

**FIND:**

```python
    pre_target_actions = []
    per_target_actions = []
    pivot_found = False
    for key, label in all_actions:
        if key == _PIVOT_KEY:
            pre_target_actions.append((key, label))
            pivot_found = True
        elif not pivot_found:
            pre_target_actions.append((key, label))
        else:
            per_target_actions.append((key, label))
```

**REPLACE:**

```python
    pre_target_actions = []
    per_target_actions = []
    post_target_actions = []
    pivot_found = False
    for key, label in all_actions:
        if key in _POST_LEVEL_KEYS:
            post_target_actions.append((key, label))
        elif key == _PIVOT_KEY:
            pre_target_actions.append((key, label))
            pivot_found = True
        elif not pivot_found:
            pre_target_actions.append((key, label))
        else:
            per_target_actions.append((key, label))
```

## ENG-6 executor 생성에 post 전달

**FIND:**

```python
    else:
        turn_executor = StandardTurnExecutor(pre_target_actions, per_target_actions)
```

**REPLACE:**

```python
    else:
        turn_executor = StandardTurnExecutor(pre_target_actions, per_target_actions,
                                             post_target_actions)
```

---

## 적용 후 검증 (Antigravity가 보고할 것)

1. `modules/turn_manager.py`와 `modules/engine.py`가 각각 py_compile 통과.
2. `grep -n "def _act_turn_end_heal" modules/engine.py` → 1건.
3. `grep -n 'register("ON_TURN_END"' modules/engine.py` → 1건.
4. `grep -n "post_target_actions" modules/turn_manager.py` → 3건(파라미터·저장·execute 루프).
5. `grep -n "post_target_actions" modules/engine.py` → 3건(분리 선언·라우팅·executor 전달).
6. 변경 라인 수: turn_manager.py +5줄, engine.py 함수 삽입 분 포함.
