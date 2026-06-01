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
    """메인 화면 expander에 가중치 슬라이더 N개 생성. 카테고리 그룹핑만.

    D5-hotfix2: preset 버튼 제거. 게임 이름 하드코딩(Pokemon/FF7/HS)이 슬라이더 원리의
    *연속체* 본질에 어긋나고(카테고리 점프), 자동 감지가 이미 게임별 컴포넌트를 정확히
    활성하므로 preset은 redundant. dead _apply_preset 함수는 데드라인 후 별도 정리.
    """
    weights = {}
    by_cat = defaultdict(list)
    for k in active_keys:
        by_cat[UI_REGISTRY[k]["category"]].append(k)
    with st.expander("⚖️ Dashboard 컴포넌트 가중치", expanded=True):
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
