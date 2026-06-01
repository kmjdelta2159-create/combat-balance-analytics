# 동적 메커니즘 PR-B — step2 메커니즘 부착 UI (Leftovers)

Antigravity 작업 지시서. PR-A(엔진 hook + Leftovers 액션) 위에 사용자 입력 UI를 얹는다. 아래 find/replace를 **정확한 문자열 치환**으로 적용한다. 두 블록 모두 `modules/step2_system_definition.py`에 byte-exact 1회 등장함을 빌더가 검증했고, 적용 후 파일 전체 py_compile 통과를 클린룸 컴파일로 확인했다.

## 목적

step2에 "동적 메커니즘 부착" expander를 추가해 사용자가 Leftovers(턴 종료 HP 회복)를 캐릭터에 부착한다. 부착 기준은 기믹 컬럼 값이다 — 지정 컬럼이 지정 값과 일치하는 캐릭터에만 적용되고, 이 키잉이라야 백테스트 정확도 측정에도 반영된다(per_battle_backtest가 캐릭터 이름을 버리고 기믹은 보존하기 때문). 사용자가 활성하지 않으면 `_mech_cfg`는 비고, game_config에 mechanisms 키가 들어가지 않아 PR-A 액션은 no-op이다.

## 변경 범위

`modules/step2_system_definition.py` 2곳. 다른 파일·다른 영역은 건드리지 않는다. expander는 채널 매핑 섹션과 시작 버튼 사이에 삽입되고, 저장은 기존 `_gc` 조립 블록에 mechanisms 병합 3줄을 더한다.

## 적용 규칙

- FIND를 찾아 REPLACE로 그대로 교체한다. 들여쓰기·공백·한글 한 글자도 바꾸지 않는다.
- 임의 리팩터·이름 변경·하드코딩 금지. 지시된 치환만.
- 적용 후 step2_system_definition.py가 py_compile 통과해야 한다.

---

# 파일: `modules/step2_system_definition.py`

## S-1 메커니즘 부착 expander 삽입

**FIND:**

```python
        st.divider()

        c_btn, c_json = st.columns(2)
        with c_btn:
```

**REPLACE:**

```python
        # ── 동적 메커니즘 부착 (Leftovers류 턴 종료 회복) — game_config["mechanisms"] ──
        _mech_cfg = {}
        with st.expander("🍃 동적 메커니즘 부착 (Mechanism Attach) — 선택", expanded=False):
            st.caption(
                "턴 종료마다 발동하는 동적 메커니즘을 캐릭터에 부착합니다. 부착 기준은 기믹 컬럼 값입니다 — "
                "지정한 컬럼이 지정 값과 일치하는 캐릭터에만 적용되며, 백테스트 정확도 측정에도 반영됩니다."
            )
            _lo_on = st.checkbox("Leftovers (턴 종료 HP 회복) 활성", value=False, key="ui_mech_leftovers_on")
            if _lo_on:
                if gimmicks:
                    _lo_col = st.selectbox(
                        "부착 기준 기믹 컬럼", list(gimmicks), key="ui_mech_leftovers_col",
                        help="이 컬럼의 값이 아래 '부착 값'과 일치하는 캐릭터에 회복을 적용."
                    )
                    _lo_vals = (sorted(df[_lo_col].dropna().astype(str).unique().tolist())
                                if _lo_col in df.columns else [])
                    if _lo_vals:
                        _lo_match = st.selectbox("부착 값", _lo_vals, key="ui_mech_leftovers_val")
                    else:
                        _lo_match = st.text_input("부착 값", value="Leftovers", key="ui_mech_leftovers_val_txt")
                    _lo_pct = st.number_input(
                        "턴 종료 회복률 (max HP 대비)", min_value=0.0, max_value=1.0,
                        value=0.0625, step=0.01, format="%.4f", key="ui_mech_leftovers_pct"
                    )
                    _mech_cfg["leftovers"] = {
                        "gimmick_col": _lo_col,
                        "match_value": str(_lo_match),
                        "percent": float(_lo_pct),
                    }
                else:
                    st.warning("기믹 컬럼이 없어 부착 기준을 지정할 수 없습니다.")

        st.divider()

        c_btn, c_json = st.columns(2)
        with c_btn:
```

## S-2 _gc에 mechanisms 병합

**FIND:**

```python
                if _gc:
                    st.session_state['game_config'] = _gc
                else:
                    st.session_state.pop('game_config', None)
```

**REPLACE:**

```python
                # ── 동적 메커니즘 부착 → game_config["mechanisms"] ──
                if _mech_cfg:
                    _gc["mechanisms"] = _mech_cfg
                if _gc:
                    st.session_state['game_config'] = _gc
                else:
                    st.session_state.pop('game_config', None)
```

---

## 적용 후 검증 (Antigravity가 보고할 것)

1. `modules/step2_system_definition.py` py_compile 통과.
2. `grep -n '_mech_cfg\["leftovers"\]' modules/step2_system_definition.py` → 1건.
3. `grep -n '_gc\["mechanisms"\] = _mech_cfg' modules/step2_system_definition.py` → 1건.
4. `grep -c 'st.expander("🍃 동적 메커니즘 부착' modules/step2_system_definition.py` → 1건.
5. Streamlit 재시작 후 Step 2에서 "🍃 동적 메커니즘 부착" expander가 보이고, Leftovers 활성 → 기믹 컬럼·부착 값·회복률 입력이 나타나는지 확인.

## 라이브 동작 확인 (사용자)

PR-A와 PR-B가 모두 적용되면, Step 2에서 item류 기믹 컬럼을 부착 기준으로 골라 "Leftovers" 값을 지정하고 회복률 0.0625로 둔 뒤, Step 5 백테스트나 단일 매치를 돌리면 전투 로그에 "🍃 … 회복 (현재/최대)" 줄이 찍힌다. 이걸로 ON_TURN_END hook의 라이브 발화를 눈으로 확인할 수 있다.
