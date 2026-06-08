# PR-UI5g — 자동 인식 실패 시 전문가 수동 오버라이드 모드 및 연속 타깃 허용

현재 시뮬레이터는 자동 인식에만 의존하며, 데미지 타깃 같은 연속 수치형 변수를 타깃으로 지정할 수 없고 실패 시 진행이 막히는 문제가 있습니다. 이를 해결하기 위해 사용자가 모든 구조를 직접 제어할 수 있는 "전문가 수동 설정" 모드를 도입하고 연속형 타깃(Regression)을 지원합니다.

## User Review Required
> [!IMPORTANT]
> - 타깃 모드가 `regression`일 경우 기존 승패 기반 ML(랜덤 포레스트, 로지스틱 회귀 등) 및 몬테카를로 분석이 비활성화되며 MAE(평균 절대 오차) 기반 데미지 분석으로 대체됩니다.
> - 수동 모드 설정은 기존 자동 탐지 결과보다 우선순위가 높습니다. 고급 JSON 직접 편집의 경우 형식이 틀리면 기존 세션에 저장된 값을 유지하며 오류 메시지를 띄웁니다.

## Proposed Changes

### 1. Step2 상단: 자동/수동 모드 토글 및 실패 알림 추가
#### [MODIFY] [step2_system_definition.py](file:///c:/Users/kmjde/OneDrive/Desktop/턴제 시뮬레이션/modules/step2_system_definition.py)
- Step2 상단에 `st.radio`를 이용한 토글 추가: `["자동 추천 사용", "전문가 수동 설정"]`
- 자동 탐지 실패(예: `binary_cols` 없음) 시 단순히 빈 값을 주는 대신, 다음 메시지 표시:
  > 자동 타깃 탐지에 실패했습니다. 전문가 수동 설정에서 타깃 타입과 컬럼을 직접 지정할 수 있습니다. 데미지 로그라면 target_mode=regression, target_col=Damage를 선택하세요.

### 2. 전문가 수동 설정 모드 로직 (Target / Stats / Gimmicks / Formula)
#### [MODIFY] [step2_system_definition.py](file:///c:/Users/kmjde/OneDrive/Desktop/턴제 시뮬레이션/modules/step2_system_definition.py)
- **타깃 타입 선택**: "승패/분류 타깃", "데미지/회귀 타깃", "리플레이 이벤트 검증 타깃", "타깃 없음" 중 선택 (세션 `target_mode` 연동).
- **타깃 컬럼 선택**: 수동 모드에서는 전체 DataFrame 컬럼을 후보로 표시하여 `Damage`를 직접 지정 가능토록 함.
- **스탯 및 기믹 선택**: 자동 추천과 무관하게 `st.multiselect`를 통해 사용자가 자유롭게 전체 컬럼 중 지정.
- **데미지 공식**: 기존 공식 검증기(수식 입력칸)와 연동하여 사용자가 직접 텍스트로 지정.
- **ML 바이패스**: `target_mode == "regression"` 또는 `none`일 경우 LogisticRegression/RandomForestClassifier 학습 스킵.

### 3. JSON 스키마 편집기 (고급 모드)
#### [MODIFY] [step2_system_definition.py](file:///c:/Users/kmjde/OneDrive/Desktop/턴제 시뮬레이션/modules/step2_system_definition.py)
- 하단에 `st.expander("고급: 스키마 JSON 직접 편집")` 추가.
- 세션의 현재 설정(타깃 모드/컬럼, 스탯, 기믹, 체력, 공식)을 JSON 텍스트로 `st.text_area`에 띄움.
- 적용 버튼 시 파싱하여 세션 업데이트. (파싱 오류 시 `st.error` 표시 및 크래시 방지).

### 4. Step3: 데미지 타깃 에러 검증
#### [MODIFY] [step5_discrepancy.py](file:///c:/Users/kmjde/OneDrive/Desktop/턴제 시뮬레이션/modules/step5_discrepancy.py)
- `target_mode == "regression"`일 때, Predicted_Value와 대상 타깃 컬럼(`Damage`) 간의 절대 오차를 `Calculated_Error`로 기록.

### 5. Step6: 대시보드 지표 전환
#### [MODIFY] [step6_dashboard.py](file:///c:/Users/kmjde/OneDrive/Desktop/턴제 시뮬레이션/modules/step6_dashboard.py)
- `target_mode == "regression"`일 경우 승률/Monte Carlo 섹션 대신 "승패 타깃이 없어 비활성화" 표출.
- 대신 데미지 중심 메트릭(타깃 이름, 평균 실제 데미지, 평균 예측 데미지, 평균 절대 오차(MAE), 상위 오차 로그)을 표시하도록 UI 분기.

### 6. CSV 자동 추천 프리셋 (Step1)
#### [MODIFY] [step1_upload.py](file:///c:/Users/kmjde/OneDrive/Desktop/턴제 시뮬레이션/modules/step1_upload.py)
- `pokemon_showdown_demo_damage_log.csv` 업로드 시 기본 추천값:
  - 타깃: `Damage`, 모드: `regression`
  - 스탯: `Atk_Attack`, `Atk_SpAtk`, `Def_Defense`, `Def_SpDef`, `Move_Power`, `hp_before`, `hp_after`
  - 기믹: `Atk_Type1`, `Atk_Type2`, `Def_Type1`, `Def_Type2`, `Move_Type`, `Move_Category`, `effect_hint`

## Verification Plan
1. `pokemon_showdown_demo_damage_log.csv` 업로드 및 자동 매핑 일치 확인.
2. Step2에서 "자동 추천 사용" 및 "전문가 수동 설정" 전환 정상 동작 확인.
3. 수동 설정에서 `Damage` 타깃 직접 선택 및 "데미지/회귀 타깃" 저장 확인.
4. JSON 편집기를 통한 값 수정 적용 정상 동작 (문법 오류 시 크래시 방지 포함).
5. Step3/Step6 진입 시 오류 발생 없이 연속형(Regression) 메트릭 정상 표시.
