# PR2 — 트레이스 모드 (관측 주입 + 이벤트 단위 데미지 diff)

## 목적
A 하니스의 2조각. 엔진 해결 파이프라인을 *그대로 두고*(DAMAGE_CALC/ELEMENT_MULT/
CRIT_CALC 무변경), 관측 행동·RNG를 주입해 **깨끗한 데미지 이벤트별로 엔진 산출 vs 로그 관측을
diff**한다. PR1(`showdown_trace`) 출력을 소비한다. 신규 파일 1개, 기존 무변경(회귀 0).

## 대상
**신규 파일** `modules/trace_replay.py` 생성. 엔진·step2·turn_manager·resource·stochasticity
**무변경**. (StochasticityModule을 *상속*만.)

## 설계 결정 (검증 중 확정)
- **턴 스케줄러 우회 — per-event 직접 구동.** 코어 검증 단위가 *전투*가 아니라 *데미지
  이벤트*이므로(설계안 §7), 각 (공격자·무브·방어자) 이벤트의 ctx를 만들어 해결 페이즈
  3개(DAMAGE_CALC→ELEMENT_MULT→CRIT_CALC)만 직접 돌려 dmg를 얻는다. 엔진 turn_manager의
  속도 정렬·교체 순서와 무관하게 *해결 파이프라인 자체*를 검증.
- **그래서 MOVE_SELECT/TARGET_SELECT 레지스트리 오버라이드 불필요.** ctx에 current_move/
  current_target을 직접 세팅하므로 selector를 갈아끼울 필요가 없다(원래 스케치보다 단순).
- **RNG 주입은 StochasticityModule 상속으로.** 명중=관측(깨끗한 이벤트는 hit), 크리=로그
  `-crit` 플래그, 데미지 분산=항등(롤 1.0 기준 R). 크리는 엔진 `_act_crit_calc`이 이미
  `stoch.roll_critical`에 위임하므로 주입만으로 강제됨.
- **데미지 롤(0.85~1.0) 미관측** → diff는 *허용구간* [0.85R, R]로 판정(R=롤 1.0 산출).

## 생성할 파일 내용 (전체 — 바이트 그대로)

```python
"""
트레이스 모드 — 관측 행동/RNG를 주입해 엔진 해결 파이프라인을 *이벤트 단위*로 구동·대조.

A 하니스의 2조각. 엔진의 결정·RNG가 ActionRegistry + StochasticityModule 시ーム으로
도는 점을 이용해, 해결 코드(DAMAGE_CALC/ELEMENT_MULT/CRIT_CALC)는 *그대로 두고*
관측값만 주입한다. 턴 스케줄러는 우회 — 각 (공격자,무브,방어자) 이벤트의 데미지를
직접 계산해 로그 관측 데미지와 diff한다(코어 검증 단위 = 데미지 이벤트).

battle_spec(참가자 스탯·무브·formula·type_table)은 PR3(레퍼런스 데이터 + 스탯 역산)가
공급한다. 본 모듈은 그 spec을 받아 *측정*만 한다 — 엔진/게임 중립.
"""
from modules.stochasticity import StochasticityModule

# 데미지 산출에 필요한 해결 페이즈(순서 고정) — APPLY_DAMAGE 전까지.
DAMAGE_PHASE_KEYS = ("DAMAGE_CALC", "ELEMENT_MULT", "CRIT_CALC")


class TraceStochasticity(StochasticityModule):
    """관측 결과 재생 — 명중/크리를 로그에서 받은 값으로 강제. 데미지 분산은 항등(롤 제거
    기준 R). 스텝마다 set_step으로 갱신."""

    def __init__(self, crit_mult=1.5, seed=None):
        super().__init__(seed)
        self.crit_mult = crit_mult
        self._hit = True
        self._crit = False

    def set_step(self, hit=True, crit=False):
        self._hit = hit
        self._crit = crit

    def roll_hit(self, attacker, target, ctx=None):
        return self._hit

    def roll_critical(self, attacker, target, ctx=None):
        return (True, self.crit_mult) if self._crit else (False, 1.0)

    def apply_damage_variance(self, damage, ctx=None):
        return damage  # 롤 1.0 기준(R) — 허용구간 판정은 diff 단에서


def make_event_ctx(attacker, defender, move, sys_stats, game_config, formula_str,
                   stoch, atk_elem="Neutral", add_log=None):
    """단일 데미지 이벤트용 최소 ctx. 엔진 build_ctx의 데미지 경로 키만 채운다."""
    return {
        "active_char": attacker, "current_target": defender, "current_move": move,
        "targets": [defender], "sys_stats": sys_stats, "formula_str": formula_str,
        "passive_logic": "", "atk_elem": atk_elem, "damage_type": None,
        "game_config": game_config, "stochasticity": stoch,
        "add_log": add_log or (lambda *a, **k: None),
        "field_state": {}, "participants": [attacker, defender], "turn": 0,
        "raw_dmg": 0, "dmg": 0, "elem_mult": 1.0, "battle_over": False,
    }


def compute_event_damage(registry, ctx, crit=False):
    """해결 페이즈를 순서대로 돌려 최종 dmg(APPLY 전) 반환. 명중=True(깨끗한 이벤트)."""
    ctx["stochasticity"].set_step(hit=True, crit=crit)
    for key in DAMAGE_PHASE_KEYS:
        f = registry.get(key)
        if f:
            f(ctx)
    return ctx["dmg"]


def run_trace_diff(registry, trace, battle_spec, clean_events, tol_low=0.85):
    """깨끗한 직격 이벤트별로 엔진 산출 vs 관측 데미지 diff.

    battle_spec: {chars:{nick:char_dict}, moves:{name:move_dict}, sys_stats,
                  game_config, formula_str, crit_mult}
    clean_events: showdown_trace.clean_damage_events(trace) 결과.
    반환: 이벤트별 {turn, move, observed, computed, in_band, effect_match}. computed=R(롤 1.0),
    관측이 [tol_low*R, R] 구간이면 in_band(데미지 롤 미관측 흡수)."""
    chars = battle_spec["chars"]; moves = battle_spec["moves"]
    stoch = TraceStochasticity(crit_mult=battle_spec.get("crit_mult", 1.5))
    out = []
    for ce in clean_events:
        atk = chars.get(ce["attacker"]); dfd = chars.get(ce["defender"])
        mv = moves.get(ce["move"])
        if atk is None or dfd is None or mv is None:
            out.append({"turn": ce["turn"], "move": ce["move"], "observed": ce["damage"],
                        "computed": None, "in_band": None, "missing": True})
            continue
        ctx = make_event_ctx(atk, dfd, mv, battle_spec["sys_stats"],
                             battle_spec["game_config"], battle_spec["formula_str"],
                             stoch, atk_elem=atk.get("_elem", "Neutral"))
        R = compute_event_damage(registry, ctx, crit=ce["crit"])
        obs = ce["damage"]
        in_band = (R > 0) and (int(tol_low * R) <= obs <= R)
        out.append({"turn": ce["turn"], "move": ce["move"], "observed": obs,
                    "computed_R": R, "in_band": in_band})
    return out
```

## API
- `TraceStochasticity(crit_mult)` — `set_step(hit, crit)`로 스텝별 관측 주입. roll_hit/roll_critical
  오버라이드. (엔진 `_act_crit_calc`이 `roll_critical`에 위임 → 크리 강제.)
- `compute_event_damage(registry, ctx, crit)` — 해결 3페이즈 구동, dmg 반환.
- `run_trace_diff(registry, trace, battle_spec, clean_events)` — 이벤트별 diff 리포트.
  `battle_spec`은 PR3가 공급(참가자 스탯·무브·formula·type_table·crit_mult).

## 검증 (실엔진·작성 시 수행 — 적용자 재현용)
엔진은 샌드박스에서 import됨. `DEFAULT_ACTION_REGISTRY`에서 DAMAGE_CALC/ELEMENT_MULT/
CRIT_CALC를 끌어와 합성 케이스로:
- **no-crit**: `(atk/df)*power × 상성` = `(200/100)*50 × 2.0(Fire→Grass)` → **R=200** ✓
- **crit ×2**: 위 ×2.0(TraceStochasticity 강제) → **R=400** ✓
- **resisted**: Fire→Water 0.5 → `(200/100)*50*0.5` → **R=50** ✓
  → 해결 파이프라인이 관측 크리/상성으로 정확히 구동됨.
- **실 트레이스 소비**: Gen5 로그를 PR1으로 파싱→`clean_damage_events`(3건)→`run_trace_diff`.
  누락 0(nick→참가자 매핑·무브 룩업 정상). *합성 스탯*이라 computed_R=100으로 관측(238/150/85)과
  안 맞는 게 정상 — **이게 PR3(레퍼런스 데이터+스탯 역산)이 채울 자리임을 정확히 보여줌.**
- `ast.parse` OK.

적용자 검증:
1. 파일 생성 후 `python -c "import ast; ast.parse(open('modules/trace_replay.py',encoding='utf-8').read())"`.
2. 위 합성 케이스(200/400/50) 재현 — 엔진 import + 3페이즈 구동.
3. 기존 모듈 무변경 확인(신규 파일, StochasticityModule 상속만).

## 회귀 0
신규 파일 1개. 엔진 해결 코드·turn_manager·stochasticity 베이스 전부 무변경. 어떤 기존
전투 경로도 이 모듈을 호출하지 않음. TraceStochasticity는 명시 주입할 때만 쓰임.

## 정직한 경계 / 다음(PR3)
- **이 하니스는 *해결 파이프라인*을 검증하지 턴 순서·교체를 검증하지 않는다**(의도 — 코어
  단위=이벤트). 전체 전투 트레이스(턴 순서·자발 교체·다중hit 루프)는 후속.
- **실 수치 diff는 PR3 없이는 안 된다**: `battle_spec`(종족값 → 유효스탯, 무브 power/type/
  category, 데미지 formula, type_table)을 레퍼런스 데이터 lazy 인입 + **관측 데미지에서 스탯
  역산**으로 채워야 R이 실제 관측과 맞기 시작한다. PR3 = 그 battle_spec 빌더 + 역산 v0.
  거기서 비로소 "Fake Out 79·Hydro Pump 150"이 맞는지가 숫자로 나온다.
