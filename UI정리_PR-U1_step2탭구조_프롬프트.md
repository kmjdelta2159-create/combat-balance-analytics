# PR-U1 — step2 4탭 구조화 (UI 정리)

> **목표**: `modules/step2_system_definition.py`의 `render_system_definition()` 내부
> 6섹션을 `st.tabs` 4탭으로 묶어 끝없는 스크롤을 탭 전환으로 대체한다.
> **기능 무변 · 레이아웃만** — 위젯 key·세션 키·제어흐름 전부 보존.

---

## 0. 핵심 안전점 (먼저 읽기)

`st.tabs`는 **Python 스코프를 만들지 않는다** — `with t_data:` 블록 안에서 정의한
`base_stats`, `gimmicks`, `is_valid` 등이 `with t_mech:` 블록이나 하단 버튼에서
그대로 읽힌다. 따라서 탭화가 변수 참조를 깨지 않는다.

제어흐름 확인(수정 전):
- 상단 가드: 124–125 (`return False, ...`)
- 하단 return: 913 (`return False, ...`) / 1072 이후 (`return True, ...`)
- 중간 return 없음 → 탭 중간에 흐름 분기 없음, 안전.

---

## 1. 현재 구조 요약

```
def render_system_definition():          # 121
    [가드 124–125]
    [🔬 RE expander 127–129]             ← if not mapping_approved 바깥
    [validation warnings 131–146]
    [df·is_valid 초기화 148–152]
    if not mapping_approved:             # 154
        [Data Mapping·Formula 155–301]
        [Move System 302–407]
        [Tag Dictionary 409–458]
        [Logic Order 460–483]
        [Channel Mapping expander 487–514]
        [동적 메커니즘·Switch 516–824]
        [하단 버튼·download 827–912]
        return False, ...                # 913
    else:                                # 915
        [매핑 완료 뷰 + return True]
```

---

## 2. 목표 구조

```
def render_system_definition():
    [가드 — 무변]
    [validation warnings — 무변]         ← 🔬 RE block 제거(탭으로 이동)
    [df·is_valid 초기화 — 무변]
    if not mapping_approved:
        t_data, t_move, t_mech, t_logic = st.tabs([
            "📊 데이터·공식", "🎯 무브·타입", "⚙️ 메커니즘·태그", "🔄 실행순서"
        ])
        with t_data:
            [Data Mapping & Formula 전체]
        with t_move:
            [Move System 전체]
        with t_mech:
            [🔬 RE expander — 여기로 이동]
            [Tag Dictionary 전체]
            [Channel Mapping expander 전체]
            [동적 메커니즘·Switch 전체]
        with t_logic:
            [Logic Execution Order 전체]
        [st.divider()]
        [하단 버튼·download — 탭 밖, 무변]
        return False, ...
    else:
        [무변]
```

---

## 3. 변경 지침 (순서대로)

### 3-A. 🔬 RE expander 블록 제거 (현 위치)

아래 세 줄을 **현 위치(127–129)에서 삭제**한다. (내용은 3-D에서 ⚙️ 탭 첫 줄로 다시 삽입)

```python
    with st.expander("🔬 트레이스 메커니즘 RE — 자동 검출 + 수정 (효과 디스패처 EFFECTS)", expanded=False):
        from modules.step_mechanism_re import render_mechanism_re
        render_mechanism_re()
```

### 3-B. 탭 선언 삽입

`if not st.session_state.get('mapping_approved', False):` (154) 라인 바로 다음 줄,
`st.markdown("## 🔍 Data Mapping...")` **앞**에 삽입:

```python
        t_data, t_move, t_mech, t_logic = st.tabs([
            "📊 데이터·공식", "🎯 무브·타입", "⚙️ 메커니즘·태그", "🔄 실행순서"
        ])
```

### 3-C. `with t_data:` — Data Mapping·Formula

탭 선언 바로 다음, 아래 블록으로 감싼다.

**시작**: `st.markdown("## 🔍 Data Mapping & Live Formula Validator")` (현 155)
**끝**: `elif _sr_cands == []: st.info("공식 후보를 찾지 못했습니다...")` (현 299–300)
그 아래 닫는 `# ═══` 주석 줄(302) **직전**까지.

즉 `# Phase 8a` 구분 주석 이전 전체.

```python
        with t_data:
            st.markdown("## 🔍 Data Mapping & Live Formula Validator")
            ... (기존 155–301 내용을 한 단계 추가 들여쓰기)
```

**섹션 내 `st.divider()`·헤더는 그대로 유지.**

### 3-D. `with t_move:` — Move System

**시작**: `# ═══ Phase 8a — Move System` 주석 (현 302)
**끝**: `st.caption("로그에 무브 컬럼... 단일 데미지 공식으로 동작합니다.")` (현 406–407)
즉 Tag Dictionary 구분 주석(409) **직전**까지.

```python
        with t_move:
            # ═══ Phase 8a — Move System ...
            ... (기존 302–407 내용을 한 단계 추가 들여쓰기)
```

맨 앞 `st.divider()` (현 305)는 **삭제**해도 되고 유지해도 됨. (탭이 시각 구분 역할)

### 3-E. `with t_mech:` — 메커니즘·태그 (🔬 이동 포함)

**이 탭의 내용 순서**:

1. **🔬 RE expander (3-A에서 제거한 블록을 여기 삽입)**:
```python
        with t_mech:
            with st.expander("🔬 트레이스 메커니즘 RE — 자동 검출 + 수정 (효과 디스패처 EFFECTS)", expanded=False):
                from modules.step_mechanism_re import render_mechanism_re
                render_mechanism_re()
```

2. **Tag Dictionary** (현 409–458): 한 단계 추가 들여쓰기로 이어서.
   앞 `st.divider()` (현 412)는 삭제 또는 유지 자유.

3. **Channel Mapping expander** (현 487–514): 한 단계 추가 들여쓰기로 이어서.

4. **동적 메커니즘·Switch** (현 516–824): 한 단계 추가 들여쓰기로 이어서.
   앞 `st.divider()` (현 460, 485)는 삭제 또는 유지 자유.

### 3-F. `with t_logic:` — Logic Execution Order

현재 Logic Order 블록(460–483)은 Tag Dictionary 뒤에 있다.
이 블록을 `with t_logic:` 으로 감싼다.

**단, 위치를 `with t_mech:` 앞으로 옮기거나 뒤로 옮기지 않는다.**
`st.tabs`는 선언 순서대로 탭을 렌더링하므로, 코드 내 `with t_logic:` 블록의
**실제 위치가 어디든** 탭 표시 순서는 `st.tabs([...])` 선언 순서(t_data·t_move·t_mech·t_logic)를 따른다. 가장 간단한 방법은 현재 위치(Tag Dictionary 다음)에서 `with t_logic:` 으로 감싸는 것.

```python
        with t_logic:
            st.markdown("## 🔄 Logic Execution Order ...")
            ... (기존 460–483 내용을 한 단계 추가 들여쓰기)
```

Logic Order 앞 `st.divider()` (현 460 직전)는 삭제 또는 유지 자유.

### 3-G. 하단 버튼·return — 탭 밖 유지 (무변)

`st.divider()` + `c_btn, c_json = st.columns(2)` + 버튼 + `st.download_button` +
`return False, ...` — **모두 탭 블록 밖**, 현 들여쓰기 수준(`if not mapping_approved:` 본문 직접 indent) 그대로.

---

## 4. 들여쓰기 원칙

- 기존 `if not mapping_approved:` 본문은 4-space 1단계 들여쓰기.
- 탭 선언 후 각 `with t_*:` 블록은 추가 4-space (합계 8-space).
- `with t_*:` 안의 내용은 다시 추가 4-space (합계 12-space).
- 기존 내용이 이미 갖고 있던 **상대 들여쓰기는 유변 없음** — 최상위 indent만 4칸 늘어남.

---

## 5. 금지 사항

- 위젯 `key=` 값 변경 금지.
- `st.session_state` 키 이름 변경 금지.
- `_channel_roles`, `move_library_edited`, `_mech_cfg` 등 하단 버튼이 참조하는
  변수명 변경 금지.
- `return` 문 위치·내용 변경 금지.
- 로직(if/else 조건·계산식·session set) 변경 금지.

---

## 6. 검증 (앱사이드, 적용 후)

1. **앱 로드 에러 없음** — `streamlit run main.py` 후 import 오류·indent 오류 없음.
2. **step2에 탭 4개 표시** — 📊·🎯·⚙️·🔄 각 탭이 보임.
3. **각 탭에 해당 섹션** — 📊 탭에 Data Mapping, 🎯 탭에 Move System,
   ⚙️ 탭에 🔬 RE + Tag + Channel + 동적 메커니즘, 🔄 탭에 Logic Order.
4. **하단 버튼 정상** — 어느 탭에서든 '🚀 파이프라인 시작' 버튼이 하단에 보이고,
   `is_valid` 계산이 정상(매핑 미완 시 disabled).
5. **다음 단계 진행** — 버튼 클릭 후 step3으로 이동, `return True` 정상.
6. **회귀0 게이트** — `run_b4.py` 골든 수치 무변.

각 탭 캡처 + 버튼 클릭 후 캡처를 붙여준다.

---

## 7. wc 무결성 (프롬프트 파일 자체)

적용 후: `wc -l UI정리_PR-U1_step2탭구조_프롬프트.md` 값을 확인.
