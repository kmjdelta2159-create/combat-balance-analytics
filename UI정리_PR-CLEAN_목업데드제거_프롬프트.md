# PR-CLEAN — 목업 대시보드 + 데드파일 제거

> 대상: `modules/step6_dashboard.py`(편집) + 파일 3개 삭제.
> 성격: **비기능 코드 제거**. 살아있는 기능·골든·복제 경로엔 영향 0.
> 검증: `ast.parse` + 앱 Step5 로드(목업 섹션 사라짐, import 에러 없음).

---

## 0. 배경 (왜 제거하나)

"🎛️ 가중치 기반 동적 Dashboard (D5 신규)" 섹션은 **실제 시뮬/복제와 통합되지 않은 목업**이다:

- `step6_dashboard.py` L1339 `_state_dict = build_mock_state_from_log(...)` — **mock** 상태 생성.
  화면의 HP(예: 75/100·60/100)·타입차트는 실데이터가 아닌 placeholder다.
- L1329 주석: *"데이터 기반 시연용 (실제 시뮬 통합은 D7~D8)"* — 데모 스텁이고 그 통합은 안 됨.
- 슬라이더를 움직여도 진짜 복제 결과와 무관 → 현재 **아무 역할 없는 가짜 화면**. 사용자에게
  오히려 혼란(가짜 숫자). 슬라이더-구동 적응 UI 비전은 추후 *실제 시뮬과 통합해* 다시 만들면
  되고(설계는 `WeightDrivenUI_설계안.md`에 보존), 이 목업은 남길 이유가 없다.

`modules/ui_registry.py`는 이 목업 전용 모듈(render_weight_panel·render_dynamic_dashboard·
build_mock_state_from_log)이고 **step6 외 어디서도 import하지 않는다** → 목업 제거 시 고아.
`step3_flow_auditor.py`·`step4_role_definition.py`는 main.py·전 모듈이 import하지 않는 데드파일.

---

## 1. 변경 A — `modules/step6_dashboard.py` 편집

### A-1. D5 목업 import 제거 (L27~32)
다음 블록 전체 삭제:
```python
# ── D5 추가: 가중치 기반 동적 Dashboard (D4 설계안 §11) ──
from modules.ui_registry import (
    render_dynamic_dashboard,
    render_weight_panel,
    build_mock_state_from_log,
)
```

### A-2. D5 목업 렌더 블록 제거 (L1327~1346)
`render_dashboard` 함수 끝부분, `return True, ""`(L1348) **직전**의 다음 블록 전체 삭제:
```python
    # ── D5 Phase A: Weight-Driven Dynamic Dashboard (D4 설계안 §8) ──
    # 기존 dashboard 섹션과 *공존*. ...
    # 사이드바 가중치 슬라이더로 미세조정. 데이터 기반 시연용 (실제 시뮬 통합은 D7~D8).
    try:
        st.divider()
        st.markdown("## 🎛️ 가중치 기반 동적 Dashboard (D5 신규)")
        ...
    except Exception as _wddash_err:
        st.warning(f"신규 dashboard 오류 ...: {_wddash_err}")
```
- 삭제 후 함수는 기존 대시보드 렌더 → 곧바로 `return True, ""`로 끝나야 한다(이 return은 **유지**).
- 들여쓰기: 삭제 후 `return True, ""`가 함수 본문 레벨(기존과 동일)에 그대로 있는지 확인.

> A-1·A-2만 하면 step6는 ui_registry를 더는 참조하지 않는다(grep으로 0 확인).

---

## 2. 변경 B — 파일 3개 삭제

- `modules/ui_registry.py` (목업 전용, A 적용 후 고아)
- `modules/step3_flow_auditor.py` (데드 — import 0)
- `modules/step4_role_definition.py` (데드 — import 0)

(모두 main.py·전 모듈에서 import 없음을 grep으로 확인함.)

---

## 3. 불변 (회귀0)
- step6의 **기존** 대시보드(팀 요약표·타입 기여도·스탯 가중치·최적화 등)·골든·복제/시뮬 경로
  전부 불변. 제거 대상은 목업 D5 섹션 + 데드파일뿐.
- `calc_instance_score`(L34)·`calculate_win_rate`(L56) 등 step6 본문 로직 불변.

---

## 4. 검증
1. `python -c "import ast; ast.parse(open('modules/step6_dashboard.py').read())"` — 통과.
2. `grep -n "ui_registry\|render_weight_panel\|render_dynamic_dashboard\|build_mock_state_from_log" modules/step6_dashboard.py` — **0건**(잔존 참조 없음).
3. `streamlit run main.py` → Step5(Dashboard) 진입: 기존 대시보드는 정상, 하단 "🎛️ 가중치 기반
   동적 Dashboard (D5 신규)" 섹션이 **사라짐**. import 에러·트레이스백 없음.
4. `ls modules/` — ui_registry.py·step3_flow_auditor.py·step4_role_definition.py 부재 확인.

---

## 5. 적용 후 보고
- step6 수정 라인 + `wc -l`/`tail` 무결성, 삭제 파일 3개 목록.
- Step5 캡처(목업 섹션 없이 기존 대시보드만 깔끔히).
