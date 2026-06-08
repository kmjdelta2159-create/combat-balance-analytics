# UI 홀리스틱 재설계안

> 작성일: 2026-06-06  
> 상태: 설계 확정 대기 → PR 실행 준비  
> 스텝 파일 전체 열람 후 작성. Sonnet 레벨 판단.

---

## 0. 현재 상태 요약 (Before)

| 스텝 | 파일 | 현상 |
|------|------|------|
| 1 | step1_upload.py | ✅ PR-F1 이미 적용됨 (멀티포맷). attack_log 업로드 없음 |
| 2 | step2_system_definition.py (1067줄) | ❌ PR-U1 탭 적용됐으나 탭 2~4 전부 빈 화면 |
| 3 | step5_discrepancy.py | ✅ 단순. 공식 없으면 조기 return. 변경 불필요 |
| 4 | step2_profiling.py | ✅ 자체 탭 작동 정상. 변경 불필요 |
| 5 | step6_dashboard.py (1348줄) | ✅ 탭 작동 정상. L488 fullscreen 버그만 잔존 |
| — | requirements.txt | ❌ openpyxl·pyarrow 손상 (문자 사이 공백) |
| — | step3_flow_auditor.py | 🗑️ 데드 파일 (49줄) |
| — | step4_role_definition.py | 🗑️ 데드 파일 (257줄) |

---

## 1. 핵심 UX 문제 3가지

### 문제 A — 파일 업로드 분리
attack_log 업로드가 Step 2 → Move System 섹션 안 expander에 묻혀 있다.  
처음 쓰는 사용자는 Step 1에서 무언가를 올리고 Step 2로 가는데,  
Move System 분석을 하려면 Step 2 깊숙이 들어가서 또 다른 파일을 올려야 한다는 걸 모른다.  
**→ attack_log 업로드를 Step 1으로 이동.**

### 문제 B — Step 2 탭 구조 실패
PR-U1이 4-tab 구조로 교체했지만 탭 2(무브·타입), 3(메커니즘·태그), 4(실행순서)가 전부 빈 화면.  
원인: Streamlit `st.tabs`는 Python scope가 아니다.  
`with tab:` 블록 밖에서 conditional로 렌더링하거나,  
내부 content가 조건부라서 session_state 조건 미충족 시 아무것도 안 그린다.  
**→ 탭을 버리고 expander로 전환. expander는 scope 문제가 없고 conditional content에 안전.**

### 문제 C — 🔬 RE expander 위치
`if not mapping_approved:` 블록 밖 L127-129에 있음.  
맵핑 완료 후에도 항상 노출됨 → 혼선.  
**→ 맵핑 블록 안으로 이동하거나 삭제.**

---

## 2. 재설계 방향 (After)

### Step 1 — "데이터 파일 업로드"
현행 구조 유지 + attack_log 업로드 추가.

```
st.subheader("새로운 전투 로그 업로드")
  [battle_log 업로더]     ← 필수
  [원본 데이터 미리보기 expander]

st.divider()

st.subheader("어택 로그 업로드 (선택)")
  st.info("📌 무브 단위 데이터가 있는 경우 업로드하세요. 없으면 건너뜁니다.")
  [attack_log 업로더]     ← optional
  [미리보기 expander]

st.divider()

st.subheader("또는 이전 맵핑 프리셋(JSON) 불러오기")
  [preset 업로더]
```

`can_proceed` 조건: battle_log만 있으면 True. attack_log는 optional.

---

### Step 2 — "시스템 정의" (expander 구조)

**전체 흐름**:
```
[🔬 RE 진단 expander]  ← if not mapping_approved 블록 안으로 이동

if not mapping_approved:
    ── 섹션 1: 🎯 데이터 맵핑      (항상 expanded=True, 가장 중요)
    ── 섹션 2: 🕹️ 무브 시스템      (expander, expanded=False, attack_log 있을 때만 헤더 활성)
    ── 섹션 3: 🏷️ 태그 사전        (expander, expanded=False)
    ── 섹션 4: ⚙️ 동적 메커니즘    (expander, expanded=False)
    ── 섹션 5: 🔄 실행 순서        (expander, expanded=False)
    ── 섹션 6: 📡 채널 맵핑        (expander, expanded=False)
    [맵핑 승인 버튼]

else:
    [맵핑 완료 요약 카드]
    [재정의 버튼]
```

**탭 vs expander 결정 근거**:
- 탭: 모두 항상 존재해야 의미 있음. conditional content면 탭이 비어 보임.
- expander: 섹션 존재 자체가 optional이어도 OK. 접힌 채로 있으면 공간 낭비 없음.
- 이 앱의 섹션들은 "데이터 컬럼이 있어야만" 렌더링되는 conditional content → expander가 맞다.

**섹션 2 (무브 시스템) 처리**:
- attack_log가 session_state에 없으면: expander 헤더에 `(attack_log 필요 — Step 1에서 업로드)` 표시 후 내용 없음
- attack_log 있으면: 기존 무브 매핑 UI 그대로 렌더링

---

### Step 3 / 4 / 5 — 변경 없음
현행 유지. 각자 작동 정상.

---

## 3. PR 목록 (우선순위 순)

### [즉시] PR-HOTFIX — requirements.txt 손상 수정

**문제**: `o p e n p y x l` ← 각 문자 사이에 공백. pip 인식 불가.  
**수정**: 파일 전체를 아래로 교체.

```
streamlit
pandas
numpy
scikit-learn
scipy
plotly
streamlit-sortables
gplearn
openpyxl
pyarrow
```

---

### [P1] PR-U2 — Step 2 탭→expander 전환 + 🔬 RE 위치 수정

**대상**: `modules/step2_system_definition.py`  
**변경 내용**:
1. 기존 `t_data, t_move, t_tag, t_mech = st.tabs([...])` 및 `with t_*:` 블록 제거
2. 각 섹션을 `with st.expander("...", expanded=False):` 로 래핑
3. 데이터 맵핑 섹션만 `expanded=True`
4. 🔬 RE expander를 `if not mapping_approved:` 블록 안으로 이동 (L127 → L130 이후)
5. 무브 시스템 섹션: attack_log 업로드 위젯 제거 (Step 1으로 이동하므로)

**주의**: 섹션 내부 로직은 일절 건드리지 않음. 래핑 구조만 변경.

---

### [P2] PR-S1 — attack_log 업로드를 Step 1으로 이동

**대상**: `modules/step1_upload.py`, `modules/step2_system_definition.py`  
**step1 변경**:
- `render_upload()` 끝부분(preset 업로더 앞)에 attack_log 섹션 추가
- `st.session_state["attack_log_df"]` 에 저장
- attack_log 관련 session_state key: `attack_df`, `attack_file_name`

**step2 변경**:
- 무브 시스템 expander 상단에서 `st.session_state.get("attack_df")` 체크
- 없으면: `st.info("Step 1에서 attack_log를 업로드하면 무브 분석이 활성화됩니다.")`
- 있으면: 기존 무브 매핑 UI 렌더링

---

### [P3] PR-DEAD — 데드 파일 삭제

- `modules/step3_flow_auditor.py` 삭제
- `modules/step4_role_definition.py` 삭제

main.py에서 import 없음 확인됨 → 삭제해도 앱 무관.

---

## 4. 실행 순서

```
PR-HOTFIX (requirements.txt) → 즉시 직접 수정 가능
PR-U2 (Step2 탭→expander)   → Antigravity 적용
PR-S1 (attack_log → Step1)  → Antigravity 적용
PR-DEAD (데드파일 삭제)       → 직접 삭제
```

PR-U2와 PR-S1은 순서 무관하나 U2 먼저 하면 Step2 구조가 안정된 상태에서 S1 작업 가능.

---

## 5. 스코프 밖 (이번 재설계에서 제외)

- Step 5 L488 fullscreen 버그 — 기능 버그, UX 재설계와 별개
- Seismic Toss / Brave Bird 점근 꼬리 — 공식 수정, UX와 무관
- Showdown HTML 직접 파싱 지원 — 타겟 유저(인디/중소게임사)에게 불필요
