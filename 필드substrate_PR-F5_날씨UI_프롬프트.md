# PR-F5 — 날씨 UI: weather_defs 정의 + set_weather 무브 (step2_system_definition.py)

## 역할/맥락
너는 Antigravity 에이전트다. 아래 변경을 `modules/step2_system_definition.py` **한 파일에만**
정확히 적용하라. 이 PR은 PR-F3(엔진, 적용·검증 완료)의 날씨를 UI에서 설정 가능하게 한다 —
두 개의 격리된 블록을 추가한다:

1. **날씨 효과 정의(weather_defs)** — 메커니즘 expander에 JSON 편집기로 날씨별 chip/면역/배율
   정의를 받아 `_mech_cfg["weather_defs"]`에 넣는다. 엔진은 `game_config['mechanisms']
   ['weather_defs'][name] = {"chip_percent": float, "immune_types": [..], "move_mult": {타입: 배율}}`
   를 정적으로 읽는다(병렬 안전). 중첩·가변 구조(타입→배율 맵이 임의 길이)라 고정 위젯 대신
   JSON 편집이 정직하다.
2. **날씨 설치/해제 무브** — 무브효과 폼에 set_weather/clear_weather 무브를 받아
   `_move_effects_cfg`에 `kind` 든 spec으로 append한다. 엔진 `_act_move_effect`가
   `kind:"set_weather"/"clear_weather"`를 만나면 `ctx["field_state"]["weather"]`에 설치/해제.

저장은 둘 다 기존 배선 재사용: `_mech_cfg` → `_gc["mechanisms"]`(이미 존재), `_move_effects_cfg`
→ `_gc["move_effects"]`(이미 존재). **저장부는 건드리지 않는다.** `json`은 이미 import됨(파일 상단).

엔진이 읽는 spec 형태(이 UI가 생성해야 하는 것):
- set_weather: `{"kind":"set_weather", "weather":"rain", "turns":5}` (절대-턴: expires=설치턴+turns).
- clear_weather: `{"kind":"clear_weather"}` (weather/turns 없음).
- weather_defs: `{"rain": {"chip_percent":0.0, "immune_types":[], "move_mult":{"Water":1.5,"Fire":0.5}}, ...}`.

## 제약
- `modules/step2_system_definition.py` 한 파일만. 아래 FIND/REPLACE **2건**만 적용. 각 FIND는
  파일에 **정확히 1회** 나타난다(검증에서 직접 확인됨). 저장부·기존 해저드/boost 블록은 무변경.
- 들여쓰기: 새 체크박스(`_wd_on`, `_wxm_on`)는 기존 해저드 체크박스(`_hz_on`/`_hzm_on`)와 같은
  12칸(expander 본문 레벨). FIND 블록 들여쓰기를 그대로 따른다(스페이스).
- 적용 후 `python -c "import ast; ast.parse(open('modules/step2_system_definition.py',encoding='utf-8').read())"`.

---

## 변경 1/2 — 메커니즘 expander에 weather_defs JSON 편집기 추가

정적 해저드 블록(`_mech_cfg["hazard"]`) 다음, 무브 효과 블록 주석 앞에 날씨 정의 블록을 끼운다.

```python
# FIND
                _mech_cfg["hazard"] = {
                    "team": _hz_team,
                    "percent": float(_hz_pct),
                }

            # ── 무브 효과 + 전략 정책 (전략 의사결정 모델) ──
```

```python
# REPLACE
                _mech_cfg["hazard"] = {
                    "team": _hz_team,
                    "percent": float(_hz_pct),
                }

            _wd_on = st.checkbox("날씨 효과 정의 (weather_defs) — 날씨별 chip/면역/타입 배율",
                                 value=False, key="ui_mech_weatherdefs_on")
            if _wd_on:
                _wd_json = st.text_area(
                    "날씨 정의 JSON (키 = 날씨 이름, 날씨 무브의 이름과 일치)",
                    value='{\n  "rain": {"chip_percent": 0.0, "immune_types": [], "move_mult": {"Water": 1.5, "Fire": 0.5}},\n  "sand": {"chip_percent": 0.0625, "immune_types": ["Rock", "Ground", "Steel"], "move_mult": {}}\n}',
                    height=170, key="ui_mech_weatherdefs_json",
                    help="chip_percent=턴종료 데미지 비율(주 자원 max 대비), immune_types=chip 면역 타입 리스트, "
                         "move_mult={공격 무브 타입: 데미지 배율}. 엔진은 이 정의를 정적으로 읽음(병렬 안전)."
                )
                try:
                    _wd_parsed = json.loads(_wd_json) if _wd_json.strip() else {}
                except (ValueError, TypeError):
                    _wd_parsed = None
                    st.warning("날씨 정의 JSON 파싱 실패 — 형식을 확인하세요.")
                if isinstance(_wd_parsed, dict) and _wd_parsed:
                    _mech_cfg["weather_defs"] = _wd_parsed

            # ── 무브 효과 + 전략 정책 (전략 의사결정 모델) ──
```

---

## 변경 2/2 — 무브효과 폼에 날씨 설치/해제 무브 UI 추가

F4 해저드 무브 블록 다음, 전략 정책 셀렉트(`_move_policy_sel`) 앞에 날씨 무브 블록을 끼운다.

```python
# FIND
                else:
                    st.warning("추출된 무브가 없어 해저드 무브를 지정할 수 없습니다.")
            _move_policy_sel = st.selectbox(
```

```python
# REPLACE
                else:
                    st.warning("추출된 무브가 없어 해저드 무브를 지정할 수 없습니다.")

            _wxm_on = st.checkbox("날씨 설치/해제 무브 (무브로 전장 날씨를 설치/해제 → 동적 날씨)",
                                  value=False, key="ui_mech_weathermove_on")
            if _wxm_on:
                if _move_names:
                    _wxm_move = st.selectbox("날씨 무브 선택", _move_names, key="ui_mech_wxm_move",
                                             help="이 무브를 사용하면 아래 설정대로 날씨를 설치/해제함.")
                    _wxm_kind = st.selectbox("동작", ["set_weather (설치)", "clear_weather (해제)"],
                                             key="ui_mech_wxm_kind")
                    _wxm_kind_val = "set_weather" if _wxm_kind.startswith("set") else "clear_weather"
                    _wxm_spec = {"kind": _wxm_kind_val}
                    if _wxm_kind_val == "set_weather":
                        _wxm_name = st.text_input(
                            "날씨 이름 (weather_defs의 키와 일치해야 효과 적용)",
                            value="rain", key="ui_mech_wxm_name",
                            help="위 '날씨 효과 정의(weather_defs)'에 같은 이름으로 chip/배율을 정의해야 효과가 납니다."
                        )
                        _wxm_turns = st.number_input(
                            "지속 턴 (라운드 수)", min_value=1, value=5, step=1,
                            key="ui_mech_wxm_turns",
                            help="설치 라운드 + 이 턴 수까지 유지(절대-턴 만료)."
                        )
                        _wxm_spec["weather"] = str(_wxm_name).strip()
                        _wxm_spec["turns"] = int(_wxm_turns)
                    _move_effects_cfg.setdefault(_wxm_move, []).append(_wxm_spec)
                else:
                    st.warning("추출된 무브가 없어 날씨 무브를 지정할 수 없습니다.")
            _move_policy_sel = st.selectbox(
```

---

## 검증 (적용 후 수행)
1. `git diff modules/step2_system_definition.py`로 변경이 위 2지점뿐인지 확인. 저장부
   (`_gc["mechanisms"]`/`_gc["move_effects"]`)·기존 해저드/boost 블록 무변경.
2. 컴파일: `python -c "import ast; ast.parse(open('modules/step2_system_definition.py',encoding='utf-8').read())"`.
3. 마커(각 1회): `ui_mech_weatherdefs_on`, `ui_mech_weatherdefs_json`, `_mech_cfg["weather_defs"]`,
   `ui_mech_weathermove_on`, `ui_mech_wxm_move`/`ui_mech_wxm_kind`,
   `_move_effects_cfg.setdefault(_wxm_move, []).append(_wxm_spec)`.
4. 들여쓰기: `_wd_on = st.checkbox(...)`·`_wxm_on = st.checkbox(...)`가 각각 `_hz_on`·`_hzm_on`과
   같은 12칸에서 시작.
5. 동작(폼 시뮬):
   - weather_defs 체크 on + 기본 JSON → `_mech_cfg["weather_defs"]`에 rain/sand dict 포함.
     깨진 JSON 입력 시 경고 + `weather_defs` 미설정(회귀 0).
   - 날씨 무브 체크 on + set_weather + "rain" + 5 → `_move_effects_cfg[무브]`에
     `{"kind":"set_weather","weather":"rain","turns":5}` 포함. clear_weather 선택 시
     `{"kind":"clear_weather"}`(weather/turns 키 없음). 체크 off → 미추가(회귀 0).

## 회귀/한계 메모
- 날씨 무브는 별도 무브로 격리(`setdefault().append()`) — 해저드/boost 블록 무변경 → 회귀 0.
- 저장은 기존 `_gc["mechanisms"]`/`_gc["move_effects"]` 재사용(별도 배선 불필요).
- weather_defs는 JSON 편집기 — 유연하나 파싱 외 스키마 검증은 없음(키 오타·잘못된 배율은
  엔진에서 no-op으로 흡수). 향후 구조화 위젯으로 보강 가능(선택).
- 날씨 이름은 무브 spec의 `weather`와 weather_defs 키가 **일치**해야 효과가 난다(엔진은 정의
  우선 — 정의 없으면 설치돼도 chip/배율 0). help 텍스트로 안내.
- 엔진 한계 그대로(PR-F3): 방어 스탯 부스트는 F3b로 분리. 멀티 액티브는 갈래 4에서.
