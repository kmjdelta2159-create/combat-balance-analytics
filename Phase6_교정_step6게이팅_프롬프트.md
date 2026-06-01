# Phase 6 교정 — step6 게이팅 누락분 적용

## 배경 (중요)

직전 Phase 6 납품에서 `modules/step6_dashboard.py`의 변경 6개 중 **단 1개**
(`spatial_module_val` 조건부화)만 적용되고 **나머지 5개가 누락**되었다. 그 결과
현재 `step6_dashboard.py`는 정의되지 않은 변수 `_spatial_on`을 참조한다
(`spatial_module_val = (SpatialModule(...) if _spatial_on else None)`) → 5단계
Dashboard 진입 시 **`NameError` 크래시**.

이 프롬프트는 **누락된 5개 변경만** 적용해 이를 바로잡는다.

- `modules/detection.py` — 정상 납품됨. **수정 금지.**
- `modules/step2_system_definition.py` — 정상 납품됨. **수정 금지.**
- `modules/step6_dashboard.py` — 아래 5개 변경을 적용한다.

## 변경 파일 (1개)

**`modules/step6_dashboard.py`만 수정한다.** 엔진(`engine.py`) · `detection.py` ·
`step2_system_definition.py` · 기타 모듈 일절 수정 금지.

## 적용 방식 — 반드시 5개 모두 적용

각 변경은 "기존 코드를 찾아 통째로 교체"한다. 제공된 교체 블록은 **이미 indentation ·
syntax 검증을 마친 코드**다 — 블록 내용을 한 글자도, 들여쓰기 한 칸도 바꾸지 말 것.
제공된 그대로 붙여넣는다. **5개 변경을 빠짐없이 모두 적용해야 한다.**

---

## 변경 1 — `module_active` import 추가

아래 줄을 찾는다:
```python
from modules.deck import DeckModule
```
다음으로 교체한다 (한 줄 추가):
```python
from modules.deck import DeckModule
from modules.detection import module_active
```

---

## 변경 2 — 게이팅 불리언 정의 (render_dashboard 상단)

아래 3줄을 찾는다 (`render_dashboard` 함수 상단, 현재 128~130행):
```python
    df = st.session_state["df"]
    sys_stats = st.session_state.get('system_stats', [])
    sys_gimmicks = st.session_state.get('system_gimmicks', [])
```
다음으로 교체한다 (5줄 추가):
```python
    df = st.session_state["df"]
    sys_stats = st.session_state.get('system_stats', [])
    sys_gimmicks = st.session_state.get('system_gimmicks', [])

    # Phase 6 — Game Profile 기반 모듈 게이팅
    _gp6 = st.session_state.get('game_profile')
    _resource_on = module_active(_gp6, 'resource')
    _spatial_on = module_active(_gp6, 'spatial')
    _deck_on = module_active(_gp6, 'deck')
```

이 변경이 `_resource_on` · `_spatial_on` · `_deck_on`을 정의한다 — 직전 납품이
남긴 `_spatial_on` 미정의 `NameError`가 이로써 해소된다.

---

## 변경 3 — 자원 섹션 게이팅 (앵커-구간 통째 교체)

`with st.expander("⚙️ 스탯 매핑 & 예산 가중치 (Weights) 설정", ...)` 블록 안에서,
아래 **시작 줄**부터 **끝 줄**까지의 **연속 구간 전체**(현재 162~213행)를 찾는다:

- 시작 줄: `            st.markdown("##### 🧪 추가 자원 선언 (Pool / Shield)")`
- 끝 줄:   `            st.session_state['damage_type_map'] = damage_type_map`

이 구간 전체를 아래 블록으로 **통째로 교체**한다 (들여쓰기 그대로):

```python
            if _resource_on:
                st.markdown("##### 🧪 추가 자원 선언 (Pool / Shield)")
                extra_candidates = [s for s in sys_stats if s != health_stat]
                extra_stats = st.multiselect(
                    "추가 자원으로 쓸 스탯 (HP 외 비-치명 자원)",
                    extra_candidates, default=[], key="ui_pool_stats"
                )
                resource_config = {"HP": {"role": "vital", "stat": health_stat, "regen": 0.0}}
                for es in extra_stats:
                    rc1, rc2 = st.columns(2)
                    with rc1:
                        role = st.selectbox(
                            f"{es} 역할", ["pool", "shield"], key=f"ui_role_{es}",
                            help="pool = 턴 재생 가능한 비-치명 자원 / shield = 데미지를 HP보다 먼저 흡수"
                        )
                    with rc2:
                        regen = st.number_input(f"{es} 턴당 재생", value=0.0, step=1.0,
                                                format="%.1f", key=f"ui_regen_{es}")
                    resource_config[es] = {"role": role, "stat": es, "regen": regen}
                st.session_state['resource_config'] = resource_config
                resource_role_stats = set(spec["stat"] for spec in resource_config.values())

                # ── damage_type 라우팅 맵 (Phase 3.5b-ii) ──
                sys_gimmicks = st.session_state.get('system_gimmicks', [])
                damage_type_col = next(
                    (c for c in sys_gimmicks
                     if 'damage_type' in c.lower() or 'dmg_type' in c.lower()),
                    None,
                )
                df = st.session_state.get('df')

                if not damage_type_col or df is None:
                    st.session_state['damage_type_map'] = {}
                else:
                    st.markdown("##### 🎯 데미지 타입 → 자원 라우팅")
                    st.caption("damage_type을 HP(vital)에 매핑하거나 미매핑하면 shield가 먼저 흡수합니다. pool/shield로 매핑하면 해당 자원으로 직격합니다.")

                    unique_dmg_types = [x for x in df[damage_type_col].dropna().unique() if str(x).strip() and str(x).strip() != "None"]
                    resource_names = list(resource_config.keys())
                    damage_type_map = {}

                    if unique_dmg_types:
                        rc_cols = st.columns(min(len(unique_dmg_types), 4))
                        for idx, dt in enumerate(unique_dmg_types):
                            with rc_cols[idx % len(rc_cols)]:
                                sel = st.selectbox(
                                    str(dt),
                                    options=resource_names,
                                    index=0,
                                    key=f"ui_dmgroute_{dt}_{'|'.join(resource_names)}"
                                )
                                damage_type_map[dt] = sel
                    st.session_state['damage_type_map'] = damage_type_map
            else:
                # 자원 모듈 OFF — HP 단일 자원(현행 baseline) 강제
                resource_config = {"HP": {"role": "vital", "stat": health_stat, "regen": 0.0}}
                st.session_state['resource_config'] = resource_config
                resource_role_stats = set(spec["stat"] for spec in resource_config.values())
                st.session_state['damage_type_map'] = {}
```

⚠️ 이 구간 바로 위의 주석 두 줄(`# ── 자원 선언 (Phase 3.5b-i) ──` 등)과 바로 아래의
`st.markdown("##### ⚖️ 스탯 예산 환산 가중치 (Budget Weights)")` 섹션은 **건드리지
않는다.** `resource_config`와 `resource_role_stats`는 `if`/`else` 양쪽 분기에서 모두
정의되므로 아래 예산 가중치 섹션이 정상 동작한다.

---

## 변경 4 — 공간 섹션 게이팅 (앵커-구간 통째 교체)

같은 `⚙️` expander 안에서, 아래 **시작 줄**부터 **끝 줄**까지의 **연속 구간 전체**
(현재 228~249행)를 찾는다:

- 시작 줄: `            st.markdown("##### 🗺️ 공간 시스템 (격자 + 사거리 + 이동)")`
- 끝 줄:   `st.session_state['grid_config'] = { ... }` 딕셔너리 대입문의 닫는 `}`
  (시작 줄로부터 아래쪽, `"width": int(grid_w), "height": int(grid_h), ...` 줄 다음의 `}` 줄)

이 구간 전체를 아래 블록으로 **통째로 교체**한다 (들여쓰기 그대로):

```python
            if _spatial_on:
                st.markdown("##### 🗺️ 공간 시스템 (격자 + 사거리 + 이동)")
                sp_c1, sp_c2, sp_c3, sp_c4, sp_c5 = st.columns(5)
                with sp_c1:
                    range_stat_sel = st.selectbox(
                        "🎯 사거리 스탯", ["(없음)"] + sys_stats, index=0,
                        help="사거리로 쓸 스탯. (없음) = 사거리 무제한 = 현행 동작과 동일")
                with sp_c2:
                    move_stat_sel = st.selectbox(
                        "🏃 이동력 스탯", ["(없음)"] + sys_stats, index=0,
                        help="턴당 이동 타일 수로 쓸 스탯. (없음) = 이동 없음 = 현행 동작과 동일")
                with sp_c3:
                    grid_w = st.number_input("격자 너비", min_value=1, value=10, step=1, key="ui_grid_w")
                with sp_c4:
                    grid_h = st.number_input("격자 높이", min_value=1, value=10, step=1, key="ui_grid_h")
                with sp_c5:
                    dist_metric = st.selectbox("거리 방식", ["manhattan", "chebyshev"],
                                               index=0, key="ui_dist_metric")
                st.session_state['range_stat'] = None if range_stat_sel == "(없음)" else range_stat_sel
                st.session_state['move_stat'] = None if move_stat_sel == "(없음)" else move_stat_sel
                st.session_state['grid_config'] = {
                    "width": int(grid_w), "height": int(grid_h), "distance_metric": dist_metric
                }
            else:
                # 공간 모듈 OFF — 사거리/이동 미사용(현행 baseline)
                st.session_state['range_stat'] = None
                st.session_state['move_stat'] = None
                st.session_state['grid_config'] = {"width": 10, "height": 10,
                                                   "distance_metric": "manhattan"}
```

⚠️ 시작 줄 바로 위의 주석(`# ── 공간 시스템: ...`)은 건드리지 않는다.

---

## 변경 5 — 덱 expander 게이팅 (앵커-구간 통째 교체)

아래 **시작 줄**부터 **끝 줄**까지의 **연속 구간 전체**(현재 251~293행)를 찾는다:

- 시작 줄: `        with st.expander("🃏 덱 전투 (Card Combat)", expanded=False):`
- 끝 줄:   `                key="ui_enemy_deck_editor")`

이 구간 전체를 아래 블록으로 **통째로 교체**한다 (들여쓰기 그대로):

```python
        if _deck_on:
            with st.expander("🃏 덱 전투 (Card Combat)", expanded=False):
                deck_mode = st.checkbox(
                    "덱 전투 모드 사용", value=False, key="ui_deck_mode",
                    help="켜면 캐릭터가 매 턴 카드를 드로우/플레이한다. 끄면 현행 전투 그대로.")
                st.session_state['deck_mode'] = deck_mode

                dc1, dc2 = st.columns(2)
                with dc1:
                    hand_size = st.number_input("핸드 크기 (턴당 드로우)", min_value=1,
                                                value=5, step=1, key="ui_hand_size")
                with dc2:
                    energy_per_turn = st.number_input("턴당 에너지", min_value=1,
                                                      value=3, step=1, key="ui_energy")
                st.session_state['deck_config'] = {
                    "hand_size": int(hand_size), "energy_per_turn": int(energy_per_turn)
                }

                _card_cols = {
                    "Name": st.column_config.TextColumn("카드 이름"),
                    "Cost": st.column_config.NumberColumn("코스트", min_value=0, step=1),
                    "Target_Logic": st.column_config.SelectboxColumn(
                        "타겟", options=["Single_Target", "AoE_All", "Lowest_HP"]),
                    "Formula": st.column_config.TextColumn("데미지 공식"),
                    "Count": st.column_config.NumberColumn("덱 매수", min_value=1, step=1),
                }
                _default_deck = [{"Name": "Strike", "Cost": 1,
                                  "Target_Logic": "Single_Target",
                                  "Formula": "phys_power - target_armor_class", "Count": 8}]
                if 'ally_deck_df' not in st.session_state:
                    st.session_state['ally_deck_df'] = pd.DataFrame(_default_deck)
                if 'enemy_deck_df' not in st.session_state:
                    st.session_state['enemy_deck_df'] = pd.DataFrame(_default_deck)

                st.markdown("##### 🔵 Ally 덱")
                st.session_state['ally_deck_df'] = st.data_editor(
                    st.session_state['ally_deck_df'], column_config=_card_cols,
                    num_rows="dynamic", use_container_width=True, hide_index=True,
                    key="ui_ally_deck_editor")
                st.markdown("##### 🔴 Enemy 덱")
                st.session_state['enemy_deck_df'] = st.data_editor(
                    st.session_state['enemy_deck_df'], column_config=_card_cols,
                    num_rows="dynamic", use_container_width=True, hide_index=True,
                    key="ui_enemy_deck_editor")
        else:
            # 덱 모듈 OFF — 덱 전투 미사용(현행 baseline)
            st.session_state['deck_mode'] = False
```

---

## 이미 적용되어 있음 — 건드리지 말 것

`spatial_module_val` 공통 변수 구역(현재 680~683행)은 직전 납품에서 이미 다음과 같이
조건부화되어 있다 — **그대로 둔다**:
```python
                _grid = st.session_state.get('grid_config') or {}
                spatial_module_val = (SpatialModule(
                    width=_grid.get('width'), height=_grid.get('height'),
                    distance_metric=_grid.get('distance_metric', 'manhattan'))
                    if _spatial_on else None)
```
변경 2가 `_spatial_on`을 정의하므로 이 줄은 정상 동작하게 된다.

## 제약 / 주의

- 변경 파일 `modules/step6_dashboard.py` 한정. 다른 파일 일절 수정 금지.
- **로직 개선 금지, 사양대로만.** 교체 블록의 코드·들여쓰기를 한 글자도 바꾸지 말 것.
- 교체 블록 안의 코드는 직전 납품 이전의 기존 코드와 **로직이 100% 동일**하다 —
  `if _resource_on:` 등으로 감싸고 +4칸 들여쓰기한 것 + `else` 분기 추가뿐이다.
- 변경 2~5의 `_resource_on`/`_spatial_on`/`_deck_on`은 변경 2에서 정의되며,
  사용처(변경 3·4·5, 그리고 기존 683행)보다 위에 있다 — 순서 정상.

## 동작 동일성 — 회귀 검증

- 게이팅은 UI 표시 여부만 제어한다. 모듈 섹션이 숨겨지면 `resource_config`=HP단일,
  `damage_type_map`={}, `range_stat`/`move_stat`=None, `spatial_module`=None,
  `deck_mode`=False → `run_simulation`이 받는 파라미터가 현행 default와 동일.
- `game_profile`이 없으면 `module_active`가 True 반환 → 전체 섹션 표시 → 현행 동작.
- `universal_test_log.csv`: 4개 모듈 모두 자동 탐지 OFF → 자원·공간·덱 섹션 숨김 →
  identity. 단일 전투 NoVariance 1v1 lopsided 데미지총량 **620.0** / near-even
  **1026.0** 불변. Monte Carlo 동일.

## 완료 기준 체크리스트

- [ ] 변경 1: `from modules.detection import module_active` import 추가됨
- [ ] 변경 2: `_gp6`/`_resource_on`/`_spatial_on`/`_deck_on` 5줄 정의됨 (현재 130행 다음)
- [ ] 변경 3: 자원 섹션이 `if _resource_on:` / `else:`로 감싸짐
- [ ] 변경 3: `resource_config`·`resource_role_stats`가 if·else 양쪽에서 정의됨
- [ ] 변경 4: 공간 섹션이 `if _spatial_on:` / `else:`로 감싸짐
- [ ] 변경 5: 덱 expander가 `if _deck_on:` / `else:`로 감싸짐
- [ ] `spatial_module_val`의 `if _spatial_on else None` 줄은 그대로 유지됨
- [ ] `modules/step6_dashboard.py` 외 파일 변경 없음
- [ ] `python -m py_compile modules/step6_dashboard.py` 통과 (구문 오류 없음)
- [ ] 5개 변경이 빠짐없이 모두 적용됨
