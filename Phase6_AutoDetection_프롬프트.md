# Phase 6 — Auto Game-Type Detection (모듈 탐지 + UI 게이팅)

## 배경

Phase 3~5에서 자원/공간/확률/덱 모듈을 추가했다. 각 모듈은 default=identity로
동작 동일성을 지켰지만, Step 6(Dashboard)이 모든 모듈의 UI 섹션(자원 선언·
damage_type 맵·공간 expander·덱 expander)을 **무조건 렌더**한다 → 장르와 무관하게
모든 컨트롤이 한 화면에 쌓인다.

Phase 6은 **탐지가 UI를 구동**하게 한다:
1. Step 2 스키마 매핑 직후, 매핑된 컬럼을 분석해 활성 모듈 셋을 **제안**한다
   (`modules/detection.py` 신규).
2. 제안 + 수동 오버라이드를 `game_profile`로 session_state에 저장한다 (Step 2 끝 패널).
3. Step 6의 모듈별 UI 섹션을 `game_profile`에 따라 렌더/숨김 한다.

탐지는 "제안"이다. 구조적 강신호(좌표 컬럼 쌍 · 범주형 damage_type 컬럼)만 자동 ON.
약신호(이름 패턴 매칭)는 힌트로만 표기하고 사용자가 수동으로 결정한다. 덱/확률은
평면 전투로그에서 신뢰 탐지가 불가능 → 자동 탐지 OFF 고정(수동 ON 전제).

## 변경 파일 (3개)

- **`modules/detection.py`** — 신규. 순수 분석 모듈 (streamlit 의존 0).
- **`modules/step2_system_definition.py`** — 탐지 호출 + Game Profile 패널.
- **`modules/step6_dashboard.py`** — 모듈별 UI 섹션 게이팅.

**엔진(`engine.py`) · `run_simulation` · 기존 모듈(`resource.py`/`spatial.py`/`deck.py`
등) 전부 수정 금지.** Phase 6은 순수 UI/오케스트레이션 작업이다.

## 설계 원칙 — 게이팅은 "표시 여부"만 제어한다

- 게이팅·탐지는 UI **표시 여부만** 제어한다. 모듈 config를 자동으로 작성하지 않는다.
- 모듈 섹션이 숨겨지면, 해당 모듈의 session_state 출력이 **identity 기본값**으로
  강제된다 → `run_simulation`이 받는 파라미터가 현행 default와 100% 동일.
- `game_profile`이 없으면(탐지 실패 등) `module_active()`가 True를 반환 → 모든 섹션
  표시 → 현행(Phase 6 이전) 동작과 100% 동일. **안전 폴백.** 이 폴백을 깨지 말 것.
- `universal_test_log.csv`는 공간/덱/damage_type/확률 컬럼이 없다 → 4개 모듈 모두
  자동 탐지 OFF → Step 6의 자원·공간·덱 섹션 숨김 → identity → 회귀 baseline 불변.

---

## 1. 신규 파일 — `modules/detection.py`

아래 코드를 **그대로** 새 파일로 생성한다. (이 코드의 실행 로직은 클린룸 회귀
24/24 통과로 검증 완료 — **실행 코드는 한 줄도 변경 금지.** 주석만 참고용이다.)

```python
"""
modules/detection.py
Phase 6 — Auto Game-Type Detection.

Step 2 스키마 매핑 직후, 매핑된 컬럼을 분석해 활성 모듈(자원/공간/확률/덱)을 제안한다.
순수 분석 모듈 — streamlit 의존 0. UI는 이 모듈의 출력을 '제안'으로만 사용한다.

설계 원칙:
- 탐지는 '제안'이다. 구조적 강신호(confidence='high')일 때만 detected=True.
- 약신호(컬럼명 패턴 매칭)는 detected를 켜지 않고 hints로만 보고한다.
- 덱/확률은 평면 전투로그에서 신뢰 탐지가 불가능 → detected 항상 False, hints만.
- detect_modules는 정상 입력에서 예외를 던지지 않는다(개별 연산 방어). 단, df 자체가
  비정상이면 예외가 호출부로 전파되어 호출부가 폴백(전체 표시)을 택한다.
"""

import pandas as pd

# ── 모듈 키 ──
MODULE_KEYS = ("resource", "spatial", "stochasticity", "deck")
# Step 6에 게이팅 대상 UI가 존재하는 모듈
GATED_MODULES = ("resource", "spatial", "deck")

# ── 컬럼명 패턴 사전 (소문자 부분 일치) ──
_DAMAGE_TYPE_HINTS = ("damage_type", "dmg_type", "dmgtype", "damagetype",
                      "element_type", "elem_type")
_RESOURCE_NAME_HINTS = ("mana", "shield", "stamina", "barrier", "energy", "rage")
_STOCH_HINTS = ("crit", "critical", "hit_chance", "hit_rate",
                "accuracy", "evasion", "dodge")
_DECK_HINTS = ("card", "deck", "hand_size", "mana_cost")


def _empty():
    return {"detected": False, "confidence": "none", "evidence": [], "hints": []}


def _find_coord_pair(columns):
    """좌표 컬럼 쌍 [x_col, y_col]을 찾는다. 못 찾으면 []."""
    low = {c: str(c).lower() for c in columns}
    x_cands = [c for c in columns
               if low[c] == "x" or low[c].endswith("_x")
               or "pos_x" in low[c] or "coord_x" in low[c] or "tile_x" in low[c]]
    y_cands = [c for c in columns
               if low[c] == "y" or low[c].endswith("_y")
               or "pos_y" in low[c] or "coord_y" in low[c] or "tile_y" in low[c]]
    if not x_cands or not y_cands:
        return []

    def _prefix(name, axis):
        for suf in ("_" + axis, axis):
            if name.endswith(suf):
                return name[: -len(suf)]
        return name

    for xc in x_cands:
        for yc in y_cands:
            if _prefix(low[xc], "x") == _prefix(low[yc], "y"):
                return [xc, yc]
    return [x_cands[0], y_cands[0]]


def detect_modules(df, stat_cols=None, gimmick_cols=None, target_col=None):
    """
    매핑된 컬럼을 분석해 활성 모듈을 제안한다.

    df          : Step 2 매핑 후 pandas DataFrame
    stat_cols   : 숫자형 스탯 컬럼 리스트 (system_stats) — 현재 분석엔 미사용, 확장용
    gimmick_cols: 카테고리/기믹 컬럼 리스트 (system_gimmicks) — 현재 분석엔 미사용
    target_col  : 타겟 변수 컬럼명 — 분석 대상에서 제외

    반환: { module_key: {'detected': bool, 'confidence': str,
                          'evidence': [근거 컬럼...], 'hints': [관련 가능 컬럼...]} }
    """
    result = {m: _empty() for m in MODULE_KEYS}

    all_cols = [c for c in list(df.columns) if c != target_col]
    low = {c: str(c).lower() for c in all_cols}

    # ── 공간 ── 좌표 컬럼 쌍(숫자형) = 구조적 강신호
    pair = _find_coord_pair(all_cols)
    if pair:
        numeric_ok = True
        for c in pair:
            try:
                if not pd.api.types.is_numeric_dtype(df[c]):
                    numeric_ok = False
            except Exception:
                numeric_ok = False
        if numeric_ok:
            result["spatial"] = {"detected": True, "confidence": "high",
                                 "evidence": list(pair), "hints": []}
        else:
            result["spatial"]["hints"] = list(pair)

    # ── 자원 ── damage_type 컬럼(저카디널리티 범주형) = 구조적 강신호
    dt_hit = None
    for c in all_cols:
        if any(h in low[c] for h in _DAMAGE_TYPE_HINTS):
            try:
                nuniq = int(df[c].dropna().nunique())
            except Exception:
                nuniq = 0
            if 2 <= nuniq <= 12:
                dt_hit = c
                break
    res_hints = [c for c in all_cols
                 if any(h in low[c] for h in _RESOURCE_NAME_HINTS)]
    if dt_hit:
        result["resource"] = {"detected": True, "confidence": "high",
                              "evidence": [dt_hit], "hints": res_hints}
    else:
        result["resource"]["hints"] = res_hints

    # ── 확률 ── 구조적 신호 없음 → 이름 약신호를 hints로만 (detected=False 고정)
    result["stochasticity"]["hints"] = [
        c for c in all_cols if any(h in low[c] for h in _STOCH_HINTS)]

    # ── 덱 ── 평면 로그에서 신뢰 탐지 불가 → detected=False 고정, hints만
    result["deck"]["hints"] = [
        c for c in all_cols if any(h in low[c] for h in _DECK_HINTS)]

    return result


def module_active(game_profile, module_key):
    """
    게임 프로파일 기준 모듈 활성 여부.
    game_profile이 None/불완전이면 True를 돌려준다 — 탐지 실패 시 전체 표시(현행 동작) 폴백.
    """
    if not game_profile or not isinstance(game_profile, dict):
        return True
    overrides = game_profile.get("overrides") or {}
    ov = overrides.get(module_key, "auto")
    if ov == "on":
        return True
    if ov == "off":
        return False
    detection = game_profile.get("detection") or {}
    entry = detection.get(module_key) or {}
    return bool(entry.get("detected", False))
```

---

## 2. `modules/step2_system_definition.py` 수정

### 2-1. import 추가

현재 12행 `import re` 다음 줄에:
```python
from modules.detection import detect_modules
```

### 2-2. Game Profile 패널 함수 (모듈 레벨)

`_apply_tag_mapping` 함수 정의가 끝난 직후(현재 63행 다음), `def render_system_definition():`
(현재 66행) **앞**에 모듈 레벨 함수로 삽입한다 (0칸 들여쓰기):

```python
def _render_game_profile_panel(game_profile):
    """Phase 6 — 탐지된 모듈 표시 + 모듈별 수동 오버라이드(Auto/ON/OFF) 패널."""
    detection = game_profile.get('detection', {})
    overrides = game_profile.setdefault('overrides', {})

    st.divider()
    st.markdown("## 🎛️ Game Profile — 활성 모듈 탐지")
    st.info("💡 매핑된 컬럼을 분석해 활성 모듈을 **제안**합니다. 탐지는 제안일 뿐이며, "
            "각 모듈을 수동으로 강제 ON/OFF 할 수 있습니다. 활성 모듈만 Dashboard에 표시됩니다.")

    _labels = {
        'resource': '🧪 자원 (다중 자원 / damage_type 라우팅)',
        'spatial':  '🗺️ 공간 (격자 / 사거리 / 이동)',
        'deck':     '🃏 덱 (카드 전투)',
    }
    _ov_opts = ['auto', 'on', 'off']
    _ov_label = {'auto': '자동 (탐지 따름)', 'on': '강제 ON', 'off': '강제 OFF'}

    for _m in ['resource', 'spatial', 'deck']:
        _d = detection.get(_m, {})
        _det = bool(_d.get('detected'))
        _evidence = _d.get('evidence') or []
        _hints = _d.get('hints') or []
        _cur = overrides.get(_m, 'auto')
        if _cur not in _ov_opts:
            _cur = 'auto'

        _c1, _c2 = st.columns([2, 3])
        with _c1:
            _choice = st.radio(
                _labels[_m], _ov_opts, index=_ov_opts.index(_cur),
                format_func=lambda x: _ov_label[x], horizontal=True,
                key=f"p6_override_{_m}")
        overrides[_m] = _choice

        _active = (_choice == 'on') or (_choice == 'auto' and _det)
        with _c2:
            if _det:
                st.success(f"✅ 탐지됨 (high) · 근거 컬럼: {', '.join(map(str, _evidence)) or '—'}")
            elif _hints:
                st.caption(f"🔍 자동 탐지 안 됨 · 관련 가능 컬럼(힌트): {', '.join(map(str, _hints))}")
            else:
                st.caption("자동 탐지 안 됨")
            st.markdown(f"**→ Dashboard 적용: {'🟢 ON' if _active else '⚪ OFF'}**")

    _stoch = detection.get('stochasticity', {})
    _stoch_hints = _stoch.get('hints') or []
    if _stoch_hints:
        st.caption(f"🎲 확률 요소 관련 컬럼 감지: {', '.join(map(str, _stoch_hints))} "
                   f"— 현재 게이팅 대상 UI 없음 (향후 Phase).")
```

### 2-3. 탐지 + 패널 호출 블록

`render_system_definition()`의 `else:` 분기(현재 304행 `else:`) 맨 끝,
`return True, ""`(현재 436행) **바로 앞**에 삽입한다. 들여쓰기 8칸 (`else:` 본문 레벨,
`with st.spinner(...)` 블록이 끝난 다음):

```python
        # ═══════════════════════════════════════════════════════════
        # Phase 6 — 모듈 자동 탐지 + Game Profile
        # ═══════════════════════════════════════════════════════════
        try:
            _df_p6 = st.session_state.get('df')
            _stat_cols_p6 = st.session_state.get('system_stats', [])
            _gim_cols_p6 = st.session_state.get('system_gimmicks', [])
            _target_p6 = st.session_state.get('target_col')
            _sig_p6 = (tuple(_df_p6.columns), tuple(_stat_cols_p6),
                       tuple(_gim_cols_p6), _target_p6)
            _gp_p6 = st.session_state.get('game_profile')
            if _gp_p6 is None or _gp_p6.get('signature') != _sig_p6:
                _detection_p6 = detect_modules(_df_p6, _stat_cols_p6,
                                               _gim_cols_p6, _target_p6)
                st.session_state['game_profile'] = {
                    'signature': _sig_p6,
                    'detection': _detection_p6,
                    'overrides': {'resource': 'auto', 'spatial': 'auto', 'deck': 'auto'},
                }
            _render_game_profile_panel(st.session_state['game_profile'])
        except Exception as _e_p6:
            st.session_state.pop('game_profile', None)
            st.warning(f"⚠️ 모듈 자동 탐지를 건너뜁니다 — Dashboard의 모든 모듈 섹션이 "
                       f"표시됩니다. ({_e_p6})")
```

동작: 매핑 시그니처(컬럼 구성 + 스탯/기믹/타겟)가 바뀌면 탐지를 재실행한다.
사용자의 오버라이드 라디오 선택은 `key`로 위젯이 유지하므로 재탐지 후에도 보존된다.
탐지가 어떤 이유로든 실패하면 `game_profile`을 제거 → Step 6이 전체 섹션을 표시
(현행 동작 폴백).

---

## 3. `modules/step6_dashboard.py` 수정

### 3-1. import 추가

현재 24행 `from modules.deck import DeckModule` 다음 줄에:
```python
from modules.detection import module_active
```

### 3-2. 게이팅 불리언 (render_dashboard 상단)

현재 130행 `sys_gimmicks = st.session_state.get('system_gimmicks', [])` **다음 줄**에
삽입한다 (4칸 들여쓰기 — `render_dashboard` 함수 본문 레벨):

```python
    # Phase 6 — Game Profile 기반 모듈 게이팅
    _gp6 = st.session_state.get('game_profile')
    _resource_on = module_active(_gp6, 'resource')
    _spatial_on = module_active(_gp6, 'spatial')
    _deck_on = module_active(_gp6, 'deck')
```

### 3-3. 자원 섹션 게이팅

`with st.expander("⚙️ 스탯 매핑 & 예산 가중치 (Weights) 설정", expanded=False):` 블록 안에서,
`st.markdown("##### 🧪 추가 자원 선언 (Pool / Shield)")` 줄(현재 162행)부터
`st.session_state['damage_type_map'] = damage_type_map` 줄(현재 213행)까지의
**연속 블록 전체**를:

- `if _resource_on:` 로 감싼다 (`if` 헤더는 현재 162행과 동일한 **12칸** 들여쓰기).
- 감싼 블록 내 모든 줄의 들여쓰기를 **+4칸** 한다 (로직은 한 줄도 바꾸지 말 것 — 들여쓰기만).
- 그 뒤에 `else:` 분기(12칸)를 추가한다:

```python
            else:
                # 자원 모듈 OFF — HP 단일 자원(현행 baseline) 강제
                resource_config = {"HP": {"role": "vital", "stat": health_stat, "regen": 0.0}}
                st.session_state['resource_config'] = resource_config
                resource_role_stats = set(spec["stat"] for spec in resource_config.values())
                st.session_state['damage_type_map'] = {}
```

⚠️ `resource_config`와 `resource_role_stats`는 바로 아래 "스탯 예산 환산 가중치"
섹션(현재 220행)이 사용한다. 따라서 `if`/`else` **양쪽 분기 모두**가 두 변수를 정의해야
한다. `if` 분기(기존 코드)는 이미 둘 다 정의하므로 그대로 두면 되고, `else` 분기는
위 코드가 둘 다 정의한다. (`health_stat`은 같은 expander 상단 152~154행에서 이미
정의되며 게이팅 대상이 아니므로 항상 사용 가능하다.)

### 3-4. 공간 섹션 게이팅

같은 expander 안에서, `st.markdown("##### 🗺️ 공간 시스템 (격자 + 사거리 + 이동)")`
줄(현재 228행 — 주석 `# ── 공간 시스템: ...`(227행) 다음 줄)부터
`st.session_state['grid_config'] = { ... }` 딕셔너리 블록 끝(현재 249행 `}`)까지를:

- `if _spatial_on:` 로 감싼다 (12칸).
- 감싼 블록 내 모든 줄 들여쓰기를 **+4칸**.
- `else:` 분기(12칸)를 추가한다:

```python
            else:
                # 공간 모듈 OFF — 사거리/이동 미사용(현행 baseline)
                st.session_state['range_stat'] = None
                st.session_state['move_stat'] = None
                st.session_state['grid_config'] = {"width": 10, "height": 10,
                                                   "distance_metric": "manhattan"}
```

### 3-5. 덱 expander 게이팅

`with st.expander("🃏 덱 전투 (Card Combat)", expanded=False):` 블록 **전체**
(현재 251~293행, 헤더부터 `key="ui_enemy_deck_editor")` 줄까지)를:

- `if _deck_on:` 로 감싼다 (`if` 헤더는 현재 251행과 동일한 **8칸** 들여쓰기).
- `with st.expander(...)` 블록 전체(헤더 포함)의 들여쓰기를 **+4칸**.
- `else:` 분기(8칸)를 추가한다:

```python
        else:
            # 덱 모듈 OFF — 덱 전투 미사용(현행 baseline)
            st.session_state['deck_mode'] = False
```

### 3-6. spatial_module_val 조건부 생성

`run_simulation` / `run_monte_carlo` 호출 직전의 공통 변수 구역(현재 679~682행)에서,
현재 코드:
```python
                _grid = st.session_state.get('grid_config') or {}
                spatial_module_val = SpatialModule(
                    width=_grid.get('width'), height=_grid.get('height'),
                    distance_metric=_grid.get('distance_metric', 'manhattan'))
```
를 다음으로 교체한다:
```python
                _grid = st.session_state.get('grid_config') or {}
                spatial_module_val = (SpatialModule(
                    width=_grid.get('width'), height=_grid.get('height'),
                    distance_metric=_grid.get('distance_metric', 'manhattan'))
                    if _spatial_on else None)
```

`deck_module_val`은 `deck_mode`가 게이팅 OFF 시 강제 False가 되므로 자동으로 None이
된다 — **수정 불필요.** `resource_module=ResourceModule(...)` 호출부도 수정 불필요
(자원 OFF 시 `resource_config`=HP단일 + `damage_type_map`={} → 현행 default와 동일).

---

## 제약 / 주의

- 변경 파일 3개 한정. 엔진(`engine.py`) · `run_simulation` · 기존 모듈 수정 금지.
- **로직 개선 금지, 사양대로만.** 탐지 휴리스틱·패턴 사전을 임의로 바꾸지 말 것.
  `detection.py`는 위 제공 코드 그대로 — 실행 코드 한 줄도 변경 금지.
- `detection.py`는 streamlit을 import하지 않는다.
- 게이팅 블록 re-indent 시 **기존 코드의 로직은 한 줄도 바꾸지 말 것** — 들여쓰기만
  +4칸. 블록 안의 중첩 `if/else`·`for`도 함께 +4칸 이동한다.
- `game_profile` 부재 시 `module_active`는 True를 반환 → 전체 섹션 표시 → 현행 동작.
  이 폴백 경로를 깨지 말 것.
- 오버라이드 라디오는 고정 옵션(`auto/on/off`) + 고정 `key` → stale-value 크래시
  위험 없음. `key`를 동적으로 만들지 말 것.

## 동작 동일성 — 회귀 검증

- `detection.py`는 신규 파일 — 어떤 기존 코드도 import하기 전까지 동작 영향 0.
- step2: 탐지/패널 블록은 매핑·ML·파이프라인 로직과 독립이며 `else:` 분기 끝에 **추가**
  될 뿐, 기존 코드를 변경하지 않는다.
- step6: 게이팅은 UI 표시 여부만 제어한다. 섹션이 숨겨지면 `resource_config`=HP단일,
  `damage_type_map`={}, `range_stat`/`move_stat`=None, `spatial_module`=None,
  `deck_mode`=False → `run_simulation`이 받는 파라미터가 현행 default와 동일.
- `universal_test_log.csv`: 컬럼에 좌표/damage_type/카드/확률 신호가 없다 → 4개 모듈
  모두 자동 탐지 OFF → 자원·공간·덱 섹션 숨김 → identity. 단일 전투 NoVariance 1v1
  lopsided 데미지총량 **620.0** / near-even **1026.0** 불변. Monte Carlo 동일.

## 완료 기준 체크리스트

- [ ] `modules/detection.py` 신규 생성 — 제공 코드의 실행 로직 그대로, streamlit import 없음
- [ ] `detection.py`가 `detect_modules`, `module_active`, `MODULE_KEYS`, `GATED_MODULES` 노출
- [ ] step2: `from modules.detection import detect_modules` import 추가
- [ ] step2: `_render_game_profile_panel` 모듈 레벨 함수 추가 (0칸 들여쓰기)
- [ ] step2: `else:` 분기 끝(`return True, ""` 앞)에 탐지+패널 블록 추가, try/except 폴백 포함
- [ ] step6: `from modules.detection import module_active` import 추가
- [ ] step6: render_dashboard 상단에 `_resource_on`/`_spatial_on`/`_deck_on` 정의
- [ ] step6: 자원 섹션(162~213행) `if _resource_on:` 게이팅 + else(HP단일 / damage_type_map={})
- [ ] step6: `resource_config`/`resource_role_stats`가 if·else 양쪽에서 정의됨 (220행 미파손)
- [ ] step6: 공간 섹션(227~249행) `if _spatial_on:` 게이팅 + else(range/move=None)
- [ ] step6: 덱 expander(251~293행) `if _deck_on:` 게이팅 + else(deck_mode=False)
- [ ] step6: `spatial_module_val`이 `_spatial_on`=False면 None
- [ ] 게이팅 블록 re-indent 외 기존 로직 0줄 변경
- [ ] 회귀: `universal_test_log.csv` → 자동 탐지 전부 OFF → 단일 전투 620.0 / 1026.0, MC 불변
