# PR-U3b — Step 2 섹션 3·4 expander → 평면 복원 (렌더 버그 수정)

> 대상: `modules/step2_system_definition.py` (단일 파일)
> 성격: **레이아웃 전용**. 섹션 내부 로직·변수·session_state·반환값 일절 변경 금지. expander 헤더
> 2개를 평면 markdown으로 바꾸고 각 본문을 -4 들여쓰기만 한다.
> 검증: Streamlit이라 클린룸 불가 → `ast.parse` 통과 + 앱 Step2 캡처.

---

## 0. 배경 (실측 버그)

PR-U3가 섹션 2~6을 expander로 감쌌는데, **섹션 3·4만** 앱에서 헤더가 깨진 흰 막대로 뜨고 내용이
정상 렌더되지 않는다(앱 캡처 확인). 원인은 expander와 **호환되지 않는 위젯**을 품었기 때문:

- **섹션 3 🏷️ Tag Dictionary (L407 expander)**: 내부에 중첩 `st.expander`(L420 `📋 ...`)가 있다.
  **Streamlit은 expander 중첩을 금지**한다(`Expanders may not be nested`). 매핑 컬럼이 있는
  데이터셋에선 예외가 나고, 없어도 외곽 헤더가 깨진다.
- **섹션 4 🔄 Logic Execution Order (L456 expander)**: 내부에 `sort_items`(streamlit-sortables
  커스텀 컴포넌트=iframe)가 있다. **커스텀 컴포넌트는 expander 안에서 높이가 0으로 접혀** 드래그
  블록이 안 보인다.

→ 이 두 섹션만 **평면(flat) 헤더로 복원**한다. 그러면 중첩이 풀려 📋가 정상 최상위 expander가
되고, sortable도 정상 높이로 렌더된다. 섹션 2(🎯)·5(🧩)·6(🍃) expander는 정상이므로 **유지**.
(이는 PR-U3가 명시한 "안전 대안"을 섹션 4까지 확장한 것.)

---

## 1. 변경 (2곳, 평면화)

### 변경 A — 섹션 3 (🏷️ Tag Dictionary) 평면화
L407을 expander → 평면 markdown으로 교체하고, **본문 L408~454 전체를 -4 들여쓰기**(16→12,
내부 상대 들여쓰기는 보존):

현재:
```python
            with st.expander("🏷️ Tag Dictionary Mapping (태그 정규화)", expanded=False):
                st.info("💡 CSV에 있는 ...")
                ...
                st.divider()
```
변경 후:
```python
            st.markdown("### 🏷️ Tag Dictionary Mapping (태그 정규화)")
            st.info("💡 CSV에 있는 ...")
            ...
            st.divider()
```
- 헤더 줄(L407)을 `st.markdown("### 🏷️ Tag Dictionary Mapping (태그 정규화)")`로 교체(들여쓰기 12).
- 그 아래 본문 L408~454(`st.info`부터 `st.divider()`까지) 전체를 **일괄 -4**. 내부의
  `if mappable_gimmicks:`/`for`/중첩 `with st.expander("📋 ...")`는 상대 들여쓰기 유지한 채 통째로
  -4(중첩 expander는 이제 외곽이 없어 합법).

### 변경 B — 섹션 4 (🔄 Logic Execution Order) 평면화
L456을 expander → 평면 markdown으로 교체하고, **본문 L457~477 전체를 -4 들여쓰기**:

현재:
```python
            with st.expander("🔄 Logic Execution Order (기획 의도/White-Box 확립)", expanded=False):
                st.info("💡 **가이드:** ...")
                ...
                    st.caption("✅ 현재 로직 실행 순서가 저장되었습니다.")
```
변경 후:
```python
            st.markdown("### 🔄 Logic Execution Order (기획 의도/White-Box 확립)")
            st.info("💡 **가이드:** ...")
            ...
                st.caption("✅ 현재 로직 실행 순서가 저장되었습니다.")
```
- 헤더 줄(L456)을 `st.markdown("### 🔄 Logic Execution Order (기획 의도/White-Box 확립)")`로 교체(들여쓰기 12).
- 본문 L457~477(`st.info`부터 sortable·caption까지) 전체를 **일괄 -4**.

### 그대로 둘 것
- 섹션 2 🎯 Move System(L306 expander)·섹션 5 🧩 채널(L482)·섹션 6 🍃 메커니즘(L512) expander 유지.
- 부제 "## ⚙️ 시스템 세부 정의 (선택)"·caption 유지.
- 섹션 4 다음 `st.divider()`(L479)와 섹션 간 divider 유지.

---

## 2. 절대 건드리지 말 것 (회귀0)
- 섹션 내부 변수·함수 호출·`st.session_state` 키·위젯 key·`tag_mapping`/`combat_flow`/`sort_items`
  로직·반환값. **들여쓰기 레벨만** 바뀐다.
- `mapping_approved` 가드·승인 버튼·else 블록.

---

## 3. 검증
1. `python -c "import ast; ast.parse(open('modules/step2_system_definition.py').read())"` — 통과 필수(들여쓰기 사고 1차 게이트).
2. `wc -l` / `tail -40 modules/step2_system_definition.py` — 끝부분 절단 없음.
3. `streamlit run main.py` → Step2 캡처: "⚙️ 시스템 세부 정의(선택)" 아래
   - 🎯 Move System: 접힌 expander(정상)
   - 🏷️ Tag Dictionary: **평면 헤더 + 내용 정상 노출**(매핑 컬럼 있으면 📋 expander가 정상 펼쳐짐)
   - 🔄 Logic Execution Order: **평면 헤더 + 드래그 블록(Phase 1/2/3) 정상 렌더**
   - 🧩 채널·🍃 메커니즘: 접힌 expander(정상)
4. 맵핑 승인 클릭 → mapping_approved 분기 정상.

`ast.parse`(1번) 실패 시 변경 B→A 역순으로 좁혀 들여쓰기 원인 격리.

---

## 4. 적용 후 보고
- 수정 라인 + `wc -l`/`tail` 무결성.
- 앱 Step2 캡처(태그 정규화 내용·실행순서 드래그 블록이 보이는지).
