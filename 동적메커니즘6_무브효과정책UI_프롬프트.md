# 동적 메커니즘 PR-G — 무브 효과 + 전략 정책 입력 UI

Antigravity 작업 지시서. PR-E(무브 효과 경로)·PR-F(setup_first 정책)는 game_config 주입으로만 작동했다. 이 PR이 그 둘을 사용자가 step2에서 직접 채우는 입력을 추가한다 — 이걸로 Calm Mind류 "초반 boost 후 데미지" 플레이를 Step 5에서 라이브로 확인할 수 있다.

기존 "🍃 동적 메커니즘 부착" expander 안, Protean 입력 다음에 무브 효과 입력(효과 무브 선택·올릴/내릴 스탯 다중선택·증감 방식·증감량·대상)과 전략 정책 선택을 추가한다. 저장은 기존 `_gc` 조립 블록에 `move_effects`·`move_policy` 두 키를 더한다. 미설정 시 키가 안 들어가 엔진은 그리디·무효과로 동작(회귀 0).

## 변경 범위

`modules/step2_system_definition.py` 2곳. 무브 이름은 기존 `move_library_edited["name"]`에서, 스탯 목록은 기존 `base_stats`에서 가져온다(둘 다 이미 스코프에 있음). 다른 파일·영역은 건드리지 않는다.

## 적용 규칙

- FIND를 찾아 REPLACE로 그대로 교체한다. 들여쓰기·공백·한글 한 글자도 바꾸지 않는다.
- 임의 리팩터·이름 변경·하드코딩 금지. 지시된 치환만.
- 적용 후 step2_system_definition.py py_compile 통과.

---

# 파일: `modules/step2_system_definition.py`

## S-1 무브 효과+정책 UI를 expander에 추가

**FIND:**

```python
                else:
                    st.warning("기믹 컬럼이 없어 Protean 기준을 지정할 수 없습니다.")

        st.divider()
```

**REPLACE:**

```python
                else:
                    st.warning("기믹 컬럼이 없어 Protean 기준을 지정할 수 없습니다.")

            # ── 무브 효과 + 전략 정책 (전략 의사결정 모델) ──
            _move_effects_cfg = {}
            _move_names = []
            if move_library_edited is not None and "name" in getattr(move_library_edited, "columns", []):
                _move_names = sorted(move_library_edited["name"].dropna().astype(str).unique().tolist())
            _me_on = st.checkbox("무브 효과 (boost/디버프) 부여 활성", value=False, key="ui_mech_moveeffect_on")
            if _me_on:
                if _move_names and base_stats:
                    _me_move = st.selectbox("효과 무브 선택", _move_names, key="ui_mech_me_move")
                    _me_stats = st.multiselect("올릴/내릴 스탯", list(base_stats), key="ui_mech_me_stats")
                    _me_mod = st.selectbox("증감 방식", ["percent", "flat"], key="ui_mech_me_mod")
                    _me_val = st.number_input(
                        "증감량 (percent는 0.5=+50%, 음수=디버프)", value=0.5, step=0.1,
                        format="%.3f", key="ui_mech_me_val"
                    )
                    _me_scope = st.selectbox("대상", ["self", "target"], key="ui_mech_me_scope")
                    if _me_stats:
                        _move_effects_cfg[_me_move] = [
                            {"target_stat": _s, "mod_type": _me_mod,
                             "value": float(_me_val), "scope": _me_scope}
                            for _s in _me_stats
                        ]
                else:
                    st.warning("추출된 무브 또는 기본 스탯이 없어 무브 효과를 지정할 수 없습니다.")
            _move_policy_sel = st.selectbox(
                "전략 정책 (무브 선택 방식)",
                ["(기본) 그리디 — 최대 기대 데미지", "setup_first — 효과 무브 먼저 사용 후 데미지"],
                index=0, key="ui_mech_move_policy"
            )

        st.divider()
```

## S-2 move_effects·move_policy → game_config 저장

**FIND:**

```python
                # ── 동적 메커니즘 부착 → game_config["mechanisms"] ──
                if _mech_cfg:
                    _gc["mechanisms"] = _mech_cfg
```

**REPLACE:**

```python
                # ── 동적 메커니즘 부착 → game_config["mechanisms"] ──
                if _mech_cfg:
                    _gc["mechanisms"] = _mech_cfg
                # ── 무브 효과 + 전략 정책 → game_config ──
                if _move_effects_cfg:
                    _gc["move_effects"] = _move_effects_cfg
                if _move_policy_sel.startswith("setup_first"):
                    _gc["move_policy"] = "setup_first"
```

---

## 적용 후 검증 (Antigravity가 보고할 것)

1. `modules/step2_system_definition.py` py_compile 통과.
2. `grep -c 'ui_mech_moveeffect_on' modules/step2_system_definition.py` → 1건.
3. `grep -c '_gc\["move_effects"\]' modules/step2_system_definition.py` → 1건.
4. `grep -c '_gc\["move_policy"\]' modules/step2_system_definition.py` → 1건.
5. Step 2 "🍃 동적 메커니즘 부착" expander에 무브 효과 입력과 "전략 정책" 셀렉트가 보이는지.

## 라이브 동작 확인 (사용자)

무브 라이브러리에 위력 0짜리 setup 무브(예: Calm Mind)가 있고 카테고리 라우팅이 설정된 상태에서, 무브 효과로 그 무브에 SpAtk +0.5(또는 해당 게임 스탯)를 self로 지정하고 전략 정책을 setup_first로 둔다. Step 5 단일 전투를 돌리면, 부착 캐릭터가 1턴에 그 무브를 골라(로그 "[Phase: ON_MOVE_EFFECT] … 효과 적용") boost를 깔고, 이후 턴엔 데미지 무브로 전환하는 패턴이 보인다.
