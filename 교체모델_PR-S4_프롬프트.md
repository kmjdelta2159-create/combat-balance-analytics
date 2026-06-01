# 교체 모델 PR-S4 — 자발적 교체 액션 + 룰 정책
Antigravity 작업 지시서. 아래 find/replace를 **정확한 문자열 치환**으로 적용한다. 각 FIND 블록은 프로젝트 파일에 byte-exact 1회 등장함을 빌더가 Grep으로 확인했고, REPLACE 로직은 하니스 단위검증(5케이스) + 클린룸 컴파일을 통과했다.
## 목적

PR-S1~S3로 강제 교체·타겟팅 제한·진입 hook이 생겼다. 이 PR은 유닛이 자기 턴에 '공격 대신 교체'를 *스스로* 고르는 자발적 교체를 더한다. `game_config['switch_policy']`가 설정돼 있고 조건을 만족하면 현재 액티브를 예비로 내리고 같은 팀 예비 유닛을 진입시킨다(턴 소모 — 이번 턴 공격은 생략). 첫 정책은 게임 중립적인 'hp_threshold'(액티브 HP 비율이 임계 이하 + 살아있는 예비 존재 시 교체)다. 직전 phase의 setup_first처럼 정책은 하나의 룰이고, 매치업 기반 등 추가 정책은 후속에서 같은 자리에 얹는다.

함께 turn_manager의 라운드 루프를 '라운드 시작 시점 on_field 유닛 스냅샷'으로 바꿔, 교체로 라운드 중간에 진입한 유닛이 같은 라운드에 또 행동하는 것을 막는다(진입 유닛은 다음 라운드부터 행동).

**회귀 0 보장**: switch_policy 미설정 시 `_maybe_voluntary_switch`가 즉시 False라 `_act_target_select`는 기존과 동일. 스냅샷은 전원-동시(전원 on_field) 기본 경로에서 participants 전체와 동일 집합이라 동작이 같다.
## 변경 범위

`modules/engine.py` 2곳(`_maybe_voluntary_switch` 함수 + `_act_target_select` 분기), `modules/turn_manager.py` 1곳(라운드 행동자 스냅샷). **다른 파일·다른 영역은 건들지 않는다.** 게임 이름·전용 분기 없음(도메인 중립).
## 적용 규칙

- FIND를 찾아 REPLACE로 **그대로** 교체한다. 들여쓰기·공백·한글 주석 한 글자도 바꾸지 않는다.
- 임의 리팩터·이름 변경·추가 최적화·하드코딩 금지. 지시된 치환만 한다.
- 적용 후 `python -c "import modules.engine, modules.turn_manager"`가 에러 없이 통과해야 한다.

---
# 파일: `modules/engine.py`
## ENG-1 _maybe_voluntary_switch 함수 삽입 (_act_target_select 직전)

**FIND:**

```python
def _act_target_select(ctx):
    """트리거 조건 확인 후 사거리 내 타겟 선택"""
```

**REPLACE:**

```python
def _maybe_voluntary_switch(ctx):
    """자발적 교체 정책 — game_config['switch_policy'] 조건 만족 시 현재 액티브를 예비로
    내리고 같은 팀 예비(reserve) 유닛을 진입시킨다(턴 소모, 이번 턴 공격 생략). 게임 중립·
    config 구동. 현재 정책: 'hp_threshold'(액티브 HP 비율이 임계 이하 + 살아있는 예비 존재
    시 교체). 미설정/조건 미충족/예비 없음 시 False → 회귀 0."""
    char = ctx["active_char"]
    gc = ctx.get("game_config") or {}
    pol = gc.get("switch_policy")
    if not pol:
        return False
    participants = ctx["participants"]
    reserve = sorted(
        (p for p in participants
         if p.get('team') == char.get('team') and not p.get('on_field')
         and get_current(p) > 0),
        key=lambda x: x.get('roster_idx', 0)
    )
    if not reserve:
        return False
    ptype = pol.get("type") if isinstance(pol, dict) else str(pol)
    do_switch = False
    if ptype == "hp_threshold":
        thr = float(pol.get("threshold", 0.25)) if isinstance(pol, dict) else 0.25
        mx = get_max(char)
        if mx > 0 and (get_current(char) / mx) <= thr:
            do_switch = True
    if not do_switch:
        return False
    incoming = reserve[0]
    char['on_field'] = False
    incoming['on_field'] = True
    incoming['just_switched_in'] = True
    ctx["add_log"](
        f"[Turn {ctx['turn']}] {char.get('id','?')} 교체 → "
        f"{incoming.get('id','?')} ({incoming.get('name','?')}) 진입"
    )
    return True


def _act_target_select(ctx):
    """트리거 조건 확인 후 사거리 내 타겟 선택"""
```

## ENG-2 _act_target_select에 자발적 교체 분기 추가

**FIND:**

```python
    # 비전투 트리거만 행동 생략. 미인식 트리거는 행동하도록 fail-safe.
    if str(trigger_val).strip() in NON_ACTING_TRIGGERS:
        ctx["targets"] = []
        return
```

**REPLACE:**

```python
    # 비전투 트리거만 행동 생략. 미인식 트리거는 행동하도록 fail-safe.
    if str(trigger_val).strip() in NON_ACTING_TRIGGERS:
        ctx["targets"] = []
        return

    # ── 자발적 교체 정책 (선택) — 조건 만족 시 교체로 턴 소모, 이번 턴 공격 생략 ──
    if _maybe_voluntary_switch(ctx):
        ctx["targets"] = []
        return
```

---
# 파일: `modules/turn_manager.py`
## TM-1 라운드 행동자 스냅샷

**FIND:**

```python
            participants.sort(
                key=lambda x: (-x.get(self.speed_stat, 0) if self.speed_stat else 0, x['id'])
            )

            for active_char in participants:
                # 액티브(on_field) 유닛만 행동. on_field 미설정 시 True(현행 전원-동시).
                if not active_char.get('on_field', True):
                    continue
```

**REPLACE:**

```python
            participants.sort(
                key=lambda x: (-x.get(self.speed_stat, 0) if self.speed_stat else 0, x['id'])
            )

            # 라운드 시작 시점의 on_field 유닛만 이번 라운드 행동자로 고정.
            # (교체로 라운드 중간에 진입한 유닛은 다음 라운드부터 행동)
            acting_units = [p for p in participants if p.get('on_field', True)]
            for active_char in acting_units:
                # 라운드 중간에 교체로 빠진 유닛은 제외. on_field 미설정 시 True(현행 전원-동시).
                if not active_char.get('on_field', True):
                    continue
```

---
## 적용 후 검증 (Antigravity가 보고할 것)

1. `modules/engine.py`와 `modules/turn_manager.py`가 각각 py_compile 통과.
2. `grep -n "def _maybe_voluntary_switch" modules/engine.py` → 1건.
3. `grep -n "_maybe_voluntary_switch(ctx)" modules/engine.py` → 2건(정의·호출).
4. `grep -n "switch_policy" modules/engine.py` → 1건.
5. `grep -n "acting_units" modules/turn_manager.py` → 2건(생성·루프).
