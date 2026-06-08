# DB코퍼스 UI4k minimalColorOnlyNoLayout 검수요약

## 1. 수정 파일
- `main.py`: CSS 색상 최소 수정 적용
- `modules/step1_upload.py`: expander 제거 및 inline 변환, 내부 용어 제거 (`DB 코퍼스`, `Pokemon Showdown` 등 금지어 제외, `전투 데이터 파일` 적용)

## 2. CSS 최소 수정
- **selector**: `input`, `textarea`, `[data-baseweb="input"] input`, `[data-baseweb="textarea"] textarea`, `[data-testid="stSelectbox"] input`, `[data-testid="stTextInput"] input`, `[data-testid="stTextArea"] textarea`, `[data-testid="stNumberInput"] input`, `[data-testid="stFileUploader"] button`, `[data-baseweb="select"] div[aria-selected="true"]`, `[data-baseweb="select"] span[title]`, `[data-baseweb="tag"] span`, `button:disabled`, `[aria-disabled="true"]`, `input:disabled`, `textarea:disabled`
- **속성**: `color`, `border-color`, `caret-color` (조건 허용범위 내)
- **금지 속성 미사용**: 확인 완료. `height`, `padding`, `overflow`, `margin`, `display` 등 레이아웃에 영향을 주는 속성은 전혀 사용하지 않고, 롤백 이전 상태에서 순수 색상값만 덮어씌움.

## 3. 가시성 확인
- **Step1**: `전투 데이터 파일`, `무브 로그 파일 (선택)`, `매핑 프리셋 파일 (JSON)`이 inline으로 표시됨. 내부 용어 노출 문제 없음.
- **Step2 selectbox**: selectbox(`Is_Victorious` 등) 내부 값이 밝은 배경 위에서 어두운 텍스트(`var(--text-on-light)`)로 올바르게 표시됨.
- **Step2 chip/tag**: `HP`, `Attack`, `Defense`, `Type1`, `Type2` 등 multiselect chip의 글자가 잘림 없이 원래 크기를 유지함. (크기 수정이 없으므로)
- **Step2 formula input**: 공식 입력창의 value/placeholder 모두 밝은 배경 대비 어두운 텍스트로 보임.
- **Dashboard**: Dataframe 셀의 텍스트가 명확하게 보임. 이전 disabled 버튼(이전/다음 버튼)의 텍스트도 완전히 감춰지지 않고 읽을 수 있음.

## 4. 스크린샷 위치
- `.codex_tmp/ui4k_minimal_color_only/step1_desktop.png`
- `.codex_tmp/ui4k_minimal_color_only/step2_mapping_desktop.png`
- `.codex_tmp/ui4k_minimal_color_only/step2_formula_desktop.png`
- `.codex_tmp/ui4k_minimal_color_only/dashboard_desktop.png`

## 5. 테스트 결과
- `py_compile main.py modules/...`: Pass
- `test_db_corpus_ui_state.py`: Pass
- `test_step1_db_corpus_upload_adapter.py`: Pass
- `test_step6_db_corpus_auto_schema.py`: Pass
- `test_step6_db_corpus_oneclick_backtest.py`: Pass
- `test_i15_integration_smoke.py`: Pass

## 6. 남은 이슈
- 없습니다. 이번 PR 목표인 레이아웃 유지 + 색상 복구를 달성했습니다.
