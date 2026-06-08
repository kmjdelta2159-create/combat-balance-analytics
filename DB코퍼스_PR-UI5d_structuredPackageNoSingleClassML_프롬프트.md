# DB코퍼스 PR-UI5d structuredPackageNoSingleClassML 프롬프트

## 역할

너는 이 저장소의 UI/UX 및 플로우 구현을 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수와 프롬프트 작성만 담당한다.

이번 작업은 `pokemon_showdown_db_extract.zip`을 일반 Step2 UI에 통합한 뒤 발생한 단일 클래스 ML 학습 오류를 해결한다.

## 현재 실패 판정

사용자 스크린샷 기준:

1. DB/ZIP 전투 데이터 패키지가 Step2 일반 UI에 들어오는 방향은 맞다.
2. 하지만 일반 CSV용 학습 파이프라인까지 그대로 실행되어 에러가 난다.
3. 오류:

```text
ValueError: This solver needs samples of at least 2 classes in the data,
but the data contains only one class: np.int64(1)

modules/step2_system_definition.py line 1068
lr_model.fit(X, y_binary)
```

4. `pokemon_showdown_db_extract.zip`은 구조화 리플레이 패키지라서 `result`가 일반 supervised target처럼 0/1 양쪽 클래스를 충분히 갖는다고 가정하면 안 된다.
5. Step2에서 자동값을 보여주고 수정 가능하게 하는 건 맞지만, Step2 확정 시 일반 CSV용 LogisticRegression 학습을 무조건 돌리면 안 된다.

## 핵심 판단

DB/ZIP 구조화 전투 데이터 패키지는 일반 CSV와 같은 UI를 쓰되, 내부 파이프라인은 다르게 gate해야 한다.

- UI: 일반 Step2와 동일한 수정 가능 control
- 기본값: 자동 schema로 prefill
- Step2 확정: session_state 저장 및 복제 검증 준비
- ML 학습: target이 2개 이상 class를 가질 때만 실행
- DB/ZIP 패키지 검증: Step3/Step6의 replay/backtest validation 사용

즉, **UI는 통합하되 ML 학습/검증 엔진은 데이터 조건에 따라 분기**해야 한다.

## P0. LogisticRegression 단일 클래스 방어

`modules/step2_system_definition.py`에서 LogisticRegression 또는 supervised classifier 학습 전 반드시 target class 수를 검사하라.

필수:

```python
unique_classes = pd.Series(y_binary).dropna().unique()
if len(unique_classes) < 2:
    # 학습 skip
```

수용 기준:

- target이 한 클래스뿐이면 traceback을 띄우지 않는다.
- 모델 학습을 skip하고 명확한 안내를 표시한다.
- Step2 확정 자체는 실패하지 않는다.
- DB/ZIP 구조화 패키지 모드에서는 replay/backtest 검증으로 진행 가능하다.

사용자-facing 안내 예:

```text
현재 결과 컬럼이 단일 클래스라 승률 예측 모델 학습은 건너뜁니다.
전투 재현 검증은 리플레이 이벤트 기반으로 진행됩니다.
```

일반 CSV에서도 동일하게:

```text
결과 컬럼에 한 종류의 값만 있어 예측 모델 학습을 건너뜁니다.
```

## P0. DB/ZIP 모드에서 Step2 확정은 ML 학습에 의존하지 말 것

현재는 Step2 확정 후 `lr_model.fit(...)` 단계에서 터진다.

DB/ZIP 전투 데이터 패키지 모드에서는:

- 시스템 정의 저장
- 자동 schema/default 저장
- 사용자 수정 mapping 저장
- replay/backtest용 schema 갱신
- roster/library 구축
- 다음 단계 진행 가능

까지는 ML 모델 학습 여부와 독립적이어야 한다.

수용 기준:

- `pokemon_showdown_db_extract.zip` 업로드 후 Step2 확정 시 LogisticRegression 오류 없음
- Step2 완료 상태가 저장됨
- Step3으로 이동 가능
- Step3에서 replay/backtest 검증 실행 가능

## P0. Step2의 자동 default 품질 개선

현재 화면에서 DB/ZIP 모드 default가 너무 빈약하다.

보이는 값:

- Target: `result`
- Stats: `HP`
- Gimmicks: `species`
- Formula: Auto

이 자체는 최소값으로는 가능하지만, 사용자가 판단할 수 있게 자동 schema 요약을 editable UI와 함께 제공해야 한다.

필수:

- 자동 schema 요약 expander/summary 유지
- `result`, `HP`, `species`가 왜 선택됐는지 간단히 설명
- state/switch/faint/action trace 사용 가능 여부 표시
- 일반 formula가 없어도 replay validation으로 갈 수 있음을 안내

단, 이 요약이 read-only 전용 화면이 되면 안 된다. editable controls가 본체여야 한다.

## P0. Step3 replay validation 함수 호출 오류도 같이 방어

이전 스크린샷에서 Step3에 다음 오류도 있었다.

```text
TypeError: run_db_corpus_backtest_from_session()
missing 1 required positional argument: 'session_state_like'
```

필수:

- `run_db_corpus_backtest_from_session` 함수 정의를 확인하라.
- Step6에서 기존에 정상 호출하는 방식과 동일하게 Step3에서 호출하라.
- 필요 인자가 `session_state_like`라면 `st.session_state`를 전달하라.
- Step3 replay validation 실행 버튼을 눌러도 TypeError가 나면 실패다.

## P0. 일반 CSV 모드 회귀 방지

일반 CSV 모드에서는:

- target이 2개 이상 class면 기존 LogisticRegression 학습 유지
- target이 1개 class면 traceback 없이 학습 skip
- Step3 formula discrepancy는 기존대로 동작

수용 기준:

- 일반 CSV 흐름이 깨지지 않는다.
- single-class target도 앱을 터뜨리지 않는다.

## 교수 시연 수용 기준

시연 파일:

- `pokemon_showdown_db_extract.zip`

필수 흐름:

1. Step1 업로드 성공
2. Step2 일반 editable UI에 자동값 prefill
3. Step2에서 사용자가 수정 가능
4. Step2 확정 시 LogisticRegression single-class 오류 없음
5. Step3 이동
6. Step3 replay validation 실행 시 TypeError 없음
7. 검증 요약 또는 mismatch 결과 표시
8. Dashboard 이동 가능

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

- `test_step2_single_class_target_guard.py`
- `test_step3_structured_package_backtest_call.py`

필수 케이스:

- `y_binary`가 단일 클래스일 때 LogisticRegression 학습 skip
- 단일 클래스 target에서도 Step2 render/confirm이 traceback 없이 종료
- DB/ZIP mode Step3에서 `run_db_corpus_backtest_from_session(st.session_state)` 또는 정확한 함수 호출로 TypeError 없음
- 일반 CSV mode + 2 class target은 기존 학습 유지

## 실제 화면 검수

필수 스크린샷:

- `.codex_tmp/ui5d_no_single_class_ml/step2_prefilled_editable.png`
- `.codex_tmp/ui5d_no_single_class_ml/step2_confirm_no_lr_error.png`
- `.codex_tmp/ui5d_no_single_class_ml/step3_replay_validation_no_typeerror.png`
- `.codex_tmp/ui5d_no_single_class_ml/dashboard_after_validation.png`

검수 체크리스트:

- Step2 확정 후 LogisticRegression single-class traceback이 없는가
- 단일 클래스 skip 안내가 표시되는가
- Step3 replay validation 버튼이 TypeError 없이 동작하는가
- 일반 Step2 editable UI가 유지되는가
- Dashboard 이동이 가능한가

## 검수요약 문서

루트에 아래 파일을 작성하라.

- `DB코퍼스_UI5d_structuredPackageNoSingleClassML_검수요약.md`

포함:

- 수정 파일
- 단일 클래스 target 방어 방식
- DB/ZIP mode Step2 확정 동작
- Step3 backtest function 호출 수정
- 일반 CSV 회귀 여부
- 추가/수정 테스트
- 스크린샷 경로
- 남은 이슈

## 완료 보고 형식

```text
UI5d 완료 보고

1. 수정 파일
- ...

2. 단일 클래스 ML 방어
- 검사 방식:
- skip 안내:

3. DB/ZIP Step2
- editable prefill:
- 확정 결과:
- LR 오류 해결:

4. Step3 replay validation
- 함수 호출:
- TypeError 해결:
- 검증 결과:

5. 일반 CSV 회귀 확인
- ...

6. 테스트 결과
- ...

7. 스크린샷
- ...

8. 남은 이슈
- ...
```
