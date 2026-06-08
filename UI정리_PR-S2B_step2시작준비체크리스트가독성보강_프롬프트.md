# UI정리 PR-S2B — Step2 시작 준비 체크리스트/가독성 보강

## 배경

PR-S2A/S2A-fix로 Step2는 다음 구조까지 정리됐다.

- `필수 매핑`
- `공식 검증`
- `선택 규칙`
- `검토/시작`

검증 결과:

- `modules/step2_system_definition.py` py_compile 통과
- `test_step2_system_definition_layout.py` 통과
- `test_step6_export_schema_cli_roundtrip.py` 통과
- `test_db_corpus_fixture_manifest.py` 통과
- `test_step6_mismatch_report.py` 통과
- `test_step6_db_corpus_schema_export.py` 통과
- `test_i15_integration_smoke.py` 통과
- `test_db_corpus_backtest_report.py` 통과
- `test_mechanism_detect_aliases.py` 통과

이제 구조 분리는 완료됐지만, Step2의 사용성은 아직 한 단계 더 다듬을 필요가 있다.

현재 남은 UX 문제:

- 첫 진입 시 상단 `Step2 Setup` 요약이 실제 기본 선택값과 어긋날 수 있다.
  - 예: target selectbox에는 자동 추론값이 잡히지만, 상단 summary는 아직 `Target: Needed`로 보일 수 있음.
- `검토/시작` 탭은 생겼지만, 사용자가 “왜 시작 버튼이 비활성인지”를 한눈에 보기 어렵다.
- 시작 조건이 `is_valid` 중심이라 target/stats/formula 준비 상태가 UI에서 명확히 연결되지 않는다.
- 선택한 stats/gimmicks가 많으면 검토 화면에서 길게 나열되기 쉽다.

이 PR은 기능 추가가 아니라 **Step2의 시작 준비 상태를 읽히게 만드는 UI/UX 보강**이다.

## 목표

Step2에서 사용자가 다음을 즉시 이해하게 한다.

```text
1. 지금 필수 매핑이 충분한가?
2. 공식은 입력됐고 실제 계산 가능한가?
3. 선택 규칙은 자동 상태인가, 수동 설정이 들어갔는가?
4. 시작 버튼이 꺼져 있다면 왜 꺼져 있는가?
```

## 수정 요구 1 — 첫 렌더 summary와 기본 선택값 동기화

`render_system_definition()`에서 summary를 그리기 전에 기본 선택 후보를 먼저 계산하고, 임시 UI key를 초기화한다.

권장 helper:

```python
def _step2_default_mapping_state(df, char_col, numeric_cols):
    ...
    return {
        "target": inferred_target_or_None,
        "base_stats": [...],
        "gimmicks": [...],
    }
```

동작:

- `ui_step2_target_col`이 없으면 inferred target으로 초기화
- `ui_step2_base_stats`가 없으면 target 제외 numeric cols로 초기화
- `ui_step2_gimmicks`가 없으면 char/target/base_stats 제외 컬럼으로 초기화
- 이후 summary는 이 UI key를 우선 읽는다.

주의:

- canonical key인 `target_col`, `system_stats`, `system_gimmicks`는 **파이프라인 시작 버튼을 누를 때만** 저장한다.
- 기존 `mapping_approved` 계약을 바꾸지 말 것.

## 수정 요구 2 — 시작 준비 상태 helper 추가

`_step2_completion_state(...)`를 확장하거나 별도 helper를 추가한다.

권장:

```python
def _step2_readiness_state(selected_target, base_stats, formula_text, formula_eval_ok):
    return {
        "target_ok": bool,
        "stats_ok": bool,
        "formula_text_ok": bool,
        "formula_eval_ok": bool,
        "can_start": bool,
        "blocking_reasons": [...],
    }
```

`can_start`는 최소한 다음을 모두 만족해야 한다.

- target 선택됨
- base stats 1개 이상
- formula text 존재
- formula eval 성공

기존 `is_valid`는 formula eval 성공 여부로 유지해도 되지만, 버튼 disabled에는 readiness의 `can_start`를 사용한다.

## 수정 요구 3 — 상단 summary를 준비 상태 중심으로 정리

상단 `Step2 Setup`은 길게 설명하지 말고 compact하게 유지한다.

권장 예:

```text
Step2 Setup | Target OK | Stats 6 | Formula OK | Optional Auto
```

또는 `st.columns`/`st.metric`을 써도 된다.

단, 화면 첫 viewport를 과하게 먹지 말 것.

## 수정 요구 4 — `검토/시작` 탭을 실제 체크리스트로 보강

`with tabs[3]:` 내부에 다음을 추가한다.

### 필수 체크

짧은 체크리스트:

- Target
- Base Stats
- Formula Text
- Formula Eval

각 항목은 `OK / Needed / Error` 정도로 표시한다.

시작 불가면 `blocking_reasons`를 짧게 보여준다.

예:

```text
시작 전 확인
Target: OK — Is_Victorious
Stats: OK — 6 columns
Formula: Error — 수식 계산 실패
```

### 선택 규칙 요약

다음 항목을 1-2줄로만 보여준다.

- move_library 설정 여부/개수
- type table/STAB 설정 여부
- channel mapping 수동 지정 개수
- mechanism 설정 여부
- switch 설정 여부

긴 JSON이나 전체 테이블을 여기서 다시 보여주지 말 것.

### 선택값 표시

stats/gimmicks는 너무 길게 나열하지 않는다.

권장 helper:

```python
def _short_list(items, limit=8):
    ...
```

예:

```text
Stats: HP, Attack, Defense, SpAtk, SpDef, Speed
Gimmicks: Type1, Type2 (+4)
```

## 수정 요구 5 — 테스트 보강

`test_step2_system_definition_layout.py`는 heavy import 없이 유지한다.

기존 `ast` 기반 helper 추출 방식을 유지하고, 다음 테스트를 추가한다.

1. `_step2_readiness_state(...)` 또는 확장된 helper가 있다면:
   - target/stats/formula/eval OK → `can_start True`
   - target 없음 → `can_start False`, blocking reason 존재
   - formula eval 실패 → `can_start False`, blocking reason 존재

2. source guard:
   - `ui_step2_target_col`
   - `ui_step2_base_stats`
   - `ui_step2_gimmicks`
   - `with tabs[3]:`
   - `blocking_reasons` 또는 equivalent reason list
   - `disabled=not`이 `can_start` 계열 readiness 값을 참조하는지 확인

## 금지 사항

- Step2 기능 삭제 금지
- Step6/DB corpus/mechanism RE 로직 수정 금지
- `game_config`/`move_library` 저장 스키마 변경 금지
- Streamlit 전체 구조 교체 금지
- CSS 대규모 테마 변경 금지
- 새 외부 dependency 추가 금지

## 검증 명령

```powershell
$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -X utf8 -m py_compile modules/step2_system_definition.py test_step2_system_definition_layout.py
& $py -X utf8 test_step2_system_definition_layout.py
& $py -X utf8 test_step6_export_schema_cli_roundtrip.py
& $py -X utf8 test_db_corpus_fixture_manifest.py
& $py -X utf8 test_step6_mismatch_report.py
& $py -X utf8 test_i15_integration_smoke.py
```

## 완료 기준

- 첫 렌더 summary가 기본 선택값과 어긋나지 않음
- `검토/시작` 탭에서 시작 가능/불가능 이유를 한눈에 볼 수 있음
- 시작 버튼은 target/stats/formula/eval 준비가 모두 OK일 때만 활성
- 기존 세션 저장 계약 유지
- 기존 회귀 테스트 통과
