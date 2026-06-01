# 엔진 추출 리팩토링 — `step6_dashboard.py` → `modules/engine.py`

## 배경 / 목표
Phase 4(Spatial Module) 착수 전 정지(整地) 작업. 전투 엔진 코어가 현재 74KB UI 파일
`modules/step6_dashboard.py` 안에 물리적으로 들어 있어, 엔진을 import하면 Streamlit이
딸려온다. 엔진 코드를 신규 모듈 `modules/engine.py`로 분리한다.

**이것은 순수 relocation 리팩토링이다 — 코드 로직·문자열·숫자·공식을 한 글자도 바꾸지 않는다.**
"개선"·하드코딩 수정·태그 정리 일절 금지. 코드를 그대로 옮기기만 한다.

## 변경 파일 (정확히 2개)
- **신규**: `modules/engine.py`
- **수정**: `modules/step6_dashboard.py` (엔진 블록 삭제 + import 1줄 추가)
- 그 외 모든 파일 무수정. (확인 완료: `main.py`는 `render_dashboard`만 import, `validation.py`는 엔진 미사용, 다른 어떤 파일도 step6에서 엔진 심볼을 import하지 않음)

---

## 추출 대상 — `step6_dashboard.py` 22~710행 (연속 블록 전체)

경계가 깔끔하다. **22행**(`element_chart = {`)에서 시작해 **710행**(`return winner, logs, sim_metrics`)에서 끝나는 연속 블록 전체가 엔진이다. 711행 빈 줄 다음 **712행 `def calc_instance_score(`부터는 UI 코드**이므로 step6에 그대로 남긴다.

이 블록에 포함된 것 (전부 그대로 이동):
- `element_chart`, `get_element_multiplier`
- `import re as _re`, `DEFAULT_COMBAT_FLOW`, `_KOREAN_TO_KEY`, `_ENGLISH_HINTS`, `_parse_action_key`
- `_CHAR_LEVEL_KEYS`, `_TARGET_LEVEL_KEYS`, `_PIVOT_KEY`, `_PHASE_TO_EVENT`
- `get_effective_stat`, `_notify_event`, `_broadcast_phase_event`, `_track_state`
- 액션 함수 9개: `_act_passive_start`, `_act_stat_calc`, `_act_target_select`, `_act_damage_calc`, `_act_element_mult`, `_act_crit_calc`, `_act_apply_damage`, `_act_on_hit`, `_act_death_check`
- `NON_ACTING_TRIGGERS`, `_normalize_target_tag`
- `DEFAULT_ACTION_REGISTRY.register(...)` 9줄 (451~459행)
- `default_stochasticity_factory`, `_worker_simulate_match`, `run_monte_carlo`, `run_simulation` (내부 중첩 함수 `build_ctx` 포함)

이 블록 안에 `st.` 코드 참조는 없다 (561행에 주석 1개뿐) — 엔진은 이미 Streamlit-free다.

---

## `modules/engine.py` 작성 방법

1. 파일 맨 위에 import 헤더를 추가한다. 이동하는 블록이 의존하지만, 그 import문은
   step6 상단(1~20행)에 있어 블록과 함께 따라오지 않으므로 새로 써 줘야 한다:

   ```python
   import copy
   import os
   import concurrent.futures
   import traceback
   from modules.action_registry import ActionRegistry, DEFAULT_ACTION_REGISTRY
   from modules.turn_manager import SequentialTurnManager
   from modules.stochasticity import StochasticityModule, NoVariance
   from modules.resource import get_current, get_max, apply_delta, ResourceModule
   from modules.win_condition import ResourceDepletion
   ```

2. 그 아래에 step6 22~710행 블록을 **그대로(verbatim)** 붙인다.
   블록 안의 `import re as _re`(40행), `_act_damage_calc` 내부의 지역 `import math`는
   그대로 둔다 (중복처럼 보여도 무해, 건드리지 말 것).

3. **engine.py는 `streamlit`/`pandas`/`numpy`/`plotly`/`scipy`를 import하지 않는다.** 이것이 추출의 핵심 목적이다.

---

## `modules/step6_dashboard.py` 수정 방법

1. 22~710행 블록 전체를 삭제한다.

2. import 구역(1~20행 근처)에 다음 1줄을 추가한다:

   ```python
   from modules.engine import run_simulation, run_monte_carlo, default_stochasticity_factory, DEFAULT_COMBAT_FLOW
   ```

   UI가 참조하는 엔진 심볼은 이 **4개뿐**이다 (grep 확인 완료):
   `run_simulation`(1231행), `run_monte_carlo`(1264행),
   `default_stochasticity_factory`(1269행), `DEFAULT_COMBAT_FLOW`(1223행).
   `element_chart`는 1329행에 문자열 리터럴 `"element_chart"`로만 등장하므로 코드 참조가 아니다 — import 불필요.

3. step6의 기존 import문(1~20행)은 **그대로 둔다.** 엔진 이동으로 일부가 미사용이 되지만
   무해하다 — 제거는 선택사항이며, 잘못 지우면 깨지므로 차라리 두는 편이 안전하다.
   특히 `from modules.resource import ... ResourceModule`은 UI(1235·1270행)가 쓰므로 **반드시 유지**.

---

## 핵심 제약 — Pickling (멀티프로세싱 안전성)

- `run_simulation` / `run_monte_carlo` / `_worker_simulate_match` /
  `default_stochasticity_factory` / 9개 `_act_*` 함수는 engine.py의 **모듈 최상위 레벨**에
  둔다. 다른 함수 안에 중첩 금지.
- `_worker_simulate_match`는 Windows spawn 워커가 pickle해야 하므로 모듈 레벨 필수.
  `build_ctx`는 `run_simulation` 내부 중첩 함수 그대로 둔다 — 워커로 전달되지 않으므로 문제없음.
- 과거 교훈: `default_stochasticity_factory`가 클로저였을 때 Windows spawn에서 Pickling
  에러가 났고, 모듈 레벨로 옮겨 해결했다. engine.py에서도 반드시 모듈 레벨 유지.
- `DEFAULT_ACTION_REGISTRY.register(...)` 9줄은 engine.py 모듈 본문에 있어야 import 시
  1회 등록된다. spawn 워커가 engine.py를 재import해도 새 인터프리터 → 새 레지스트리 →
  1회만 등록되므로 중복 등록 `ValueError`는 발생하지 않는다 (현행과 동일한 동작).

---

## 동작 100% 동일성 — 회귀 검증

순수 relocation이므로 시뮬레이션 결과가 **완전히 동일**해야 한다.
검증 베이스라인 (1v1, 공격자 Vit500/Phys100/Arm30/Spd50, 공식
`phys_power - target_armor_class`, `DEFAULT_COMBAT_FLOW`, 전원 `Active_Cast`/`Single_Target`):

- **NoVariance**: lopsided(적 Vit400/Phys70/Arm30/Spd40) 데미지총량 **620.0** /
  near-even(적 Vit500/Phys100/Arm33/Spd49) **1026.0**
- **DamageVariance(±10%) 300회**: lopsided 승률 **100%** / near-even **85%**
- **HitChance(85%)**: lopsided **100%** / near-even **61%**

`universal_test_log.csv`로 단일 전투 + 1만회 Monte Carlo를 실행해 추출 전과 동일한
결과가 나오는지 확인한다.

---

## 완료 기준 체크리스트

- [ ] `modules/engine.py` 신규 생성 — import 헤더 + step6 22~710행 블록 verbatim
- [ ] engine.py가 streamlit/pandas/numpy/plotly/scipy를 import하지 않음
- [ ] `modules/step6_dashboard.py`에서 22~710행 삭제, `from modules.engine import ...` 4심볼 1줄 추가
- [ ] 변경 파일이 정확히 2개 (engine.py 신규, step6 수정) — 그 외 모든 파일 무수정
- [ ] `python -c "import modules.engine"` 가 에러 없이 통과
- [ ] step6에 `NameError` 없음 — 참조되는 엔진 심볼이 전부 import됨
- [ ] 엔진 함수가 전부 engine.py 모듈 최상위 레벨 — 중첩/클로저 없음 (`build_ctx`만 예외, 원래 중첩)
- [ ] 코드 로직·문자열·숫자·공식 변경 0건 (순수 이동)
- [ ] 단일 전투 결과가 추출 전과 동일
- [ ] Monte Carlo(1만회, 멀티프로세싱) 정상 동작 + 결과 동일 — Pickling 에러 없음
- [ ] 회귀 베이스라인 일치: NoVariance 620.0 / 1026.0
