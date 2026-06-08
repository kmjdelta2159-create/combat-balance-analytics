# PR-U3 — Step 2 선택 섹션 expander 전환 + 위계 정리

> 대상 파일: `modules/step2_system_definition.py` (단일 파일)
> 성격: **레이아웃 전용**. 섹션 내부 로직·변수·session_state·반환값 일절 변경 금지. `with st.expander(...)` 래핑과 들여쓰기, 부제 1줄 추가만 한다.
> 검증: Streamlit이라 클린룸 불가 → 앱 로드 후 Step 2 캡처로만 확인. 적용 후 `wc -l`·`tail` 무결성 점검.

---

## 0. 배경 (왜 이 PR인가)

PR-U1이 Step 2를 `st.tabs` 4탭으로 바꿨다가 탭 2~4가 빈 화면이 되어 PR-U2에서 `if True:` 평면 렌더링으로 되돌렸다. 원인은 단순 버그가 아니라 도구 오선택이다 — 이 섹션들은 **조건부 콘텐츠**(컬럼/attack_log가 있어야 내용이 생김)라, 항상 채워져 있어야 의미 있는 탭과 맞지 않는다. 접힌 expander는 내용이 없어도 "닫힌 선택 섹션"으로 자연스럽게 읽힌다. **탭으로 회귀하지 말 것.**

현재 Step 2(`if not mapping_approved:` 블록)의 6개 섹션 중:

- 섹션 1 🔍 Data Mapping & Live Formula Validator — **진행에 필수**. 평면.
- 섹션 2 🎯 Move System — 평면
- 섹션 3 🏷️ Tag Dictionary — 평면
- 섹션 4 🔄 Logic Execution Order — 평면
- 섹션 5 🧩 기믹 채널 매핑 — 이미 expander
- 섹션 6 🍃 동적 메커니즘 — 이미 expander

진행에 반드시 필요한 건 섹션 1 하나뿐이고 2~6은 전부 선택적 정밀화다. 그래서 **카테고리가 아니라 필요성**으로 위계를 잡는다: 섹션 1은 항상 펼친 채 크게 두고, 2~6은 "시스템 세부 정의(선택)" 부제 하나 아래로 묶어 전부 접힌 expander로 만든다.

---

## 1. 변경 명세

### 변경 A — 선택 섹션 부제 삽입 (섹션 1과 섹션 2 사이)

현재 섹션 1의 끝과 섹션 2의 시작 사이는 이렇다 (L303 부근, 들여쓰기 12스페이스 기준):

```python
            st.divider()
            st.markdown("## 🎯 Move System (무브/어빌리티)")
```

이 `st.divider()` 다음, `## 🎯 Move System` 줄 **앞에** 부제 1줄을 추가한다:

```python
            st.divider()
            st.markdown("## ⚙️ 시스템 세부 정의 (선택) — 펼쳐서 정밀 조정")
            st.caption("아래 항목은 모두 선택입니다. 데이터 맵핑만 끝내면 맵핑 승인으로 진행할 수 있습니다.")
            with st.expander("🎯 Move System (무브/어빌리티)", expanded=False):
```

즉 기존 `st.markdown("## 🎯 Move System (무브/어빌리티)")` 줄을 위 3줄(부제 markdown + caption + expander 헤더)로 교체한다. 이때 **섹션 2 본문 전체를 expander 안으로** 넣어야 하므로 변경 B를 함께 적용한다.

### 변경 B — 섹션 2 (🎯 Move System) expander 래핑

- 시작: 위에서 교체한 `with st.expander("🎯 Move System (무브/어빌리티)", expanded=False):`
- 본문 범위: 현재 `move_library_edited = None` 줄(헤더 바로 다음)부터 **섹션 3 시작 직전**(`# ═══ Tag Normalization ═══` 주석 블록 / `st.divider()` 앞)까지.
- 그 본문 전 범위를 **+4스페이스 추가 들여쓰기**(12→16스페이스)한다.
- 섹션 2와 섹션 3 사이의 `st.divider()`는 **삭제**한다(expander가 자체적으로 구획을 나누므로 중복).

### 변경 C — 섹션 3 (🏷️ Tag Dictionary) expander 래핑

현재:

```python
            st.divider()
            st.markdown("## 🏷️ Tag Dictionary Mapping (태그 정규화)")
            st.info("💡 CSV에 있는 고유 태그를 ...")
```

`st.divider()`는 삭제하고, `st.markdown("## 🏷️ ...")` 줄을 다음으로 교체:

```python
            with st.expander("🏷️ Tag Dictionary Mapping (태그 정규화)", expanded=False):
```

- 본문 범위: 기존 `st.info("💡 CSV에 있는 ...")` 줄부터 **섹션 4 시작 직전**(`## 🔄 Logic Execution Order` 앞의 `st.divider()`)까지.
- 그 본문 전 범위를 **+4스페이스 추가 들여쓰기**한다.
- 단, 이 섹션 안에는 이미 `with st.expander(f"📋 ...")`(고유값별)가 중첩돼 있다. **중첩 expander는 그대로 두고** 함께 +4 밀면 된다 — Streamlit은 expander 중첩을 허용하므로 동작에 문제 없다. (만약 렌더 경고가 우려되면 변경 C는 래핑하지 말고 섹션 3을 평면 유지해도 된다. 아래 "안전 대안" 참고.)

### 변경 D — 섹션 4 (🔄 Logic Execution Order) expander 래핑

현재:

```python
            st.divider()

            st.markdown("## 🔄 Logic Execution Order (기획 의도/White-Box 확립)")
            st.info("💡 **가이드:** 각 로직 블록을 ...")
```

섹션 3과 섹션 4 사이의 `st.divider()`는 삭제하고, `st.markdown("## 🔄 ...")` 줄을 다음으로 교체:

```python
            with st.expander("🔄 Logic Execution Order (기획 의도/White-Box 확립)", expanded=False):
```

- 본문 범위: 기존 `st.info("💡 **가이드:** ...")` 줄부터 **섹션 5 시작 직전**(`# ── Phase 8d ──` 주석 / `with st.expander("🧩 기믹 채널 매핑 ...")` 앞의 `st.divider()`)까지.
- 그 본문 전 범위를 **+4스페이스 추가 들여쓰기**한다.
- 섹션 4와 섹션 5 사이의 `st.divider()`는 **남겨 둔다** — 이미 expander인 섹션 5·6과의 구분선이므로 유지가 자연스럽다. (선택: 삭제해도 무방하나 기본은 유지)

### 섹션 5·6 (🧩 채널 매핑 / 🍃 동적 메커니즘)

**변경 없음.** 이미 `with st.expander(..., expanded=False)`다. 새 부제 "시스템 세부 정의" 아래에 자연스럽게 형제로 놓이게 된다.

---

## 2. 절대 건드리지 말 것 (회귀0 게이트)

- 섹션 내부의 변수 대입·함수 호출·`st.session_state` 키·위젯 key·반환값(`return False, ...` / `return True, ...`)
- L151 `if not st.session_state.get('mapping_approved', False):` 가드, L152 `if True:` 블록, 하단 맵핑 승인 버튼·JSON 내보내기·`else`(mapping_approved=True) 블록
- 섹션 3 내부의 중첩 `with st.expander(f"📋 ...")`
- `_preprocess_dataframe` 등 L1~120 헬퍼

이 PR은 **레이아웃만** 바꾼다. 기능 동작·골든 출력은 0% 변해야 한다.

---

## 3. 들여쓰기 작업 주의 (가장 큰 리스크)

가장 흔한 실패는 **본문 일부만 +4 밀고 일부를 빠뜨려** 들여쓰기가 깨지는 것이다. 섹션별로 다음을 지킨다:

1. expander 헤더 다음 줄부터 다음 섹션 시작 직전까지 **연속 블록 전체**를 한 번에 +4한다. 빈 줄·주석 줄도 포함.
2. 본문 안의 기존 `if/for/with` 중첩은 상대 들여쓰기를 보존한 채 통째로 +4한다.
3. 멀티라인 문자열(삼중따옴표 `st.caption("""..."""`)이 있으면 문자열 **내용**은 밀지 말고 여는/닫는 줄 위치만 +4한다.

---

## 4. 안전 대안 (중첩 expander가 걱정되면)

섹션 3은 내부에 expander가 중첩돼 있어 가장 위험하다. 만약 Antigravity가 중첩 래핑에서 들여쓰기 정합을 확신하지 못하면, **변경 C만 생략**하고 섹션 3을 평면 유지하라(부제 아래 평면 markdown 헤더로 남김). 섹션 2·4 래핑 + 부제 추가만으로도 스크롤 피로의 대부분이 해소된다. 이 경우 보고에 "섹션 3 평면 유지" 명시.

---

## 5. 적용 후 산출/검증

1. `wc -l modules/step2_system_definition.py` — 줄 수 변화 보고(부제 +2줄, divider 삭제 -3줄 내외 ≈ 순증감 소폭).
2. `tail -40 modules/step2_system_definition.py` — 파일 끝(`else` 블록·Game Profile)이 절단 없이 온전한지 확인.
3. `python -c "import ast; ast.parse(open('modules/step2_system_definition.py').read())"` — 구문/들여쓰기 정합 확인(통과 필수).
4. `streamlit run main.py` → Step 2 진입 → 캡처: 섹션 1만 펼쳐지고, 그 아래 "⚙️ 시스템 세부 정의(선택)" 부제와 함께 🎯/🏷️/🔄/🧩/🍃 expander 5개가 접힌 채 나란히 보이는지. 각 expander 펼쳤을 때 내용이 정상 렌더되는지.
5. 맵핑 승인 버튼 클릭 → mapping_approved=True 분기 정상 진입(레이아웃 변경이 제어흐름을 깨지 않았는지) 확인.

3번(`ast.parse`)이 들여쓰기 사고를 잡는 1차 게이트다. 통과 못 하면 변경 D→C→B 역순으로 좁혀 원인 격리.
