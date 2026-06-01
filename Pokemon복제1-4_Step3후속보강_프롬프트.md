# Pokemon 복제 1/4 · Step 3 (step5_discrepancy.py) 후속 보강

## 문제

직전 두 PR(무브공급, Validator후속보강)이 Step 2의 dict env 평가만 풀었다. main.py가
Step 3 indicator를 `step5_discrepancy.py:render_discrepancy`로 매핑하는데, 이 함수는
사용자 공식을 **pandas DataFrame.eval** 방식으로 평가(step2와 다른 패턴)한다. eval_df
(메인 df의 lowercase copy)에 무브 컬럼이 없어 `move_power * attack / defense` 공식
입력 시 `name 'move_power' is not defined`로 멈춰 Step 3 진행 불가능.

본 PR은 step5_discrepancy.py 단일 파일에 import 1줄 추가와 broadcast 17줄 신규.

(곁가지 분석: step4_role_definition.py와 step3_flow_auditor.py는 main.py가 import 안
함이라 dead code. step2_profiling.py와 step6_dashboard.py는 무브 변수 평가 0건이라
청정. 본 PR로 시연 흐름 끝까지 unblock 완료.)

## 변경 사이트 — 단 2곳

- **Change A**: 모듈 헤더(L1~L4) → import 추가
- **Change B**: try 블록 안 `eval_formula = formula.lower()` 라인(unique 매칭) 직전 broadcast 삽입

곁가지 수정 0건.

## 라인 수 산술

- Change A: 기존 4줄 → 신규 5줄 (+1)
- Change B: 기존 1줄 → 신규 17줄 (+16)
- **총 변경: +17줄** (step5_discrepancy.py 73줄 → 90줄)

## 새 import

`from modules.move_extraction import detect_move_columns, has_move_data` (L3 신규)

이미 step2_system_definition.py L17에서 사용하는 헬퍼와 동일.

---

## Change A — 모듈 헤더 import 추가

### Find (4줄, 정확 일치)

```python
import streamlit as st
import pandas as pd

def render_discrepancy():
```

### Replace (5줄)

```python
import streamlit as st
import pandas as pd
from modules.move_extraction import detect_move_columns, has_move_data

def render_discrepancy():
```

---

## Change B — try 블록 안 broadcast 삽입

`eval_formula = formula.lower()`는 step5_discrepancy.py에 단 한 번 등장하는 unique
라인이라 Find가 정확히 1곳에 매칭. 그 라인 자체는 Replace의 마지막 줄로 그대로
유지(byte-equal 보존).

### Find (1줄, 정확 일치, 들여쓰기 12 스페이스)

```python
            eval_formula = formula.lower()
```

### Replace (17줄)

```python
            # ── Phase 8a: 무브 변수 broadcast (attack_log 보조 진입) ──
            _atk_log_df = st.session_state.get("attack_log_df")
            _mv_src = df if has_move_data(df) else (_atk_log_df if _atk_log_df is not None and has_move_data(_atk_log_df) else None)
            if _mv_src is not None:
                _mv_cols = detect_move_columns(_mv_src)
                _pwr_col = _mv_cols.get("power")
                if _pwr_col and _pwr_col in _mv_src.columns:
                    _pw = pd.to_numeric(_mv_src[_pwr_col], errors="coerce").dropna()
                    _mp = float(_pw.mean()) if len(_pw) else 0.0
                    eval_df["move_power"] = _mp
                    eval_df["target_move_power"] = _mp
                    _bs = st.session_state.get("system_stats", [])
                    if _bs and _bs[0].lower() in eval_df.columns:
                        eval_df["offense"] = eval_df[_bs[0].lower()]
                        eval_df["defense"] = eval_df[_bs[0].lower()]

            eval_formula = formula.lower()
```

---

## 검증 단서 (납품 후 사용자가 확인)

1. **라인 수 산술**: 변경 후 `step5_discrepancy.py` 라인 수 = 73 + 17 = 90
2. **마커 grep 양성** (있어야 함):
   - `from modules.move_extraction import detect_move_columns, has_move_data` (L3 import)
   - `_atk_log_df = st.session_state.get("attack_log_df")`
   - `_mv_src = df if has_move_data(df) else`
   - `eval_df["move_power"] = _mp`
   - `eval_df["target_move_power"] = _mp`
   - `eval_df["offense"] = eval_df[_bs[0].lower()]`
   - `eval_df["defense"] = eval_df[_bs[0].lower()]`
3. **마커 grep 음성**: `eval_formula = formula.lower()`는 변경 후에도 정확히 1건 (이중 등장 없음)
4. **동작 테스트**:
   - Streamlit 재시작 (`Ctrl+C` → `streamlit run main.py`) — 모듈 캐시 reload 필수
   - Step 1 → Step 2 진행, attack_log 업로드 + 공식 `move_power * attack / defense` + 적용
   - Step 3 진입 시 "수식 오류" 없이 anomaly_df 테이블이 노출
   - "다음 단계로" 버튼 활성, Step 4·5 진행 가능

## 제약

- **곁가지 수정 0건**: Change A·B 외 라인 절대 건드리지 않는다.
- **들여쓰기**: Change A는 들여쓰기 없음(모듈 톱 레벨), Change B는 12 스페이스. 탭 금지.
- **session_state 키 신규 0**: `attack_log_df`는 1/4 PR이 도입한 키를 read-only로 사용.
- **DataFrame.eval 패턴 보존**: L32의 `eval_df.eval(eval_formula)` 호출은 건드리지 않는다.
