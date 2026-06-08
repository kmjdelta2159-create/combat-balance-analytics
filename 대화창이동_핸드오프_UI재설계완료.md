# 대화창 이동 핸드오프 — UI 재설계 완료

> 작성일: 2026-06-06  
> 이전 대화에서 완료된 내용 + 다음 대화에서 할 일

---

## 1. 프로젝트 개요

**Combat Balance Analytics** — 턴제 게임 밸런스 분석 도구.  
타겟: 인디게임 개발자 + 중소게임사.  
스택: Streamlit SPA (5단계 위저드) + Python ML.

앱 진입점: `main.py` → Step1→2→3→4→5 순서형 흐름.

| 스텝 | 파일 | 역할 |
|------|------|------|
| 1 | modules/step1_upload.py (199줄) | 전투로그 파일 업로드 |
| 2 | modules/step2_system_definition.py (1065줄) | 컬럼 매핑 + 공식 정의 |
| 3 | modules/step5_discrepancy.py | 공식 오류 상위 20행 표시 |
| 4 | modules/step2_profiling.py | ML 프로파일링 (탭 2개, 작동 정상) |
| 5 | modules/step6_dashboard.py (1348줄) | GM Mode + Character Builder 시뮬레이터 |

---

## 2. 이번 대화에서 완료한 작업

### 2-1. PR-F1 (이전에 이미 적용됨)
step1_upload.py: CSV 전용 → CSV·xlsx·xls·json·tsv·txt·parquet 멀티포맷 지원.  
`_parse_log_file()` 함수로 확장자별 분기 파싱.

### 2-2. requirements.txt 수정
`o p e n p y x l` 형태로 문자 사이 공백이 생긴 손상 파일 → 정상 복구.

### 2-3. PR-U2 — Step 2 빈 탭 버그 수정
**문제**: Antigravity가 이전에 `st.tabs` 4-탭 구조를 적용했으나 탭 2~4가 전부 빈 화면.  
**원인**: Streamlit `st.tabs`는 Python scope가 아님. `with t_data:` 안에 모든 content가 들어가고 t_move/t_mech/t_logic 블록이 비어있었음.  
**수정**: `st.tabs` 4줄 → `if True:` 1줄 교체. 모든 섹션 평면 렌더링.

```python
# Before
t_data, t_move, t_mech, t_logic = st.tabs([
    "📊 데이터·공식", "🎯 무브·타입", "⚙️ 메커니즘·태그", "🔄 실행순서"
])
with t_data:

# After
if True:  # 탭 제거 — 모든 섹션 평면 렌더링
```

### 2-4. PR-S1 — attack_log 업로드 Step 1으로 이동
**문제**: attack_log 업로드 위젯이 Step 2 → Move System 섹션 안 expander에 묻혀 있었음.  
**수정**:
- step1_upload.py에 "어택 로그 업로드 (선택)" 섹션 추가 (battle log 업로더 아래).
- step2_system_definition.py의 attack_log file_uploader 위젯 제거. session_state 읽기(`st.session_state.get("attack_log_df")`)는 그대로 유지 — 기존 무브 분석 로직 정상 작동.

### 2-5. 홀리스틱 재설계안 문서화
`UI_홀리스틱_재설계안.md` 작성. 전체 문제 목록 + PR 우선순위 포함.

---

## 3. 현재 남은 작업

### [선택] PR-U3 — Step 2 섹션 expander 래핑
현재 Step 2는 모든 섹션이 평면으로 보임. 섹션이 많아 스크롤이 길다.  
아래 3개 섹션을 `st.expander(expanded=False)`로 래핑하면 UX 개선됨:

| 섹션 | 현재 | 목표 |
|------|------|------|
| 🎯 무브 시스템 (L307) | 항상 펼쳐짐 | expander |
| 🏷️ 태그 사전 (L413) | 항상 펼쳐짐 | expander |
| 🔄 실행 순서 (L461) | 항상 펼쳐짐 | expander |

**주의**: 각 섹션의 콘텐츠 전체를 `with st.expander():` 안에 넣어야 하므로 해당 콘텐츠를 4스페이스 추가 들여쓰기해야 함. 난이도: 중간.

이미 expander로 감싸진 섹션:
- 채널 매핑 (L489) ✅
- 동적 메커니즘 (L519) ✅

### [미해결] PR-DEAD — 데드 파일 삭제
샌드박스 삭제 권한 없어 수동 삭제 필요:
- `modules/step3_flow_auditor.py` (49줄) — 앱에 import 없음, 무관
- `modules/step4_role_definition.py` (257줄) — 앱에 import 없음, 무관

### [보류] 점근 꼬리 (Asymptotic Tail)
- Seismic Toss — `fixed_damage` 처리
- Brave Bird — `recoil` 처리
기능 버그. UI와 무관.

---

## 4. 파일 구조 핵심 메모

### step2_system_definition.py 구조 (1065줄)
```
L1-120   헬퍼 함수들 (_preprocess_dataframe, _apply_tag_mapping, _render_game_profile_panel)
L121     render_system_definition() 시작
L124-125 df 없으면 조기 return
L126-143 Validation warnings 배너 (mapping_approved 이전에도 항상 표시)
L151     if not mapping_approved: 블록 시작
L152     if True:  ← PR-U2로 탭 대체됨
L155     st.markdown("## 🔍 Data Mapping & Live Formula Validator")  ← 섹션 1
L303     st.divider() + L307 st.markdown("## 🎯 Move System")       ← 섹션 2
L314     attack_log_df = st.session_state.get(...)  ← Step1에서 읽어옴
L318     st.caption(...)  ← upload 위젯 없어짐
L409     st.divider() + L413 st.markdown("## 🏷️ Tag Dictionary")   ← 섹션 3
L457     st.divider() + L461 st.markdown("## 🔄 Logic Execution Order") ← 섹션 4
L485     with st.expander("🧩 기믹 채널 매핑...")                    ← 섹션 5 (이미 expander)
L515     with st.expander("🍃 동적 메커니즘 부착...")                ← 섹션 6 (이미 expander)
L822     if True: 블록 끝
L824     st.divider()
L826-910 맵핑 승인 버튼 + JSON 내보내기
L912     return False, "..."
L914-1065 else 블록 (mapping_approved=True): ML 학습 + Game Profile
```

### session_state 주요 키
```
df                  — 메인 전투 로그 DataFrame
attack_log_df       — 어택 로그 DataFrame (Step 1에서 저장)
mapping_approved    — bool
global_damage_formula
system_stats        — 숫자형 스탯 컬럼 리스트
system_gimmicks     — 카테고리/기믹 컬럼 리스트
target_col          — 승패 결과 컬럼
ml_coefs            — 로지스틱 회귀 계수 dict
character_library   — 캐릭터 라이브러리 dict
game_config         — 무브 시스템 + 동적 메커니즘 설정
```

---

## 5. 외부 코드 생성기

이 프로젝트는 **Antigravity**라는 외부 코드 생성기를 사용한다.  
사용법: .md 프롬프트 파일을 Antigravity에 붙여넣으면 코드 변경을 적용함.  
단, Claude(나)가 직접 Edit/Write 도구로 파일을 수정할 수 있으므로 Antigravity가 불필요한 경우가 많음.

---

## 6. 앱 실행

```bash
streamlit run main.py
```
