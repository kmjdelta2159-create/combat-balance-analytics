# PR-F2 — 동적 해저드 (무브로 설치/청소 + 정적·동적 max 합성) — engine.py

## 역할/맥락
너는 Antigravity 에이전트다. 아래 변경을 `modules/engine.py`에 **정확히** 적용하라. 이 PR은
F1이 깐 `field_state` substrate 위에 **동적 해저드**를 얹는다:
1. `_apply_entry_hazard`가 정적(game_config) **OR** 동적(field_state.hazard)을 **max로 합성**해
   읽는다(사용자 결정: 이중과세 방지로 합산 아닌 큰 값).
2. `_act_move_effect`(무브 효과 hook)가 `kind:"set_hazard"`/`"clear_hazard"` 효과를 만나면
   `ctx["field_state"]["hazard"]`에 진영별 해저드를 설치/청소한다.

회귀 0: 기존 move_effects spec엔 `kind` 키가 없어 분기 안 탐(기존 스탯 boost 경로 보존).
field_state.hazard 비면 동적 percent=0 → 정적만 → H1(PR-H1)과 byte-동일.

설계 근거(정찰·확정):
- `_act_move_effect`(engine L805)는 `game_config["move_effects"][무브이름]`의 spec_list를 순회해
  전부 `_track_state`로 스탯 boost를 부여한다. spec에 `kind`가 없으면 기존 경로.
- `_apply_entry_hazard`는 F1에서 `field_state=None` 선택 인자를 이미 받는다. field_state.hazard
  형태: `{"Ally": 0.125, "Enemy": 0.0, "both": 0.0}`(진영별 진입 데미지 비율, 없으면 0).
- 무브 효과 hook은 ctx를 받으므로 `ctx["field_state"]`로 설치 대상에 접근한다(F1로 ctx에 흐름).

## 제약
- `modules/engine.py` 한 파일만. 아래 2개 FIND/REPLACE만 적용. 각 FIND는 파일에 정확히 1회.
- `_apply_entry_hazard`의 외부 시그니처·로그 문자열 형식은 유지(라이브 로그 호환). 본문만 합성
  로직으로 교체.
- 적용 후 `python -c "import ast; ast.parse(open('modules/engine.py',encoding='utf-8').read())"`.

## 변경 1/2 — `_apply_entry_hazard` 본문을 정적·동적 max 합성으로 교체

```python
# FIND
    mechs = (game_config or {}).get("mechanisms") or {}
    spec = mechs.get("hazard")
    if not spec:
        return
    team = spec.get("team")
    if team and str(team).lower() != "both" and str(team) != str(char.get("team")):
        return
    before = get_current(char)
    if before <= 0:
        return
    mx = get_max(char)
    if mx <= 0:
        return
    percent = float(spec.get("percent", 0.125))
    apply_delta(char, -mx * percent)          # apply_delta는 새 current를 반환하므로 차분으로 계산
    lost = before - get_current(char)
    if lost > 0:
        add_log(f"  -> [Phase: ON_SWITCH] {char.get('id','?')} 진입 데미지 {int(lost)} (Hazard)")
    if get_current(char) <= 0:
        add_log(f"  [Phase: ON_SWITCH] ☠️ {char.get('id','?')} 진입 데미지로 쓰러짐! (Hazard)")
```

```python
# REPLACE
    my_team = str(char.get("team"))
    # 정적 해저드(game_config) — team 매칭 시 percent.
    static_pct = 0.0
    mechs = (game_config or {}).get("mechanisms") or {}
    spec = mechs.get("hazard")
    if spec:
        team = spec.get("team")
        if (not team) or str(team).lower() == "both" or str(team) == my_team:
            static_pct = float(spec.get("percent", 0.125))
    # 동적 해저드(field_state.hazard) — 무브로 설치된 진영별 비율. "both" 또는 내 진영 키.
    dyn_pct = 0.0
    fhaz = (field_state or {}).get("hazard") or {}
    if fhaz:
        dyn_pct = max(float(fhaz.get("both", 0) or 0),
                      float(fhaz.get(my_team, 0) or 0))
    # 합성: 이중과세 방지로 큰 값(사용자 결정).
    percent = max(static_pct, dyn_pct)
    if percent <= 0:
        return
    before = get_current(char)
    if before <= 0:
        return
    mx = get_max(char)
    if mx <= 0:
        return
    apply_delta(char, -mx * percent)          # apply_delta는 새 current를 반환하므로 차분으로 계산
    lost = before - get_current(char)
    if lost > 0:
        add_log(f"  -> [Phase: ON_SWITCH] {char.get('id','?')} 진입 데미지 {int(lost)} (Hazard)")
    if get_current(char) <= 0:
        add_log(f"  [Phase: ON_SWITCH] ☠️ {char.get('id','?')} 진입 데미지로 쓰러짐! (Hazard)")
```

## 변경 2/2 — `_act_move_effect` 루프에 set/clear_hazard kind 분기

```python
# FIND
    char = ctx["active_char"]
    tgt = ctx.get("current_target")
    applied = False
    for spec in spec_list:
        recipient = char if spec.get("scope", "self") == "self" else tgt
        if recipient is None:
            continue
```

```python
# REPLACE
    char = ctx["active_char"]
    tgt = ctx.get("current_target")
    applied = False
    for spec in spec_list:
        # 필드 효과(F2): 무브로 진영별 해저드 설치/청소. field_state(F1 substrate)에 쓴다.
        # kind 없는 기존 spec은 아래 스탯 boost 경로로 빠진다(회귀 0).
        kind = spec.get("kind")
        if kind in ("set_hazard", "clear_hazard"):
            fs = ctx.get("field_state")
            if fs is None:
                continue
            haz = fs.setdefault("hazard", {})
            hz_team = str(spec.get("team", "Enemy"))
            if kind == "set_hazard":
                haz[hz_team] = float(spec.get("percent", 0.125))
                ctx["add_log"](
                    f"  -> [Phase: ON_MOVE_EFFECT] {char.get('id','?')} {hz_team} 진영에 "
                    f"해저드 설치 ({haz[hz_team]:.3f})"
                )
            else:
                haz[hz_team] = 0.0
                ctx["add_log"](
                    f"  -> [Phase: ON_MOVE_EFFECT] {char.get('id','?')} {hz_team} 진영 해저드 청소"
                )
            applied = True
            continue
        recipient = char if spec.get("scope", "self") == "self" else tgt
        if recipient is None:
            continue
```

## 검증 (적용 후 수행)
1. `git diff modules/engine.py`로 변경이 위 2지점뿐인지 확인.
2. 컴파일: `python -c "import ast; ast.parse(open('modules/engine.py',encoding='utf-8').read())"`.
3. 마커: `static_pct = 0.0` 1회, `dyn_pct = 0.0` 1회, `percent = max(static_pct, dyn_pct)` 1회,
   `if kind in ("set_hazard", "clear_hazard"):` 1회, `haz = fs.setdefault("hazard", {})` 1회.
4. 동작 단위검증(아래 케이스):
   - **회귀(H1 보존)**: field_state 빈 dict, game_config hazard={"team":"Enemy","percent":0.25},
     char.team="Enemy", max=200 → 데미지 50, 로그 동일.
   - **동적 발동**: game_config hazard 없음, field_state={"hazard":{"Ally":0.125}}, char.team="Ally",
     max=160 → 데미지 20.
   - **max 합성**: 정적 0.1 + 동적 0.25(같은 진영) → percent=0.25(합 아님).
   - **둘 다 0/team 불일치**: → no-op(회귀 0).
   - **설치 무브**: move_effects에 `[{"kind":"set_hazard","team":"Enemy","percent":0.125}]` →
     실행 후 ctx["field_state"]["hazard"]["Enemy"]==0.125, 로그 "해저드 설치".
   - **청소 무브**: `[{"kind":"clear_hazard","team":"Enemy"}]` → ["Enemy"]==0.0.
   - **기존 boost spec(kind 없음)**: 분기 안 타고 _track_state 경로 그대로(회귀 0).

## 회귀/한계 메모
- 합성은 max(정적, 동적). 정적 H1과 동적 F2가 같은 진영에 겹치면 큰 값만 적용(이중과세 방지).
- field_state.hazard는 단일 전투 범위(F1: 전투마다 새 dict). 무브 설치가 그 전투 내내 유지.
- 설치 team은 spec이 직접 지정(게임 중립). Pokemon식 "상대 진영에 설치"는 무브 효과 정의에서
  team="Enemy" 등으로 표현(F4 UI에서 사용자 지정).
- 진입 KO 즉시 연쇄(갈래 6)는 별개 — F2가 즉사를 더 자주 유발할 수 있으나 정리 타이밍은 H1과
  동일(다음 _resolve_faint 사이클).
