# DB코퍼스 PR-UI4j cssRollbackAndStableTheme 프롬프트

## 역할

너는 이 저장소의 UI/UX 구현을 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수와 프롬프트 작성만 담당한다.

이번 작업은 추가 미세 조정이 아니다. 이전 UI4 계열 CSS 수정이 화면을 더 망가뜨렸으므로 **문제 CSS를 롤백/정리하고 안정적인 테마 기준으로 다시 잡는 복구 작업**이다.

## 현재 실패 판정

사용자 확인 결과:

- 가시성 문제가 해결되지 않았다.
- 오히려 화면이 더 이상해졌다.
- selectbox의 선택 값이 흰 배경 위에서 여전히 잘 보이지 않는다.
- multiselect tag/chip 텍스트가 잘리거나 일부 글자만 보인다.
  - 예: `HP`가 `P`처럼 보임
  - `Type1`이 `ype1`처럼 보임
- form field 안쪽에 커서/텍스트/배경 처리만 어색하게 바뀌었다.
- 일부 label/chip에 파란 highlight를 붙이는 식의 땜질이 생겼다.
- 전체 디자인 일관성이 깨졌다.

따라서 이번 PR의 목표는 **더 많은 selector를 덧붙이는 것**이 아니라, 잘못된 CSS를 제거하고 안정된 규칙으로 재구성하는 것이다.

## P0. 문제 CSS 롤백/제거

먼저 최근 UI4c~UI4i에서 추가된 가시성 관련 CSS를 감사하라.

제거해야 할 가능성이 높은 항목:

- 전역 `*`, `span`, `p`, `label`에 강한 색을 주는 selector
- `[data-baseweb="select"] *`처럼 내부 요소 전체를 무차별로 덮는 selector
- multiselect tag 내부를 직접 건드려 텍스트 clipping을 만든 selector
- label에 파란 배경/highlight를 붙이는 selector
- 특정 텍스트만 보이게 만드는 inline style
- 밝은 input/select surface 내부 텍스트를 흰색으로 만드는 selector
- padding/line-height/height를 건드려 chip 텍스트를 잘리게 만든 selector

필수:

- Step2 multiselect chip이 원래처럼 글자가 온전히 보여야 한다.
- `HP`, `Attack`, `Defense`, `Type1`, `Type2`가 잘리지 않아야 한다.
- selectbox selected value가 온전히 보여야 한다.
- form component의 높이/패딩/line-height를 무리하게 조작하지 마라.

## P0. 안정 테마 전략

이번에는 두 가지 중 하나만 선택하라.

### 권장안 A: Streamlit/BaseWeb 기본 form surface 유지

- selectbox/input/multiselect/uploader의 밝은 surface는 그대로 둔다.
- 내부 value/placeholder/help text는 기본 dark text로 명확히 보이게 한다.
- chip/tag는 BaseWeb 기본 크기/패딩을 유지하고, 텍스트 색만 안전하게 조정한다.
- outer dark app 배경 위 label/caption만 밝게 조정한다.

이 경우 CSS는 최소한으로 해야 한다.

### 대안 B: form surface를 dark theme로 통일

- 모든 input/select/multiselect/uploader background를 dark로 바꾼다.
- value/placeholder/icon/border/focus/disabled/tag까지 모두 dark theme에 맞춘다.
- BaseWeb chip padding/height가 깨지지 않게 한다.

대안 B는 위험하므로, 확실히 검수할 수 없으면 권장안 A를 사용하라.

## P0. 사용자-facing 문구 정리 유지

Step1 사용자 화면에는 내부 용어를 노출하지 마라.

금지:

- `Pokemon Showdown`
- `DB 코퍼스`
- `코퍼스 파일`

허용:

- 확장자 안내의 `DB`, `ZIP`

권장:

- `전투 데이터 파일`
- `지원 형식: CSV, Excel, JSON, TSV, TXT, Parquet, DB, ZIP`

## P0. Step1 구조 유지

Step1은 세 입력이 inline으로 보여야 한다.

- 전투 데이터 파일
- 무브 로그 파일 (선택)
- 매핑 프리셋 JSON (선택)

금지:

- 탭
- expander
- 접힌 보조 옵션
- 내부 DB 코퍼스 섹션

## P0. Step2 복구 기준

현재 Step2가 가장 심하게 망가졌다. 아래를 먼저 복구하라.

필수 수용 기준:

- `타겟 컬럼` selectbox 안의 `Is_Victorious`가 온전히 보인다.
- `숫자형 스탯 (Base Stats)` multiselect chip의 `HP`, `Attack`, `Defense`, `SpAtk`, `SpDef`, `Speed`가 잘리지 않는다.
- `카테고리/기믹 (Gimmicks)` chip의 `Type1`, `Type2`가 잘리지 않는다.
- chip 좌측 글자가 잘려 사라지지 않는다.
- selectbox 오른쪽 icon/clear icon이 정상 위치에 있다.
- formula input의 값/placeholder가 보인다.
- disabled 이전 단계 버튼 텍스트가 읽힌다.
- label에 파란 highlight가 없어야 한다.

## P0. 가시성은 최소 CSS로 해결

이번 PR에서는 computed contrast audit보다 먼저 **시각적 회귀 복구**가 우선이다.

필수:

- form component 내부의 텍스트가 보이게 하되, layout을 깨지 마라.
- chip/tag height, padding, overflow를 건드리지 마라.
- `overflow: hidden`, `line-height`, `height`, `padding-left`를 chip 내부에 새로 지정하지 마라.
- 필요하면 color만 조정하라.
- selectbox/input은 background와 text color만 최소 조정하라.

## P0. 실제 브라우저 검수

HTTP 200만으로 완료하지 마라. 반드시 실제 브라우저 화면을 확인하고 스크린샷을 남겨라.

필수 스크린샷:

- `.codex_tmp/ui4j_css_rollback_stable_theme/step1_desktop.png`
- `.codex_tmp/ui4j_css_rollback_stable_theme/step2_mapping_desktop.png`
- `.codex_tmp/ui4j_css_rollback_stable_theme/step2_formula_desktop.png`
- `.codex_tmp/ui4j_css_rollback_stable_theme/dashboard_desktop.png`
- `.codex_tmp/ui4j_css_rollback_stable_theme/mobile_step1.png`
- `.codex_tmp/ui4j_css_rollback_stable_theme/mobile_step2.png`

스크린샷 검수 체크리스트:

- chip 텍스트가 잘리지 않는가
- selectbox 값이 보이는가
- input value/placeholder가 보이는가
- label/caption이 hover 없이 읽히는가
- 파란 highlight 땜질이 없는가
- Step1 문구에 내부 용어가 없는가
- Step1 세 입력이 inline으로 보이는가

## P0. 실패 시 완료 금지

아래 중 하나라도 있으면 완료 보고하지 마라.

- 흰 배경 위 흰/옅은 텍스트
- chip 텍스트 잘림
- label 파란 highlight
- Step1 사용자-facing 내부 용어 노출
- Step1 보조 입력 expander/tabs 복귀
- 스크린샷 미제출

## 테스트 요구사항

필수 실행:

```powershell
python -m py_compile main.py modules/step1_upload.py modules/step2_system_definition.py modules/step5_discrepancy.py modules/step6_dashboard.py modules/ui_db_corpus_helper.py
python test_db_corpus_ui_state.py
python test_db_corpus_scale_validation.py
python test_step1_db_corpus_upload_adapter.py
python test_step6_db_corpus_auto_schema.py
python test_step6_db_corpus_oneclick_backtest.py
python test_showdown_db_extract_adapter.py
python test_db_corpus_backtest_report.py
python test_i15_integration_smoke.py
```

추가:

- 사용자-facing Step1 문자열에 `Pokemon Showdown`, `DB 코퍼스`, `코퍼스 파일`이 남지 않았는지 확인하라.
- `.db`/`.zip` 자동 분기는 유지되는지 확인하라.

## 검수요약 문서

루트에 아래 파일을 작성하라.

- `DB코퍼스_UI4j_cssRollbackAndStableTheme_검수요약.md`

포함:

- 수정 파일
- 제거/롤백한 CSS selector 목록
- 유지한 CSS selector 목록
- 선택한 안정 테마 전략(A 또는 B)
- Step2 chip/selectbox 복구 확인
- 사용자-facing 문구 정리 결과
- 스크린샷 경로
- 테스트 결과
- 남은 이슈

## 완료 보고 형식

```text
UI4j 완료 보고

1. 수정 파일
- ...

2. CSS 롤백/정리
- 제거:
- 유지:
- 안정 전략:

3. 복구 확인
- selectbox value:
- multiselect chip:
- formula input:
- disabled button:
- highlight 제거:

4. Step1 UX
- 문구:
- inline 입력:
- DB/ZIP 분기 유지:

5. 스크린샷
- ...

6. 테스트 결과
- ...

7. 남은 이슈
- ...
```
