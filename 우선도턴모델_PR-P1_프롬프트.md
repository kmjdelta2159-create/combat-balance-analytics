# 우선도 턴 모델 PR-P1 — 무브 우선도 필드 (순수 가법)
Antigravity 작업 지시서. 아래 find/replace를 **정확한 문자열 치환**으로 적용한다. 각 FIND 블록은 프로젝트 파일에 byte-exact 1회 등장함을 빌더가 Grep으로 확인했고, REPLACE 로직은 하니스 단위검증(5케이스) + 클린룸 컴파일을 통과했다.
## 목적

결정-후-해결/우선도 작업의 토대다. 무브 엔티티에 `priority` 필드를 더한다. `move_extraction`이 우선도 컬럼을 자동 감지하고(힌트: priority/우선도/우선순위), 추출된 무브 dict에 `priority`(기본 0)를 포함한다. step2는 감지된 우선도 컬럼을 extract_moves에 넘긴다.

**순수 가법·회귀 0**: 우선도 컬럼이 없으면 priority_col=None → 그룹핑 키 불변, 모든 무브 priority=0. 아직 이 필드를 읽는 곳이 없어(우선도 정렬은 PR-P2) 시뮬 동작 변화 0. 무브 표(data_editor)에 priority 열이 보여 사용자가 직접 우선도를 수정할 수도 있다(개입).
## 변경 범위

`modules/move_extraction.py` 5곳(힌트 상수·detect 반환·extract 시그니처·groupby 키·무브 dict), `modules/step2_system_definition.py` 1곳(extract_moves 호출). **다른 파일·다른 영역은 건들지 않는다.** 게임 이름·전용 분기 없음(도메인 중립).
## 적용 규칙

- FIND를 찾아 REPLACE로 **그대로** 교체한다. 들여쓰기·공백·한글 주석 한 글자도 바꾸지 않는다.
- 임의 리팩터·이름 변경·추가 최적화·하드코딩 금지. 지시된 치환만 한다.
- 적용 후 `python -c "import modules.move_extraction, modules.step2_system_definition"`가 통과해야 한다.

---
# 파일: `modules/move_extraction.py`
## MX-1 우선도 힌트 상수 추가

**FIND:**

```python
_NAME_EXACT = ("move", "skill", "ability", "무브", "스킬")
```

**REPLACE:**

```python
_NAME_EXACT = ("move", "skill", "ability", "무브", "스킬")
_PRIORITY_HINTS = ("move_priority", "priority", "우선도", "우선순위")
```

## MX-2 detect_move_columns에 priority 감지

**FIND:**

```python
    type_ = _find(cols, _TYPE_HINTS, exclude={power, category, name})
    return {"power": power, "type": type_, "category": category, "name": name}
```

**REPLACE:**

```python
    type_ = _find(cols, _TYPE_HINTS, exclude={power, category, name})
    priority = _find(cols, _PRIORITY_HINTS, exclude={power, category, name, type_})
    return {"power": power, "type": type_, "category": category, "name": name, "priority": priority}
```

## MX-3 extract_moves 시그니처에 priority_col

**FIND:**

```python
def extract_moves(df, power_col, type_col=None, category_col=None, name_col=None):
```

**REPLACE:**

```python
def extract_moves(df, power_col, type_col=None, category_col=None, name_col=None, priority_col=None):
```

## MX-4 groupby 키에 priority_col 포함

**FIND:**

```python
    keys = [c for c in (name_col, type_col, category_col, power_col)
            if c and c in df.columns]
```

**REPLACE:**

```python
    keys = [c for c in (name_col, type_col, category_col, power_col, priority_col)
            if c and c in df.columns]
```

## MX-5 무브 dict에 priority 필드

**FIND:**

```python
        moves.append({"name": name, "power": power, "type": mtype,
                      "category": category, "count": int(len(sub))})
```

**REPLACE:**

```python
        try:
            prio = int(float(rec.get(priority_col))) if (priority_col and rec.get(priority_col) is not None) else 0
        except (TypeError, ValueError):
            prio = 0
        moves.append({"name": name, "power": power, "type": mtype,
                      "category": category, "priority": prio, "count": int(len(sub))})
```

---
# 파일: `modules/step2_system_definition.py`
## ST-1 extract_moves에 감지된 우선도 컬럼 전달

**FIND:**

```python
            _moves = extract_moves(
                df_for_moves,
                _pcol if _pcol != "(없음)" else None,
                _tcol if _tcol != "(없음)" else None,
                _ccol if _ccol != "(없음)" else None,
                _ncol if _ncol != "(없음)" else None,
            )
```

**REPLACE:**

```python
            _moves = extract_moves(
                df_for_moves,
                _pcol if _pcol != "(없음)" else None,
                _tcol if _tcol != "(없음)" else None,
                _ccol if _ccol != "(없음)" else None,
                _ncol if _ncol != "(없음)" else None,
                _mv_detect.get("priority"),
            )
```

---
## 적용 후 검증 (Antigravity가 보고할 것)

1. `modules/move_extraction.py`와 `modules/step2_system_definition.py`가 py_compile 통과.
2. `grep -n "_PRIORITY_HINTS" modules/move_extraction.py` → 2건(정의·detect 사용).
3. `grep -n '"priority":' modules/move_extraction.py` → 2건(detect 반환·무브 dict).
4. `grep -n "priority_col" modules/move_extraction.py` → 4건 이상(시그니처·키·dict 추출).
5. `grep -n '_mv_detect.get("priority")' modules/step2_system_definition.py` → 1건.
