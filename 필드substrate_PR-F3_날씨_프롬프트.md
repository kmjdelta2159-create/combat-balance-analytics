# PR-F3 — 날씨 (field_state weather 슬롯 + chip 데미지 + 무브 배율 + 절대-턴 만료)

## 역할/맥락
너는 Antigravity 에이전트다. 아래 변경을 `modules/engine.py` **한 파일에만** 정확히 적용하라.
이 PR은 필드 substrate(F1) 위에 **두 번째 동적 상태인 날씨**를 올린다. 무브로 날씨를 설치/해제
하고(`set_weather`/`clear_weather`), 설치된 날씨가 (1) 매 턴 종료에 출전 유닛에게 chip 데미지를
주고, (2) 공격 무브의 타입별 데미지 배율을 건다. 만료는 **절대-턴 방식**(사용자 결정, 설계
§5-c) — 설치 시점에 `expires_turn = 현재 라운드 + 지속턴`을 저장하고, 모든 날씨 체크가
`ctx["turn"] <= expires_turn`로 판정한다(카운터 차감 없음 → 캐릭터별/라운드 이중차감 문제 소멸).

엔진 진실 출처(이 PR 설계의 근거, 적용 전 현 파일 상태):
- 날씨 *정의*는 정적이라 `game_config['mechanisms']['weather_defs']`에 둔다(병렬 워커 안전).
  형태: `{"rain": {"chip_percent": 0.0, "immune_types": [], "move_mult": {"Water": 1.5, "Fire": 0.5}}, ...}`.
- 날씨 *현재 상태*는 동적이라 `ctx["field_state"]["weather"] = {"name": ..., "expires_turn": ...}`에
  둔다(전투마다 새 dict — F1 substrate). 무브가 여기에 쓴다.
- `ctx["turn"]`은 라운드 번호(turn_manager의 `while turn` 카운터, build_ctx engine 내부에서 주입).
- ON_TURN_END/ON_STATUS_TICK은 **캐릭터별 post-level** 페이즈다(`_POST_LEVEL_KEYS`). 날씨 chip은
  같은 패턴의 **새 페이즈 `ON_WEATHER_TICK`**로 추가한다 — 기존 ON_TURN_END(레프트오버)·
  ON_STATUS_TICK(상태이상)을 **덮어쓰지 않는다**(레지스트리는 키당 단일 함수).

## 제약
- `modules/engine.py` 한 파일만. 아래 FIND/REPLACE **6건**만 적용. 각 FIND는 파일에 **정확히 1회**
  나타난다(검증에서 직접 확인됨). 다른 곳·다른 함수·저장부는 절대 건드리지 마라.
- 들여쓰기를 FIND 블록 그대로 따른다(스페이스, 탭 금지). REPLACE의 새 줄도 같은 규칙.
- 적용 후 `python -c "import ast; ast.parse(open('modules/engine.py',encoding='utf-8').read())"`로
  컴파일 확인.
- **회귀 0 원칙**: 날씨 미설정(field_state에 weather 없음) + weather_defs 미설정 시 모든 신규 hook이
  no-op이어야 한다. set_weather 무브를 아무도 안 쓰면 기존 전투와 byte-동일.

---

## 변경 1/6 — `_POST_LEVEL_KEYS`에 `ON_WEATHER_TICK` 추가

새 날씨 chip 페이즈를 캐릭터-턴종료(post-level)로 분류해 pivot 분할 시 post_target_actions로 가게 한다.

```python
# FIND
_POST_LEVEL_KEYS = {"ON_TURN_END", "ON_STATUS_TICK"}
```

```python
# REPLACE
_POST_LEVEL_KEYS = {"ON_TURN_END", "ON_STATUS_TICK", "ON_WEATHER_TICK"}
```

---

## 변경 2/6 — `_act_move_effect`에 set_weather/clear_weather 분기 추가

기존 해저드(set_hazard/clear_hazard) 분기 바로 다음, 스탯 boost 경로(`recipient = ...`) 앞에
날씨 설치/해제 분기를 끼운다. kind 없는 기존 spec은 영향 없음(회귀 0).

```python
# FIND
            applied = True
            continue
        recipient = char if spec.get("scope", "self") == "self" else tgt
```

```python
# REPLACE
            applied = True
            continue
        if kind in ("set_weather", "clear_weather"):
            # 필드 효과(F3): 무브로 날씨 설치/해제. 절대-턴 만료 — 설치 시 expires_turn 저장.
            fs = ctx.get("field_state")
            if fs is None:
                continue
            if kind == "set_weather":
                wname = str(spec.get("weather", "weather"))
                turns = int(spec.get("turns", 5))
                fs["weather"] = {"name": wname,
                                 "expires_turn": int(ctx.get("turn", 0)) + turns}
                ctx["add_log"](
                    f"  -> [Phase: ON_MOVE_EFFECT] {char.get('id','?')} 날씨 '{wname}' 설치 "
                    f"({turns}턴, ~{fs['weather']['expires_turn']}턴까지)"
                )
            else:
                fs["weather"] = None
                ctx["add_log"](
                    f"  -> [Phase: ON_MOVE_EFFECT] {char.get('id','?')} 날씨 해제"
                )
            applied = True
            continue
        recipient = char if spec.get("scope", "self") == "self" else tgt
```

---

## 변경 3/6 — `_act_element_mult`에 날씨 데미지 배율 삽입

상성 배율(elem_mult) 계산 직후, ctx 반영 직전에 유효 날씨의 무브타입 배율을 곱한다.
날씨 없음/만료/해당 타입 배율 없음 시 1.0(회귀 0). `move`는 이 함수 상단에서 이미 바인딩됨.

```python
# FIND
    ctx["elem_mult"] = elem_mult
    ctx["dmg"] = int(ctx["dmg"] * elem_mult)
```

```python
# REPLACE
    # 날씨 데미지 modifier (F3) — 유효 날씨 def의 move_mult[무브타입] 배율을 elem_mult에 곱한다.
    #   날씨 없음/만료/해당 타입 배율 없음 시 1.0(회귀 0). _active_weather가 절대-턴 만료 처리.
    _wdef = _active_weather(ctx)
    if _wdef and move:
        _wm = (_wdef.get("move_mult") or {}).get(move.get("type"))
        if _wm:
            elem_mult *= float(_wm)
    ctx["elem_mult"] = elem_mult
    ctx["dmg"] = int(ctx["dmg"] * elem_mult)
```

---

## 변경 4/6 — `_active_weather` 헬퍼 + `_act_weather_chip` 액션 정의

레지스트리 등록 블록 주석 바로 앞에 두 함수를 정의한다(등록부보다 위 → 변경 5에서 참조 가능).
`_active_weather`가 절대-턴 만료(lazy 청소·1회 로그)를 단일 지점에서 처리한다.

```python
# FIND
# ── 디폴트 액션을 글로벌 레지스트리에 등록 ──
```

```python
# REPLACE
def _active_weather(ctx):
    """현재 유효한 날씨 def 반환 — 절대-턴 만료(설계 §5-c). field_state.weather =
    {"name", "expires_turn"}이고 ctx["turn"](라운드 번호) > expires_turn이면 만료 →
    lazy 청소 후 None(만료 로그 1회). game_config['mechanisms']['weather_defs'][name]가
    chip_percent/immune_types/move_mult 정의를 담는다(정적 — 병렬 안전). 날씨 미설정/
    정의 없음 시 None → 모든 날씨 hook no-op(회귀 0)."""
    fs = ctx.get("field_state")
    if not fs:
        return None
    w = fs.get("weather")
    if not w:
        return None
    if int(ctx.get("turn", 0)) > int(w.get("expires_turn", 0)):
        if fs.get("weather") is not None:
            fs["weather"] = None
            ctx["add_log"](f"  -> [Phase: WEATHER] 날씨 '{w.get('name','?')}' 만료")
        return None
    defs = ((ctx.get("game_config") or {}).get("mechanisms") or {}).get("weather_defs") or {}
    wdef = defs.get(w.get("name"))
    if wdef is None:
        return None
    return {"name": w.get("name"), **wdef}


def _act_weather_chip(ctx):
    """날씨 턴종료 chip 데미지(ON_WEATHER_TICK) — 유효 날씨의 chip_percent를 active_char에
    주 자원 max 대비로 적용. immune_types에 캐릭터 타입(current_type 또는 type_columns 값)이
    들면 면제. 날씨 없음/만료/chip 0/면제/사망 시 no-op(회귀 0)."""
    wdef = _active_weather(ctx)
    if not wdef:
        return
    chip = float(wdef.get("chip_percent", 0) or 0)
    if chip <= 0:
        return
    char = ctx["active_char"]
    immune = [str(x).strip().lower() for x in (wdef.get("immune_types") or [])]
    if immune:
        if char.get("current_type"):
            ctypes = [str(char.get("current_type")).strip().lower()]
        else:
            ctypes = [str(char.get("gimmicks", {}).get(c, "")).strip().lower()
                      for c in (ctx.get("game_config") or {}).get("type_columns", [])]
        if any(ct and ct in immune for ct in ctypes):
            return
    rm = ctx.get("resource_module")
    vitals = rm.vital_resources() if rm else ()
    rname = vitals[0] if vitals else "HP"
    res = char.get("resources", {}).get(rname)
    if not res or res.get("current", 0) <= 0:
        return
    before = res["current"]
    res["current"] = max(0, res["current"] - res["max"] * chip)
    lost = before - res["current"]
    if lost > 0:
        ctx["add_log"](
            f"  -> [Phase: ON_WEATHER_TICK] {char.get('id','?')} {rname} {int(lost)} 날씨 피해 "
            f"({wdef.get('name','?')}) ({int(res['current'])}/{int(res['max'])})"
        )
    if res["current"] <= 0:
        ctx["add_log"](f"  [Phase: ON_WEATHER_TICK] ☠️ {char.get('id','?')} 날씨로 쓰러짐!")


# ── 디폴트 액션을 글로벌 레지스트리에 등록 ──
```

---

## 변경 5/6 — `ON_WEATHER_TICK` 레지스트리 등록

ON_STATUS_TICK 등록 바로 다음 줄에 날씨 chip 액션을 등록한다.

```python
# FIND
DEFAULT_ACTION_REGISTRY.register("ON_STATUS_TICK", _act_status_tick)
```

```python
# REPLACE
DEFAULT_ACTION_REGISTRY.register("ON_STATUS_TICK", _act_status_tick)
DEFAULT_ACTION_REGISTRY.register("ON_WEATHER_TICK", _act_weather_chip)
```

---

## 변경 6/6 — `ON_WEATHER_TICK` 자동 삽입 (흐름에 페이즈 추가)

ON_STATUS_TICK 자동 삽입 블록 바로 다음에 ON_WEATHER_TICK 삽입 블록을 추가한다(상태틱 직후 발화).

```python
# FIND
    # ON_STATUS_TICK 자동 삽입 — ON_TURN_END 직후, 턴 종료 상태이상 데미지 hook
    if "ON_STATUS_TICK" not in [k for k, _ in all_actions]:
        all_actions.append(("ON_STATUS_TICK", "Status Tick (상태이상 처리)"))
```

```python
# REPLACE
    # ON_STATUS_TICK 자동 삽입 — ON_TURN_END 직후, 턴 종료 상태이상 데미지 hook
    if "ON_STATUS_TICK" not in [k for k, _ in all_actions]:
        all_actions.append(("ON_STATUS_TICK", "Status Tick (상태이상 처리)"))

    # ON_WEATHER_TICK 자동 삽입 — ON_STATUS_TICK 직후, 턴 종료 날씨 chip 데미지 hook (F3)
    if "ON_WEATHER_TICK" not in [k for k, _ in all_actions]:
        all_actions.append(("ON_WEATHER_TICK", "Weather Tick (날씨 처리)"))
```

---

## 검증 (적용 후 수행)
1. `git diff modules/engine.py`로 변경이 위 6지점뿐인지 확인. 다른 함수·저장부 무변경.
2. 컴파일: `python -c "import ast; ast.parse(open('modules/engine.py',encoding='utf-8').read())"`.
3. 마커(각 1회): `_POST_LEVEL_KEYS = {"ON_TURN_END", "ON_STATUS_TICK", "ON_WEATHER_TICK"}`,
   `def _active_weather(ctx):`, `def _act_weather_chip(ctx):`,
   `DEFAULT_ACTION_REGISTRY.register("ON_WEATHER_TICK", _act_weather_chip)`,
   `("ON_WEATHER_TICK", "Weather Tick (날씨 처리)")`, set_weather 분기의
   `if kind in ("set_weather", "clear_weather"):`.
4. 회귀 0 스모크: 날씨 무브·weather_defs 없이 기존 전투 1판 → 로그에 `[Phase: WEATHER]`/
   `ON_WEATHER_TICK`/`날씨` 문자열이 **하나도** 안 나오는지(no-op) 확인.
5. 라이브(별도 스크립트 `F3_라이브실증.py`): active_count=1 + move_policy=setup_first +
   movepool에 set_weather 무브 포함 + `mechanisms.weather_defs`에 날씨 정의. 기대:
   - 설치 무브 발화 → `날씨 '<name>' 설치 (N턴, ~Kturn까지)`.
   - 설치 이후 턴종료마다 비면역 유닛에 `ON_WEATHER_TICK ... 날씨 피해` (chip_percent×max).
   - 면역 타입 유닛은 chip 면제(피해 로그 없음).
   - move_mult 정의 시 해당 타입 공격 데미지가 배율만큼 변동.
   - `ctx.turn > expires_turn`인 라운드에 `날씨 ... 만료` 1회 후 이후 chip/배율 0.

## 회귀/한계 메모
- 절대-턴 만료: 카운터를 깎지 않고 `expires_turn`을 비교만 한다 → ON_TURN_END가 캐릭터별로
  여러 번 발화해도 만료 시점은 라운드 단위로 일정(사용자 결정 §5-c, 멀티 액티브 갈래와 무충돌).
- chip 데미지는 `_act_weather_chip`가 캐릭터별로 적용(각 출전 유닛이 턴종료에 1회) — Pokemon
  날씨 chip과 동일 의미.
- 무브 배율은 공격 무브의 *타입*에 건다(rain×Water 등). type_table 미사용(레거시 element)
  경로는 `move`가 없어 배율 skip — 타입표 게임에서 작동.
- **방어 스탯 부스트(모래 Rock SpD +50%류)는 이 PR 범위 밖**(STAT_CALC 조건부 타입 buff 필요) →
  후속 F3b로 분리. F3는 chip + 공격 배율 + 만료까지.
- 날씨 정의(weather_defs)는 game_config 정적(병렬 안전), 현재 날씨는 field_state 동적(전투 범위).
  weather_defs에 name이 없으면 설치돼도 효과 없음(정의 우선) — config가 효과를 정의해야 함.
- UI는 후속 **PR-F5**(step2 무브효과 폼에 set_weather 무브 + mechanisms에 weather_defs 편집).
  엔진(이 PR) 적용·검증 후 진행 — H1→H3, F2→F4와 같은 "엔진 먼저, UI 나중" 분할.
