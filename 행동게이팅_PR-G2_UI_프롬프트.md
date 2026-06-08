# PR-G2 — 행동 게이팅 상태이상 UI (status_gates 정의 + inflict_status 무브)

## 역할/맥락
너는 Antigravity 에이전트다. 아래 변경을 `modules/step2_system_definition.py` **한 파일에만**
정확히 적용하라. 이 PR은 PR-G1(엔진, 적용·검증 완료)의 행동 게이팅 상태이상을 UI에서 설정
가능하게 한다 — 날씨(PR-F5)와 동일 패턴의 격리된 두 블록:

1. **status_gates 정의** — 메커니즘 expander에 JSON 편집기. 상태별 gate/chance/turns/
   self_hit_percent를 받아 `_mech_cfg["status_gates"]`에 넣는다. 엔진은
   `game_config['mechanisms']['status_gates'][name]`을 정적으로 읽는다(병렬 안전).
2. **상태이상 부여 무브** — 무브효과 폼에 inflict_status 무브를 받아 `_move_effects_cfg`에
   `kind:"inflict_status"` spec으로 append. 엔진 `_act_move_effect`가 대상 active_states에
   게이팅 상태를 부여.

저장은 둘 다 기존 배선 재사용: `_mech_cfg`→`_gc["mechanisms"]`, `_move_effects_cfg`→
`_gc["move_effects"]`. **저장부 무변경.** `json`은 이미 import됨.

엔진이 읽는 형태(이 UI가 생성):
- inflict_status: `{"kind":"inflict_status", "status":"paralysis", "chance":1.0, "scope":"target"}`.
- status_gates: `{"paralysis": {"gate":"skip_chance","chance":0.25,"turns":0}, "sleep": {"gate":"skip_full","turns":2}, "confusion": {"gate":"confuse","chance":0.5,"turns":3,"self_hit_percent":0.125}}`.

## 제약
- `modules/step2_system_definition.py` 한 파일만. 아래 FIND/REPLACE **2건**. 각 FIND는 파일에
  **정확히 1회**(검증 확인). 저장부·기존 날씨/해저드/boost 블록 무변경.
- 들여쓰기: 새 체크박스(`_sg_on`, `_ifm_on`)는 날씨 체크박스(`_wd_on`/`_wxm_on`)와 같은 12칸.
- 적용 후 `python -c "import ast; ast.parse(open('modules/step2_system_definition.py',encoding='utf-8').read())"`.

---

## 변경 1/2 — 메커니즘 expander에 status_gates JSON 편집기 추가

날씨 정의(weather_defs) 블록 다음, 무브 효과 블록 주석 앞에 상태 정의 블록을 끼운다.

```python
# FIND
                if isinstance(_wd_parsed, dict) and _wd_parsed:
                    _mech_cfg["weather_defs"] = _wd_parsed

            # ── 무브 효과 + 전략 정책 (전략 의사결정 모델) ──
```

```python
# REPLACE
                if isinstance(_wd_parsed, dict) and _wd_parsed:
                    _mech_cfg["weather_defs"] = _wd_parsed

            _sg_on = st.checkbox("행동 게이팅 상태이상 정의 (status_gates) — 마비/잠듦/혼란",
                                 value=False, key="ui_mech_statusgates_on")
            if _sg_on:
                _sg_json = st.text_area(
                    "상태 정의 JSON (키 = 상태 이름, inflict_status 무브의 status와 일치)",
                    value='{\n  "paralysis": {"gate": "skip_chance", "chance": 0.25, "turns": 0},\n  "sleep": {"gate": "skip_full", "turns": 2},\n  "confusion": {"gate": "confuse", "chance": 0.5, "turns": 3, "self_hit_percent": 0.125}\n}',
                    height=170, key="ui_mech_statusgates_json",
                    help="gate: skip_chance(매 턴 chance 확률 행동불가·turns 0=영구), skip_full(turns 동안 무조건 행동불가), "
                         "confuse(chance 확률 자해+행동불가, self_hit_percent=주 자원 max 대비 자해 비율). turns=고정 지속 턴."
                )
                try:
                    _sg_parsed = json.loads(_sg_json) if _sg_json.strip() else {}
                except (ValueError, TypeError):
                    _sg_parsed = None
                    st.warning("상태 정의 JSON 파싱 실패 — 형식을 확인하세요.")
                if isinstance(_sg_parsed, dict) and _sg_parsed:
                    _mech_cfg["status_gates"] = _sg_parsed

            # ── 무브 효과 + 전략 정책 (전략 의사결정 모델) ──
```

---

## 변경 2/2 — 무브효과 폼에 상태이상 부여 무브 UI 추가

날씨 무브 블록 다음, 전략 정책 셀렉트(`_move_policy_sel`) 앞에 상태이상 부여 무브 블록을 끼운다.

```python
# FIND
                else:
                    st.warning("추출된 무브가 없어 날씨 무브를 지정할 수 없습니다.")
            _move_policy_sel = st.selectbox(
```

```python
# REPLACE
                else:
                    st.warning("추출된 무브가 없어 날씨 무브를 지정할 수 없습니다.")

            _ifm_on = st.checkbox("상태이상 부여 무브 (무브로 마비/잠듦/혼란 부여 → 행동 게이팅)",
                                  value=False, key="ui_mech_inflictmove_on")
            if _ifm_on:
                if _move_names:
                    _ifm_move = st.selectbox("상태이상 무브 선택", _move_names, key="ui_mech_ifm_move",
                                             help="이 무브를 사용하면 아래 상태를 대상에 부여함.")
                    _ifm_status = st.text_input(
                        "부여할 상태 이름 (status_gates의 키와 일치)",
                        value="paralysis", key="ui_mech_ifm_status",
                        help="위 '행동 게이팅 상태이상 정의(status_gates)'에 같은 이름으로 정의해야 효과가 납니다."
                    )
                    _ifm_chance = st.number_input(
                        "부여 확률", min_value=0.0, max_value=1.0, value=1.0, step=0.05,
                        format="%.2f", key="ui_mech_ifm_chance",
                        help="1.0 = 항상 부여. 0.3 = 30% 확률 부여(시드 RNG)."
                    )
                    _ifm_scope = st.selectbox("대상", ["target", "self"], key="ui_mech_ifm_scope",
                                              help="target=상대에게 부여, self=자신에게 부여.")
                    _ifm_spec = {"kind": "inflict_status", "status": str(_ifm_status).strip(),
                                 "chance": float(_ifm_chance), "scope": _ifm_scope}
                    _move_effects_cfg.setdefault(_ifm_move, []).append(_ifm_spec)
                else:
                    st.warning("추출된 무브가 없어 상태이상 무브를 지정할 수 없습니다.")
            _move_policy_sel = st.selectbox(
```

---

## 검증 (적용 후 수행)
1. `git diff modules/step2_system_definition.py`로 변경이 위 2지점뿐인지 확인. 저장부·기존
   날씨/해저드/boost 블록 무변경.
2. 컴파일: `python -c "import ast; ast.parse(open('modules/step2_system_definition.py',encoding='utf-8').read())"`.
3. 마커(각 1회): `ui_mech_statusgates_on`, `ui_mech_statusgates_json`, `_mech_cfg["status_gates"]`,
   `ui_mech_inflictmove_on`, `ui_mech_ifm_move`/`ui_mech_ifm_status`,
   `_move_effects_cfg.setdefault(_ifm_move, []).append(_ifm_spec)`.
4. 들여쓰기: `_sg_on`·`_ifm_on` 체크박스가 각각 `_wd_on`·`_wxm_on`과 같은 12칸.
5. 동작(폼 시뮬):
   - status_gates 체크 on + 기본 JSON → `_mech_cfg["status_gates"]`에 paralysis/sleep/confusion
     포함. 깨진 JSON → 경고 + 미설정(회귀 0).
   - 상태이상 무브 체크 on + "paralysis" + 확률 1.0 + target → `_move_effects_cfg[무브]`에
     `{"kind":"inflict_status","status":"paralysis","chance":1.0,"scope":"target"}` 포함.
     체크 off → 미추가(회귀 0).

## 회귀/한계 메모
- 상태이상 무브는 별도 무브로 격리(`setdefault().append()`) — 기존 블록 무변경 → 회귀 0.
- 저장은 기존 `_gc["mechanisms"]`/`_gc["move_effects"]` 재사용.
- status_gates는 JSON 편집(가변 구조). 상태 이름은 무브 spec의 `status`와 정의 키가 **일치**해야
  효과(엔진은 정의 우선 — 없으면 게이트 no-op). help로 안내.
- 엔진 한계 그대로(PR-G1): 싱글 액티브 가정, 마비 속도감소는 별개(스탯 디버프), 자해 KO 정리는
  다음 _resolve_faint 사이클.
