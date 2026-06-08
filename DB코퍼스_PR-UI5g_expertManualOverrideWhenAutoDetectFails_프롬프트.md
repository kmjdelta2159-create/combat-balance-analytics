# DB코퍼스 PR-UI5g — 자동 인식 실패 시 전문가 수동 오버라이드 모드

## 배경

현재 시뮬레이터는 자동 인식이 실패하면 사용자가 다음 단계로 의미 있게 진행하기 어렵다.

하지만 이 프로젝트의 핵심은 “시뮬레이터가 혼자 완전 복제”가 아니라:

> 시뮬레이터가 전투 로그에서 복제 초안을 역설계하고, 사용자가 그 초안을 검수/수정/보강해서 복제본을 완성하는 반자동 전투 시스템 복제 도구

이다.

따라서 자동 인식 실패는 막다른 길이 아니라, 전문가가 직접 구조를 지정하는 수동 입력 경로로 이어져야 한다.

## 목표

Step2에 **전문가 수동 오버라이드 모드**를 추가하라.

자동 탐지 결과가 불완전하거나 틀렸을 때 사용자가 직접 다음 항목을 지정할 수 있어야 한다.

- 타깃 타입
- 타깃 컬럼
- 스탯 컬럼
- 기믹/카테고리 컬럼
- 체력/자원 컬럼
- 데미지 공식
- 선택 규칙/상성/메커니즘 초안
- 필요 시 JSON 스키마 직접 편집

## 핵심 원칙

자동 인식은 “추천값”일 뿐이다.

사용자는 언제든 추천값을 덮어쓸 수 있어야 한다.

자동 탐지가 실패해도 다음과 같은 식의 흐름이 가능해야 한다.

1. CSV 업로드
2. 앱이 “타깃 후보 없음/스탯 후보 부족/공식 불명”을 감지
3. Step2에서 “전문가 수동 설정으로 진행” 버튼 제공
4. 사용자가 직접 컬럼/공식/규칙 지정
5. Step3에서 사용자 정의 복제 초안 검증
6. Dashboard에서 가능한 분석만 표시

## 변경 요구사항

### 1. Step2 상단에 자동/수동 모드 토글 추가

다음 상태를 제공하라.

```text
자동 추천 사용
전문가 수동 설정
```

기본값은 자동 추천이지만, 자동 인식 실패 시 수동 설정으로 전환할 수 있어야 한다.

자동 인식 실패 조건 예:

- 타깃 후보 없음
- `Damage` 같은 연속 데미지 타깃을 자동으로 못 찾음
- 스탯 후보 0개
- 공식 자동 추정 실패
- ZIP/DB 패키지에서 schema 불완전

### 2. 타깃 타입 직접 선택

사용자가 다음 중 하나를 직접 고를 수 있게 하라.

```text
승패/분류 타깃
데미지/회귀 타깃
리플레이 이벤트 검증 타깃
타깃 없음: 공식/규칙 초안만 작성
```

선택값은 세션에 저장한다.

```python
st.session_state["target_mode"] = "classification" | "regression" | "replay_validation" | "none"
```

### 3. 타깃 컬럼 직접 선택

수동 모드에서는 타깃 드롭다운이 이진 컬럼으로 제한되면 안 된다.

모든 컬럼을 후보로 보여주고, 사용자가 직접 선택할 수 있어야 한다.

특히 `pokemon_showdown_demo_damage_log.csv`에서는 사용자가 `Damage`를 직접 선택할 수 있어야 한다.

### 4. 스탯/기믹 컬럼 직접 선택

수동 모드에서는 자동 추천과 무관하게 사용자가 직접 선택할 수 있어야 한다.

추천 기본값은 유지하되, 다음 컬럼들이 선택 가능해야 한다.

수치형 스탯 예:

```text
Atk_Attack
Atk_SpAtk
Def_Defense
Def_SpDef
Move_Power
hp_before
hp_after
```

기믹 예:

```text
Atk_Type1
Atk_Type2
Def_Type1
Def_Type2
Move_Type
Move_Category
effect_hint
```

### 5. 공식/규칙 직접 입력

사용자가 데미지 공식 또는 의사 공식을 직접 입력할 수 있어야 한다.

예:

```text
Move_Power * Atk_SpAtk / Def_SpDef
Move_Power * Atk_Attack / Def_Defense
Move_Power * offense / defense * type_multiplier
```

주의:

- 원시 Python `eval`을 무제한 허용하지 마라.
- 기존 공식 입력 방식처럼 제한된 수식 DSL 또는 안전한 pandas eval 범위에서 처리하라.
- 사용자가 입력한 공식은 Step3에서 실제 타깃과 비교해야 한다.

### 6. JSON 스키마 직접 편집 고급 모드

Step2 하단 또는 별도 expander에 “고급: 스키마 JSON 직접 편집”을 제공하라.

사용자가 다음 구조를 편집할 수 있어야 한다.

```json
{
  "target_mode": "regression",
  "target_col": "Damage",
  "system_stats": ["Atk_Attack", "Atk_SpAtk", "Def_Defense", "Def_SpDef", "Move_Power"],
  "system_gimmicks": ["Atk_Type1", "Def_Type1", "Move_Type", "Move_Category", "effect_hint"],
  "health_stat": "hp_before",
  "damage_formula": "Move_Power * Atk_SpAtk / Def_SpDef"
}
```

JSON 파싱 실패 시 앱이 크래시하지 말고 오류 메시지를 표시한다.

### 7. 자동 탐지 실패 메시지 개선

“타겟 컬럼 없음” 같은 막힌 문장만 표시하지 마라.

다음처럼 사용자가 무엇을 할 수 있는지 보여줘라.

```text
자동 타깃 탐지에 실패했습니다.
전문가 수동 설정에서 타깃 타입과 컬럼을 직접 지정할 수 있습니다.
데미지 로그라면 target_mode=regression, target_col=Damage를 선택하세요.
```

### 8. Step3/Step6 분기

수동 설정이 저장되면 Step3/Step6은 자동 탐지 결과가 아니라 사용자 지정 세션 값을 우선 사용해야 한다.

우선순위:

1. 사용자가 수동으로 지정한 값
2. 저장된 mapping preset
3. 자동 탐지 결과
4. fallback

## 금지사항

- 사용자가 원시 Python 코드를 앱 내부에서 마음대로 실행하게 하지 마라.
- 자동 탐지 실패를 이유로 Step2 전체를 막지 마라.
- 수동 모드에서 타깃 후보를 0/1 이진 컬럼으로 제한하지 마라.
- 수동 모드를 DB/ZIP 패키지에만 한정하지 마라. 일반 CSV에서도 동작해야 한다.
- UI 색상/CSS는 건드리지 마라.

## 검수 파일

다음 파일로 검수한다.

```text
C:\Users\kmjde\OneDrive\Desktop\턴제 시뮬레이션\pokemon_showdown_demo_damage_log.csv
```

## 검수 기준

1. Step1에서 CSV 업로드 성공
2. Step2에서 자동 추천이 틀리거나 부족해도 “전문가 수동 설정”을 선택 가능
3. 수동 모드에서 `Damage`를 타깃으로 선택 가능
4. `target_mode=regression` 저장됨
5. 수치형 스탯/기믹을 사용자가 직접 선택 가능
6. 공식 직접 입력 가능
7. Step2 완료 버튼이 활성화됨
8. Step3에서 사용자 공식과 `Damage`의 오차를 계산함
9. Dashboard에서 승패 예측이 불가능하면 크래시하지 않고 비활성 안내 표시

## 시연 메시지

이 기능은 다음 시연 문장과 일치해야 한다.

> 자동 역설계는 초안을 제안하고, 사용자는 전문가 수동 설정을 통해 타깃·스탯·기믹·공식을 보정합니다. 따라서 자동 인식이 완벽하지 않아도 복제 작업은 계속 진행할 수 있습니다.

