# Phase 4b-UI — Step 6 이동력 스탯 선언 + 엔진 전달

## 배경
Phase 4b 엔진(`engine.py`의 `_act_move`/`MOVE` 액션, `spatial.py`의 `step_toward`)은
**이미 완료·검증됨**. 이 프롬프트는 4b의 **UI 부분** — Step 6에서 이동력 스탯을
선언해 엔진에 전달한다. 이것으로 Phase 4(공간 시스템) 전체가 끝난다.

엔진 측 인터페이스 (이미 존재, 수정 금지):
- `run_simulation(..., move_stat=None)` / `run_monte_carlo(..., move_stat=None)`
- 엔진은 `move_stat`이 None이면 `_act_move`가 no-op → 현행 동작과 동일

`move_stat`은 4a-UI의 `range_stat`과 **정확히 평행한 구조**다 (스탯 셀렉트박스,
`(없음)` 기본값, 세션 저장, 버튼 전달).

## 변경 파일 (1개)
**`modules/step6_dashboard.py`만 수정.** 엔진(`engine.py`/`spatial.py`) 수정 금지 — 이미 완료.

## 설계 원칙 — default = OFF = identity
이동력 스탯 셀렉트박스 기본값은 `(없음)`. `(없음)`이면 `move_stat=None` → 엔진
`_act_move`가 즉시 no-op. 테스트 CSV는 `(없음)` 그대로 → **동작 100% 현행과 동일**.

---

## 1. 공간 시스템 선언 UI — 이동력 스탯 셀렉트박스 추가

현재 "스탯 매핑" expander 안의 공간 시스템 블록(현재 198~215행)은 4칸 컬럼
(사거리 스탯 / 격자 너비 / 격자 높이 / 거리 방식)이다. 이 블록 **전체를** 아래로
교체한다 — 5칸으로 늘려 **이동력 스탯** 셀렉트박스를 사거리 스탯 옆에 추가:

```python
            # ── 공간 시스템: 사거리/이동력 스탯 + 격자 (Phase 4a-UI / 4b-UI) ──
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
```

`move_stat_sel`은 `range_stat_sel`과 마찬가지로 **key 없이** 둔다 (CSV 재로드 시
옵션 변경 stale-value 크래시 방지).

---

## 2. 캐릭터 좌표 배치 UI — 게이트에 move_stat 반영

이동에도 좌표가 필요하다. 현재 좌표 배치 블록(현재 306~309행)은 `range_stat`이
있을 때만 렌더링한다. 사거리 또는 **이동력 둘 중 하나라도** 켜져 있으면 좌표 배치가
나타나도록 게이트 조건을 넓힌다.

현재:
```python
                # ── 캐릭터 격자 배치 (Phase 4a-UI) ──
                char_positions = {}
                _range_stat = st.session_state.get('range_stat')
                if _range_stat:
```
변경:
```python
                # ── 캐릭터 격자 배치 (Phase 4a-UI / 4b-UI) ──
                char_positions = {}
                _range_stat = st.session_state.get('range_stat')
                _move_stat = st.session_state.get('move_stat')
                if _range_stat or _move_stat:
```
(블록의 나머지 내용은 그대로 둔다 — 캐릭터별 X/Y 입력, `char_positions` 저장 등.)

---

## 3. 버튼 — `move_stat` 전달

### 3-1. 공통 환경 변수 (현재 592~596행)
`spatial_module_val = SpatialModule(...)` 블록 근처, `range_stat_val` 다음에 추가:
```python
                move_stat_val = st.session_state.get('move_stat')
```

### 3-2. 단일 전투 버튼 (현재 601~611행)
`run_simulation(...)` 호출의 `range_stat=range_stat_val` 다음에 추가:
```python
                                spatial_module=spatial_module_val,
                                range_stat=range_stat_val,
                                move_stat=move_stat_val
```

### 3-3. Monte Carlo 버튼 (현재 636~648행)
`run_monte_carlo(...)` 호출의 `range_stat=range_stat_val` 다음에 추가:
```python
                                spatial_module=spatial_module_val,
                                range_stat=range_stat_val,
                                move_stat=move_stat_val
```

---

## 제약 / 주의
- 변경 파일은 `modules/step6_dashboard.py` **한정**. 엔진 수정 금지.
- `move_stat_sel` 셀렉트박스는 **key 없이** (range_stat과 동일 패턴).
- 좌표 배치 블록 내부 로직(X/Y number_input, `max_value` 없음, `char_positions` 저장)은
  건드리지 말 것 — 게이트 조건 한 줄만 변경.
- 이동이 실제로 동작하려면 사용자는 이동력 스탯 + 좌표 배치를 설정해야 한다. 좌표
  배치는 이제 사거리 또는 이동력 중 하나만 켜도 나타난다.

## 동작 동일성 — 회귀 검증
이동력 스탯 = `(없음)`(기본값)일 때: `move_stat=None` → 엔진 `_act_move`가 no-op.
사거리 스탯도 `(없음)`이면 좌표 배치 UI 미렌더. 버튼이 `move_stat=None`을 넘기므로
현행과 **100% 동일**.

베이스라인: `universal_test_log.csv`로 단일 전투 + Monte Carlo 실행 시
NoVariance 1v1 lopsided 데미지총량 **620.0** / near-even **1026.0** 불변.

## 완료 기준 체크리스트
- [ ] `modules/step6_dashboard.py` 외 파일 변경 없음
- [ ] 공간 시스템 블록에 이동력 스탯 셀렉트박스 추가 (5칸 컬럼)
- [ ] `st.session_state['move_stat']` 저장 (`(없음)` → None)
- [ ] 좌표 배치 게이트가 `range_stat` 또는 `move_stat` 중 하나라도 있으면 렌더
- [ ] 공통 변수에 `move_stat_val` 추가
- [ ] 단일 전투 버튼이 `move_stat` 전달
- [ ] Monte Carlo 버튼이 `move_stat` 전달
- [ ] 회귀 검증: 사거리·이동력 모두 `(없음)` 상태로 `universal_test_log.csv` 단일 전투
      + MC → 베이스라인 620.0 / 1026.0 일치
