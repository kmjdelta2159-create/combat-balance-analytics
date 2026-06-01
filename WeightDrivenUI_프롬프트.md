# Antigravity 프롬프트 — 가중치 기반 동적 상태 주도 UI (D5)

D4 설계안(`WeightDrivenUI_설계안.md`)의 §11 입력 요건 구현. 본 프롬프트는 **2개 변경
사이트**만 다룬다: (1) 신규 파일 `modules/ui_registry.py` 생성, (2) `modules/step6_dashboard.py`
2개 지점 수정 (import 추가 + 메인 함수 끝 직전 공존 섹션 추가).

기존 dashboard 섹션은 *삭제하지 않는다*. 새 dashboard가 페이지 *하단에 공존*하며, 사용자가
비교 검증 후 D7~D8에서 점진적으로 기존 섹션을 제거한다. 이게 곁가지 0건 보장에 가장
안전한 패턴이다.

`modules/engine.py`는 *변경하지 않는다*. state_dict 빌딩 훅은 D7~D8로 미루며, D5는
`build_mock_state_from_log()`로 로그 컬럼 기반 mock state를 사용해 시연한다.

---

## 변경 사이트 요약

| # | 파일 | 동작 | 라인 변화 |
|---|---|---|---|
| 1 | `modules/ui_registry.py` | **신규 생성** | 0 → 300 |
| 2A | `modules/step6_dashboard.py` (L20~L26) | import 영역에 4 import 추가 | +6 |
| 2B | `modules/step6_dashboard.py` (L1316~L1320) | 메인 함수 끝 직전에 공존 섹션 추가 | +22 |

`step6_dashboard.py` 합계: 1320 → **1348 lines** (산술 검증 통과). py_compile 통과,
변경 사이트 외 영역 byte-equality 확인 (곁가지 0건 입증).

---

## 1. 신규 파일: `modules/ui_registry.py`

다음 파일을 *전체 신규 생성*한다. MD5 = `89d6dddff3dc782fc0138f7886177545`.

```python
# -*- coding: utf-8 -*-
"""ui_registry.py — 가중치 기반 동적 상태 주도 UI 골격.

D4 설계안 §1~§11 구현. 4 톱니바퀴:
  1. State Emitter — engine.py가 sim_metrics['state_dict']로 방출 (D7~D8에서 통합)
  2. UI Registry  — 본 모듈의 UI_REGISTRY dict
  3. 가중치 패널  — render_weight_panel()
  4. Layout Manager — render_dynamic_dashboard()

D5 단계는 *데모용 mock state*도 함께 제공 (build_mock_state_from_log) — 실제 엔진 통합
전에도 로그별 UI 자동 가변 시연이 가능하다.

새 컴포넌트 추가: UI_REGISTRY에 한 줄 추가하면 메인 화면 코드 *무수정*. OCP 보장.
"""
import streamlit as st
import pandas as pd
from collections import defaultdict


# ─────────────────────────────────────────────────────────────────────
# 1. 렌더 함수 (각 컴포넌트별, 시그니처 (state_value, container, weight))
# ─────────────────────────────────────────────────────────────────────

def render_hp_bar(state_value, container, weight):
    """HP 막대. weight에 따라 표시 풍부도 조절."""
    if weight >= 7:
        container.markdown("### ❤️ HP")
    elif weight >= 4:
        container.markdown("#### HP")
    else:
        container.caption("HP")
    ally = state_value.get("ally_current", 0)
    ally_max = state_value.get("ally_max", 1)
    enemy = state_value.get("enemy_current", 0)
    enemy_max = state_value.get("enemy_max", 1)
    container.progress(ally / max(1, ally_max), text=f"Ally {ally}/{ally_max}")
    container.progress(enemy / max(1, enemy_max), text=f"Enemy {enemy}/{enemy_max}")


def render_type_chart(state_value, container, weight):
    """18타입 상성 시각화 (Pokemon 카테고리)."""
    if weight >= 7:
        container.markdown("### 🔥 타입 상성 차트")
    else:
        container.markdown("#### 타입 상성")
    types = state_value.get("types", [])
    if types:
        container.write(f"감지된 타입: {', '.join(types[:10])}")
    matrix = state_value.get("matrix")
    if matrix is not None and weight >= 5:
        container.dataframe(matrix, use_container_width=True)


def render_element_routing(state_value, container, weight):
    """Physical/Magic 데미지 라우팅 (FF7 카테고리)."""
    if weight >= 7:
        container.markdown("### ⚔️ Physical / Magic 라우팅")
    else:
        container.markdown("#### 데미지 라우팅")
    phys_count = state_value.get("physical_count", 0)
    magic_count = state_value.get("magic_count", 0)
    container.metric("Physical 공격 수", phys_count)
    container.metric("Magic 공격 수", magic_count)
    elements = state_value.get("elements_seen", [])
    if elements and weight >= 5:
        container.caption(f"감지된 속성: {', '.join(elements)}")


def render_card_trade(state_value, container, weight):
    """카드 데미지 교환 시각화 (Hearthstone 카테고리)."""
    if weight >= 7:
        container.markdown("### 🎴 카드 데미지 교환")
    else:
        container.markdown("#### 카드 교환")
    archetypes = state_value.get("archetypes", [])
    if archetypes:
        container.write(f"감지된 archetype: {', '.join(archetypes)}")
    avg_attack = state_value.get("avg_attack")
    minion_count = state_value.get("minion_count")
    if avg_attack is not None:
        container.metric("덱 평균 공격력", f"{avg_attack:.2f}")
    if minion_count is not None and weight >= 5:
        container.metric("덱 평균 미니언 수", minion_count)


# ─────────────────────────────────────────────────────────────────────
# 2. UI Registry — 8 필드 schema
# ─────────────────────────────────────────────────────────────────────

UI_REGISTRY = {
    "hp_bar": {
        "key": "hp_bar",
        "render_func": render_hp_bar,
        "component_type": "display",
        "is_fixed": False,
        "layout_hint": "row",
        "category": "core",
        "default_weight": 8,
        "min_log_columns": [],
    },
    "type_chart": {
        "key": "type_chart",
        "render_func": render_type_chart,
        "component_type": "display",
        "is_fixed": False,
        "layout_hint": "expander",
        "category": "pokemon",
        "default_weight": 6,
        "min_log_columns": ["Type1", "Type2"],
    },
    "element_routing": {
        "key": "element_routing",
        "render_func": render_element_routing,
        "component_type": "display",
        "is_fixed": False,
        "layout_hint": "column",
        "category": "ff7",
        "default_weight": 6,
        "min_log_columns": ["Element", "ResistElement", "AbsorbElement"],
    },
    "card_trade": {
        "key": "card_trade",
        "render_func": render_card_trade,
        "component_type": "display",
        "is_fixed": False,
        "layout_hint": "column",
        "category": "hearthstone",
        "default_weight": 6,
        "min_log_columns": ["DeckAvgAttack", "DeckMinionCount"],
    },
}


# ─────────────────────────────────────────────────────────────────────
# 3. 헬퍼 — 자동 감지 + 기본 가중치 + mock state 생성
# ─────────────────────────────────────────────────────────────────────

def detect_components(df_columns):
    """로그 컬럼명에서 활성 컴포넌트 key 목록 반환 (OR 조건)."""
    active = []
    cols_set = set(df_columns)
    for key, cfg in UI_REGISTRY.items():
        triggers = cfg["min_log_columns"]
        if not triggers:
            active.append(key)
        elif cols_set & set(triggers):
            active.append(key)
    return active


def get_default_weights(active_keys):
    """각 active 컴포넌트의 default_weight를 dict로 반환."""
    return {k: UI_REGISTRY[k]["default_weight"] for k in active_keys}


def build_mock_state_from_log(df):
    """로그 DataFrame으로부터 데모용 state_dict 생성.

    실제 엔진 통합(D7~D8) 전에 *로그별 UI 자동 가변*만 시연하기 위한 mock.
    detect_components의 컬럼명 트리거를 그대로 따라 활성 컴포넌트의 state만 채운다.
    """
    state = {
        "hp_bar": {
            "ally_current": 75, "ally_max": 100,
            "enemy_current": 60, "enemy_max": 100,
        },
    }
    cols = set(df.columns)
    if cols & {"Type1", "Type2"}:
        types = set()
        for c in ("Type1", "Type2"):
            if c in df.columns:
                types |= set(df[c].dropna().astype(str).unique())
        state["type_chart"] = {
            "types": sorted(t for t in types if t and t != "None")[:15],
            "matrix": None,
        }
    if cols & {"Element", "ResistElement", "AbsorbElement"}:
        elements = set()
        for c in ("Element", "ResistElement", "AbsorbElement"):
            if c in df.columns:
                elements |= set(df[c].dropna().astype(str).unique())
        state["element_routing"] = {
            "physical_count": int(len(df) // 3),
            "magic_count": int(len(df) // 2),
            "elements_seen": sorted(e for e in elements if e and e != "None")[:9],
        }
    if cols & {"DeckAvgAttack", "DeckMinionCount"}:
        archs = []
        if "Archetype" in df.columns:
            archs = sorted(set(df["Archetype"].dropna().astype(str).unique()))[:5]
        avg_atk = float(df["DeckAvgAttack"].mean()) if "DeckAvgAttack" in df.columns else 0.0
        mc = int(df["DeckMinionCount"].mean()) if "DeckMinionCount" in df.columns else 0
        state["card_trade"] = {
            "archetypes": archs,
            "avg_attack": avg_atk,
            "minion_count": mc,
        }
    return state


# ─────────────────────────────────────────────────────────────────────
# 4. 가중치 패널 (사이드바)
# ─────────────────────────────────────────────────────────────────────

def _apply_preset(name):
    """preset별 가중치 초기값을 session_state에 갱신."""
    presets = {
        "pokemon":     {"hp_bar": 8, "type_chart": 8, "element_routing": 0, "card_trade": 0},
        "ff7":         {"hp_bar": 8, "type_chart": 0, "element_routing": 8, "card_trade": 0},
        "hearthstone": {"hp_bar": 8, "type_chart": 0, "element_routing": 0, "card_trade": 8},
    }
    for k, v in presets.get(name, {}).items():
        st.session_state[f"weight_{k}"] = v


def render_weight_panel(active_keys):
    """사이드바에 가중치 슬라이더 N개 생성. 카테고리 그룹핑 + preset 버튼."""
    weights = {}
    by_cat = defaultdict(list)
    for k in active_keys:
        by_cat[UI_REGISTRY[k]["category"]].append(k)
    with st.sidebar:
        st.markdown("### 🎮 게임 preset")
        c1, c2, c3 = st.columns(3)
        if c1.button("Pokemon", key="preset_pokemon"):
            _apply_preset("pokemon")
        if c2.button("FF7", key="preset_ff7"):
            _apply_preset("ff7")
        if c3.button("HS", key="preset_hs"):
            _apply_preset("hearthstone")
        st.divider()
        st.markdown("### ⚖️ 컴포넌트 가중치")
        for cat in ["core", "pokemon", "ff7", "hearthstone", "common"]:
            if cat not in by_cat:
                continue
            st.markdown(f"**{cat}**")
            for k in by_cat[cat]:
                cfg = UI_REGISTRY[k]
                weights[k] = st.slider(
                    f"{k}",
                    min_value=0, max_value=10,
                    value=st.session_state.get(f"weight_{k}", cfg["default_weight"]),
                    key=f"weight_{k}",
                )
    return weights


# ─────────────────────────────────────────────────────────────────────
# 5. Dynamic Layout Manager
# ─────────────────────────────────────────────────────────────────────

def render_dynamic_dashboard(state_dict, weights, registry=None):
    """state_dict + weights → 화면 실시간 조립.

    핵심: 함수 본문 어디에도 컴포넌트 key 하드코딩 없음.
    Registry에 새 컴포넌트 추가 시 *본 함수 무수정*. OCP 보장.
    """
    if registry is None:
        registry = UI_REGISTRY
    active = []
    for k in state_dict.keys():
        if k not in registry:
            continue
        cfg = registry[k]
        if weights.get(k, 0) < 1 and not cfg["is_fixed"]:
            continue
        active.append(k)

    by_hint = defaultdict(list)
    for k in active:
        by_hint[registry[k]["layout_hint"]].append(k)

    # fixed (상단 고정)
    for k in by_hint.get("fixed", []):
        registry[k]["render_func"](state_dict[k], st, weights.get(k, 5))

    # column 그룹 — 가중치 비율로 너비 분배
    if by_hint["column"]:
        col_weights = [max(1, weights[k]) for k in by_hint["column"]]
        cols = st.columns(col_weights)
        for col, k in zip(cols, by_hint["column"]):
            with col:
                registry[k]["render_func"](state_dict[k], col, weights[k])

    # row 그룹 — 세로 쌓기 (가중치 큰 순서)
    for k in sorted(by_hint["row"], key=lambda x: -weights[x]):
        registry[k]["render_func"](state_dict[k], st, weights[k])

    # tab 그룹
    if by_hint["tab"]:
        tabs = st.tabs([k for k in by_hint["tab"]])
        for tab, k in zip(tabs, by_hint["tab"]):
            with tab:
                registry[k]["render_func"](state_dict[k], tab, weights[k])

    # expander 그룹 — 가중치 7+ 면 펼친 상태
    for k in by_hint["expander"]:
        with st.expander(f"{k}", expanded=(weights[k] >= 7)):
            registry[k]["render_func"](state_dict[k], st, weights[k])
```

---

## 2A. `modules/step6_dashboard.py` — import 영역 (L20~L26)

다음 7줄을 13줄로 치환한다 (delta +6). find 문자열은 step6에서 *정확히 1번* 나타난다
(검증 완료, L20에서 시작).

### Find (MD5 `fdb973addd07967a007309a863082011`)

```python
from modules.win_condition import ResourceDepletion

from modules.engine import run_simulation, run_monte_carlo, default_stochasticity_factory, DEFAULT_COMBAT_FLOW
from modules.optimizer import optimize_allocation
from modules.spatial import SpatialModule
from modules.deck import DeckModule
from modules.detection import module_active
```

### Replace (MD5 `45ca14ea87f70a526c03cef557b2de67`)

```python
from modules.win_condition import ResourceDepletion

from modules.engine import run_simulation, run_monte_carlo, default_stochasticity_factory, DEFAULT_COMBAT_FLOW
from modules.optimizer import optimize_allocation
from modules.spatial import SpatialModule
from modules.deck import DeckModule
from modules.detection import module_active
# ── D5 추가: 가중치 기반 동적 Dashboard (D4 설계안 §11) ──
from modules.ui_registry import (
    render_dynamic_dashboard,
    render_weight_panel,
    build_mock_state_from_log,
)
```

---

## 2B. `modules/step6_dashboard.py` — 메인 함수 끝 직전 (L1316~L1320)

다음 5줄을 27줄로 치환한다 (delta +22). find 문자열은 step6에서 *정확히 1번* 나타난다
(검증 완료, L1316에서 시작). 주의: L1319의 **16-space trailing whitespace를 정확히
보존**할 것 — replace 블록도 같은 위치에 같은 16 spaces를 유지한다.

### Find (MD5 `e1a009bfdf4801fd5fedf94f24c44806`)

```python
            if st.button("Save to Global Library", type="primary"):
                st.session_state.setdefault('character_library', {})[char_name] = {"stats": {s: st.session_state.get(f'builder_stat_input_{s}', 100.0) for s in sys_stats}, "gimmicks": {g: st.session_state.get(f'builder_gimmick_{g}', "None") for g in sys_gimmicks}}
                st.success(f"✅ '{char_name}' 저장 완료!")
                
    return True, ""
```

### Replace (MD5 `f41e4367366fa6d632b3866c672da0da`)

```python
            if st.button("Save to Global Library", type="primary"):
                st.session_state.setdefault('character_library', {})[char_name] = {"stats": {s: st.session_state.get(f'builder_stat_input_{s}', 100.0) for s in sys_stats}, "gimmicks": {g: st.session_state.get(f'builder_gimmick_{g}', "None") for g in sys_gimmicks}}
                st.success(f"✅ '{char_name}' 저장 완료!")
                

    # ── D5 Phase A: Weight-Driven Dynamic Dashboard (D4 설계안 §8) ──
    # 기존 dashboard 섹션과 *공존*. 사용자가 로그 업로드 시 자동 감지로 컴포넌트 가변.
    # 사이드바 가중치 슬라이더로 미세조정. 데이터 기반 시연용 (실제 시뮬 통합은 D7~D8).
    try:
        st.divider()
        st.markdown("## 🎛️ 가중치 기반 동적 Dashboard (D5 신규)")
        st.caption(
            "로그의 컬럼 구성에 따라 컴포넌트가 자동으로 활성/비활성됩니다. "
            "사이드바의 게임 preset 버튼과 컴포넌트 가중치 슬라이더로 화면을 미세조정하세요."
        )
        _df_for_dashboard = st.session_state.get('df')
        if _df_for_dashboard is not None and len(_df_for_dashboard) > 0:
            _state_dict = build_mock_state_from_log(_df_for_dashboard)
            _active = list(_state_dict.keys())
            _weights = render_weight_panel(_active)
            render_dynamic_dashboard(_state_dict, _weights)
        else:
            st.info("Step 1에서 로그를 업로드하면 가변 dashboard가 활성화됩니다.")
    except Exception as _wddash_err:
        st.warning(f"신규 dashboard 오류 (기존 화면에는 영향 없음): {_wddash_err}")

    return True, ""
```

---

## 3. 검증 절차 (Antigravity 납품 후 사용자가 실행)

납품된 변경에 대해 다음을 **순서대로** 실행한다. 한 단계라도 실패하면 즉시 보고.

### 3-1. 파일 존재 확인

```bash
ls -la modules/ui_registry.py modules/step6_dashboard.py
```

`ui_registry.py`가 ~300줄, `step6_dashboard.py`가 정확히 **1348줄**이어야 한다.

### 3-2. 라인 수 산술 검증

```bash
wc -l modules/step6_dashboard.py
```

`1348 modules/step6_dashboard.py`가 출력되어야 한다. 산술: 원본 1320 + Change A (+6) + Change B (+22) = 1348.

### 3-3. 신규 마커 Grep (포지티브)

```bash
grep -n "from modules.ui_registry import" modules/step6_dashboard.py
grep -n "D5 Phase A: Weight-Driven Dynamic Dashboard" modules/step6_dashboard.py
grep -n "render_dynamic_dashboard" modules/step6_dashboard.py
grep -n "build_mock_state_from_log" modules/step6_dashboard.py
```

위 4개 grep이 모두 **각각 1회 이상** 매치되어야 한다.

### 3-4. 옛 마커 부재 확인 (네거티브 — 곁가지 0건 보증)

```bash
grep -c "render_dashboard()" modules/step6_dashboard.py
```

정확히 **1회**여야 한다 (기존 L124의 `def render_dashboard():` 정의 한 곳). 새 import는
`render_dynamic_dashboard`라는 다른 이름을 쓰므로 충돌 없음.

### 3-5. py_compile

```bash
python3 -m py_compile modules/ui_registry.py
python3 -m py_compile modules/step6_dashboard.py
```

둘 다 exit 0이어야 한다.

### 3-6. UI_REGISTRY 8 필드 정합성 (단위 테스트)

```bash
python3 -c "
import sys
class _Stub:
    def __getattr__(self, n): return lambda *a, **k: None
    session_state = {}
sys.modules['streamlit'] = _Stub()
from modules.ui_registry import UI_REGISTRY, detect_components, build_mock_state_from_log
required = {'key','render_func','component_type','is_fixed','layout_hint','category','default_weight','min_log_columns'}
for k, cfg in UI_REGISTRY.items():
    assert set(cfg.keys()) == required, f'{k} schema mismatch: {set(cfg.keys()) ^ required}'
print('UI_REGISTRY schema OK:', list(UI_REGISTRY.keys()))
# 자동 감지 검증
assert sorted(detect_components(['Type1','Type2','HP'])) == ['hp_bar','type_chart']
assert sorted(detect_components(['Element','ResistElement'])) == ['element_routing','hp_bar']
assert sorted(detect_components(['DeckAvgAttack','DeckMinionCount'])) == ['card_trade','hp_bar']
print('detect_components OK')
"
```

### 3-7. Streamlit 라이브 실행

```bash
streamlit run main.py
```

세 검증 시나리오:

| 입력 로그 | 사이드바 활성 슬라이더 | 메인 화면 하단 컴포넌트 |
|---|---|---|
| `pkmn_battle_log.csv` | hp_bar, type_chart | HP + 타입 상성 차트 (expander) |
| `ff7_battle_log.csv` | hp_bar, element_routing | HP + Physical/Magic 라우팅 (column) |
| `hs_battle_log.csv` | hp_bar, card_trade | HP + 카드 데미지 교환 (column) |

각 로그에서 *코드 수정 없이* 컴포넌트가 자동 가변해야 한다. 사이드바 슬라이더로 가중치를
0으로 내리면 해당 컴포넌트가 즉시 사라져야 한다. 게임 preset 버튼 클릭 시 슬라이더 값이
preset 분포로 갱신되어야 한다.

---

## 4. 곁가지 0건 보장 (검증 완료)

본 프롬프트 작성 시 다음을 *클린룸 하니스에서 사전 검증*했다:

- **라인 수 산술**: original 1320 + (+6) + (+22) = 1348. 실제 적용 결과 1348. 정확 일치.
- **py_compile**: 변경 적용된 step6의 문법 검증 통과.
- **byte-equality**: original에서 두 find string을 제거한 잔여 영역이 modified에서 두 replace
  string을 제거한 잔여 영역과 *정확히 동등*. 변경 사이트 외 어디에도 수정 없음.
- **find string uniqueness**: 두 find string 모두 step6에서 정확히 1회 나타남.

Antigravity가 곁가지 수정을 일으키면 위 세 검증 중 하나가 반드시 실패한다.

---

## 5. trajectory 정합성

본 변경은 D4 설계안 §10의 X1~X8 호환성을 그대로 유지한다:

- **X1 (5축 형식화)** — 새 메커니즘이 추가될 때 그 메커니즘의 state key를 `UI_REGISTRY`에
  한 줄 추가하면 화면에 자동 등장. 본 D5에서 그 인프라가 들어간다.
- **X3 (표준 메커니즘 라이브러리)** — poison·burn·sleep 등이 각자 자기 render_func + registry
  항목을 추가하는 패턴이 본 PR에 박혀 있다.
- **X6 (카드/덱 엔진)** — 본 D5에 `card_trade` 컴포넌트가 등록됨. X6 본격 진행 시
  `mana_curve`, `hand_size` 등이 같은 방식으로 추가된다.
- **X8 (Python plugin escape hatch)** — 외부 plugin이 `UI_REGISTRY[key] = {...}`로 자가
  등록할 수 있도록 dict 구조 그대로 노출.

---

## 6. 사후 정리 (D7~D8 작업 — 본 PR 범위 외)

데드라인 후 또는 D7~D8에서 다음을 별도 PR로:

1. `engine.py`의 `run_simulation()` 반환의 `sim_metrics`에 *진짜* state_dict 빌딩.
   `build_mock_state_from_log()`는 제거 또는 fallback으로 유지.
2. step6의 기존 시뮬·최적화·backtest·인사이트 4 섹션을 `render_dynamic_dashboard` 호출로
   대체. 본 PR에서 *공존*시킨 새 dashboard가 그 자리로 이동.

이 분리가 *기능 추가와 구조 변경을 별도 PR로* 만들어 안전한 점진 마이그레이션을 보장한다.

---

*프롬프트 작성 환경: 빌더 스크립트가 하니스 파일에서 코드 블록을 자동 추출. MD5
라운드트립으로 전사 오류 0건 입증.*
