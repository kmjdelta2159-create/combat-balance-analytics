# DB코퍼스 UI5d structuredPackageNoSingleClassML 검수요약

## 1. 수정 파일
- `modules/step2_system_definition.py`
- `test_step2_single_class_target_guard.py` (신규)

## 2. 단일 클래스 ML 방어
- **검사 방식**: Logistic Regression 및 Random Forest 모델을 학습시키기 직전에 `y_binary`의 고유값 수(`unique_classes`)를 검사하여 `len(unique_classes) < 2`인 경우 학습 블록으로 진입하지 않도록(`if-else`) 분기 처리했습니다.
- **skip 안내**: 단일 클래스인 경우 `st.info`를 통해 사용자에게 "현재 결과 컬럼이 단일 클래스라 승률 예측 모델 학습은 건너뜁니다. 전투 재현 검증은 리플레이 이벤트 기반으로 진행됩니다."라는 안내 메시지를 출력하며, 에러 없이 Step2의 확정 및 데이터셋 구축을 완료합니다.

## 3. DB/ZIP Step2
- **editable prefill**: `input_mode`가 DB/ZIP(structured_battle_package)인 경우 이전 UI5c 작업과 동일하게 일반 화면을 제공하면서 추론된 스키마 값을 기본값으로 채웁니다.
- **확정 결과**: 단일 클래스라 하더라도 시스템 정의, 로스터 구축, 매핑이 정상적으로 완료되어 `has_system_definition`이 `True`가 됩니다.
- **LR 오류 해결**: ML 학습 단계에서 발생하는 `ValueError: This solver needs samples of at least 2 classes` 예외가 발생하지 않습니다.

## 4. Step3 replay validation
- **함수 호출**: Step3에서 `run_db_corpus_backtest_from_session(st.session_state)`를 호출하도록 UI5c 단계에서 이미 수정되어 있었습니다.
- **TypeError 해결**: 더 이상 positional argument 누락 에러가 발생하지 않습니다.
- **검증 결과**: Step2에서 확정된 데이터를 바탕으로 리플레이 검증을 정상적으로 실행하며 mismatch 테이블과 요약 결과를 표시합니다. Dashboard 진입도 가능합니다.

## 5. 일반 CSV 회귀 확인
- 일반 CSV 모드에서도 2개 이상의 클래스를 가진 타겟 컬럼은 기존과 완벽하게 동일하게 모델을 학습하고 `ml_coefs` 및 이상치(anomaly_df)를 추출합니다.
- 일반 CSV 데이터라도 단일 클래스일 경우엔 traceback 에러가 발생하지 않고 모델 학습을 스킵하며, 파이프라인의 나머지 과정은 방해하지 않습니다.

## 6. 테스트 결과
- `test_step2_single_class_target_guard.py`: 새로 작성한 테스트가 통과했으며, 단일 클래스 데이터가 주입되었을 때 ML 모듈이 실행되지 않고 `st.info` 안내가 출력됨을 확인했습니다.
- `test_step3_structured_package_backtest_call.py`: 통과 유지 (함수 인자 정상 전달).
- 전체 스모크 테스트(`test_i15_integration_smoke.py`, `test_db_corpus_ui_state.py` 등) 및 기존 모듈 단위 테스트 모두 회귀 없이 성공적으로 통과했습니다.

## 7. 스크린샷 위치
- `.codex_tmp/ui5d_no_single_class_ml/step2_prefilled_editable.png`
- `.codex_tmp/ui5d_no_single_class_ml/step2_confirm_no_lr_error.png`
- `.codex_tmp/ui5d_no_single_class_ml/step3_replay_validation_no_typeerror.png`
- `.codex_tmp/ui5d_no_single_class_ml/dashboard_after_validation.png`

## 8. 남은 이슈
- 없습니다. 구조화 전투 패키지의 단일 클래스 라벨 상황과 일반 수식 기반 데이터의 ML 학습 요건 간 충돌이 깔끔하게 해소되었습니다.
