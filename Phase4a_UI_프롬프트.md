# Phase 4a-UI — Step 6 공간 시스템 UI (격자 선언 + 좌표 배치 + 사거리 매핑)

## 배경
Phase 4a 엔진(`modules/spatial.py`의 `SpatialModule`, `engine.py`의 사거리 타겟팅)은
**이미 완료·검증됨**. 이 프롬프트는 4a의 **UI 부분** — Step 6에서 격자를 선언하고,
캐릭터를 좌표에 배치하고, 사거리 스탯을 매핑해서, 그 정보를 엔진에 전달한다.

엔진 측 인터페이스 (이미 존재, 수정 금지):
- `run_simulation(..., spatial_module=None, range_stat=None)`
- `run_monte_carlo(..., spatial_module=None, range_stat=None)`
- `SpatialModule(width=None, height=None, distance_metric="manhattan")` — 순수 데이터
- 캐릭터 위치는 인스턴스 dict의 `position` 키: `{'x': int, 'y': int}` (없으면 None)
- 엔진은 `range_stat`이 None이면 사거리 필터를 건너뛴다 → 현행 동작과 동일

## 변경 파일 (1개)
**`modules/step6_dashboard.py`만 수정.** 그 외 모든 파일 무수정.

## 설계 원칙 — default = OFF = identity
사거리 스탯 셀렉트박스의 기본값은 `(없음)`이다. `(없음)`이면:
- `range_stat = None` → 엔진이 사거리 필터를 건너뜀
- 좌표 배치 UI를 렌더링하지 않음 → `char_positions = {}` → 인스턴스에 `position` 없음

테스트 CSV(`universal_test_log.csv`)는 사거리 스탯을 선언할 일이 없으므로 `(없음)`
그대로 → **동작 100% 현행과 동일**.

---

## 1. import 추가
import 구역(현재 22행 `from modules.engine import ...` 근처)에 추가:
```python
from modules.spatial import SpatialModule
```

---

## 2. 공간 시스템 선언 UI — "스탯 매핑" expander 안

`with st.expander("⚙️ 스탯 매핑 & 예산 가중치 (Weights) 설정", ...)` 블록의 **맨 끝**
(현재 195행 `st.session_state['stat_weights'] = {}` 다음, expander가 닫히기 직전,
budget weights 섹션과 같은 12칸 들여쓰기)에 삽입:

```python
            # ── 공간 시스템: 사거리 스탯 + 격자 (Phase 4a-UI) ──
            st.markdown("##### 🗺️ 공간 시스템 (격자 + 사거리)")
            sp_c1, sp_c2, sp_c3, sp_c4 = st.columns(4)
            with sp_c1:
                range_stat_sel = st.selectbox(
                    "🎯 사거리 스탯", ["(없음)"] + sys_stats, index=0,
                    help="사거리로 쓸 스탯. (없음) = 사거리 무제한 = 현행 동작과 동일")
            with sp_c2:
                grid_w = st.number_input("격자 너비", min_value=1, value=10, step=1, key="ui_grid_w")
            with sp_c3:
                grid_h = st.number_input("격자 높이", min_value=1, value=10, step=1, key="ui_grid_h")
            with sp_c4:
                dist_metric = st.selectbox("거리 방식", ["manhattan", "chebyshev"],
                                           index=0, key="ui_dist_metric")
            st.session_state['range_stat'] = None if range_stat_sel == "(없음)" else range_stat_sel
            st.session_state['grid_config'] = {
                "width": int(grid_w), "height": int(grid_h), "distance_metric": dist_metric
            }
```

`range_stat_sel`은 anchor/health/speed 셀렉트박스와 마찬가지로 **key 없이** 둔다
(새 CSV 로드 시 옵션 변경에 따른 stale-value 크래시 방지).

---

## 3. 캐릭터 좌표 배치 UI — 파티 에디터 직후

`with col_input:` 블록 안, **enemy 파티 data_editor 직후**(현재 284행
`st.rerun()` 다음), `def df_to_instances` 정의 **직전**(현재 286행 앞)에 삽입.
들여쓰기는 16칸 (data_editor·`def df_to_instances`와 동일 레벨):

```python
                # ── 캐릭터 격자 배치 (Phase 4a-UI) ──
                char_positions = {}
                _range_stat = st.session_state.get('range_stat')
                if _range_stat:
                    _grid_cfg = st.session_state.get('grid_config', {})
                    _gw = _grid_cfg.get('width', 10)
                    _gh = _grid_cfg.get('height', 10)
                    st.markdown("##### 🗺️ 캐릭터 격자 배치")
                    st.caption(f"격자 {_gw}×{_gh} · 거리 {_grid_cfg.get('distance_metric','manhattan')} "
                               f"— 좌표는 0부터")
                    for _team, _tdf in [("Ally", st.session_state['ally_df']),
                                        ("Enemy", st.session_state['enemy_df'])]:
                        for _idx, (_, _row) in enumerate(_tdf.iterrows()):
                            _hero = _row["Hero"]
                            if _hero and _hero != "비어 있음" and not pd.isna(_hero):
                                _pc1, _pc2 = st.columns(2)
                                with _pc1:
                                    _px = st.number_input(
                                        f"{_team} · {_hero} — X", min_value=0, value=0, step=1,
                                        key=f"ui_posx_{_team}_{_idx}")
                                with _pc2:
                                    _py = st.number_input(
                                        f"{_team} · {_hero} — Y", min_value=0, value=0, step=1,
                                        key=f"ui_posy_{_team}_{_idx}")
                                char_positions[f"{_team}_{_idx}"] = {"x": int(_px), "y": int(_py)}
                st.session_state['char_positions'] = char_positions
```

`_range_stat`이 None(공간 OFF)이면 이 블록은 아무 위젯도 렌더하지 않고
`char_positions`를 빈 dict로 저장 → 인스턴스에 `position`이 안 붙음.

---

## 4. `df_to_instances` — team 파라미터 + position 부착

현재 `def df_to_instances(df_target):` (286행)를 아래로 교체.
변경점: `team=None` 파라미터 추가 / 행 인덱스를 `enumerate`로 / `char_positions`에서
`position` 조회해 부착. **나머지 로직(자원 빌드 등)은 그대로.**

```python
                def df_to_instances(df_target, team=None):
                    instances = []
                    resource_config = st.session_state.get('resource_config')
                    if not resource_config:
                        # 폴백 — 자원 설정 미존재 시 health_stat 기반 HP 단일 자원
                        h_stat = st.session_state.get('health_stat')
                        resource_config = {"HP": {"role": "vital", "stat": h_stat, "regen": 0.0}}
                    char_positions = st.session_state.get('char_positions', {})
                    for _idx, (_, row) in enumerate(df_target.iterrows()):
                        if row["Hero"] and row["Hero"] != "비어 있음" and not pd.isna(row["Hero"]):
                            inst = {"name": row["Hero"], "gimmicks": {}}
                            for g in sys_gimmicks: inst["gimmicks"][g] = row.get(g, "None")
                            for s in sys_stats: inst[s] = float(row[s])
                            # 자원 설정 기반 다중 자원 빌드
                            inst['resources'] = {}
                            for rname, rspec in resource_config.items():
                                stat = rspec.get('stat')
                                val = float(inst[stat]) if (stat and stat in inst) else 1.0
                                inst['resources'][rname] = {"current": val, "max": val}
                            # 격자 좌표 부착 (공간 OFF면 char_positions가 비어 있어 미부착)
                            _pos = char_positions.get(f"{team}_{_idx}")
                            if _pos is not None:
                                inst['position'] = _pos
                            instances.append(inst)
                    return instances
```

호출부 2곳(현재 307~308행)을 `team` 인자와 함께 호출하도록 수정:
```python
                ally_instances = df_to_instances(st.session_state['ally_df'], team="Ally")
                enemy_instances = df_to_instances(st.session_state['enemy_df'], team="Enemy")
```

---

## 5. 버튼 — `spatial_module` / `range_stat` 전달

### 5-1. 공통 환경 변수 (현재 534~538행)
`global_formula_val = ...` 다음에 추가:
```python
                range_stat_val = st.session_state.get('range_stat')
                _grid = st.session_state.get('grid_config') or {}
                spatial_module_val = SpatialModule(
                    width=_grid.get('width'), height=_grid.get('height'),
                    distance_metric=_grid.get('distance_metric', 'manhattan'))
```

### 5-2. 단일 전투 버튼 (현재 543~551행)
`run_simulation(...)` 호출에 인자 2개 추가:
```python
                            winner, battle_logs, sim_metrics = run_simulation(
                                ally_instances, enemy_instances, max_turns=sim_max_turns,
                                combat_flow=combat_flow_val, speed_stat=speed_stat_val,
                                sys_stats=sys_stats_val, global_damage_formula=global_formula_val,
                                resource_module=ResourceModule(
                                    st.session_state.get('resource_config') or None,
                                    damage_type_map=st.session_state.get('damage_type_map') or None
                                ),
                                spatial_module=spatial_module_val,
                                range_stat=range_stat_val
                            )
```

### 5-3. Monte Carlo 버튼 (현재 576~586행)
`run_monte_carlo(...)` 호출에 인자 2개 추가:
```python
                            mc_result = run_monte_carlo(
                                ally_instances, enemy_instances, combat_flow_val,
                                speed_stat_val, sys_stats_val, global_formula_val,
                                num_simulations=10000, max_turns=sim_max_turns,
                                progress_callback=progress_cb,
                                stochasticity_factory=default_stochasticity_factory,
                                resource_module=ResourceModule(
                                    st.session_state.get('resource_config') or None,
                                    damage_type_map=st.session_state.get('damage_type_map') or None
                                ),
                                spatial_module=spatial_module_val,
                                range_stat=range_stat_val
                            )
```

---

## 제약 / 주의

- 변경 파일은 `modules/step6_dashboard.py` **한정**. 엔진(`engine.py`/`spatial.py`)
  수정 금지 — 이미 완료됨.
- `range_stat_sel` 셀렉트박스는 **key 없이** (anchor/health/speed와 동일 — CSV 재로드 시
  옵션 변경 stale-value 크래시 방지). 격자 number_input과 거리방식 셀렉트박스는 key 부여.
- 좌표 number_input에 `max_value`를 두지 말 것 — 격자 크기를 바꾸면 key에 묶인 저장값이
  새 max_value를 초과해 크래시할 수 있다. 4a 엔진은 좌표 경계를 강제하지 않으므로
  `min_value=0`만 둔다.
- `df_to_instances`의 자원 빌드 로직은 그대로 둔다 — position 부착만 추가.
- `char_positions`는 순수 dict이고 인스턴스의 `position`도 `{'x':int,'y':int}` 순수
  dict → pickle 안전 (MC 워커 전달 OK).

## 동작 동일성 — 회귀 검증

사거리 스탯 = `(없음)`(기본값)일 때:
`range_stat=None` → 엔진 사거리 필터 skip / 좌표 배치 UI 미렌더 / `position` 미부착.
버튼이 `spatial_module`(SpatialModule 인스턴스)을 넘기더라도 `range_stat=None`이면
`_act_target_select`의 사거리 필터는 작동하지 않는다 → **현행과 100% 동일**.

베이스라인: `universal_test_log.csv`로 단일 전투 + Monte Carlo 실행 시
NoVariance 1v1 lopsided 데미지총량 **620.0** / near-even **1026.0** 불변.

## 완료 기준 체크리스트
- [ ] `modules/step6_dashboard.py` 외 파일 변경 없음
- [ ] `from modules.spatial import SpatialModule` import 추가
- [ ] expander에 공간 시스템 선언 UI (사거리 스탯 셀렉트박스 + 격자 너비/높이/거리방식)
- [ ] `st.session_state['range_stat']` / `['grid_config']` 저장
- [ ] 사거리 스탯 `(없음)`이면 좌표 배치 UI 미렌더 + `char_positions = {}`
- [ ] 사거리 스탯 선택 시 편성된 캐릭터마다 X/Y 좌표 입력
- [ ] 좌표 number_input에 `max_value` 없음
- [ ] `df_to_instances`에 `team` 파라미터 + `char_positions` 기반 `position` 부착 (자원 로직 보존)
- [ ] `df_to_instances` 호출 2곳에 `team="Ally"` / `team="Enemy"` 전달
- [ ] 단일 전투 버튼이 `spatial_module` + `range_stat` 전달
- [ ] Monte Carlo 버튼이 `spatial_module` + `range_stat` 전달
- [ ] 회귀 검증: 사거리 스탯 `(없음)` 상태로 `universal_test_log.csv` 단일 전투 + MC →
      베이스라인 620.0 / 1026.0 일치
