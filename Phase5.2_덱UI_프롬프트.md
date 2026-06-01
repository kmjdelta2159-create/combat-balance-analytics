# Phase 5.2 — Step 6 덱 전투 UI

## 배경
Phase 5.1 덱 엔진(`DeckModule`/`CardTurnExecutor`)은 완료·검증됨. 5.2는 그 엔진을
Step 6 GM 모드에서 쓸 수 있게 한다 — 덱(카드 리스트)을 작성하고 `DeckModule`을 선언해
단일 전투·MC 버튼이 `deck_module`을 넘기게 한다. 이것으로 Phase 5 전체가 끝난다.

엔진 측 인터페이스 (이미 존재, 수정 금지):
- `run_simulation(..., deck_module=None)` / `run_monte_carlo(..., deck_module=None)`
- `DeckModule(hand_size=5, energy_per_turn=3)` — 순수 데이터
- 카드 dict: `{"name": str, "cost": int, "gimmicks": {"Target_Logic": ..., "Formula": ...}}`
- 인스턴스의 `deck` 키에 카드 리스트를 넣으면 엔진이 사용. `deck_module`이 None이면
  `StandardTurnExecutor` → 현행 동작.

## 변경 파일 (1개)
**`modules/step6_dashboard.py`만 수정.** 엔진 수정 금지.

## 범위 (5.2)
- 진영별 덱 1개씩(Ally 덱 / Enemy 덱). 같은 진영 캐릭터는 동일 덱 사용 — 캐릭터별
  개별 덱은 향후.
- 카드 = 공격 카드(이름/코스트/타겟/공식). 효과 카드(패시브 스크립트) 작성 UI는 향후.

## 설계 원칙 — default = OFF = identity
"덱 전투 모드" 체크박스 기본값은 **꺼짐**. 꺼져 있으면 `deck_module=None` + 인스턴스에
`deck` 미부착 → `StandardTurnExecutor` → **현행 100% 동일**. 테스트 CSV는 이 경로.

---

## 1. import 추가
import 구역(현재 23행 `from modules.spatial import SpatialModule`) 다음에:
```python
from modules.deck import DeckModule
```

## 2. 덱→카드 전개 헬퍼 (모듈 레벨 함수)
모듈 레벨 헬퍼 함수 구역(`get_default_df` 등 다른 모듈 레벨 def 근처)에 추가:
```python
def _deck_df_to_cards(deck_df):
    """덱 DataFrame을 카드 dict 리스트로 전개한다 (Count 만큼 복제)."""
    cards = []
    if deck_df is None:
        return cards
    for _, row in deck_df.iterrows():
        name = row.get("Name")
        if name is None or str(name).strip() == "" or str(name).strip().lower() == "nan":
            continue
        try:
            count = int(row.get("Count", 1) or 1)
        except (ValueError, TypeError):
            count = 1
        try:
            cost = int(row.get("Cost", 0) or 0)
        except (ValueError, TypeError):
            cost = 0
        for _ in range(max(1, count)):
            cards.append({
                "name": str(name),
                "cost": cost,
                "gimmicks": {
                    "Target_Logic": str(row.get("Target_Logic") or "Single_Target"),
                    "Formula": str(row.get("Formula") or "0"),
                },
            })
    return cards
```

## 3. 덱 전투 expander UI

`with top_col1:` 블록 안, "⚙️ 스탯 매핑 & 예산 가중치" expander가 닫힌 **직후**
(현재 220행 `}` 다음, 221행 빈 줄, 222행 `tab1, tab2 = st.tabs(...)` **앞**)에 삽입.
들여쓰기는 `with st.expander`가 8칸 — 스탯 매핑 expander와 동일 레벨:

```python
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
```

`Formula`는 데미지 공식 — 리터럴(`"70"`)이나 스탯 참조(`"phys_power - target_armor_class"`)
모두 가능 (캐릭터 데미지 공식과 동일 문법). `Count`는 그 카드를 덱에 몇 장 넣을지.

## 4. `df_to_instances` — 덱 부착

`df_to_instances`(현재 339~363행)에서, 좌표 부착 블록(현재 358~361행) 다음, `instances.append(inst)`
(현재 362행) **앞**에 추가:
```python
                            # 덱 부착 (덱 전투 모드일 때만)
                            if st.session_state.get('deck_mode'):
                                _deck_df = (st.session_state.get('ally_deck_df')
                                            if team == "Ally"
                                            else st.session_state.get('enemy_deck_df'))
                                inst['deck'] = _deck_df_to_cards(_deck_df)
```
(덱 전투 모드가 꺼져 있으면 `deck` 키를 부착하지 않는다 → 엔진이 빈 덱 취급.)

## 5. 버튼 — `deck_module` 전달

### 5-1. 공통 환경 변수
`spatial_module_val = SpatialModule(...)` 블록(현재 601~603행) 다음에 추가:
```python
                _deck_cfg = st.session_state.get('deck_config') or {}
                deck_module_val = (DeckModule(
                    hand_size=_deck_cfg.get('hand_size', 5),
                    energy_per_turn=_deck_cfg.get('energy_per_turn', 3))
                    if st.session_state.get('deck_mode') else None)
```

### 5-2. 단일 전투 버튼
`run_simulation(...)` 호출의 `move_stat=move_stat_val` 다음에 추가:
```python
                                spatial_module=spatial_module_val,
                                range_stat=range_stat_val,
                                move_stat=move_stat_val,
                                deck_module=deck_module_val
```

### 5-3. Monte Carlo 버튼
`run_monte_carlo(...)` 호출의 `move_stat=move_stat_val` 다음에 추가:
```python
                                spatial_module=spatial_module_val,
                                range_stat=range_stat_val,
                                move_stat=move_stat_val,
                                deck_module=deck_module_val
```

---

## 제약 / 주의
- 변경 파일 `modules/step6_dashboard.py` 한정. 엔진(`deck.py`/`engine.py`) 수정 금지.
- 덱 에디터는 `num_rows="dynamic"` — 사용자가 카드 행 추가/삭제 가능.
- `df_to_instances`의 기존 로직(자원 빌드·좌표 부착)은 그대로 — 덱 부착만 추가.
- 덱 전투 모드 꺼짐(기본값) → `deck_module=None` + `deck` 미부착 → 현행 100% 동일.
- 카드 dict의 `gimmicks`는 캐릭터 gimmicks와 동형 — `build_ctx`가 그대로 읽는다.

## 동작 동일성 — 회귀 검증
"덱 전투 모드" 체크박스 꺼짐일 때: `deck_module=None`, 인스턴스에 `deck` 미부착 →
`run_simulation`이 `StandardTurnExecutor` 사용 → **현행 100% 동일**.

베이스라인: `universal_test_log.csv`로 단일 전투 + Monte Carlo 시 NoVariance 1v1
lopsided 데미지총량 **620.0** / near-even **1026.0** 불변.

## 완료 기준 체크리스트
- [ ] `modules/step6_dashboard.py` 외 파일 변경 없음
- [ ] `from modules.deck import DeckModule` import 추가
- [ ] `_deck_df_to_cards` 모듈 레벨 헬퍼 추가
- [ ] "🃏 덱 전투" expander — 모드 토글 + hand_size/energy + Ally/Enemy 덱 에디터
- [ ] `st.session_state['deck_mode']` / `['deck_config']` / `['ally_deck_df']` / `['enemy_deck_df']` 저장
- [ ] 덱 에디터는 `num_rows="dynamic"`, 컬럼 Name/Cost/Target_Logic/Formula/Count
- [ ] `df_to_instances`가 덱 전투 모드일 때 `team` 따라 `inst['deck']` 부착 (기존 로직 보존)
- [ ] 공통 변수에 `deck_module_val` (모드 꺼짐 시 None)
- [ ] 단일 전투 버튼이 `deck_module` 전달
- [ ] Monte Carlo 버튼이 `deck_module` 전달
- [ ] 회귀: 덱 전투 모드 꺼짐 + `universal_test_log.csv` 단일 전투 + MC → 베이스라인 620.0 / 1026.0
