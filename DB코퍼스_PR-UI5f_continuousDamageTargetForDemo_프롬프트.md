# DB코퍼스 PR-UI5f — 데미지 연속 타깃 허용 및 시연 CSV 정상 진입

## 배경

내일 시연용 파일 `pokemon_showdown_demo_damage_log.csv`는 실제 Pokemon Showdown 리플레이 기반의 공격/피해 단위 가공 CSV다.

현재 파일에는 다음 컬럼이 정상 존재한다.

```text
battle_id, turn, attacker_species, defender_species, move_name,
Move_Power, Move_Type, Move_Category,
Atk_Attack, Atk_SpAtk, Def_Defense, Def_SpDef,
Atk_Type1, Atk_Type2, Def_Type1, Def_Type2,
hp_before, hp_after, Damage, effect_hint
```

하지만 Step2가 타깃 후보를 `0/1` 이진 승패 컬럼으로만 필터링하고 있어 `Damage`가 타겟 컬럼 드롭다운에 나오지 않는다. 이 때문에 시연용 데미지 복제 CSV를 업로드해도 “타겟 컬럼 없음” 상태가 된다.

이 문제는 파일 문제가 아니라 앱의 타깃 타입 모델 문제다.

## 목표

Step2에서 타깃 변수를 다음 두 종류로 분리해 지원하라.

1. **승패/분류 타깃**
   - 예: `result`, `win`, `is_win`, `label`
   - 기존 밸런스 예측/승률 모델용

2. **데미지/회귀 타깃**
   - 예: `Damage`, `damage`, `total_damage`, `hp_delta`, `delta_hp`
   - 데미지 공식 역설계/검증용

시연용 CSV에서는 `Damage`가 기본 타깃으로 선택되어야 한다.

## 변경 요구사항

### 1. Step2 타깃 후보 생성 수정

현재 `modules/step2_system_definition.py`는 대략 아래처럼 이진 컬럼만 타깃 후보로 만든다.

```python
binary_cols = [...]
selected_target = st.selectbox("타겟 컬럼", binary_cols if binary_cols else ["None"], ...)
```

이를 다음 구조로 바꿔라.

- `binary_target_cols`: 기존 0/1 승패 후보
- `continuous_target_cols`: 수치형 컬럼 중 데미지 후보
- `target_candidates`: 두 후보를 합친 목록

데미지 후보 우선순위:

```text
Damage
damage
total_damage
hp_delta
delta_hp
DamageValue
```

대소문자 차이는 허용한다.

`pokemon_showdown_demo_damage_log.csv`에서는 `Damage`가 기본 선택되어야 한다.

### 2. target_mode 저장

선택된 타깃에 따라 세션에 모드를 저장하라.

```python
st.session_state["target_mode"] = "classification"  # 0/1 승패
st.session_state["target_mode"] = "regression"      # 연속 데미지
```

판정 기준:

- 값이 0/1 두 클래스면 `classification`
- 수치형이고 unique 값이 2개 초과면 `regression`

### 3. Step2 시작 조건 수정

기존처럼 타깃이 반드시 binary일 필요가 없다.

다음이면 시작 가능해야 한다.

- 타깃 컬럼이 존재함
- 스탯 컬럼이 1개 이상 선택됨
- 일반 CSV 모드에서는 공식 텍스트가 있거나, 공식 자동 추정 결과를 사용할 수 있음

`Damage` 연속 타깃을 선택해도 “타겟 컬럼 선택 안됨”으로 막지 마라.

### 4. Step2 ML 학습 분기 보호

`target_mode == "regression"`일 때는 LogisticRegression/RandomForestClassifier 같은 분류 모델을 돌리지 마라.

필요하면 다음 중 하나로 처리하라.

- 회귀 모델(`RandomForestRegressor`, `LinearRegression`) 사용
- 또는 ML 승패 예측 학습을 건너뛰고 “데미지 회귀 타깃: 승패 예측 모델은 비활성화”라고 표시

중요: 연속 `Damage`를 대상으로 분류 모델을 학습하다가 오류가 나면 안 된다.

### 5. Step3 공식 검증

Step3/Discrepancy에서는 선택된 `target_col`이 `Damage`일 경우 사용자 공식 예측값과 `Damage`를 비교해야 한다.

즉 다음이 정상이어야 한다.

```python
Calculated_Error = abs(Predicted_Value - df["Damage"])
```

`result` 같은 승패 컬럼을 억지로 요구하지 마라.

### 6. Dashboard 분기

`target_mode == "regression"`일 때는 승률 예측/Monte Carlo 승패 패널을 기본 성공 지표로 삼지 마라.

대신 다음을 표시하라.

- 데미지 타깃: `Damage`
- 평균 절대 오차(MAE)
- 평균 실제 데미지
- 평균 예측 데미지
- 상위 오차 행

승률/몬테카를로가 데이터 구조상 불가능하면 크래시하지 말고 “승패 타깃이 없어 비활성화”라고 표시한다.

### 7. 기본 매핑 추천

`pokemon_showdown_demo_damage_log.csv` 업로드 시 기본 추천값:

타깃:

```text
Damage
```

수치형 스탯:

```text
Atk_Attack
Atk_SpAtk
Def_Defense
Def_SpDef
Move_Power
hp_before
hp_after
```

기믹:

```text
Atk_Type1
Atk_Type2
Def_Type1
Def_Type2
Move_Type
Move_Category
effect_hint
```

## 금지사항

- ZIP/DB 코퍼스 구조를 다시 건드리지 마라.
- UI 색상/가시성 CSS를 건드리지 마라.
- `Damage`를 가짜 0/1 컬럼으로 변환하지 마라.
- 사용자가 `result` 컬럼을 직접 추가해야만 진행되는 구조로 만들지 마라.
- Step2를 자동 완료시켜 사용자의 검수 단계를 건너뛰지 마라.

## 검수 기준

다음 파일로 수동 검수한다.

```text
C:\Users\kmjde\OneDrive\Desktop\턴제 시뮬레이션\pokemon_showdown_demo_damage_log.csv
```

기대 결과:

1. Step1 업로드 성공
2. Step2 필수 매핑 탭에서 타겟 컬럼 드롭다운에 `Damage`가 보임
3. `Damage`가 기본 선택됨
4. 수치형 스탯/기믹 추천값이 위 목록과 유사하게 자동 선택됨
5. 공식 입력 후 Step2 시작 가능
6. Step3에서 `Damage` 기준 오차 검증 가능
7. Dashboard에서 승패/몬테카를로가 불가능해도 크래시하지 않음

## 시연 설명 문장

이 수정 후 시연 메시지는 다음과 일치해야 한다.

> 이 시스템은 실제 Pokemon Showdown 리플레이에서 추출한 공격/피해 로그를 바탕으로 전투 데미지 시스템의 초안을 역설계하고, 사용자가 그 초안을 검수해 복제본을 완성하는 반자동 전투 시스템 복제 도구입니다.

