# Antigravity 프롬프트 — D5-hotfix2: 게임 preset 버튼 제거

D5-hotfix 시연에서 사용자 결정: *게임 preset 버튼(Pokemon/FF7/HS) 제거*. 이유 — 게임 이름이
코드에 하드코딩된 preset 버튼은 핸드오프 §1의 "슬라이더는 연속체이지 카테고리 점프가 아니다"
원칙에 어긋남. 자동 감지가 이미 게임별 컴포넌트를 정확히 활성하므로 preset 버튼은 redundant.

해결: `modules/ui_registry.py`의 `render_weight_panel()` 함수에서 preset 섹션(Pokemon/FF7/HS
3 버튼 + apply_preset 호출 + divider + 게임 preset 마크다운 헤더) 제거. expander 제목도
단순화. dead `_apply_preset` 함수는 데드라인 후 별도 정리.

---

## 변경 사이트 요약

| # | 파일 | 동작 | 라인 변화 |
|---|---|---|---|
| 1 | `modules/ui_registry.py` (render_weight_panel) | preset 섹션 제거 + 제목 단순화 + docstring 갱신 | -9 |

`ui_registry.py` 합계: 304 → **295 lines** (산술 검증 통과). py_compile 통과,
변경 사이트 외 byte-equality 확인.

---

## 1. `modules/ui_registry.py` — `render_weight_panel()` 함수 교체

`render_weight_panel` 함수 전체를 다음 새 버전으로 교체한다. find 문자열은 ui_registry.py에서
*정확히 1번* 나타난다 (검증 완료, L217에서 시작).

### Find (MD5 `d81ccc0c9fa72b21212b9eacd9a77d3b`)

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

### Replace (MD5 `8a5d6c2761d37444730a850f458d0a66`)

```python
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
```

---

## 2. 검증 절차

### 2-1. 라인 수 산술

```bash
wc -l modules/ui_registry.py
```

`295 modules/ui_registry.py` 출력 (304 + (-9) = 295).

### 2-2. 마커 grep

```bash
grep -c "preset_pokemon\|preset_ff7\|preset_hs" modules/ui_registry.py
grep -c "Dashboard 컴포넌트 가중치" modules/ui_registry.py
grep -c "D5-hotfix2:" modules/ui_registry.py
```

순서대로 **0회 / 1회 / 1회**여야 한다. 첫 grep이 0회인 게 *옛 마커 부재 확인*(preset 버튼이
완전히 제거됨).

### 2-3. py_compile

```bash
python3 -m py_compile modules/ui_registry.py
```

exit 0.

### 2-4. Streamlit 라이브 실행

세 로그 모두에서 메인 화면의 "🎛️ 가중치 기반 동적 Dashboard (D5 신규)" 섹션 안 expander가
`⚖️ Dashboard 컴포넌트 가중치` 제목으로 바뀌어 있고, *preset 버튼 섹션이 사라짐*. 컴포넌트
가중치 슬라이더만 남아 있어야 한다.

---

## 3. 곁가지 0건 보장

- 라인 수 산술: 304 + (-9) = 295. 실제 적용 결과 295. 정확 일치.
- py_compile: 변경 적용된 ui_registry.py 문법 검증 통과.
- byte-equality: 변경 사이트 외 영역 동등.
- find string uniqueness: 정확히 1회 매치.

---

*프롬프트 작성: 빌더 스크립트가 하니스에서 코드 블록 자동 추출. MD5 라운드트립 검증 통과.*
