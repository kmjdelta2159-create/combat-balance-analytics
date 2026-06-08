# UI정리 PR-S2A-fix — Step2 검토/시작 탭 실배치 + 테스트 import 보정

## 배경

PR-S2A 적용 결과 `modules/step2_system_definition.py`에 Step2 탭 구조는 들어갔다.

현재 확인된 상태:

- `st.tabs(["필수 매핑", "공식 검증", "선택 규칙", "검토/시작"])` 존재
- 필수 매핑 / 공식 검증 / 선택 규칙 탭 분리는 적용됨
- `formula_input_ui`, `ui_move_library_editor`, `ui_channel_`, `ui_mech_` 키 문자열은 보존됨
- `py_compile` 통과
- Step6 export, DB corpus fixture manifest, mismatch report 회귀 테스트 통과

하지만 아직 S2A 완료로 보기 어려운 문제가 있다.

## 문제 1 — `검토/시작` 탭이 실제로 채워지지 않음

현재 파일 기준:

- `with tabs[0]`, `with tabs[1]`, `with tabs[2]`는 있음
- `with tabs[3]`가 없음
- `기획 의도 확립 및 파이프라인 시작` 버튼과 `mapping_preset.json` 다운로드 버튼이 `tabs[3]` 안이 아니라 탭 블록 바깥에 있음

즉 사용자는 네 번째 탭을 보지만, 실제 검토/시작 UI는 탭 안에 들어간 것이 아니다.

### 수정 요구

`modules/step2_system_definition.py`에서 다음 영역을 반드시 `with tabs[3]:` 안으로 옮긴다.

- 현재 설정 요약
- 파이프라인 시작 버튼
- `mapping_preset.json` 다운로드 버튼

최소 구조 예:

```python
with tabs[3]:
    st.markdown("## 검토/시작")
    # selected_target, base_stats, gimmicks, formula_input_ui, optional 설정 요약
    # 기존 시작 버튼 로직
    # 기존 preset 다운로드 로직
```

주의:

- 버튼 내부 저장 로직은 기존과 동일해야 한다.
- `mapping_approved`, `target_col`, `target_variable`, `system_stats`, `system_gimmicks`,
  `global_damage_formula`, `damage_formula`, `tag_mapping`, `pipeline_impute_strategy`,
  `move_library`, `game_config`, `combat_flow`, `validation_warnings` 계약을 바꾸지 말 것.
- `선택 규칙` 탭의 고급 설정 기능을 삭제하지 말 것.
- `검토/시작` 탭 안에는 현재 선택값이 한눈에 보이도록 짧은 summary를 넣을 것.
  예: target, base stats count/list, gimmicks count/list, formula, optional rule summary.

## 문제 2 — 상단 Step2 Setup summary가 현재 선택값보다 저장된 session_state를 우선 읽음

현재 summary는 `target_col`, `system_stats`, `system_gimmicks` 같은 확정 저장값을 읽는다.
하지만 mapping 승인 전에는 사용자가 탭에서 고른 현재 선택값이 아직 이 canonical key에 저장되지 않는다.

이 때문에 첫 화면 summary가 실제 선택 UI와 어긋날 수 있다.

### 수정 요구

가능하면 Step2 임시 위젯 key를 도입해 summary가 현재 선택값을 반영하게 한다.

권장:

- target selectbox에 `key="ui_step2_target_col"`
- base stats multiselect에 `key="ui_step2_base_stats"`
- gimmicks multiselect에 `key="ui_step2_gimmicks"`
- summary는 이 임시 key가 있으면 우선 사용하고, 없으면 기존 canonical session_state를 fallback으로 사용

단, canonical key는 파이프라인 시작 버튼을 누를 때만 기존처럼 저장한다.

## 문제 3 — `test_step2_system_definition_layout.py`가 heavy import 때문에 실패

현재 테스트는 helper 확인을 위해 아래처럼 전체 Step2 모듈을 import한다.

```python
from modules.step2_system_definition import _step2_completion_state, _step2_optional_summary
```

이 환경에서는 import 과정에서 `sklearn.cluster._dbscan_inner` DLL 로드가 차단되어 테스트가 실패한다.

실패 예:

```text
ImportError: DLL load failed while importing _dbscan_inner:
애플리케이션 제어 정책에서 이 파일을 차단했습니다.
```

이 테스트는 UI layout/helper source guard가 목적이므로 sklearn/streamlit 전체 import에 의존하면 안 된다.

### 수정 요구

`test_step2_system_definition_layout.py`를 source-light 방식으로 바꾼다.

허용 방식:

1. `ast.parse()`로 `modules/step2_system_definition.py`를 읽는다.
2. `_step2_completion_state`, `_step2_optional_summary` 함수 정의 노드만 추출한다.
3. 그 함수 노드만 `compile/exec`해서 테스트한다.

이렇게 하면 top-level `streamlit`, `sklearn` import를 실행하지 않아도 된다.

또한 source guard를 강화한다.

필수 assert:

- `st.tabs([` 존재
- `"필수 매핑"`, `"공식 검증"`, `"선택 규칙"`, `"검토/시작"` 존재
- `"with tabs[3]"` 존재
- `"기획 의도 확립 및 파이프라인 시작"` 존재
- `"mapping_preset.json"` 존재
- 기존 key 문자열 보존:
  - `formula_input_ui`
  - `ui_move_library_editor`
  - `ui_channel_`
  - `ui_mech_`

## 검증 명령

```powershell
$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -X utf8 -m py_compile modules/step2_system_definition.py test_step2_system_definition_layout.py
& $py -X utf8 test_step2_system_definition_layout.py
& $py -X utf8 test_step6_export_schema_cli_roundtrip.py
& $py -X utf8 test_db_corpus_fixture_manifest.py
& $py -X utf8 test_step6_mismatch_report.py
```

## 완료 기준

- 새 layout 테스트가 DLL import 없이 통과
- `with tabs[3]`가 실제 코드에 존재
- 시작 버튼과 preset 다운로드가 `검토/시작` 탭 안에 있음
- 기존 Step6/DB corpus 회귀 테스트 통과
- 기능 삭제 없이 Step2 필수 흐름과 선택 규칙 분리가 유지됨
