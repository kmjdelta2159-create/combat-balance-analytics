# DB코퍼스 PR-UI5b autoSchemaReviewAndReplayValidation 프롬프트

## 역할

너는 이 저장소의 UI/UX 및 플로우 구현을 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수와 프롬프트 작성만 담당한다.

이번 작업은 `pokemon_showdown_db_extract.zip` 같은 구조화 전투 데이터 패키지 업로드 후 Step2/Step3이 사용자 판단 없이 건너뛰어지는 문제를 해결한다.

## 프로젝트 핵심 원칙

이 프로젝트는 전투로그 기반 범용 턴제 전투 시뮬레이터다.

최종 목표:

1. 전투 로그를 역설계한다.
2. 전문가(사용자) 개입을 받아 게임의 전투 시스템을 복제한다.
3. 복제본을 밸런스 분석용으로 최적화한다.

핵심 원리는 연속 슬라이더다.

- 대중적인/구조화된 게임 로그일수록 자동 역설계 비중이 높다.
- 비대중적이거나 미지의 게임일수록 사용자 개입 비중이 높다.
- 자동 역설계와 사용자 개입은 서로 다른 경로가 아니라 하나의 연속 슬라이더다.

따라서 구조화된 전투 데이터 패키지라고 해서 Step2/Step3을 아무 설명 없이 건너뛰면 안 된다. 자동으로 추론한 내용을 사용자에게 보여주고, 사용자가 검토/수정/승인할 수 있어야 한다.

## 현재 문제

`pokemon_showdown_db_extract.zip` 업로드 후:

- Step2가 자동 완료 처리된다.
- Step3은 일반 로그용 `damage_formula`가 없어 에러가 나거나, 이후 우회 처리되면 사실상 건너뛰게 된다.
- 사용자는 자동 적용된 schema, 전투 시스템 해석, replay 검증 결과를 확인할 수 없다.

이 흐름은 교수 시연과 최종 목표 모두에 맞지 않는다.

## 목표

DB/ZIP 전투 데이터 패키지 모드에서도 Step2와 Step3은 사라지면 안 된다.

대신 모드별 의미가 달라져야 한다.

- 일반 로그 모드 Step2: 수동 시스템 정의
- 전투 데이터 패키지 모드 Step2: 자동 추론된 시스템 정의 검토/승인
- 일반 로그 모드 Step3: 수식 기반 discrepancy 검증
- 전투 데이터 패키지 모드 Step3: replay/event/state 기반 복제 검증

즉, DB/ZIP 모드는 Step2/Step3을 skip하는 것이 아니라 **자동 추론 결과와 복제 검증 결과를 보여주는 검토 단계**로 바뀌어야 한다.

## P0. Step2: 자동 시스템 정의 검토 화면

DB/ZIP 전투 데이터 패키지 모드에서 Step2는 자동 완료만 하지 말고, 아래 내용을 보여줘라.

### 표시할 내용

1. 파일 인식 결과
   - 전투 데이터 패키지로 인식됨
   - battle count
   - player/participant count
   - event count
   - turn count 또는 max turn

2. 자동 추론된 전투 구조
   - game type 또는 battle format
   - player sides
   - roster/team structure
   - turn column
   - actor/target identifier columns
   - move/action columns
   - HP/status/state columns
   - switch/faint/state trace 사용 여부

3. 자동 추론된 시스템 요소
   - stats/resource columns
   - gimmick/category columns
   - health stat
   - target/result column
   - log schema flags

4. 사용자 개입 지점
   - 자동 추론 schema를 그대로 승인
   - 필요한 경우 주요 mapping override 가능
   - 최소한 "자동 추론 결과 승인" 버튼이 있어야 함

### 사용자-facing 문구

내부 용어를 과하게 노출하지 말고, 다음 식으로 설명하라.

```text
전투 데이터 패키지에서 전투 구조를 자동 추론했습니다.
아래 항목을 확인한 뒤 복제 검증 단계로 진행하세요.
```

단, 개발자용 상세 expander나 검수요약에서는 `schema`, `trace`, `backtest` 같은 용어를 써도 된다.

### 수용 기준

- DB/ZIP 업로드 후 Step2가 빈 화면 또는 자동 완료만으로 끝나지 않는다.
- 사용자가 어떤 전투 구조가 자동 적용됐는지 볼 수 있다.
- 사용자가 자동 추론 결과를 승인했다는 명시적 상태가 생긴다.
- 승인 전에는 다음 단계 이동 조건이 명확하다.
- 일반 로그 모드 Step2는 기존 수동 매핑 흐름을 유지한다.

## P0. Step3: replay/event/state 기반 복제 검증 화면

DB/ZIP 전투 데이터 패키지 모드에서 Step3은 `damage_formula` 기반 discrepancy가 아니라 replay validation 화면이어야 한다.

### 표시할 내용

1. 검증 기준
   - 로스터 일치
   - 이벤트 타임라인 파싱
   - turn/action replay
   - HP/state/status trace
   - switch/faint trace
   - outcome/winner 일치

2. 검증 요약
   - battle count
   - replayed battle count
   - state check count
   - action/move check count
   - mismatch count
   - outcome mismatch count
   - state/resource mismatch count
   - accuracy 또는 pass rate

3. mismatch 상세
   - mismatch가 없으면 명확히 표시
   - mismatch가 있으면 table로 표시
   - event id/turn/actor/expected/observed/delta 등을 보여줌

4. 다음 단계 의미
   - Step3 통과 후 Dashboard에서 밸런스 분석/백테스트/시뮬레이션을 확인한다는 안내

### 사용자-facing 문구

```text
수식 오차 분석 대신, 실제 전투 이벤트를 복제본이 얼마나 재현하는지 검증합니다.
```

### 수용 기준

- DB/ZIP 모드 Step3에서 `damage_formula`가 없어도 에러가 나지 않는다.
- Step3이 그냥 건너뛰어지지 않는다.
- 사용자가 "복제본이 제대로 적용됐는지" 판단할 수 있는 검증 지표를 본다.
- mismatch가 있으면 어디가 틀렸는지 볼 수 있다.
- 일반 로그 모드 Step3의 기존 수식 discrepancy 기능은 유지된다.

## P0. 모드 분기 정리

명시적 mode flag를 사용하라.

권장:

```python
st.session_state["input_mode"] = "structured_battle_package"
```

또는:

```python
st.session_state["db_corpus_mode"] = True
```

일반 로그 업로드 시에는 이 플래그를 제거하거나 일반 모드로 바꿔라.

주의:

- 일반 CSV 업로드 후 DB/ZIP 모드 UI가 남으면 실패다.
- DB/ZIP 업로드 후 일반 damage formula Step3으로 들어가면 실패다.
- Step2/Step3 route는 mode에 따라 화면 의미를 바꿔야 한다.

## P0. 교수 시연 기준

시연 파일:

- `pokemon_showdown_db_extract.zip`

시연 흐름:

1. Step1에서 전투 데이터 파일 업로드
2. Step2에서 자동 추론된 전투 구조/로스터/이벤트 schema 확인
3. Step2에서 자동 추론 결과 승인
4. Step3에서 replay/event/state 기반 복제 검증 확인
5. Dashboard에서 복제본 기반 분석/백테스트 결과 확인

교수 앞 설명 포인트:

```text
일반 CSV라면 사용자가 Step2에서 직접 시스템을 정의합니다.
이 파일은 실제 리플레이에서 추출한 구조화 전투 데이터라 자동 추론 비중이 높습니다.
하지만 자동 추론 결과를 Step2에서 검토하고, Step3에서 실제 이벤트 재현 검증을 확인합니다.
즉, 자동화와 사용자 개입은 별도 경로가 아니라 같은 복제 슬라이더 위에 있습니다.
```

## P1. Step2/Step3 네이밍

기존 step title은 유지해도 되지만, DB/ZIP 모드에서 하위 제목은 모드에 맞게 바꿔라.

Step2:

- `자동 시스템 정의 검토`
- `전투 구조 자동 추론 결과`

Step3:

- `복제 검증`
- `리플레이 재현 검증`

일반 로그 모드에서는 기존 제목을 유지한다.

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

추가 테스트를 작성/보강하라.

권장:

- `test_step2_structured_package_review.py`
- `test_step3_structured_package_validation.py`

테스트 케이스:

- DB/ZIP mode에서 Step2가 자동 schema review state를 반환
- DB/ZIP mode에서 Step2 승인 전/후 진행 조건이 명확
- DB/ZIP mode에서 Step3이 `damage_formula` 없이 replay validation summary를 표시
- 일반 로그 mode에서 기존 Step2/Step3 흐름 유지

## 실제 화면 검수

필수 스크린샷:

- `.codex_tmp/ui5b_auto_schema_review/step1_zip_uploaded.png`
- `.codex_tmp/ui5b_auto_schema_review/step2_auto_review.png`
- `.codex_tmp/ui5b_auto_schema_review/step3_replay_validation.png`
- `.codex_tmp/ui5b_auto_schema_review/dashboard_after_validation.png`

검수 체크리스트:

- Step2가 자동 완료만으로 사라지지 않는가
- Step2에서 자동 추론된 schema/전투 구조를 볼 수 있는가
- Step3이 그냥 skip되지 않는가
- Step3에서 복제 검증 지표를 볼 수 있는가
- `damage_formula` KeyError가 없는가
- 일반 로그 모드가 깨지지 않았는가

## 검수요약 문서

루트에 아래 파일을 작성하라.

- `DB코퍼스_UI5b_autoSchemaReviewAndReplayValidation_검수요약.md`

포함:

- 수정 파일
- Step2 DB/ZIP 모드 동작
- Step3 DB/ZIP 모드 동작
- 일반 로그 모드 회귀 여부
- 교수 시연 흐름 확인
- 추가/수정 테스트
- 스크린샷 경로
- 남은 이슈

## 완료 보고 형식

```text
UI5b 완료 보고

1. 수정 파일
- ...

2. Step2 자동 시스템 정의 검토
- 표시 항목:
- 승인 방식:

3. Step3 복제 검증
- 검증 지표:
- mismatch 표시:

4. 일반 로그 모드 회귀 확인
- ...

5. 교수 시연 흐름
- Step1:
- Step2:
- Step3:
- Dashboard:

6. 테스트 결과
- ...

7. 스크린샷
- ...

8. 남은 이슈
- ...
```
