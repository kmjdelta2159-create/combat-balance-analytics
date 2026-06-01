# 가중치 기반 동적 상태 주도 UI 설계안 (Weight-Driven Dynamic State UI)

D4 산출물. D5(5/31)의 Antigravity 프롬프트 작성을 위한 입력 자료. 본 문서는 4 톱니바퀴
아키텍처의 인터페이스 경계와 데이터 흐름을 *Antigravity가 코드를 만들 수 있는 수준*까지
명세한다. 핸드오프 §2-2에서 합의된 아키텍처의 정밀 명세 버전이다.

---

## 0. 한 줄 요약

엔진은 UI 구조를 모른다. UI는 *엔진 State*와 *사용자 가중치*로부터 매 프레임 재구성된다.
게임마다 다른 UI가 *코드 수정 없이 자동 생성*되는 것이 핵심. 슬라이더 원리(연속 정밀도)의
UI 차원 1:1 매핑이다.

---

## 1. 왜 이 아키텍처인가

현재 `step6_dashboard.py`는 1321줄의 `if/elif` 하드코딩 vine이다. 새 게임 지원 시 메인
화면 코드를 직접 수정해야 하고, 컴포넌트 간 우선순위와 화면 비율이 코드에 박혀 있다.
OCP(개방-폐쇄 원칙) 위반이고, X1~X9 trajectory의 어느 단계도 *메인 코드 수정 없이는*
컴포넌트를 추가할 수 없다.

본 아키텍처가 풀려는 두 문제는 *개방-폐쇄 보장*과 *로그 자동 적응*이다. 새 컴포넌트는
registry에 한 줄만 추가하고, 로그의 컬럼 구성에 따라 자동으로 활성/비활성된다. 사용자
가중치가 그 위에서 미세조정을 담당한다. 자동 감지(역설계 측면)와 사용자 가중치(개입 측면)가
함께 작동해서 *게임마다 다른 UI가 자동으로 생성*된다.

---

## 2. 4 톱니바퀴 아키텍처 개요

```
┌──────────────────────────────────────────────────────────────────┐
│  [1] 엔진 State Emitter         [3] 사용자 가중치 패널           │
│  modules/engine.py              사이드바 슬라이더                 │
│       │                                │                          │
│       ▼                                ▼                          │
│  state_dict = {                  weights = {                      │
│    "hp_bar": ...,                  "hp_bar": 8,                   │
│    "type_chart": ...,              "type_chart": 5,               │
│    "card_trade": ...,              "card_trade": 0,               │
│    ...                             ...                            │
│  }                               }                                │
│       │                                │                          │
│       └────────────┬───────────────────┘                          │
│                    ▼                                              │
│  [4] Dynamic Layout Manager                                       │
│  state_dict + weights + registry → 화면                           │
│                    │                                              │
│                    ▼                                              │
│  [2] UI Registry (참조)                                           │
│  modules/ui_registry.py                                           │
│  {key → render_func, schema, layout_hint, ...}                    │
└──────────────────────────────────────────────────────────────────┘
```

엔진은 자기 결과를 *unstructured dict*로 방출하기만 한다. Registry가 각 key의 렌더링
방법을 알고, Layout Manager가 가중치를 곱해서 화면을 즉석 조립한다. *어느 컴포넌트도
다른 컴포넌트를 모른다* — 모든 결합은 dict key를 통한 약결합.

---

## 3. State Emitter 명세 (톱니 1)

### 3-1. 엔진 인터페이스 변경

현재 `run_simulation()`은 `(winner, logs, sim_metrics)` 3-튜플 반환. 본 아키텍처는
*기존 호환을 유지*하며 `sim_metrics` 안에 `state_dict` 키를 추가한다:

```python
sim_metrics = {
    # ... 기존 키 ...
    "state_dict": {
        "hp_bar":     {"ally_hp_series": [...], "enemy_hp_series": [...]},
        "log_text":   ["턴 1: Ally가 Slash 사용...", ...],
        "move_usage": {"Slash": 12, "Fire2": 5, ...},
        # 활성 플러그인이 자기 키만 추가
        "mp_bar":     {...},   # resource_module 활성 시
        "deck_state": {...},   # deck_module 활성 시
        ...
    }
}
```

이렇게 하면 기존 호출처(`winner, logs, sim_metrics = run_simulation(...)`)는 무수정
유지된다.

### 3-2. State key 네이밍 규약

key는 *snake_case 명사*다. 데이터 타입은 dict 또는 list. 값의 *내부 스키마는 render_func
가 정의*한다 — 엔진은 그 스키마를 모른다(약결합).

### 3-3. 활성 플러그인의 self-emission

각 플러그인(resource_module, deck_module, spatial_module 등)은 *자기 State key만*
state_dict에 추가한다. 비활성 플러그인의 key는 *키 자체가 없음*. registry의 자동 감지
(§5)가 key 존재 여부로 컴포넌트를 활성한다.

### 3-4. 핵심 State key 목록 (초기 등록 대상)

| key | 데이터 | 활성 조건 | 카테고리 |
|---|---|---|---|
| `hp_bar` | 양 진영 HP 시계열 | 항상 | core |
| `log_text` | 인간 가독 전투 로그 | 항상 | core |
| `winner` | "Ally" / "Enemy" / "Draw" | 항상 | core |
| `move_usage` | 무브별 사용 빈도 | move 시스템 활성 | core |
| `type_chart` | 타입 상성 시각화 데이터 | 18타입 인식 시 | pokemon |
| `element_routing` | Physical/Magic 데미지 라우팅 | Element 컬럼 인식 시 | ff7 |
| `card_trade` | 카드 트레이드 누적 시각화 | DeckAvg* 컬럼 인식 시 | hearthstone |
| `optimization_result` | 진화 전략 산출물 | 최적화 실행 후 | core |
| `backtest_result` | Per-Battle Backtest 결과 | 백테스트 실행 후 | core |
| `insights` | 자동 인사이트 텍스트 | 항상 | core |

---

## 4. UI Registry 명세 (톱니 2)

### 4-1. 파일 위치

`modules/ui_registry.py` 신규 생성. 단일 모듈에 `UI_REGISTRY` dict 상수와 헬퍼 함수
(`detect_components`, `get_default_weights`)를 둔다.

### 4-2. Registry schema — 8 필드 정확 명세

각 컴포넌트 등록 항목은 다음 8 필드의 dict:

```python
{
    "key": "hp_bar",                       # State Emitter dict key와 1:1
    "render_func": render_hp_bar,          # callable
    "component_type": "display",           # "display" | "form" | "fixed"
    "is_fixed": False,                     # bool
    "layout_hint": "row",                  # "column" | "row" | "tab" | "expander" | "modal"
    "category": "core",                    # "core" | "pokemon" | "ff7" | "hearthstone" | "common"
    "default_weight": 8,                   # int 0~10
    "min_log_columns": [],                 # list[str], 자동 감지 조건
}
```

#### 4-2-1. `key` (str)

State Emitter가 방출하는 `state_dict`의 key와 *문자열 일치*. 매칭 실패면 컴포넌트가
활성되지 않는다 (오타 방지를 위해 부팅 시 cross-check 권장).

#### 4-2-2. `render_func` (callable)

시그니처: `(state_value, container, weight) -> None`
- `state_value`: `state_dict[key]`의 값. 타입은 함수가 정의
- `container`: Streamlit 컨테이너 (`st`, `col`, `tab` 중 하나)
- `weight`: int 0~10. 함수가 *가중치에 따라 표시 풍부도를 조절*할 수 있음 (예: 가중치
  높으면 큰 차트, 낮으면 sparkline)

#### 4-2-3. `component_type` (str)

- `"display"`: 데이터를 보여주는 일반 컴포넌트 (대부분)
- `"form"`: 사용자 입력 폼 (preset 선택, 가중치 슬라이더 등). 가중치 0이어도 *입력은
  필요할 수 있음* — `is_fixed`와 조합해서 결정
- `"fixed"`: 항상 화면 위/아래에 고정 (네비게이션 바, 상태 표시줄 등)

#### 4-2-4. `is_fixed` (bool)

True면 가중치 0이어도 표시. 네비게이션이나 *반드시 보여야 할* 상태 표시(예: 시뮬레이션
실행 버튼)에 사용. False(기본)면 가중치 0일 때 화면에서 완전히 사라짐.

#### 4-2-5. `layout_hint` (str)

Layout Manager가 컴포넌트를 어떤 *방식*으로 배치할지 힌트:
- `"column"`: 가로 분할의 한 컬럼. 같은 hint를 가진 컴포넌트들이 *가중치 비율로 너비
  분배*되어 `st.columns([w1, w2, ...])` 생성
- `"row"`: 세로 쌓기 (전체 너비)
- `"tab"`: 같은 hint를 가진 컴포넌트들을 `st.tabs()`로 묶음
- `"expander"`: `st.expander()` 접이식
- `"modal"`: 모달 다이얼로그 (Streamlit 1.30+ `@st.dialog`)

#### 4-2-6. `category` (str)

게임/도메인 분류. preset 적용과 가중치 패널의 그룹 표시에 사용. 정해진 값:
- `"core"`: 모든 게임 공통 (HP, 로그, 시뮬 결과 등)
- `"pokemon"`, `"ff7"`, `"hearthstone"`: 게임별
- `"common"`: 여러 게임에서 *유사 형태*로 쓰이는 컴포넌트 (예: 무브 사용 빈도는
  Pokemon/FF7 공통)

#### 4-2-7. `default_weight` (int)

부팅 시 사이드바 슬라이더의 초기값. 0~10 정수. core 컴포넌트는 보통 7~8, 게임별
컴포넌트는 5~6, expander 안에 들어갈 보조 정보는 3~4.

#### 4-2-8. `min_log_columns` (list[str])

*자동 감지 조건*. 업로드된 로그의 컬럼명 중 *이 목록 중 하나라도 존재*하면 컴포넌트가
활성된다. 빈 리스트면 *항상 활성* (core 컴포넌트). OR 조건이며 AND가 필요하면 별도
key로 등록.

예시:
- `type_chart` → `["Type1", "Type2"]` (Pokemon 로그)
- `element_routing` → `["Element", "ResistElement", "AbsorbElement"]` (FF7 로그)
- `card_trade` → `["DeckAvgAttack", "DeckMinionCount"]` (Hearthstone 로그)

### 4-3. Registry 예시 (초기 4개)

```python
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
```

---

## 5. 자동 감지 휴리스틱 (Registry 헬퍼)

```python
def detect_components(df_columns: list[str]) -> list[str]:
    """업로드된 로그 컬럼명에서 활성 컴포넌트 key 목록 반환."""
    active = []
    cols_set = set(df_columns)
    for key, cfg in UI_REGISTRY.items():
        triggers = cfg["min_log_columns"]
        if not triggers:
            active.append(key)  # 항상 활성
        elif cols_set & set(triggers):
            active.append(key)  # OR 조건 매치
    return active
```

핵심: 컬럼명 매칭은 *대소문자 구분*. Phase 8d 채널 매핑이 이미 한국어/영어 컬럼명을
정규화하는 단계를 제공하므로, Registry는 정규화 *후* 컬럼명을 받는다고 가정한다 — 즉
Phase 8d와의 호환을 유지한다.

부가 헬퍼:

```python
def get_default_weights(active_keys: list[str]) -> dict[str, int]:
    return {k: UI_REGISTRY[k]["default_weight"] for k in active_keys}
```

---

## 6. 사용자 가중치 패널 명세 (톱니 3)

Streamlit 사이드바에 슬라이더 N개 자동 생성. 활성 컴포넌트마다 한 슬라이더. 카테고리별로
그룹핑.

```python
def render_weight_panel(active_keys: list[str]) -> dict[str, int]:
    weights = {}
    # 카테고리별 그룹 표시
    by_cat = defaultdict(list)
    for k in active_keys:
        by_cat[UI_REGISTRY[k]["category"]].append(k)

    with st.sidebar:
        # preset 버튼
        st.markdown("### 게임 preset")
        col1, col2, col3 = st.columns(3)
        if col1.button("Pokemon"): apply_preset("pokemon")
        if col2.button("FF7"):     apply_preset("ff7")
        if col3.button("HS"):      apply_preset("hearthstone")
        st.divider()
        # 가중치 슬라이더
        for cat in ["core", "pokemon", "ff7", "hearthstone", "common"]:
            if cat not in by_cat: continue
            st.markdown(f"#### {cat}")
            for k in by_cat[cat]:
                cfg = UI_REGISTRY[k]
                weights[k] = st.slider(
                    f"{k} 비중",
                    min_value=0, max_value=10,
                    value=st.session_state.get(f"weight_{k}", cfg["default_weight"]),
                    key=f"weight_{k}",
                )
    return weights
```

### 6-1. 게임별 preset

`apply_preset()`은 `st.session_state[f"weight_{k}"]`를 갱신해서 슬라이더 초기값을 변경:

- **Pokemon**: hp_bar 8, type_chart 8, move_usage 7, log_text 5, element_routing 0, card_trade 0, ...
- **FF7**: hp_bar 8, element_routing 8, move_usage 7, log_text 5, type_chart 0, card_trade 0, mp_bar 6, ...
- **Hearthstone**: hp_bar 8, card_trade 8, mana_curve 7, log_text 5, type_chart 0, element_routing 0, ...

preset은 *현재 활성 컴포넌트만* 영향. 활성되지 않은 컴포넌트의 가중치 설정은 무의미.

---

## 7. Dynamic Layout Manager 의사코드 (톱니 4)

```python
from collections import defaultdict

def render_dashboard(state_dict, weights, registry=UI_REGISTRY):
    # 1. 활성 컴포넌트 필터 — state에 있고, registry에 있고, weight>=1 또는 is_fixed
    active = []
    for k in state_dict.keys():
        if k not in registry: continue
        cfg = registry[k]
        if weights.get(k, 0) < 1 and not cfg["is_fixed"]: continue
        active.append(k)

    # 2. layout_hint별로 그룹
    by_hint = defaultdict(list)
    for k in active:
        by_hint[registry[k]["layout_hint"]].append(k)

    # 3. fixed (상단 고정)
    for k in by_hint.get("fixed", []):
        registry[k]["render_func"](state_dict[k], st, weights.get(k, 5))

    # 4. column 그룹 — 가중치 비율로 너비 분배
    if by_hint["column"]:
        col_weights = [max(1, weights[k]) for k in by_hint["column"]]
        cols = st.columns(col_weights)
        for col, k in zip(cols, by_hint["column"]):
            with col:
                registry[k]["render_func"](state_dict[k], col, weights[k])

    # 5. row 그룹 — 세로 쌓기 (가중치 큰 순서로)
    for k in sorted(by_hint["row"], key=lambda x: -weights[x]):
        registry[k]["render_func"](state_dict[k], st, weights[k])

    # 6. tab 그룹
    if by_hint["tab"]:
        tabs = st.tabs([k for k in by_hint["tab"]])
        for tab, k in zip(tabs, by_hint["tab"]):
            with tab:
                registry[k]["render_func"](state_dict[k], tab, weights[k])

    # 7. expander 그룹 — 가중치 높은 것은 펼친 상태로 시작
    for k in by_hint["expander"]:
        with st.expander(f"{k}", expanded=(weights[k] >= 7)):
            registry[k]["render_func"](state_dict[k], st, weights[k])
```

핵심 속성: 함수 본문 어디에도 *컴포넌트 key 하드코딩*이 없다. Registry에 새 컴포넌트를
추가하면 본 함수 *수정 없이* 화면에 나타난다. OCP 보장.

---

## 8. 마이그레이션 경로 — step6_dashboard.py 부분 refactor

step6의 1321줄을 한 번에 갈아엎지 않는다. *부분 추출* 전략:

### Phase A (D5, 5/31 작성 — D7, 6/1 납품)

다음 4 섹션을 registry로 추출:
1. 시뮬레이션 결과 (state_dict["sim_result"])
2. 최적화 결과 (state_dict["optimization_result"])
3. Per-Battle Backtest (state_dict["backtest_result"])
4. 자동 인사이트 (state_dict["insights"])

step6의 해당 4 섹션 코드를 삭제하고 `render_dashboard(state_dict, weights)` 한 줄로
대체. 나머지 if/elif vine은 *그대로 둠* — 점진적 이관.

### Phase B (D7, 6/2)

게임별 컴포넌트 등록:
- `type_chart` (Pokemon 활성 시)
- `element_routing` (FF7 활성 시)
- `card_trade` (Hearthstone 활성 시)

### Phase C (데드라인 이후)

나머지 if/elif vine을 점진적으로 registry로 이관. 데모 데드라인엔 Phase A·B만 필수.

---

## 9. 검증 시나리오

### 9-1. 자동 감지 검증

3개 로그를 차례로 업로드하면서 활성 컴포넌트 변화 확인:

| 입력 로그 | 활성 컴포넌트 (게임별 카테고리만) |
|---|---|
| `pkmn_battle_log.csv` | `type_chart` 활성, `element_routing` 비활성, `card_trade` 비활성 |
| `ff7_battle_log.csv` | `element_routing` 활성, `type_chart` 비활성, `card_trade` 비활성 |
| `hs_battle_log.csv` | `card_trade` 활성, `type_chart` 비활성, `element_routing` 비활성 |

core 카테고리(hp_bar, log_text, insights 등)는 세 경우 모두 활성.

### 9-2. 가중치 슬라이더 응답 검증

사용자가 사이드바의 `type_chart` 가중치를 8→0으로 내리면 그 컴포넌트가 *즉시 화면에서
사라져야 한다*. 8→3으로 내리면 더 작은 영역에 sparkline 형태로 축소되어 표시(`weight`를
받는 render_func의 자체 로직).

### 9-3. preset 검증

"Pokemon" preset 클릭 → 모든 슬라이더가 Pokemon 분포로 즉시 갱신. "FF7" → FF7 분포로
갱신. "HS" → Hearthstone 분포로 갱신. preset이 적용된 후에도 *수동 슬라이더 조정 가능*
(preset은 단순히 초기값 갱신).

### 9-4. OCP 회귀 보호

데모 후 새 컴포넌트(예: 가챠 게임의 `summon_rate`)를 registry에 한 줄만 추가. 메인 화면
코드(`step6_dashboard.py`, `render_dashboard`)를 *전혀 수정하지 않고* 화면에 새 컴포넌트가
나타나는지 확인. 이 회귀 테스트가 OCP 보장의 증명이다.

---

## 10. trajectory와의 정합성

본 아키텍처는 X1~X9 trajectory와 완전 호환:

- **X1 (5축 형식화)**: 새 메커니즘이 추가되면 그 메커니즘의 State key가 자동으로
  state_dict에 들어오고, registry에 한 줄 추가로 컴포넌트가 화면에 등장. 메인 코드 무수정.
- **X3 (표준 메커니즘 라이브러리)**: 각 표준 메커니즘(poison, burn, sleep 등)이 자기
  State key + render_func을 *자체 등록*. plugin 패턴의 정확한 적용처.
- **X6 (카드/덱 엔진)**: 카드 게임 본격 지원 시 `card_state`, `mana_curve`, `hand_size`
  등 새 State key가 추가되고 Registry에 등록. step6 메인 코드 수정 없음.
- **X8 (Python plugin escape hatch)**: 외부 plugin이 부팅 시 자기 컴포넌트를 registry에
  자가 등록(`UI_REGISTRY[key] = {...}`). 도구 코어를 깨지 않고 임의 확장 가능.

본 아키텍처가 *trajectory의 모든 후속 작업을 메인 코드 수정 없이 흡수*하는 것이 가장 큰
이득이다.

---

## 11. D5 Antigravity 프롬프트 입력 요건

D5에 작성할 Antigravity 프롬프트는 다음 변경을 정확한 find/replace 블록으로 명세:

1. **신규 파일** `modules/ui_registry.py`
   - UI_REGISTRY dict (초기 4 컴포넌트: hp_bar, type_chart, element_routing, card_trade)
   - `detect_components()` 헬퍼
   - `get_default_weights()` 헬퍼
   - `render_dashboard()` 함수 (Layout Manager)
   - `render_weight_panel()` 함수 (사이드바)
   - render_func 4개 (각 컴포넌트별)

2. **`modules/engine.py` 수정**
   - `run_simulation()` 반환의 `sim_metrics`에 `state_dict` 키 추가
   - 기존 호출처 영향 없음 (sim_metrics는 이미 dict)
   - state_dict 핵심 키 5개 populate (hp_bar, log_text, winner, move_usage, sim_result)

3. **`modules/step6_dashboard.py` 부분 refactor**
   - 시뮬·최적화·backtest·인사이트 4 섹션 삭제
   - 그 자리에 `from modules.ui_registry import render_dashboard, render_weight_panel`
     import 추가
   - 사이드바에 `weights = render_weight_panel(active)` 호출 추가
   - 메인 화면에 `render_dashboard(state_dict, weights)` 한 줄로 4 섹션 대체

4. **`main.py` 또는 `app_backup.py`에 preset 버튼 핸들러** (optional)

각 변경 사이트는 D5 작성 단계에서 Grep으로 정확히 식별. 마커 일관 사용. 라인 수 산술로
곁가지 수정 0건 보장. 검증 워크플로(Phase 8d 패턴)를 그대로 따른다.

---

## 12. 위험 요소와 완화

| 위험 | 완화 |
|---|---|
| state_dict이 너무 커져서 메모리 부담 | 컴포넌트별 *lazy 생성* — render_func 호출 시점에만 계산 |
| 컴포넌트 간 의존성 (HP 변화가 로그에도 표시되어야 등) | *데이터 중복* 허용. 약결합 우선 |
| 가중치 0/1 토글의 UX 혼란 | 가중치 0 → 완전 삭제, 1~3 → sparkline, 4~7 → 일반, 8~10 → 풀 차트로 단계화 |
| Registry의 key 오타 (state_dict key와 불일치) | 부팅 시 cross-check: state_dict.keys() ∩ registry.keys() 출력 |
| 카테고리 preset이 비활성 컴포넌트에 영향 | preset은 *활성 컴포넌트만* 갱신. 비활성은 무시 |

---

## 13. 데모 narrative 함의

본 아키텍처가 데모에 주는 *시연 포인트*:

같은 도구에 Pokemon 로그를 올리면 type_chart가 출현하고, FF7 로그를 올리면
element_routing이 출현하며, Hearthstone 로그를 올리면 card_trade가 출현한다. *코드는 한
줄도 안 바뀌었는데* UI가 게임별로 자동 가변한다. 그 위에서 사용자가 사이드바 슬라이더로
가중치를 조절하면 화면 비율이 즉시 변한다. type_chart 가중치 0이면 Pokemon 로그에서도
그 컴포넌트가 사라진다.

이게 핸드오프 §1의 *슬라이더 원리*가 UI 차원에서 1:1 매핑된 결과다. 자동 감지(역설계
측면)와 사용자 가중치(개입 측면)가 *연속체*로 작동한다. 카테고리 점프 없음.

---

*본 설계 문서는 검증 자산(샌드박스 산출물)이며 프로젝트 코드가 아님. D5에 Antigravity
프롬프트의 입력 자료로 사용됨.*
