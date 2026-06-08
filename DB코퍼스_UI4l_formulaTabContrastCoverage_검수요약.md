# DB코퍼스 UI4l formulaTabContrastCoverage 검수요약

## 1. 수정 파일
- `main.py`: 글로벌 CSS 인젝션 업데이트

## 2. CSS 최소 수정 사항
- **수정한 selector**:
  - `[data-testid="stPills"] button`, `[data-testid="stPills"] span`, `[data-testid="stPills"] p`, `[data-baseweb="pill"] span` (변수 칩/pill 텍스트)
  - `[data-baseweb="base-input"] input`, `[data-baseweb="base-input"] textarea` (입력 폼)
  - `[data-testid="stButton"] button:disabled`, `[data-testid="stFormSubmitButton"] button:disabled` (disabled 상태 버튼)
  - `.stMarkdown p`, `[data-testid="stText"] p`, `[data-testid="stTab"] p`, `.stAlert p` 등 (공식 검증 탭 label/help text)
- **사용한 CSS 속성**:
  - `color`, `caret-color`, `border-color`
- **금지 속성 미사용**: 크기, 여백, 레이아웃 등과 관련된 CSS 속성은 전혀 건드리지 않고, 순수하게 색상 관련 텍스트 가시성 속성만 수정.

## 3. 가시성 해결 여부 (공식 검증 탭)
- **변수 칩**: 흰 배경의 pill 텍스트 (HP, Attack 등 8개 변수)가 어두운 색상(`var(--text-on-light)`)으로 지정되어 명확히 보임.
- **formula input placeholder/value**: '전투 데미지 공식 (Damage Formula)' 입력창이 밝은 텍스트/caret 색상을 적용받아 흰 배경 위에서 가시성 문제 해결됨.
- **disabled 다음 단계 버튼**: `[data-testid="stButton"] button:disabled`을 구체적으로 타겟팅하여 어두운 배경과 섞이지 않도록 수정, 텍스트 가시성 확보.
- **공식 검증 탭 label/help text**: Hover 없이도 텍스트가 명확하게 보이도록 `var(--text-on-dark)` 등 대비 강화.

## 4. 회귀 확인
- **Step2 필수 매핑 탭**: 이전 UI4k에서 수정한 selectbox, multiselect chip 잘림, input 크기 등이 다시 깨지거나 변경되지 않고 레이아웃 원형을 그대로 유지함.
- **chip 잘림**: 크기 조정을 하지 않았으므로 단어 첫 글자나 전체 텍스트 잘림 현상 발생 안 함.

## 5. 스크린샷 위치
- `.codex_tmp/ui4l_formula_tab_contrast/step2_formula_empty.png`
- `.codex_tmp/ui4l_formula_tab_contrast/step2_formula_with_value.png`
- `.codex_tmp/ui4l_formula_tab_contrast/step2_mapping_regression.png`

## 6. 테스트 결과
- `py_compile`: Pass
- `test_db_corpus_ui_state.py`: Pass
- `test_step1_db_corpus_upload_adapter.py`: Pass
- `test_step6_db_corpus_auto_schema.py`: Pass
- `test_step6_db_corpus_oneclick_backtest.py`: Pass
- `test_i15_integration_smoke.py`: Pass

## 7. 남은 이슈
- 없습니다. 레이아웃 파괴 없이 공식 검증 탭 내부의 색상 대비 문제 해결을 완료했습니다.
