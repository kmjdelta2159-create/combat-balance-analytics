# UI정리 PR-S2A — Step2 필수 흐름 가독성 개편

## 배경

현재 Step2(`modules/step2_system_definition.py`)는 기능은 많지만, UI/UX 가독성과 편의성이 좋지 않다.

스크린샷 기준 문제:

- 첫 화면에서 사용자가 “지금 무엇을 하면 다음 단계로 갈 수 있는지” 바로 알기 어렵다.
- 필수 입력(타깃/스탯/기믹/데미지 공식)과 선택 입력(무브 시스템/타입 상성/태그/채널/메커니즘)이 한 화면에 길게 이어진다.
- `시스템 세부 정의 (선택)` 아래에 Move System, 타입 상성표, Tag Dictionary, Logic Execution Order, Channel Mapping, Mechanism Attach가 모두 이어져 스크롤 피로가 크다.
- 흰색 Streamlit 기본 입력 박스/expander가 어두운 배경 위에 길게 반복되어 화면 밀도가 높고 눈이 피곤하다.
- 고급 기능은 좋은데, 처음 보는 사용자는 이것이 “필수인지 선택인지” 판단하기 어렵다.

이 작업은 Streamlit을 버리는 작업이 아니다.
1차 목표 종료 후 UI/UX 정리의 첫 조각으로, **Step2의 정보 구조를 다듬어 현재 검증 콘솔에서 덜 헷갈리게 만드는 작업**이다.

## 목표

Step2를 다음 흐름으로 재구성한다.

```text
상단 요약/체크리스트
→ 필수 매핑: target, base stats, gimmicks, imputation
→ 공식 검증: damage formula 입력/검증/자동 추정
→ 선택 규칙: move/type/tag/channel/mechanism/execution order
→ 검토 후 파이프라인 시작
```

핵심은 기능 삭제가 아니라 **필수 흐름과 고급 설정을 시각적으로 분리**하는 것이다.

## 구현 요구사항

### 1. Step2 상단에 상태 요약 추가

`render_system_definition()`의 mapping 승인 전 화면 상단에 compact summary/checklist를 추가한다.

권장 표시:

- 데이터 행 수
- target 선택 여부
- base stats 개수
- gimmicks 개수
- formula 입력 여부/검증 여부
- optional rule 설정 여부(move_library/game_config 등)

예시:

```text
Step2 Setup
[Target: OK] [Stats: 6] [Gimmicks: 2] [Formula: Needed] [Optional Rules: Auto]
```

Streamlit에서는 `st.columns`, `st.metric`, `st.caption`, `st.status` 중 기존 스타일과 잘 맞는 방식을 사용한다.

주의:

- 새 summary는 설명문을 길게 쓰지 말 것.
- 화면 첫 viewport에서 “무엇이 부족한지” 보이게 한다.

### 2. 필수/선택 UI를 탭으로 분리

mapping 승인 전 Step2 본문을 `st.tabs`로 나눈다.

권장 탭:

1. `필수 매핑`
2. `공식 검증`
3. `선택 규칙`
4. `검토/시작`

각 탭 배치:

#### 필수 매핑

현재의 다음 UI를 이 탭에 둔다.

- 원본 데이터 샘플 expander
- 타깃 변수
- 기본 스탯 & 기믹
- 결측치 채우기

원본 데이터 샘플은 기본 collapsed 유지.

#### 공식 검증

현재의 다음 UI를 이 탭에 둔다.

- 변수 chip/pills
- damage formula text input
- formula eval 결과
- symbolic regression/자동 추정 후보

중요:

- 공식이 없으면 이 탭에만 경고를 표시하고, 첫 화면 전체를 노란 경고로 압도하지 않는다.
- `formula_input_ui` 세션 키는 그대로 유지한다.

#### 선택 규칙

현재의 다음 UI를 이 탭 안에서 다시 expander로 나눈다.

- Move System
- 타입 상성표/STAB
- Tag Dictionary Mapping
- Logic Execution Order
- Channel Mapping
- Mechanism Attach

주의:

- 기존 기능을 제거하지 말 것.
- 기존 `st.session_state` 키를 바꾸지 말 것.
- expander가 너무 많아도 지금보다 낫다. 단, 기본 collapsed를 적극 사용한다.
- 가능하면 `Move System` 안의 타입 상성표를 별도 expander로 분리한다.

#### 검토/시작

마지막 탭에는 현재 설정 summary와 버튼을 둔다.

- 선택된 target
- base stats 리스트
- gimmicks 리스트
- formula
- optional 설정 요약
- `기획 의도 확립 및 파이프라인 시작` 버튼
- `mapping_preset.json` 다운로드 버튼

주의:

- 기존 primary button 동작을 유지한다.
- `mapping_approved`, `target_col`, `system_stats`, `system_gimmicks`, `global_damage_formula`, `damage_formula`, `tag_mapping`, `pipeline_impute_strategy`, `move_library`, `game_config` 저장 계약을 유지한다.

### 3. 기존 저장/세션 계약 유지

다음 키와 의미를 깨지 말 것.

- `mapping_approved`
- `formula_input_ui`
- `global_damage_formula`
- `damage_formula`
- `target_col`
- `target_variable`
- `system_stats`
- `system_gimmicks`
- `tag_mapping`
- `pipeline_impute_strategy`
- `move_library`
- `game_config`
- `combat_flow`
- `validation_warnings`

Step6/CLI/export/corpus 테스트가 이 값에 의존한다.

### 4. 작은 helper 추가

가능하면 UI 로직 일부를 테스트 가능한 helper로 뺀다.

권장 helper:

- `_step2_completion_state(selected_target, base_stats, gimmicks, formula_text)`
- `_step2_optional_summary(move_library_edited, game_config_like)`

테스트에서 직접 호출 가능해야 한다.

`_step2_completion_state`는 최소 다음 형태를 반환한다.

```python
{
    "target_ok": bool,
    "stats_ok": bool,
    "formula_ok": bool,
    "can_start": bool,
}
```

`can_start`는 기존 `is_valid` 의미와 충돌하지 않게 한다.
공식 검증 성공 여부가 기존 `is_valid`를 결정한다면 그 흐름을 유지하되, summary에서는 “formula needed/ok”로 표시한다.

### 5. 테스트 추가

권장 파일:

- `test_step2_system_definition_layout.py`

최소 테스트:

1. `_step2_completion_state("Is_Victorious", ["HP"], ["Type"], "attack - defense")`
   - target/stats/formula OK
2. target 없음
   - `target_ok is False`
3. formula 없음
   - `formula_ok is False`
4. source guard
   - `modules/step2_system_definition.py`에 `st.tabs`가 있는지
   - 탭 라벨 `필수 매핑`, `공식 검증`, `선택 규칙`, `검토/시작`이 있는지
   - 기존 key 문자열 `formula_input_ui`, `ui_move_library_editor`, `ui_channel_`, `ui_mech_`가 남아 있는지

### 6. 시각 검증

가능하면 로컬 Streamlit에서 Step2를 열어 다음을 확인한다.

- 첫 viewport에서 상단 summary와 탭이 보인다.
- 필수 매핑 탭이 스크린샷보다 덜 과밀하다.
- 선택 규칙 탭으로 들어가기 전까지 Move/Type/Mechanism 고급 설정이 사용자를 압도하지 않는다.
- 파이프라인 시작 버튼은 검토/시작 탭에 있다.
- 기존 Step2를 완료하고 Step3로 넘어가는 흐름이 깨지지 않는다.

브라우저 자동 검증이 가능하면 screenshot을 확인한다.

## 금지사항

- Streamlit 전체 구조를 교체하지 말 것.
- Step2 기능을 삭제하지 말 것.
- `game_config`/`move_library` 저장 계약을 바꾸지 말 것.
- Step6, DB corpus, mechanism RE 로직을 건드리지 말 것.
- 대규모 CSS 테마 변경을 하지 말 것.
- 카드 안에 카드를 중첩하지 말 것.
- 랜딩 페이지처럼 만들지 말 것.

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

- Step2가 필수 매핑/공식 검증/선택 규칙/검토 시작의 흐름으로 분리된다.
- 처음 보는 사용자가 필수 입력과 선택 고급 설정을 구분할 수 있다.
- 기존 Step2 기능과 세션 저장 계약이 유지된다.
- 새 helper 테스트와 기존 핵심 regression 테스트가 통과한다.
