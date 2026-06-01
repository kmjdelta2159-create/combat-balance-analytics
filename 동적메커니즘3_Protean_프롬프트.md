# 동적 메커니즘 PR-D — Protean (무브마다 동적 타입 갱신)

Antigravity 작업 지시서. PR-A~C가 ON_TURN_END post 슬롯 계열만 다뤘다면, 이번에는 **새 per-target hook `ON_MOVE_USE`** 를 MOVE_SELECT 직후·DAMAGE_CALC 이전에 도입한다. 부착 캐릭터가 무브를 쓸 때 자신의 `current_type`을 그 무브 타입으로 갱신하고, STAB 계산기(`_move_stab_multiplier`)가 `current_type`을 공격자 타입으로 우선 참조한다. 결과적으로 Protean 캐릭터의 모든 무브에 STAB가 붙는다.

## 정직한 범위

이 PR은 **공격 측 STAB**만 동적화한다. Protean이 실제 Pokemon에서 갖는 **방어 측 타입 변경**(상대 무브의 상성 계산에 반영)은 이번 범위가 아니다 — `_move_type_multiplier`(방어자 상성)는 여전히 정적 기믹 타입을 읽는다. 부분 구현임을 명시한다. `current_type`은 무브 사용 시 갱신되어 다음 갱신까지 유지된다.

## 변경 범위

`modules/engine.py` 5곳, `modules/step2_system_definition.py` 1곳. game_config 저장은 기존 `_gc["mechanisms"] = _mech_cfg` 병합이 protean을 실어 나른다(추가 변경 없음). current_type은 reader가 `.get("current_type")`로 읽으므로 instance 초기화 변경이 필요 없다.

## 적용 규칙

- FIND를 찾아 REPLACE로 그대로 교체한다. 들여쓰기·공백·한글 한 글자도 바꾸지 않는다.
- 임의 리팩터·이름 변경·하드코딩 금지. 지시된 치환만.
- 적용 후 `python -c "import modules.engine"` 및 step2 py_compile 통과.

---

# 파일: `modules/engine.py`

## ENG-1 _TARGET_LEVEL_KEYS에 ON_MOVE_USE 추가

**FIND:**

```python
_TARGET_LEVEL_KEYS = {"MOVE_SELECT", "DAMAGE_CALC", "ELEMENT_MULT", "CRIT_CALC", "APPLY_DAMAGE", "ON_HIT", "DEATH_CHECK"}
```

**REPLACE:**

```python
_TARGET_LEVEL_KEYS = {"MOVE_SELECT", "ON_MOVE_USE", "DAMAGE_CALC", "ELEMENT_MULT", "CRIT_CALC", "APPLY_DAMAGE", "ON_HIT", "DEATH_CHECK"}
```

## ENG-2 _move_stab_multiplier가 current_type 우선 참조

**FIND:**

```python
    atypes = [char.get("gimmicks", {}).get(c)
              for c in (game_config or {}).get("type_columns", [])]
    return sf if mtype in atypes else 1.0
```

**REPLACE:**

```python
    # Protean 등 동적 타입(current_type)이 설정돼 있으면 그것을 공격자 타입으로 우선 사용
    if char.get("current_type"):
        atypes = [char.get("current_type")]
    else:
        atypes = [char.get("gimmicks", {}).get(c)
                  for c in (game_config or {}).get("type_columns", [])]
    return sf if mtype in atypes else 1.0
```

## ENG-3 _act_move_use 함수 삽입

**FIND:**

```python
# ── 디폴트 액션을 글로벌 레지스트리에 등록 ──
```

**REPLACE:**

```python
def _act_move_use(ctx):
    """무브 사용 직전 hook — Protean류 동적 타입 갱신. game_config['mechanisms']['protean'] 기반.
    부착 캐릭터가 무브를 쓸 때 자신의 current_type을 그 무브의 타입으로 갱신한다(STAB 상시 적용).
    미부착/미설정/무브에 타입 없음 시 no-op."""
    char = ctx["active_char"]
    move = ctx.get("current_move")
    mechs = (ctx.get("game_config") or {}).get("mechanisms") or {}
    spec = mechs.get("protean")
    if not spec or not move:
        return
    col = spec.get("gimmick_col")
    want = str(spec.get("match_value", "")).strip().lower()
    have = str(char.get("gimmicks", {}).get(col, "")).strip().lower() if col else ""
    if not col or have != want:
        return
    mtype = move.get("type")
    if not mtype:
        return
    if char.get("current_type") != mtype:
        char["current_type"] = mtype
        ctx["add_log"](
            f"  -> [Phase: ON_MOVE_USE] {char.get('id','?')} 타입이 {mtype}(으)로 변경 (Protean)"
        )


# ── 디폴트 액션을 글로벌 레지스트리에 등록 ──
```

## ENG-4 ON_MOVE_USE 레지스트리 등록

**FIND:**

```python
DEFAULT_ACTION_REGISTRY.register("ON_STATUS_TICK", _act_status_tick)
```

**REPLACE:**

```python
DEFAULT_ACTION_REGISTRY.register("ON_STATUS_TICK", _act_status_tick)
DEFAULT_ACTION_REGISTRY.register("ON_MOVE_USE",    _act_move_use)
```

## ENG-5 ON_MOVE_USE 자동 삽입 (MOVE_SELECT 직후)

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

    # ON_MOVE_USE 자동 삽입 — MOVE_SELECT 직후, 무브 사용 직전 동적 타입 hook
    if "ON_MOVE_USE" not in [k for k, _ in all_actions]:
        _mu_idx = next((i for i, (k, _) in enumerate(all_actions) if k == "MOVE_SELECT"), -1)
        all_actions.insert(_mu_idx + 1, ("ON_MOVE_USE", "Use Move (무브 사용)"))
```

---

# 파일: `modules/step2_system_definition.py`

## S-1 Protean 부착 UI를 expander에 추가

**FIND:**

```python
                else:
                    st.warning("기믹 컬럼이 없어 상태이상 기준을 지정할 수 없습니다.")

        st.divider()
```

**REPLACE:**

```python
                else:
                    st.warning("기믹 컬럼이 없어 상태이상 기준을 지정할 수 없습니다.")

            _pt_on = st.checkbox("Protean (무브마다 타입 갱신 → STAB 상시) 활성", value=False, key="ui_mech_protean_on")
            if _pt_on:
                if gimmicks:
                    _pt_col = st.selectbox(
                        "Protean 기준 기믹 컬럼", list(gimmicks), key="ui_mech_protean_col",
                        help="이 컬럼의 값이 아래 'Protean 값'과 일치하는 캐릭터가 무브 사용 시 그 무브 타입으로 갱신됨."
                    )
                    _pt_vals = (sorted(df[_pt_col].dropna().astype(str).unique().tolist())
                                if _pt_col in df.columns else [])
                    if _pt_vals:
                        _pt_match = st.selectbox("Protean 값", _pt_vals, key="ui_mech_protean_val")
                    else:
                        _pt_match = st.text_input("Protean 값", value="Protean", key="ui_mech_protean_val_txt")
                    _mech_cfg["protean"] = {
                        "gimmick_col": _pt_col,
                        "match_value": str(_pt_match),
                    }
                else:
                    st.warning("기믹 컬럼이 없어 Protean 기준을 지정할 수 없습니다.")

        st.divider()
```

---

## 적용 후 검증 (Antigravity가 보고할 것)

1. `modules/engine.py` import 통과, step2 py_compile 통과.
2. `grep -n 'def _act_move_use' modules/engine.py` → 1건.
3. `grep -n 'register("ON_MOVE_USE"' modules/engine.py` → 1건.
4. `grep -c 'ON_MOVE_USE' modules/engine.py` → 5건(_TARGET_LEVEL_KEYS·함수참조·등록·자동삽입 조건·insert).
5. `grep -c 'current_type' modules/engine.py` → 함수 2 + stab 리더 2 = 4건 이상.
6. `grep -c '_mech_cfg\["protean"\]' modules/step2_system_definition.py` → 1건.

## 라이브 동작 확인 (사용자)

Step 2 "🍃 동적 메커니즘 부착" expander에서 Protean을 활성하고 기준 기믹 컬럼·값(예: ability == Protean)을 지정한 뒤, Step 5 단일 전투를 돌리면 부착 캐릭터가 무브를 쓸 때 "[Phase: ON_MOVE_USE] … 타입이 X(으)로 변경 (Protean)" 줄이 찍히고, 그 무브의 데미지에 STAB(stab_factor, 예 1.5x)가 적용된다. 단, 무브 라이브러리에 type이 채워져 있고 stab_factor가 1.0이 아니어야 효과가 보인다.
