# DB코퍼스 PR-UI5c unifyStructuredPackageWithNormalWorkflow 프롬프트

## 역할

너는 이 저장소의 UI/UX 및 플로우 구현을 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수와 프롬프트 작성만 담당한다.

이번 작업은 `pokemon_showdown_db_extract.zip` 같은 구조화 전투 데이터 패키지를 일반 파일 흐름과 다른 별도 UI로 분리하면서 생긴 문제를 해결한다.

## 현재 문제

사용자 확인 결과:

1. Step2가 자동 추론 결과를 알려주기만 하고 수정할 방법이 없다.
2. 사용자는 자동 적용된 값이 맞는지 판단하거나 고칠 수 없다.
3. Step3에서 `리플레이 검증 실행`을 누르면 에러가 난다.

현재 Step3 에러:

```text
TypeError: run_db_corpus_backtest_from_session() missing 1 required positional argument: 'session_state_like'
modules/step5_discrepancy.py line 26
summary, mismatches = run_db_corpus_backtest_from_session()
```

즉, DB/ZIP용 Step2/Step3을 별도로 만들었지만 기존 검증 함수와 세션 계약이 맞지 않아 깨지고 있다.

## 핵심 판단

DB/ZIP 전투 데이터 패키지도 일반 파일과 같은 Step2/Step3 UI 흐름을 가져가야 한다.

문제 생기는 것이 아니라, 오히려 그게 맞다.

- 일반 CSV: 빈 값에서 사용자가 매핑/수식/검증을 구성
- DB/ZIP 패키지: 자동 추론값을 Step2 UI에 prefill하고 사용자가 수정 가능

즉, DB/ZIP은 별도 UI가 아니라 **자동 추천값이 채워진 일반 복제 workflow**여야 한다.

## 목표

DB/ZIP 패키지 모드에서도 Step2/Step3을 일반 파일과 동일한 UX 원칙으로 통합하라.

- Step2: 일반 Step2와 같은 수정 가능한 매핑 UI 사용
- Step2 기본값: DB/ZIP 자동 추론 schema로 prefill
- Step3: 일반 Step3과 같은 검증 단계 UI 사용
- Step3 검증 기준: formula discrepancy 또는 replay validation 중 현재 데이터에 맞는 검증을 선택/표시
- 함수 호출 에러 제거

## P0. Step2를 editable auto-prefill UI로 바꿔라

현재처럼 자동 추론 결과만 보여주고 승인 버튼만 있는 화면은 실패다.

DB/ZIP 모드에서도 Step2에서 사용자가 다음을 수정할 수 있어야 한다.

- target/result column
- stats/resource columns
- gimmick/category columns
- health stat
- battle id column
- turn column
- actor id column
- target id column
- move/action column
- state HP/status/fainted columns
- switch/faint 관련 columns

구현 방식:

- 일반 Step2 UI 컴포넌트를 가능한 한 재사용하라.
- DB/ZIP schema에서 감지된 값을 default로 넣어라.
- 자동 감지된 값은 badge/caption으로 표시하되 수정 가능해야 한다.
- 사용자가 수정 후 `시스템 정의 확정` 또는 기존 파이프라인 시작 버튼을 누르면 session_state에 반영하라.

수용 기준:

- DB/ZIP 모드 Step2에서 selectbox/multiselect가 read-only가 아니다.
- 자동 추론값을 수정할 수 있다.
- 일반 CSV 모드 Step2와 UX가 크게 다르지 않다.
- DB/ZIP 자동 schema는 default value로만 작동한다.

## P0. Step2 자동 추론 설명은 보조 정보로 낮춰라

자동 추론 정보는 필요하지만, 화면의 본체가 되면 안 된다.

권장:

- 상단에 `자동 감지된 전투 데이터 구조를 기본값으로 채웠습니다. 필요하면 수정하세요.`
- 상세 schema는 expander나 하단 요약으로 둔다.
- 주요 입력은 editable control이어야 한다.

## P0. Step3 검증 UI를 일반 흐름과 통합하라

현재 Step3 별도 리플레이 검증 버튼이 함수 인자 오류로 깨진다.

필수 수정:

- `run_db_corpus_backtest_from_session()` 호출 시 필요한 `session_state_like`를 전달하라.
- 함수 시그니처를 확인하고 기존 Step6/대시보드에서 사용하는 방식과 동일하게 호출하라.
- Step3에서 새로운 검증 함수를 임의로 만들기보다 기존 backtest/replay validation helper를 재사용하라.

예상 수정 방향:

```python
summary, mismatches = run_db_corpus_backtest_from_session(st.session_state)
```

단, 실제 함수 정의를 확인하고 정확히 맞춰라.

## P0. Step3 검증 모드

Step3은 mode에 따라 다음처럼 동작하라.

### 일반 로그 모드

- 기존 formula discrepancy 유지
- `damage_formula` 필요
- formula가 없으면 traceback 대신 안내

### DB/ZIP 패키지 모드

- replay/backtest 검증 사용
- `damage_formula`가 없어도 됨
- 사용자가 Step2에서 수정한 schema/mapping을 반영해 검증 실행
- mismatch summary와 상세를 표시

수용 기준:

- DB/ZIP 모드 Step3에서 `damage_formula` KeyError 없음
- DB/ZIP 모드 Step3에서 `run_db_corpus_backtest_from_session` TypeError 없음
- Step2 수정값이 Step3 검증에 반영됨
- 일반 로그 Step3은 기존 기능 유지

## P0. "다른 파일과 UI를 똑같이" 가져가는 기준

사용자가 말한 방향을 구현 기준으로 삼아라.

DB/ZIP이라도:

- Step2는 같은 mapping/system definition 화면을 사용한다.
- 단, default가 자동 감지값이다.
- 사용자가 수정 가능하다.
- Step3는 같은 검증 단계로 보인다.
- 단, 검증 엔진은 데이터 모드에 맞게 formula discrepancy 또는 replay validation을 사용한다.

즉, UI는 통합하고 내부 엔진만 mode에 따라 분기한다.

## P1. 교수 시연 흐름

시연 파일:

- `pokemon_showdown_db_extract.zip`

원하는 시연:

1. Step1 업로드
2. Step2에 자동 감지된 전투 구조가 기본값으로 채워짐
3. 사용자가 필요하면 값 수정 가능
4. Step2 확정
5. Step3에서 replay/backtest 검증 실행
6. mismatch/accuracy/pass summary 표시
7. Dashboard 이동

교수 앞 설명:

```text
구조화된 리플레이 패키지는 자동 역설계 비중이 높기 때문에 기본 매핑이 자동으로 채워집니다.
하지만 일반 파일과 같은 Step2에서 사용자가 검토하고 수정할 수 있습니다.
Step3에서는 그 정의를 바탕으로 실제 이벤트 재현 검증을 수행합니다.
```

## 테스트 요구사항

필수 실행:

```powershell
python -m py_compile main.py modules/step1_upload.py modules/step2_system_definition.py modules/step5_discrepancy.py modules/step6_dashboard.py modules/ui_db_corpus_helper.py
python test_step1_db_corpus_upload_adapter.py
python test_step6_db_corpus_auto_schema.py
python test_step6_db_corpus_oneclick_backtest.py
python test_db_corpus_ui_state.py
python test_i15_integration_smoke.py
```

추가 테스트 작성/보강:

- `test_step2_structured_package_editable_defaults.py`
- `test_step3_structured_package_backtest_call.py`

필수 케이스:

- DB/ZIP mode Step2 controls가 자동값으로 prefill됨
- DB/ZIP mode Step2 값 수정 후 session_state에 반영됨
- DB/ZIP mode Step3이 `run_db_corpus_backtest_from_session(st.session_state)` 또는 정확한 인자 방식으로 호출됨
- DB/ZIP mode Step3에서 TypeError 없음
- 일반 로그 mode Step2/Step3 회귀 없음

## 실제 화면 검수

필수 스크린샷:

- `.codex_tmp/ui5c_unified_workflow/step1_zip_uploaded.png`
- `.codex_tmp/ui5c_unified_workflow/step2_editable_prefilled_schema.png`
- `.codex_tmp/ui5c_unified_workflow/step2_modified_schema.png`
- `.codex_tmp/ui5c_unified_workflow/step3_replay_validation_result.png`
- `.codex_tmp/ui5c_unified_workflow/dashboard_after_validation.png`

검수 체크리스트:

- Step2가 read-only 안내 화면이 아닌가
- Step2 자동값을 수정할 수 있는가
- Step3 replay validation 실행 시 TypeError가 없는가
- Step3이 Step2 수정값을 반영하는가
- 일반 CSV 흐름이 깨지지 않았는가

## 검수요약 문서

루트에 아래 파일을 작성하라.

- `DB코퍼스_UI5c_unifyStructuredPackageWithNormalWorkflow_검수요약.md`

포함:

- 수정 파일
- Step2 통합 UI 방식
- 자동 schema prefill 항목
- 사용자 수정 가능 항목
- Step3 검증 함수 호출 수정
- 일반 로그 모드 회귀 확인
- 테스트 결과
- 스크린샷 경로
- 남은 이슈

## 완료 보고 형식

```text
UI5c 완료 보고

1. 수정 파일
- ...

2. Step2 통합
- 일반 UI 재사용:
- 자동 prefill:
- 수정 가능 항목:

3. Step3 검증
- 함수 호출 수정:
- replay validation 결과:
- TypeError 해결:

4. 일반 로그 회귀 확인
- ...

5. 테스트 결과
- ...

6. 스크린샷
- ...

7. 남은 이슈
- ...
```
