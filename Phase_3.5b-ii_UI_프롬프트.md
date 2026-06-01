# Phase 3.5b-ii UI — damage_type → 자원 라우팅 매핑 테이블

## 배경
엔진 측 작업(Phase 3.5b-ii 엔진)은 **이미 완료**되어 있다. `ResourceModule`이 `damage_type`으로 데미지 대상 자원을 결정하는 `route_damage(target, dmg, damage_type)`를 갖고 있고, `build_ctx`가 `damage_type` 기믹 컬럼을 ctx에 소싱한다. 이번 작업은 **UI만** 추가한다.

목표: Step 6에 **damage_type → 자원 매핑 테이블**을 추가하고, 단일 전투·Monte Carlo 버튼이 그 맵을 `ResourceModule`에 전달하게 한다.

## 변경 파일
**`modules/step6_dashboard.py` 단 하나만 수정한다.** 다른 파일(`modules/resource.py`, `turn_manager.py` 등)은 절대 건드리지 말 것. 엔진은 이미 완성됨.

## 참고용 현재 코드 사실 (수정하지 말 것, 맥락용)
- `modules/resource.py`: `ResourceModule.__init__(self, specs=None, damage_type_map=None)` — 두 번째 인자가 이미 존재한다. `damage_type_map` 미지정 시 `{}`.
- 자원 설정은 `st.session_state['resource_config']`에 dict로 저장됨: `{"HP": {...}, <stat명>: {...}}`. **dict 키가 곧 자원 이름** (HP / pool·shield로 선언한 스탯명).
- 자원 선언 UI는 `render_dashboard()` 내부, expander `"⚙️ 스탯 매핑 & 예산 가중치 (Weights) 설정"` 안에 있다. 자원 설정 빌드가 끝나는 지점은 대략:
  ```python
  st.session_state['resource_config'] = resource_config
  resource_role_stats = set(spec["stat"] for spec in resource_config.values())
  ```
- 엔진의 damage_type 컬럼 탐지 휴리스틱 (`build_ctx` 내부, line ~663):
  ```python
  next((c for c in gimmicks if 'damage_type' in c.lower() or 'dmg_type' in c.lower()), None)
  ```
- 기믹 컬럼 목록: `sys_gimmicks = st.session_state.get('system_gimmicks', [])` (line ~788).
- 원본 데이터프레임: `df = st.session_state["df"]` (line ~786).
- 단일 전투 버튼(line ~1197) / Monte Carlo 버튼(line ~1214) — 둘 다 현재 다음과 같이 `ResourceModule`을 생성한다:
  ```python
  resource_module=ResourceModule(st.session_state.get('resource_config') or None)
  ```

---

## 작업 1 — damage_type 매핑 UI 추가

**위치**: 자원 선언 블록 직후, 즉 위에 적은 `resource_role_stats = ...` 줄 **다음**, `"##### ⚖️ 스탯 예산 환산 가중치"` 섹션 **시작 전**. (자원 선언과 동일한 expander 안, 동일 들여쓰기 레벨)

**로직**:

1. damage_type 컬럼을 엔진과 **완전히 동일한 휴리스틱**으로 탐지한다:
   ```python
   damage_type_col = next(
       (c for c in sys_gimmicks
        if 'damage_type' in c.lower() or 'dmg_type' in c.lower()),
       None,
   )
   ```

2. **컬럼이 없으면**: 매핑 UI를 렌더링하지 않고 `st.session_state['damage_type_map'] = {}`만 설정한다. (현재 테스트 CSV가 이 경로 → 동작 100% 동일)

3. **컬럼이 있으면**:
   - 고유값 수집: `df[damage_type_col]`에서 `dropna()` 후 `unique()`. `None`·`"None"`·빈 문자열은 제외.
   - 자원 이름 목록: `resource_names = list(resource_config.keys())` (HP 포함, 선언 순서 유지).
   - `st.markdown("##### 🎯 데미지 타입 → 자원 라우팅")`
   - 각 damage_type 값마다 `st.selectbox` 하나:
     - label = 해당 damage_type 값
     - `options = resource_names`
     - default = index 0 (`resource_names[0]` 은 항상 `"HP"` = vital → 미매핑과 동일 동작)
   - **selectbox key 주의**: 자원 셋(pool/shield 추가·제거)이 바뀌면 `options`가 달라져, key에 묶인 저장값이 무효가 되며 Streamlit이 크래시할 수 있다. key에 자원 이름 시그니처를 포함시켜 자원 셋 변경 시 위젯이 새로 초기화되게 한다:
     ```python
     key=f"ui_dmgroute_{dt}_{'|'.join(resource_names)}"
     ```
   - 선택 결과로 `damage_type_map = {dt: 선택된_자원이름 for 각 dt}`를 빌드해 `st.session_state['damage_type_map']`에 저장한다.
   - 안내 캡션: damage_type을 `HP`(vital)에 매핑하는 것은 미매핑과 동일하다(둘 다 vital 자원으로 라우팅, shield가 먼저 흡수). pool/shield로 매핑하면 해당 자원으로 직격한다.

---

## 작업 2 — 버튼 2곳에 맵 전달

단일 전투 버튼(line ~1203)과 Monte Carlo 버튼(line ~1235), **두 곳 모두**의 `ResourceModule(...)` 생성을 다음으로 변경한다:

```python
resource_module=ResourceModule(
    st.session_state.get('resource_config') or None,
    damage_type_map=st.session_state.get('damage_type_map') or None,
)
```

---

## 제약 / 주의사항

- 변경 파일은 `modules/step6_dashboard.py` **한정**.
- 엔진(`ResourceModule`, `route_damage`, `build_ctx`)은 이미 완성됨 — 수정 금지.
- 옵셔널 파라미터 `damage_type_map`은 엔진 측에서 이미 `default=None`. UI는 맵이 없으면 `None`/`{}`을 전달한다.
- **Worker 함수·멀티프로세싱 코드는 손대지 말 것.** `damage_type_map`은 순수 dict이므로 `ResourceModule` 인스턴스가 그대로 pickle 안전하다 → 기존 인스턴스 직접 전달 패턴 유지.
- Worker 함수 내부에서 `st.session_state` 접근 금지 (현행대로 버튼 핸들러에서 값을 추출해 인자로 전달).
- **동작 100% 동일성**: 현재 테스트 CSV(`universal_test_log.csv`)에는 `damage_type`/`dmg_type` 컬럼이 없다 → 매핑 UI 미렌더 → `damage_type_map = {}` → `route_damage`가 전부 vital(HP)로 라우팅 → 기존 동작과 **완전히 동일**해야 한다.

---

## 완료 기준 체크리스트

- [ ] `modules/step6_dashboard.py` 외 파일 변경 없음
- [ ] damage_type 컬럼 탐지에 엔진과 동일한 휴리스틱(`'damage_type'`/`'dmg_type'` 부분문자열) 사용
- [ ] damage_type 컬럼이 없을 때: 매핑 UI 미렌더 + `st.session_state['damage_type_map'] = {}` 설정
- [ ] damage_type 컬럼이 있을 때: 고유값마다 자원 selectbox 1개 (None/빈값 제외)
- [ ] selectbox `options` = `resource_config` 키 목록 (HP / pool·shield 스탯명)
- [ ] selectbox `key`에 자원 이름 시그니처 포함 → 자원 셋 변경 시 크래시 없음
- [ ] `damage_type_map`을 `st.session_state['damage_type_map']`에 저장
- [ ] 단일 전투 버튼이 `damage_type_map=...`을 `ResourceModule`에 전달
- [ ] Monte Carlo 버튼이 `damage_type_map=...`을 `ResourceModule`에 전달
- [ ] 회귀 검증: `universal_test_log.csv`로 단일 전투 + Monte Carlo 실행 시 베이스라인과 일치 — NoVariance 1v1 lopsided 데미지총량 **620.0**, near-even **1026.0**
