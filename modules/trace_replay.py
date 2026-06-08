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
