# PR-L1 — Step2 미소비 설정 정리 + effects 스키마 연결

> 대상: `modules/step2_system_definition.py`
> 성격: **연결 정리 PR**. 엔진이 실제로 소비하지 않는 UI 설정을 숨기고, 엔진이 이미 소비하는
> `game_config["mechanisms"]["effects"]` 입력면을 Step2에 연결한다.
> 목적: "핵심 부품은 있는데 제품 플로우에 연결이 덜 됨" 상태를 첫 단계로 줄인다.

---

## 0. 배경

코드 확인 결과, Step2의 동적 메커니즘 UI에는 엔진이 실제로 소비하지 않는 설정이 섞여 있다.

현재 Step2가 만드는 설정:

- `_mech_cfg["leftovers"]`, `_mech_cfg["status"]`, `_mech_cfg["protean"]`, `_mech_cfg["trace"]`,
  `_mech_cfg["hazard"]`
- `_mech_cfg["weather_defs"]`, `_mech_cfg["status_gates"]`, `_mech_cfg["move_props"]`
- `_move_effects_cfg` 안의 일반 boost/debuff spec
- `_move_effects_cfg` 안의 `{"kind": "set_hazard"|"clear_hazard"}`
- `_move_effects_cfg` 안의 `{"kind": "set_weather"|"clear_weather"}`
- `_move_effects_cfg` 안의 `{"kind": "inflict_status"}`

엔진이 실제로 소비하는 쪽:

- `engine.py`는 `mechanisms.leftovers/status/protean/trace/hazard`를 직접 읽는다.
- `engine.py`는 `game_config["mechanisms"]["effects"]`를 `_act_effect_dispatch()`에서 읽는다.
- `engine.py`는 `move_effects`의 일반 스탯 boost/debuff와 `kind in ("set_hazard", "clear_hazard")`
  만 처리한다.
- `weather_defs`, `status_gates`, `move_props`, `set_weather`, `clear_weather`, `inflict_status`는
  현재 실행 경로가 없다.

따라서 화면에 남겨두면 사용자가 "설정했는데 복제에 반영되는" 것으로 오해한다. 이 PR은 새 엔진 룰을
크게 만들지 않고, **실제로 연결된 설정만 남기는 정리**와 **이미 존재하는 effects 디스패처 입력면 연결**만
한다.

---

## 1. 변경 A — 미소비 UI 블록 제거

`modules/step2_system_definition.py`의 `with st.expander("🍃 동적 메커니즘 부착 ..."):` 내부에서
아래 블록을 제거한다.

### A-1. `weather_defs` 블록 제거

제거 대상: `날씨 효과 정의 (weather_defs) — 날씨별 chip/면역/타입 배율` 체크박스부터
`_mech_cfg["weather_defs"] = _wd_parsed`까지.

이유: 엔진은 `mechanisms.weather_defs`를 읽지 않는다. 현재 날씨 효과는 `mechanisms.effects`와
`weather_by_turn` 조합으로만 동작한다.

### A-2. `status_gates` 블록 제거

제거 대상: `행동 게이팅 상태이상 정의 (status_gates) — 마비/잠듦/혼란` 체크박스부터
`_mech_cfg["status_gates"] = _sg_parsed`까지.

이유: 엔진은 `mechanisms.status_gates`를 읽지 않는다. `StochasticityModule.roll_chance()`는 있지만
상태 게이팅 액션이 현재 레지스트리에 없다.

### A-3. `move_props` 블록 제거

제거 대상: `무브 속성 정의 (move_props) — per-move 명중률·다중 hit` 체크박스부터
`_mech_cfg["move_props"] = _mp_parsed`까지.

이유: 엔진은 `mechanisms.move_props`를 읽지 않는다. 명중률/다중 hit는 아직 `StochasticityModule`이나
무브 실행 루프에 연결되지 않았다.

### A-4. `set_weather`/`clear_weather` 무브 블록 제거

제거 대상: `날씨 설치/해제 무브 (무브로 전장 날씨를 설치/해제 → 동적 날씨)` 체크박스 블록 전체.

이유: `_act_move_effect()`는 `kind in ("set_hazard", "clear_hazard")`만 처리한다.
`set_weather`/`clear_weather`는 `move_effects`에 저장돼도 실행되지 않는다.

### A-5. `inflict_status` 무브 블록 제거

제거 대상: `상태이상 부여 무브 (무브로 마비/잠듦/혼란 부여 → 행동 게이팅)` 체크박스 블록 전체.

이유: `_act_move_effect()`는 `kind == "inflict_status"`를 처리하지 않는다.

---

## 2. 변경 B — 엔진이 이미 소비하는 `effects` 입력면 추가

같은 expander 안에서, `hazard` 블록 뒤 또는 무브 효과 블록 앞에 다음 UI를 추가한다.

```python
                _eff_on = st.checkbox(
                    "발동형 효과 스키마 (effects) 직접 입력 — 고급",
                    value=False, key="ui_mech_effects_on"
                )
                if _eff_on:
                    st.caption(
                        "엔진이 이미 소비하는 game_config['mechanisms']['effects'] 입력입니다. "
                        "키는 ability/item/status/weather/move 이름과 맞춰야 하며, 값은 trigger·effect·scope·source를 가진 dict입니다."
                    )
                    _eff_json = st.text_area(
                        "effects JSON",
                        value='{\n'
                              '  "Leftovers": {"trigger": "ON_TURN_END", "effect": {"type": "heal_frac", "frac": 0.0625, "of": "maxhp"}, "scope": "self", "source": "item"},\n'
                              '  "Burn": {"trigger": "ON_TURN_END", "effect": {"type": "damage_frac", "frac": 0.125, "of": "maxhp"}, "scope": "self", "source": "status"}\n'
                              '}',
                        height=220,
                        key="ui_mech_effects_json",
                        help="지원 effect.type: damage_frac, heal_frac, self_faint, swap_item. 조건은 condition dict로 추가합니다."
                    )
                    try:
                        _eff_parsed = json.loads(_eff_json) if _eff_json.strip() else {}
                    except (ValueError, TypeError):
                        _eff_parsed = None
                        st.warning("effects JSON 파싱 실패 — JSON 형식을 확인하세요.")
                    if isinstance(_eff_parsed, dict) and _eff_parsed:
                        _mech_cfg["effects"] = _eff_parsed
```

주의:

- 이 입력면은 엔진의 기존 `_act_effect_dispatch()`에 바로 연결된다.
- Python literal이 아니라 JSON이므로 `1/16` 같은 표현은 쓰지 않고 `0.0625`를 쓴다.
- 기존 `leftovers/status` 단순 UI는 유지한다. 단순 사용자는 그걸 쓰고, 고급 사용자는 `effects`를 쓴다.
- 동일 효과를 단순 UI와 `effects`에 동시에 넣으면 둘 다 발동할 수 있다. 캡션에 "중복 입력 주의"를 한 문장
  더해도 좋다.

---

## 3. 변경 C — 문구 정리

동적 메커니즘 expander의 설명 문구를 약간 조정한다.

현재 요지:

```python
"턴 종료마다 발동하는 동적 메커니즘을 캐릭터에 부착합니다..."
```

변경 요지:

```python
"엔진에 실제 연결된 동적 메커니즘만 설정합니다. 단순 항목은 폼으로 지정하고, 복잡한 발동형 효과는 effects JSON으로 입력합니다."
```

의도: 사용자가 화면에 보이는 설정이 실제 복제에 반영된다고 믿을 수 있게 만든다.

---

## 4. 불변

- `move_library`, `categories`, `type_table`, `stab_factor`, `channels` 저장 로직은 건드리지 않는다.
- `leftovers`, `status`, `protean`, `trace`, `hazard` 단순 메커니즘은 유지한다.
- 일반 스탯 boost/debuff 무브 효과는 유지한다.
- 해저드 설치/청소 무브(`set_hazard`, `clear_hazard`)는 유지한다. 엔진이 실제로 처리한다.
- 교체 모델(`active_count`, `on_active_faint`, `switch_policy`, `switch_priority`)은 유지한다.
- 엔진 파일은 이 PR에서 수정하지 않는다.

---

## 5. 검증

1. `ast.parse`:

```bash
python -c "import ast; ast.parse(open('modules/step2_system_definition.py', encoding='utf-8').read())"
```

2. 미소비 키 제거 확인:

```bash
grep -n "weather_defs\\|status_gates\\|move_props\\|set_weather\\|clear_weather\\|inflict_status" modules/step2_system_definition.py
```

결과는 0건이어야 한다.

3. 연결 키 확인:

```bash
grep -n "ui_mech_effects_on\\|ui_mech_effects_json\\|_mech_cfg\\[\"effects\"\\]" modules/step2_system_definition.py
```

3건 이상 나와야 한다.

4. 앱 확인:

- Step2의 동적 메커니즘 expander에서 미소비 블록들이 사라졌는지 확인한다.
- "발동형 효과 스키마 (effects) 직접 입력 — 고급"을 켜고 기본 JSON이 렌더되는지 확인한다.
- 잘못된 JSON을 넣으면 경고가 나오고, 올바른 JSON을 넣으면 `st.session_state["game_config"]["mechanisms"]["effects"]`
  로 저장되는지 확인한다.

5. 회귀 확인:

- Move System에서 무브 추출, 타입표, STAB, 카테고리 라우팅은 기존처럼 동작해야 한다.
- Step5 단일 전투 또는 백테스트가 import error 없이 진입해야 한다.

---

## 6. 의미

이 PR은 새 메커니즘을 많이 추가하는 PR이 아니다. 목적은 더 중요하다.

현재 제품 플로우에서 "UI가 받는 설정"과 "엔진이 실제로 먹는 설정"을 맞춘다. 미소비 설정을 걷어내고,
엔진에 이미 있는 발동형 효과 디스패처를 전문가 입력면으로 연결한다. 이 다음 PR에서 DB로그 IR을 붙일 때,
사용자는 더 이상 가짜 토글이 아니라 실제 실행되는 설정 언어 위에서 작업하게 된다.
