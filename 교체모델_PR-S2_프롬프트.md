# 교체 모델 PR-S2 — 타겟팅을 상대 on_field(액티브)로 제한
Antigravity 작업 지시서. 아래 find/replace를 **정확한 문자열 치환**으로 적용한다. 각 FIND 블록은 프로젝트 파일에 byte-exact 1회 등장함을 빌더가 Grep으로 확인했고, REPLACE 로직은 하니스 단위검증(4케이스) + 클린룸 컴파일을 통과했다.
## 목적

PR-S1로 액티브/예비(on_field) 구분이 생겼다. 그러나 타겟 선택은 여전히 상대 팀 *전원*(예비 포함)을 후보로 본다. 이 PR은 타겟 후보를 상대 팀의 on_field 유닛으로 좁힌다. 더불어 'on_field 적이 없으면 전투 종료'라는 기존 가정을 '예비 포함 상대 팀이 전멸했을 때만 종료'로 교정한다 — 예비가 남았는데 액티브만 쓰러진 순간 조기 종료되는 것을 막는다.

**회귀 0 보장**: on_field 미설정 시 True로 평가되어 상대 전원이 후보가 되고, 그때 opponents_all이 비면 team_alive도 거짓이라 기존과 동일하게 battle_over가 선다. active_count 미설정(전원-동시)에서 동작이 완전히 동일하다.
## 변경 범위

`modules/engine.py` 2곳(`_act_target_select`, `_act_move`). **다른 파일·다른 영역은 건들지 않는다.** 게임 이름·전용 분기 없음(도메인 중립).
## 적용 규칙

- FIND를 찾아 REPLACE로 **그대로** 교체한다. 들여쓰기·공백·한글 주석 한 글자도 바꾸지 않는다.
- 임의 리팩터·이름 변경·추가 최적화·하드코딩 금지. 지시된 치환만 한다.
- 적용 후 `python -c "import modules.engine"`가 에러 없이 통과해야 한다.

---
# 파일: `modules/engine.py`
## S2-1 _act_target_select 타겟 후보 on_field 제한 + 종료 판정 교정

**FIND:**

```python
    # 살아있는 적 진영 전체
    opponents_all = [p for p in participants
                     if p['team'] != char['team'] and get_current(p) > 0]
    if not opponents_all:
        # 적 진영 실제 궤멸 → 전투 종료
        ctx["add_log"](f"  [Phase: TARGET_SELECT] 🏆 {char['team']} 반대 진영 궤멸!")
        ctx["battle_over"] = True
        ctx["targets"] = []
        return
```

**REPLACE:**

```python
    # 타겟 후보: 상대 팀의 on_field(액티브) 유닛만. 예비(reserve)는 제외.
    # on_field 미설정 시 True → 현행 전원-동시 동작과 동일(회귀 0).
    opponents_all = [p for p in participants
                     if p['team'] != char['team'] and get_current(p) > 0
                     and p.get('on_field', True)]
    if not opponents_all:
        # on_field 적이 없음. 예비 포함 상대 팀 전멸 여부로만 전투 종료를 판정한다.
        team_alive = any(p['team'] != char['team'] and get_current(p) > 0
                         for p in participants)
        if not team_alive:
            ctx["add_log"](f"  [Phase: TARGET_SELECT] 🏆 {char['team']} 반대 진영 궤멸!")
            ctx["battle_over"] = True
        ctx["targets"] = []
        return
```

## S2-2 _act_move 이동 대상 on_field 제한

**FIND:**

```python
    enemies = [p for p in ctx["participants"]
               if p['team'] != char['team'] and get_current(p) > 0
               and p.get('position') is not None]
```

**REPLACE:**

```python
    enemies = [p for p in ctx["participants"]
               if p['team'] != char['team'] and get_current(p) > 0
               and p.get('on_field', True)
               and p.get('position') is not None]
```

---
## 적용 후 검증 (Antigravity가 보고할 것)

1. `modules/engine.py`가 py_compile 통과.
2. `grep -n "p.get('on_field', True)" modules/engine.py` → 2건 이상(타겟 후보·이동 대상).
3. `grep -n "team_alive = any" modules/engine.py` → 1건.
4. `grep -n "반대 진영 궤멸" modules/engine.py` → 1건(종료 판정 if 안).
