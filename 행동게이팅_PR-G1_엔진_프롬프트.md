# PR-G1 — 행동 게이팅 상태이상 엔진 (마비/잠듦/혼란)

## 역할/맥락
너는 Antigravity 에이전트다. 아래 변경을 **두 파일**(`modules/stochasticity.py`,
`modules/engine.py`)에 정확히 적용하라. 이 PR은 "이번 턴 행동을 막는" 게이팅 상태이상을
추가한다 — 기존 `mechanisms.status`(독/화상 턴종료 데미지)와 **별개**다.

설계(`행동게이팅상태이상_설계안.md`):
- 정의는 정적: `game_config['mechanisms']['status_gates'][name] = {"gate":..., "chance":..,
  "turns":.., "self_hit_percent":..}` (병렬 안전). gate 종류:
  `skip_chance`(마비, 매 턴 chance 확률 행동불가), `skip_full`(잠듦, 지속 동안 무조건 행동불가),
  `confuse`(혼란, chance 확률 자해+행동불가).
- 동적 상태는 캐릭터 active_states에 `{"gate_status": name, "expire_trigger":"ON_TURN_END",
  "expire_count": turns}`로 산다. 기존 expire 기계가 ON_TURN_END마다 1차감 → 고정 N턴 후
  자동 소멸(사용자 결정: 고정 N턴). turns 0이면 PERMANENT(영구, 마비용).
- 부여는 무브: `_act_move_effect`의 `kind:"inflict_status"` 분기가 대상 active_states에 추가.
- RNG는 시드 재현(백테스트 결정론): stochasticity base에 `roll_chance(p)` 추가.
- 행동 차단점은 `_act_target_select` 맨 앞 — 게이트가 막으면 `targets=[]; return`(기존 "턴 생략"
  패턴 재사용). 혼란 자해는 config 고정 비율(주 자원 max × self_hit_percent, 사용자 결정).

## 제약
- 두 파일만. 아래 FIND/REPLACE **4건**(stochasticity 1 + engine 3). 각 FIND는 해당 파일에
  **정확히 1회**(검증 확인). 다른 곳·저장부 무변경.
- 들여쓰기 FIND 그대로(스페이스). 적용 후 두 파일 각각
  `python -c "import ast; ast.parse(open('<path>',encoding='utf-8').read())"`.
- **회귀 0**: status_gates 미설정 + 게이팅 상태 없음(inflict_status 무브 안 씀) 시 전부 no-op.

---

## 변경 1/4 — `modules/stochasticity.py`: base에 `roll_chance` 추가

`StochasticityModule` base의 `roll_hit` 다음, `shuffle_tie_order` 앞에 범용 확률 판정을 넣는다.
(base에만 추가 — 모든 서브클래스가 상속한다.)

```python
# FIND
        명중 판정. True면 공격 적중, False면 빗나감.
        기본: 항상 적중.
        """
        return True

    def shuffle_tie_order(self, participants_with_same_speed: list) -> list:
```

```python
# REPLACE
        명중 판정. True면 공격 적중, False면 빗나감.
        기본: 항상 적중.
        """
        return True

    def roll_chance(self, p: float, ctx=None) -> bool:
        """범용 확률 판정 — p 확률로 True. 시드 제어되는 self.rng 사용(재현성).
        마비/혼란 등 행동 게이팅 판정에 쓴다. NoVariance(기본 결정론)도 상속하므로
        시드 고정 시 재현 가능."""
        return self.rng.random() < float(p)

    def shuffle_tie_order(self, participants_with_same_speed: list) -> list:
```

---

## 변경 2/4 — `modules/engine.py`: `_apply_action_gate` 헬퍼 추가

`_act_target_select` 정의 바로 앞에 게이트 헬퍼를 정의한다.

```python
# FIND
def _act_target_select(ctx):
```

```python
# REPLACE
def _apply_action_gate(ctx):
    """행동 게이팅 상태이상(마비/잠듦/혼란) — active_char의 active_states에서 gate_status를
    찾아 game_config['mechanisms']['status_gates'][status] 정의대로 이번 턴 행동을 막을지
    판정한다. True면 호출자(_act_target_select)가 targets=[]로 턴을 생략한다. 게이팅 상태
    없음/정의 없음 시 False(회귀 0). 지속은 expire_count 기계(ON_TURN_END)로 자동 만료.
    confuse는 막을 때 자해(주 자원 max × self_hit_percent)도 적용(사용자 결정: 고정 비율)."""
    char = ctx["active_char"]
    states = char.get("active_states", [])
    if not states:
        return False
    gates = ((ctx.get("game_config") or {}).get("mechanisms") or {}).get("status_gates") or {}
    if not gates:
        return False
    stoch = ctx.get("stochasticity")
    for s in states:
        status = s.get("gate_status")
        if not status:
            continue
        gdef = gates.get(status)
        if not gdef:
            continue
        gate = gdef.get("gate")
        if gate == "skip_full":
            ctx["add_log"](f"  -> [Phase: ACTION_GATE] {char.get('id','?')} 행동 불가 ({status})")
            return True
        chance = float(gdef.get("chance", 0) or 0)
        roll = stoch.roll_chance(chance, ctx) if stoch else (chance >= 1.0)
        if not roll:
            continue
        if gate == "skip_chance":
            ctx["add_log"](f"  -> [Phase: ACTION_GATE] {char.get('id','?')} 행동 불가 ({status})")
            return True
        if gate == "confuse":
            pct = float(gdef.get("self_hit_percent", 0.125) or 0)
            rm = ctx.get("resource_module")
            vitals = rm.vital_resources() if rm else ()
            rname = vitals[0] if vitals else "HP"
            res = char.get("resources", {}).get(rname)
            if res and res.get("current", 0) > 0 and pct > 0:
                before = res["current"]
                res["current"] = max(0, res["current"] - res["max"] * pct)
                lost = before - res["current"]
                ctx["add_log"](
                    f"  -> [Phase: ACTION_GATE] {char.get('id','?')} 혼란 자해 {int(lost)} ({status})"
                )
                if res["current"] <= 0:
                    ctx["add_log"](f"  [Phase: ACTION_GATE] ☠️ {char.get('id','?')} 혼란 자해로 쓰러짐!")
            return True
    return False


def _act_target_select(ctx):
```

---

## 변경 3/4 — `modules/engine.py`: `_act_target_select` 맨 앞 게이트 체크

타겟 변수 바인딩 직후, 비전투 트리거 체크 앞에 게이트를 끼운다.

```python
# FIND
    target_val = ctx["target_val"]

    # 비전투 트리거만 행동 생략. 미인식 트리거는 행동하도록 fail-safe.
```

```python
# REPLACE
    target_val = ctx["target_val"]

    # 행동 게이팅 상태이상(마비/잠듦/혼란) — 이번 턴 행동 차단 시 생략(targets 비움).
    if _apply_action_gate(ctx):
        ctx["targets"] = []
        return

    # 비전투 트리거만 행동 생략. 미인식 트리거는 행동하도록 fail-safe.
```

---

## 변경 4/4 — `modules/engine.py`: `_act_move_effect`에 `inflict_status` 분기

날씨(set_weather/clear_weather) 분기 다음, 스탯 boost 경로(`recipient = ...`) 앞에 상태 부여
분기를 끼운다.

```python
# FIND
            else:
                fs["weather"] = None
                ctx["add_log"](
                    f"  -> [Phase: ON_MOVE_EFFECT] {char.get('id','?')} 날씨 해제"
                )
            applied = True
            continue
        recipient = char if spec.get("scope", "self") == "self" else tgt
```

```python
# REPLACE
            else:
                fs["weather"] = None
                ctx["add_log"](
                    f"  -> [Phase: ON_MOVE_EFFECT] {char.get('id','?')} 날씨 해제"
                )
            applied = True
            continue
        if kind == "inflict_status":
            # 행동 게이팅 상태이상 부여 — 대상(scope)의 active_states에 게이팅 상태 append.
            #   지속은 status_gates[status].turns(고정 N턴) → expire_count 기계로 자동 만료.
            recipient2 = char if spec.get("scope") == "self" else tgt
            if recipient2 is None:
                continue
            status = str(spec.get("status", ""))
            gdef = (((ctx.get("game_config") or {}).get("mechanisms") or {})
                    .get("status_gates") or {}).get(status) or {}
            chance = float(spec.get("chance", 1.0) or 0)
            roll = (ctx.get("stochasticity").roll_chance(chance, ctx)
                    if ctx.get("stochasticity") else chance >= 1.0)
            if status and roll:
                turns = int(gdef.get("turns", 0) or 0)
                recipient2.setdefault("active_states", []).append({
                    "id": f"gate_{status}",
                    "gate_status": status,
                    "expire_trigger": "ON_TURN_END" if turns > 0 else "PERMANENT",
                    "expire_count": turns if turns > 0 else 9999,
                    "source_id": char.get("id"),
                })
                ctx["add_log"](
                    f"  -> [Phase: ON_MOVE_EFFECT] {char.get('id','?')} → "
                    f"{recipient2.get('id','?')} {status} 부여"
                )
            applied = True
            continue
        recipient = char if spec.get("scope", "self") == "self" else tgt
```

---

## 검증 (적용 후 수행)
1. `git diff`로 변경이 위 4지점뿐인지 확인(두 파일). 저장부·기존 분기 무변경.
2. 컴파일: 두 파일 각각 `ast.parse`.
3. 마커(각 1회): `def roll_chance(self, p: float, ctx=None) -> bool:`(stochasticity),
   `def _apply_action_gate(ctx):`, `if _apply_action_gate(ctx):`,
   `if kind == "inflict_status":`(engine).
4. 회귀 0 스모크: status_gates·inflict_status 무브 없이 기존 전투 1판 → 로그에
   `ACTION_GATE`/`gate_`/`부여` 문자열 없음(no-op).
5. 라이브(`G1_라이브실증.py`): active_count=1, movepool에 inflict_status 무브, setup_first,
   `mechanisms.status_gates`에 sleep/paralysis/confusion 정의, stochasticity 시드 고정.
   기대:
   - 무브 발화 → `<대상> sleep 부여`.
   - 다음 대상 턴부터 `ACTION_GATE ... 행동 불가 (sleep)` — 정확히 turns번, 이후 `State Expired`
     `gate_sleep ... 소멸`.
   - paralysis(turns 0): 영구, 매 턴 chance로 `행동 불가 (paralysis)`(시드 고정 시 재현).
   - confusion: `혼란 자해 <N> (confusion)` (N = max × self_hit_percent) + 행동불가.

## 회귀/한계 메모
- 게이트는 active_char 자기 상태만 읽음 — 싱글 액티브 가정(멀티는 갈래 ④).
- roll_chance는 base에 추가 → NoVariance(기본)도 상속, 시드 고정 시 결정론. 미시드(시스템시간)면
  실행마다 다름 — 크리티컬/명중과 동일 동작. 백테스트 하니스는 워커별 시드 주입(기존 패턴).
- 자해 KO 시 정리는 다음 _resolve_faint 사이클(갈래 ⑥ 근사와 동일).
- 마비 속도감소는 이 PR 범위 밖(기존 스탯 디버프 move_effect로 표현) — 게이트는 행동차단만.
- UI는 후속 **PR-G2**(step2: status_gates 편집 + inflict_status 무브). 엔진(G1) 적용·검증 후.
