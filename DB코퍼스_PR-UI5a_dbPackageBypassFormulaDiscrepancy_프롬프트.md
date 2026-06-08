# DB코퍼스 PR-UI5a dbPackageBypassFormulaDiscrepancy 프롬프트

## 역할

너는 이 저장소의 UI/UX 및 플로우 구현을 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수와 프롬프트 작성만 담당한다.

이번 작업은 교수 시연 전 필수 안정화다. `pokemon_showdown_db_extract.zip` 업로드 후 Step2가 자동 완료되고 Step3에서 `damage_formula` KeyError가 발생하는 문제를 해결하라.

## 현재 버그

시연용 파일:

- `pokemon_showdown_db_extract.zip`

재현 흐름:

1. Step1에서 `pokemon_showdown_db_extract.zip` 업로드
2. 앱이 DB 패키지로 자동 처리
3. Step2가 자동 완료된 상태가 됨
4. Step3으로 이동
5. 아래 오류 발생

```text
KeyError: 'st.session_state has no key "damage_formula"'
modules/step5_discrepancy.py line 12
formula = st.session_state['damage_formula']
```

원인:

- DB 패키지 업로드는 일반 수식 기반 분석이 아니라 replay/backtest 패키지 흐름이다.
- 그런데 Step3 `Discrepancy`는 일반 로그 플로우의 `damage_formula`가 반드시 있다고 가정한다.
- DB 패키지 자동 매핑에서는 `damage_formula`가 세팅되지 않거나, 세팅될 필요가 없다.
- 따라서 DB 패키지 시연 흐름에서 Step3이 일반 formula discrepancy 화면처럼 동작하면 안 된다.

## 목표

`pokemon_showdown_db_extract.zip`을 업로드한 뒤 사용자가 에러 없이 게임 복제/리플레이 검증 흐름으로 이동할 수 있게 하라.

핵심:

- DB 패키지 모드에서는 `damage_formula`가 없어도 Step3에서 KeyError가 나면 안 된다.
- DB 패키지 모드에서는 Step3을 우회하거나, DB replay/backtest 안내 화면으로 처리해야 한다.
- 교수 시연용 흐름은 Step1 업로드 후 Step6/Dashboard의 replay/backtest 결과까지 안정적으로 이어져야 한다.

## P0. Step3 KeyError 제거

`modules/step5_discrepancy.py`에서 아래처럼 직접 접근하지 마라.

```python
formula = st.session_state['damage_formula']
```

필수:

- `st.session_state.get("damage_formula")` 형태로 안전하게 읽어라.
- formula가 없을 때 일반 로그 모드와 DB 패키지 모드를 구분하라.
- 어떤 경우에도 Streamlit KeyError traceback이 화면에 노출되면 실패다.

## P0. DB 패키지 모드 판정

DB 패키지 업로드 후 이미 세팅되는 session state를 사용해 DB 패키지 모드를 판정하라.

후보:

- `db_corpus_adapter_report`
- `db_corpus_schema`
- `bb_last_log_schema`
- `db_corpus_last_backtest_has_run`
- `current_file_name` 확장자 `.zip`/`.db`

명시적인 플래그가 없으면 추가해도 된다.

권장:

```python
st.session_state["db_corpus_mode"] = True
```

일반 로그 업로드 시에는 이 플래그를 제거하거나 `False`로 둬라.

## P0. DB 패키지 모드의 Step3 동작

DB 패키지 모드에서 Step3에 진입하면 다음 중 하나로 처리하라.

### 권장안 A: Step3을 DB replay 안내/통과 화면으로 처리

Step3 화면에 다음 의미를 보여준다.

- `DB/ZIP 전투 데이터 패키지는 수식 기반 Discrepancy 검증을 건너뜁니다.`
- `로스터/이벤트/상태 추적 기반 검증은 Dashboard의 백테스트에서 확인합니다.`
- 현재 로드된 battle count, event count, participant count 등 간단한 요약을 표시한다.
- `can_proceed=True`를 반환해 다음 단계로 이동 가능하게 한다.

주의:

- 사용자-facing 문구에는 이전 UI 지침을 반영해 `DB 코퍼스` 같은 내부 용어를 피하라.
- 권장 문구: `전투 데이터 패키지`, `리플레이 검증`, `백테스트`

### 대안 B: Step3 자동 우회

DB 패키지 모드에서는 Step3을 자동으로 통과시키고 Dashboard로 이동할 수 있게 한다.

주의:

- 자동 이동이 Streamlit rerun 루프를 만들면 안 된다.
- 사용자가 현재 어떤 단계를 건너뛰었는지 알 수 있어야 한다.

권장안 A를 우선 사용하라.

## P0. 일반 로그 모드 보호

일반 로그 모드에서는 기존 Step3 수식 기반 Discrepancy 기능을 유지하라.

단, `damage_formula`가 없으면 traceback 대신 사용자 안내를 보여라.

예:

```text
Step2에서 데미지 공식을 입력하고 파이프라인을 시작해야 오차 분석을 볼 수 있습니다.
```

반환:

- `can_proceed=False`
- 명확한 warning message

## P0. Step1/Step2 세션 상태 정리

DB 패키지 업로드 성공 시 Step3이 터지지 않도록 필요한 session state를 정리하라.

필수 확인:

- `mapping_approved=True`가 DB 패키지 모드에서 필요한 경우 유지
- `target_col`/`target_variable` 세팅 여부 확인
- `damage_formula`가 없어도 Step3 DB 모드가 안전하게 처리
- 일반 로그 업로드 시 DB 패키지 관련 session state가 남아 Step3을 잘못 우회하지 않도록 정리

## P0. 교수 시연 흐름 수용 기준

`pokemon_showdown_db_extract.zip` 기준으로 아래가 가능해야 한다.

1. Step1 업로드 성공
2. Step2 자동 완료 또는 DB 패키지용 요약 확인
3. Step3에서 traceback 없음
4. Step3에서 전투 데이터 패키지용 안내/요약 표시
5. 다음 단계 이동 가능
6. Dashboard/Step6에서 replay/backtest 흐름 접근 가능

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

권장 파일:

- `test_step3_db_package_mode.py`

테스트 케이스:

- DB 패키지 모드 + `damage_formula` 없음 → `render_discrepancy()`가 KeyError 없이 `can_proceed=True` 또는 명확한 DB 안내 상태 반환
- 일반 로그 모드 + `damage_formula` 없음 → KeyError 없이 `can_proceed=False`
- 일반 로그 모드 + `damage_formula` 있음 → 기존 동작 유지

## 실제 화면 검수

필수 스크린샷:

- `.codex_tmp/ui5a_db_package_step3/step1_zip_uploaded.png`
- `.codex_tmp/ui5a_db_package_step3/step3_db_package_no_formula_error.png`
- `.codex_tmp/ui5a_db_package_step3/dashboard_after_zip.png`

검수 체크리스트:

- Step3에 Streamlit traceback이 없는가
- `damage_formula` KeyError가 없는가
- DB 패키지 흐름에서 다음 단계 이동이 가능한가
- 일반 로그 Step3 기능이 깨지지 않았는가

## 검수요약 문서

루트에 아래 파일을 작성하라.

- `DB코퍼스_UI5a_dbPackageBypassFormulaDiscrepancy_검수요약.md`

포함:

- 수정 파일
- 원인 분석
- DB 패키지 모드 판정 방식
- Step3 DB 패키지 동작
- 일반 로그 모드 보호 방식
- 추가/수정 테스트
- 스크린샷 경로
- 남은 이슈

## 완료 보고 형식

```text
UI5a 완료 보고

1. 수정 파일
- ...

2. 원인
- ...

3. 해결
- DB 패키지 모드:
- Step3 처리:
- 일반 로그 보호:

4. 교수 시연 흐름 확인
- zip 업로드:
- Step3:
- Dashboard:

5. 테스트 결과
- ...

6. 스크린샷
- ...

7. 남은 이슈
- ...
```
