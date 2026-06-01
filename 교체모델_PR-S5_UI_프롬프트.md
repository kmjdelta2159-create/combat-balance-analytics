# 교체 모델 PR-S5(UI) — step2 교체 설정 입력 UI
Antigravity 작업 지시서. 아래 find/replace를 **정확한 문자열 치환**으로 적용한다. 각 FIND 블록은 프로젝트 파일에 byte-exact 1회 등장함을 빌더가 Grep으로 확인했고, REPLACE의 _gc 할당 로직은 하니스 단위검증(4케이스) + 클린룸 컴파일을 통과했다.
## 목적

PR-S1~S4로 교체 모델 엔진이 들어갔지만 active_count·on_active_faint·switch_policy를 game_config에 직접 넣어야만 켜진다. 이 PR은 step2 시스템 정의 화면에 이 세 값을 *사용자 개입*으로 설정하는 입력 UI를 더해, 사용자가 폼에서 교체 모델을 켜고 파라미터화할 수 있게 한다. 직전 phase의 무브 효과/전략 정책 UI와 동일 양식·동일 위치.

**회귀 0 보장**: 모든 입력의 기본값이 '미설정'(액티브 수 0=전원 동시, 사망 처리 (없음), 정책 (없음))이라 사용자가 건드리지 않으면 game_config에 교체 키가 추가되지 않아 현행 동작과 동일하다.
## 변경 범위

`modules/step2_system_definition.py` 2곳(메커니즘 expander 내 입력 위젯 + 시작 버튼 핸들러의 game_config 조립). **다른 파일·다른 영역은 건들지 않는다.** 게임 이름·전용 분기 없음(도메인 중립).
## 적용 규칙

- FIND를 찾아 REPLACE로 **그대로** 교체한다. 들여쓰기·공백·한글 주석 한 글자도 바꾸지 않는다.
- 임의 리팩터·이름 변경·추가 최적화·하드코딩 금지. 지시된 치환만 한다.
- 적용 후 step2 화면이 정상 렌더되고 `python -c "import modules.step2_system_definition"`가 통과해야 한다.

---
# 파일: `modules/step2_system_definition.py`
## UI-1 교체 설정 입력 위젯 (전략 정책 selectbox 직후)

**FIND:**

```python
            _move_policy_sel = st.selectbox(
                "전략 정책 (무브 선택 방식)",
                ["(기본) 그리디 — 최대 기대 데미지", "setup_first — 효과 무브 먼저 사용 후 데미지"],
                index=0, key="ui_mech_move_policy"
            )
```

**REPLACE:**

```python
            _move_policy_sel = st.selectbox(
                "전략 정책 (무브 선택 방식)",
                ["(기본) 그리디 — 최대 기대 데미지", "setup_first — 효과 무브 먼저 사용 후 데미지"],
                index=0, key="ui_mech_move_policy"
            )

            # ── 교체(switch) 모델 — 액티브/예비 회전 (게임 중립, 미설정 시 전원-동시) ──
            st.markdown("**교체(switch) 모델** — 액티브/예비 회전 (미설정 시 현행 전원-동시)")
            _active_count_in = st.number_input(
                "팀별 액티브 수 (0=전원 동시, 1=싱글, 2=더블 …)",
                min_value=0, value=0, step=1, key="ui_switch_active_count"
            )
            _faint_rule_sel = st.selectbox(
                "액티브 사망 시 처리",
                ["(없음)", "예비에서 교체 (replace_from_reserve)"],
                index=0, key="ui_switch_faint_rule"
            )
            _switch_policy_sel = st.selectbox(
                "자발적 교체 정책",
                ["(없음)", "HP 임계 교체 (hp_threshold)"],
                index=0, key="ui_switch_policy"
            )
            _switch_thr = st.number_input(
                "HP 임계 비율 (hp_threshold일 때 적용)",
                min_value=0.0, max_value=1.0, value=0.25, step=0.05,
                format="%.2f", key="ui_switch_threshold"
            )
```

## UI-2 시작 버튼 핸들러 — 교체 설정 → game_config

**FIND:**

```python
                if _move_policy_sel.startswith("setup_first"):
                    _gc["move_policy"] = "setup_first"
                if _gc:
                    st.session_state['game_config'] = _gc
```

**REPLACE:**

```python
                if _move_policy_sel.startswith("setup_first"):
                    _gc["move_policy"] = "setup_first"
                # ── 교체 모델 설정 → game_config (게임 중립) ──
                if _active_count_in and int(_active_count_in) > 0:
                    _gc["active_count"] = int(_active_count_in)
                if _faint_rule_sel.startswith("예비에서 교체"):
                    _gc["on_active_faint"] = "replace_from_reserve"
                if _switch_policy_sel.startswith("HP 임계"):
                    _gc["switch_policy"] = {"type": "hp_threshold",
                                            "threshold": float(_switch_thr)}
                if _gc:
                    st.session_state['game_config'] = _gc
```

---
## 적용 후 검증 (Antigravity가 보고할 것)

1. `modules/step2_system_definition.py`가 py_compile 통과.
2. `grep -n "ui_switch_active_count" modules/step2_system_definition.py` → 1건.
3. `grep -n "ui_switch_faint_rule" modules/step2_system_definition.py` → 1건.
4. `grep -n "ui_switch_policy" modules/step2_system_definition.py` → 1건.
5. `grep -n '_gc\["active_count"\]' modules/step2_system_definition.py` → 1건.
6. `grep -n '_gc\["switch_policy"\]' modules/step2_system_definition.py` → 1건.
