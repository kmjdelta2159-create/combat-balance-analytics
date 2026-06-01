# Antigravity 프롬프트 — D5-hotfix: 가중치 패널 위치 이동

D5 납품 후 사용자 시연 시 발견된 *디자인 충돌* 해결. `main.py` L42의 `[data-testid="stHeader"] { display: none !important; }` CSS가 Streamlit 사이드바 토글 버튼까지 함께 숨겨서, 사용자가 *사이드바를 열 방법이 없는 상태*. 동시에 main.py L92의 `st.info("💡 사이드바는 상태 확인 전용입니다...")` 가 명시하듯 *기존 사이드바 정책은 Status Board 전용*. D5에서 가중치 슬라이더를 사이드바에 넣은 게 이 정책과 충돌.

해결: `modules/ui_registry.py`의 `render_weight_panel()` 함수의 컨테이너만 `st.sidebar` → 메인 화면 `st.expander`로 변경. main.py와 step6_dashboard.py는 *손대지 않음*. 기존 사이드바 정책 유지.

---

## 변경 사이트 요약

| # | 파일 | 동작 | 라인 변화 |
|---|---|---|---|
| 1 | `modules/ui_registry.py` (L217 함수 정의) | `with st.sidebar:` → `with st.expander(...)` + docstring 갱신 | +4 |

`ui_registry.py` 합계: 300 → **304 lines** (산술 검증 통과). py_compile 통과, 변경 사이트 외 byte-equality 확인.

DOM 진단 증거: 사이드바는 `<section data-testid="stSidebar" aria-expanded="false" style="width: 299px">` 상태로 DOM에 존재하지만, stHeader 숨김 때문에 펼침 토글이 없음. 따라서 사이드바 자체가 *접근 불가*. 본 hotfix는 가중치 패널을 메인 화면 expander로 옮겨 사용자가 자유롭게 접고 펼 수 있게 함.

---

## 1. `modules/ui_registry.py` — `render_weight_panel()` 함수 교체 (L217~L247)

`render_weight_panel` 함수 전체를 다음 새 버전으로 교체한다. find 문자열은 ui_registry.py에서 *정확히 1번* 나타난다 (검증 완료, L217에서 시작). 다른 함수는 *손대지 않는다*.

### Find (MD5 `9678c71728e8bce43e466a0da8a254ad`)

```python
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
```

### Replace (MD5 `d81ccc0c9fa72b21212b9eacd9a77d3b`)

```python
def render_weight_panel(active_keys):
    """메인 화면 expander에 가중치 슬라이더 N개 생성. 카테고리 그룹핑 + preset 버튼.

    D5-hotfix: main.py L42가 stHeader를 숨겨서 사이드바 토글이 접근 불가 → 사이드바 → 메인
    expander로 이동. expanded=True로 기본 펼침. 기존 사이드바 'Status Board 전용' 정책 유지.
    """
    weights = {}
    by_cat = defaultdict(list)
    for k in active_keys:
        by_cat[UI_REGISTRY[k]["category"]].append(k)
    with st.expander("🎛️ Dashboard 가중치 패널 (preset 버튼 + 컴포넌트 슬라이더)", expanded=True):
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
```

---

## 2. 검증 절차 (Antigravity 납품 후)

### 2-1. 라인 수 산술

```bash
wc -l modules/ui_registry.py
```

`304 modules/ui_registry.py`가 출력되어야 한다. 산술: 300 + 4 = 304.

### 2-2. 마커 grep (positive + negative)

```bash
grep -c "with st.sidebar:" modules/ui_registry.py
grep -c "with st.expander("🎛️ Dashboard 가중치 패널" modules/ui_registry.py
grep -c "D5-hotfix:" modules/ui_registry.py
```

순서대로 **0회 / 1회 / 1회**여야 한다. `with st.sidebar:`가 0회인 게 *옛 마커 부재 확인*(곁가지 0건 보증의 핵심).

### 2-3. py_compile

```bash
python3 -m py_compile modules/ui_registry.py
```

exit 0이어야 한다.

### 2-4. Streamlit 라이브 실행 시연

```bash
streamlit run main.py
```

세 검증 시나리오:

| 입력 로그 | 메인 화면 하단 출력 |
|---|---|
| pkmn_battle_log.csv | `## 🎛️ 가중치 기반 동적 Dashboard (D5 신규)` 섹션 안에 `🎛️ Dashboard 가중치 패널` expander(펼침 상태)가 보이고, 그 안에 Pokemon·FF7·HS 버튼 + hp_bar·type_chart 슬라이더 2개. expander 아래에 HP 막대 + 타입 상성 차트 |
| ff7_battle_log.csv | 같은 expander 안에 hp_bar·element_routing 슬라이더 2개. 아래에 HP + Physical/Magic 라우팅 |
| hs_battle_log.csv | 같은 expander 안에 hp_bar·card_trade 슬라이더 2개. 아래에 HP + 카드 데미지 교환 |

사이드바는 *변경 없이* main.py의 Status Board만 표시(원래는 stHeader 숨김으로 접근 불가이지만 그건 hotfix 범위 밖).

---

## 3. 곁가지 0건 보장 (검증 완료)

- **라인 수 산술**: 300 + (+4) = 304. 실제 적용 결과 304. 정확 일치.
- **py_compile**: 변경 적용된 ui_registry.py 문법 검증 통과.
- **byte-equality**: 변경 사이트 외 영역 동등. render_weight_panel 함수 한 곳 외에는 무수정.
- **find string uniqueness**: 정확히 1회 매치.

---

## 4. 사후 정리 (데드라인 후 — 본 PR 범위 외)

- step6_dashboard.py L488의 fullscreen 모드 `UnboundLocalError: ally_instances` 기존 버그는 *D5 변경과 무관*하지만 별도 micro-hotfix로 수정 권장 (1줄 가드 추가).
- main.py L42의 `[data-testid="stHeader"] { display: none !important; }` 정책은 *유지*. 본 hotfix는 그 정책을 거스르지 않음.

---

*프롬프트 작성: 빌더 스크립트가 하니스에서 코드 블록 자동 추출. MD5 라운드트립 검증 통과.*
