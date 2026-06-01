import copy
import os
import concurrent.futures
import traceback
from modules.action_registry import ActionRegistry, DEFAULT_ACTION_REGISTRY
from modules.turn_manager import SequentialTurnManager, StandardTurnExecutor
from modules.deck import CardTurnExecutor
from modules.stochasticity import StochasticityModule, NoVariance
from modules.resource import get_current, get_max, apply_delta, ResourceModule
from modules.win_condition import ResourceDepletion
from modules.spatial import SpatialModule

element_chart = {
    "Fire": {"strong_against": "Wood", "weak_against": "Water"},
    "Water": {"strong_against": "Fire", "weak_against": "Wood"},
    "Wood": {"strong_against": "Water", "weak_against": "Fire"},
    "Light": {"strong_against": "Dark", "weak_against": ""},
    "Dark": {"strong_against": "Light", "weak_against": ""},
    "Neutral": {"strong_against": "", "weak_against": ""}
}

def get_element_multiplier(atk_elem, def_elem):
    if element_chart.get(atk_elem, {}).get("strong_against") == def_elem: return 1.5
    if element_chart.get(atk_elem, {}).get("weak_against") == def_elem: return 0.5
    return 1.0


def _channel_col(gimmicks, channels, role, fallback_keywords):
    """Phase 8d — 기믹 채널 명시 매핑 우선, 미설정 시 컬럼명 키워드 추측 폴백.

    channels: game_config['channels'] dict — {"passive": col_name, "trigger": ..., ...}.
    각 role의 값이 컬럼명을 가리키면 그걸 반환. 명시 None이면 None(채널 비활성).
    role이 channels에 없으면 fallback_keywords로 컬럼명 부분일치 검색(기존 동작).
    """
    if channels and role in channels:
        mapped = channels[role]
        if mapped is None:
            return None
        if mapped in gimmicks:
            return mapped
    if isinstance(fallback_keywords, (tuple, list)):
        return next((c for c in gimmicks
                     if any(k in str(c).lower() for k in fallback_keywords)), None)
    return next((c for c in gimmicks
                 if str(fallback_keywords) in str(c).lower()), None)

# ═══════════════════════════════════════════════════════════════════════════════
# Combat Flow Dispatcher — 동적 전투 흐름 엔진
# ═══════════════════════════════════════════════════════════════════════════════

import re as _re

# ── Fail-Safe 기본 전투 흐름 (session_state.combat_flow 누락 시 폴백) ──
DEFAULT_COMBAT_FLOW = [
    {
        "header": "Phase 1: Pre-calculation",
        "items": ["Apply Passives (패시브 적용)", "Base Stat Calculation (기본 스탯 계산)"]
    },
    {
        "header": "Phase 2: Combat Flow",
        "items": ["Determine Targeting (타겟팅 결정)", "Calculate Base Damage (기본 데미지 계산)",
                  "Apply Elemental Multipliers (속성 상성 적용)", "Apply Critical Hit (치명타 적용)"]
    },
    {
        "header": "Phase 3: Resolution",
        "items": ["Apply Damage (최종 데미지 적용)", "Trigger On-Hit Effects (피격 효과 발동)",
                  "Check Death (사망 판정)"]
    }
]

# ── 한국어 괄호 → 정규화 키 매핑 테이블 ──
_KOREAN_TO_KEY = {
    "패시브 적용":     "PASSIVE_START",
    "기본 스탯 계산":  "STAT_CALC",
    "타겟팅 결정":     "TARGET_SELECT",
    "기본 데미지 계산": "DAMAGE_CALC",
    "속성 상성 적용":  "ELEMENT_MULT",
    "치명타 적용":     "CRIT_CALC",
    "최종 데미지 적용": "APPLY_DAMAGE",
    "피격 효과 발동":  "ON_HIT",
    "사망 판정":       "DEATH_CHECK",
    "이동": "MOVE",
    "무브 선택": "MOVE_SELECT",
}

# ── 영문 폴백 키워드 매핑 ──
_ENGLISH_HINTS = [
    ("passive",    "PASSIVE_START"),
    ("stat calc",  "STAT_CALC"),
    ("targeting",  "TARGET_SELECT"),
    ("base damage","DAMAGE_CALC"),
    ("elemental",  "ELEMENT_MULT"),
    ("critical",   "CRIT_CALC"),
    ("crit",       "CRIT_CALC"),
    ("apply damage","APPLY_DAMAGE"),
    ("on-hit",     "ON_HIT"),
    ("hit effect", "ON_HIT"),
    ("death",      "DEATH_CHECK"),
    ("move", "MOVE"),
    ("select move", "MOVE_SELECT"),
]

def _parse_action_key(item_str):
    """전투 흐름 아이템 문자열에서 정규화된 액션 키를 추출한다."""
    match = _re.search(r'\((.*?)\)', str(item_str))
    if match:
        korean = match.group(1).strip()
        if korean in _KOREAN_TO_KEY:
            return _KOREAN_TO_KEY[korean]
    lower = str(item_str).lower()
    for hint, key in _ENGLISH_HINTS:
        if hint in lower:
            return key
    return None

# ── 액션 분류: TARGET_SELECT가 피벗(Pivot)이며 이전은 캐릭터 단위, 이후는 타겟 단위 ──
_CHAR_LEVEL_KEYS  = {"PASSIVE_START", "STAT_CALC", "TARGET_SELECT", "MOVE"}
_TARGET_LEVEL_KEYS = {"MOVE_SELECT", "ON_MOVE_USE", "ON_MOVE_EFFECT", "DAMAGE_CALC", "ELEMENT_MULT", "CRIT_CALC", "APPLY_DAMAGE", "ON_HIT", "DEATH_CHECK"}
# 캐릭터 턴 종료 후 1회 실행되는 동적 메커니즘 hook (타겟 무관)
_POST_LEVEL_KEYS = {"ON_TURN_END", "ON_STATUS_TICK"}
_PIVOT_KEY = "TARGET_SELECT"


# ═══════════════════════════════════════════════════════════════════════════════
# Event-Driven State Machine — 범용 동적 상태(Buff/Debuff) 엔진
# ═══════════════════════════════════════════════════════════════════════════════
#
# State Object 명세:
#   {
#     "id":             str,   # 고유 식별자 (예: "Armor_Break_01")
#     "target_stat":    str,   # 변경 대상 스탯 (예: "ATK", "DEF", "SPD")
#     "mod_type":       str,   # "flat" (가산) | "percent" (곱연산, 1.0 = +100%)
#     "value":          float, # 변경량 (음수 = 디버프)
#     "expire_trigger": str,   # 소멸 조건 이벤트 (디스패처 Phase 키와 대응)
#     "expire_count":   int,   # 해당 이벤트 발생 N회 후 소멸 (0 이하 = 즉시 소멸)
#     "source_id":      str,   # 부여자 ID (선택)
#   }
#
# expire_trigger 예시:
#   "ON_TURN_START"  — 해당 캐릭터의 턴 시작마다 카운트 차감
#   "ON_ATTACK"      — 해당 캐릭터가 공격할 때마다 차감
#   "ON_HIT"         — 해당 캐릭터가 피격될 때마다 차감
#   "ON_TURN_END"    — 해당 캐릭터의 턴 종료 시 차감
#   "PERMANENT"      — 절대 소멸하지 않음
# ═══════════════════════════════════════════════════════════════════════════════

# 디스패처 Phase 키 → 이벤트 이름 매핑
_PHASE_TO_EVENT = {
    "PASSIVE_START": "ON_TURN_START",
    "STAT_CALC":     "ON_TURN_START",
    "TARGET_SELECT": "ON_TARGET_SELECT",
    "DAMAGE_CALC":   "ON_ATTACK",
    "ELEMENT_MULT":  "ON_ELEMENT",
    "CRIT_CALC":     "ON_CRIT",
    "APPLY_DAMAGE":  "ON_DAMAGE",
    "ON_HIT":        "ON_HIT",
    "DEATH_CHECK":   "ON_DEATH",
    "TURN_END":      "ON_TURN_END",
}


def get_effective_stat(character, stat_name):
    """
    동적 스탯 게터: 원본 스탯 + active_states 증감치를 합산하여 반환.
    flat → 가산 먼저, percent → 곱연산 이후 적용.
    """
    base = float(character.get(stat_name, 0))
    states = character.get("active_states", [])

    flat_sum = 0.0
    pct_mult = 1.0
    for s in states:
        if s.get("target_stat") != stat_name:
            continue
        mod = s.get("mod_type", "flat")
        val = float(s.get("value", 0))
        if mod == "flat":
            flat_sum += val
        elif mod == "percent":
            pct_mult *= (1.0 + val)

    return (base + flat_sum) * pct_mult


def _notify_event(event_name, character, ctx, role="actor"):
    """
    Event Broadcaster: 이벤트 발생 시 캐릭터의 active_states를 순회하며
    expire_trigger가 일치하는 상태의 expire_count를 1 차감한다.
    카운트가 0 이하가 된 상태는 즉시 안전하게 제거(Pop)된다.

    Args:
        event_name: 발생 이벤트 (예: "ON_TURN_START", "ON_HIT")
        character:  이벤트 대상 캐릭터 dict
        ctx:        턴 컨텍스트 (로그용)
        role:       "actor" | "target" (로그 식별용)
    """
    if event_name == "PERMANENT":
        return  # 영구 상태는 절대 만료되지 않음

    states = character.get("active_states", [])
    if not states:
        return

    expired = []
    for s in states:
        if s.get("expire_trigger") == event_name:
            s["expire_count"] = s.get("expire_count", 0) - 1
            if s["expire_count"] <= 0:
                expired.append(s)

    for s in expired:
        states.remove(s)
        ctx["add_log"](
            f"    🔔 [State Expired] {character.get('id','?')}: "
            f"{s.get('id', '?')} ({s.get('target_stat','?')} "
            f"{'+' if s.get('value',0) >= 0 else ''}{s.get('value',0)}) "
            f"소멸 (trigger: {event_name})"
        )


def _broadcast_phase_event(phase_key, ctx, targets=None):
    """
    디스패처 Phase 실행 후 호출되는 래퍼.
    Phase 키를 이벤트 이름으로 변환하고, 관련 캐릭터들에게 브로드캐스트한다.
    - actor (active_char): 항상 알림
    - targets: 제공 시 각 타겟에도 알림
    """
    event = _PHASE_TO_EVENT.get(phase_key)
    if not event:
        return

    actor = ctx.get("active_char")
    if actor:
        _notify_event(event, actor, ctx, role="actor")

    if targets:
        for t in (targets if isinstance(targets, list) else [targets]):
            _notify_event(event, t, ctx, role="target")


# ═══════════════════════════════════════════════════════════════════════════════
# 개별 액션 블록 구현 (각각 ctx dict를 받아 상태를 읽고/쓴다)
# ═══════════════════════════════════════════════════════════════════════════════

def _track_state(ctx, target, state):
    target.setdefault("active_states", []).append(state)
    if "sim_metrics" in ctx:
        ctx["sim_metrics"]["buff_count"] += 1
        ctx["sim_metrics"]["buff_turns"] += state.get("expire_count", 1)

def _act_passive_start(ctx):
    """On_Turn_Start 패시브 실행 + 이벤트 브로드캐스트
    exec 환경에 3대 헬퍼 (add_state, add_target_state, add_attacker_state) 노출.
    턴 시작 시점에서는 target이 아직 결정되지 않았으므로 add_target_state 는 no-op.
    """
    char = ctx["active_char"]
    passive = ctx["passive_logic"]
    if passive:
        # exec 환경에 상태 부여 헬퍼를 노출
        exec(passive, {}, {
            "character": char,
            "trigger": "On_Turn_Start",
            "add_state":          lambda s: _track_state(ctx, char, s),
            "add_target_state":   lambda s: None,  # 턴 시작 시점에는 타겟 미확정
            "add_attacker_state": lambda s: None,  # 턴 시작 시점에는 공격자 미확정
        })
    _broadcast_phase_event("PASSIVE_START", ctx)

def _act_stat_calc(ctx):
    """
    스탯 재계산 Phase: ON_TURN_START 이벤트를 브로드캐스트하여
    턴 시작 기반 상태 이상의 expire_count를 차감한다.
    """
    _broadcast_phase_event("STAT_CALC", ctx)

# 비전투 트리거 — 이 태그만 행동을 생략한다. 그 외(미인식 포함)는 모두 행동(fail-safe).
NON_ACTING_TRIGGERS = {"Passive_Only"}

def _normalize_target_tag(target_val):
    """타겟 태그를 엔진 표준 키(Single_Target / AoE_All / Lowest_HP)로 정규화.
    표준 태그는 정확 일치, 비표준 태그는 부분문자열 휴리스틱으로 폴백."""
    v = str(target_val or "").strip().lower()
    # 표준 태그 정확 일치 (회귀 안전)
    if v in ("single_target", "attacker"):
        return "Single_Target"
    if v in ("aoe_all", "aoe_frontrow"):
        return "AoE_All"
    if v == "lowest_hp":
        return "Lowest_HP"
    # 비표준 태그 휴리스틱 폴백
    if any(k in v for k in ("aoe", "sweep", "_all")):
        return "AoE_All"
    if any(k in v for k in ("lowest", "snipe")):
        return "Lowest_HP"
    return "Single_Target"

def _will_voluntary_switch(char, participants, game_config):
    """read-only — _maybe_voluntary_switch가 이번 턴 교체를 할지 예측한다(부작용 없음).
    행동 우선도 정렬용. _maybe_voluntary_switch의 판정 조건과 일치해야 한다."""
    gc = game_config or {}
    pol = gc.get("switch_policy")
    if not pol:
        return False
    reserve_alive = any(
        p.get('team') == char.get('team') and not p.get('on_field') and get_current(p) > 0
        for p in participants
    )
    if not reserve_alive:
        return False
    ptype = pol.get("type") if isinstance(pol, dict) else str(pol)
    if ptype == "hp_threshold":
        thr = float(pol.get("threshold", 0.25)) if isinstance(pol, dict) else 0.25
        mx = get_max(char)
        return mx > 0 and (get_current(char) / mx) <= thr
    return False


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
    ctx["add_log"](
        f"[Turn {ctx['turn']}] {char.get('id','?')} 교체 → "
        f"{incoming.get('id','?')} ({incoming.get('name','?')}) 진입"
    )
    # 진입 즉시 처리 (S7) — 다음 턴이 아니라 교체 시점에 진입 효과·이벤트 발화 + 이중 발화 방지.
    incoming['just_switched_in'] = False
    _fire_switch_in(incoming, participants, gc, ctx["add_log"], ctx.get("field_state"))
    return True


def _candidate_targets(char, participants, target_val, spatial_module, attack_range):
    """read-only 타겟 후보 결정 — 상대 on_field 후보 → 사거리 필터 → target 태그 정규화로
    최종 타겟 리스트를 만든다. 부작용 없음(로그·battle_over·교체 없음). 후보 없거나 사거리
    내 타겟이 없으면 빈 리스트. _act_target_select(실행)와 행동순서 예측기가 공유한다 —
    예측=실행 보장을 위해 타겟 선택 로직은 이 함수 1벌로만 존재한다."""
    opponents_all = [p for p in participants
                     if p['team'] != char['team'] and get_current(p) > 0
                     and p.get('on_field', True)]
    if not opponents_all:
        return []
    if spatial_module is not None and attack_range is not None:
        opponents = [o for o in opponents_all
                     if spatial_module.in_range(char, o, attack_range)]
    else:
        opponents = opponents_all
    if not opponents:
        return []
    norm_target = _normalize_target_tag(target_val)
    if norm_target == "AoE_All":
        return opponents
    elif norm_target == "Lowest_HP":
        return [min(opponents, key=lambda x: get_current(x))]
    else:  # Single_Target
        return [opponents[0]]


def _act_target_select(ctx):
    """트리거 조건 확인 후 사거리 내 타겟 선택. 후보·사거리·태그 선택은 공유 순수 코어
    _candidate_targets(행동순서 예측기와 동일 경로)에 위임한다 — 셸은 비전투 트리거 스킵,
    자발적 교체, battle_over 판정, 로그만 담당한다."""
    char = ctx["active_char"]
    participants = ctx["participants"]
    trigger_val = ctx["trigger_val"]
    target_val = ctx["target_val"]

    # 비전투 트리거만 행동 생략. 미인식 트리거는 행동하도록 fail-safe.
    if str(trigger_val).strip() in NON_ACTING_TRIGGERS:
        ctx["targets"] = []
        return

    # ── 자발적 교체 정책 (선택) — 조건 만족 시 교체로 턴 소모, 이번 턴 공격 생략 ──
    if _maybe_voluntary_switch(ctx):
        ctx["targets"] = []
        return

    # 타겟 후보: 상대 팀의 on_field(액티브) 유닛만. 예비(reserve)는 제외.
    # on_field 미설정 시 True → 현행 전원-동시 동작과 동일(회귀 0).
    opponents_all = [p for p in participants
                     if p['team'] != char['team'] and get_current(p) > 0
                     and p.get('on_field', True)]
    if not opponents_all:
        # on_field 적이 없음. 예비 포함 상대 팀 전멸 여부로만 전투 종료 판정한다.
        team_alive = any(p['team'] != char['team'] and get_current(p) > 0
                         for p in participants)
        if not team_alive:
            ctx["add_log"](f"  [Phase: TARGET_SELECT] 🏆 {char['team']} 반대 진영 궤멸!")
            ctx["battle_over"] = True
        ctx["targets"] = []
        return

    # ── 후보 → 사거리 → target 태그 (공유 순수 코어; 예측기와 동일 경로) ──
    targets = _candidate_targets(char, participants, target_val,
                                 ctx.get("spatial_module"), ctx.get("attack_range"))
    if not targets:
        # 적은 살아있으나 사거리 내 타겟 없음 → 이번 턴 행동 생략 (battle_over 아님)
        ctx["add_log"](
            f"[Turn {ctx['turn']}] {char['id']} ({char['name']}) "
            f"[Phase: TARGET_SELECT] 사거리 내 타겟 없음 — 행동 생략"
        )
        ctx["targets"] = []
        return

    ctx["targets"] = targets
    ctx["add_log"](
        f"[Turn {ctx['turn']}] {char['id']} ({char['name']}) 행동! "
        f"[Phase: TARGET_SELECT] 타겟: {', '.join(t['id'] for t in ctx['targets'])}"
    )

def _act_move(ctx):
    """이동 (Phase 4b) — 가장 가까운 적을 향해 move_range 타일 접근.
    attack_range가 있으면 그 거리에서, 없으면 인접(거리 1)에서 멈춘다.
    이동 비활성(move_range 없음/위치 없음/spatial 없음)이면 no-op → 현행 동일."""
    char = ctx["active_char"]
    spatial = ctx.get("spatial_module")
    move_range = ctx.get("move_range")
    if spatial is None or not move_range or char.get('position') is None:
        return
    enemies = [p for p in ctx["participants"]
               if p['team'] != char['team'] and get_current(p) > 0
               and p.get('on_field', True)
               and p.get('position') is not None]
    if not enemies:
        return
    my_pos = char['position']
    nearest = min(enemies, key=lambda e: spatial.distance(my_pos, e['position']))
    dist = spatial.distance(my_pos, nearest['position'])
    attack_range = ctx.get("attack_range")
    stop_dist = max(int(attack_range), 1) if attack_range is not None else 1
    steps = min(int(move_range), dist - stop_dist)
    if steps <= 0:
        return  # 이미 사거리/인접 안 — 이동 불필요
    new_pos = spatial.step_toward(my_pos, nearest['position'], steps)
    if new_pos != my_pos:
        char['position'] = new_pos
        ctx["add_log"](
            f"[Turn {ctx['turn']}] {char['id']} ({char['name']}) "
            f"이동 → ({new_pos['x']},{new_pos['y']})"
        )

def _select_move_pure(char, target, sys_stats, game_config, formula_str):
    """read-only 무브 선택 — setup_first 정책 분기 + 그리디(기대 데미지 최대) 선택.
    movepool 미보유 시 None, 타겟 None 시 movepool[0]. 상태 변경 없음(읽기만).
    _act_move_select(실행)와 행동순서 예측기가 공유한다 — 예측=실행 보장을 위해 무브
    선택 로직은 이 함수 1벌로만 존재한다. (game_config None은 {}로 정규화해 현행 동일.)"""
    movepool = char.get("movepool")
    if not movepool:
        return None
    gc = game_config or {}
    # ── 전략 정책 (선택): setup_first — 아직 안 쓴 효과 무브를 데미지보다 먼저 고른다 ──
    if gc.get("move_policy") == "setup_first":
        _eff_map = gc.get("move_effects") or {}
        for _smv in movepool:
            _snm = _smv.get("name")
            if _snm in _eff_map and not any(
                str(_s.get("id", "")).startswith(f"move_effect_{_snm}_")
                for _s in char.get("active_states", [])
            ):
                return _smv
    t = target
    if t is None:
        return movepool[0]
    import math
    formula_eval = str(formula_str).lower() if formula_str else "0"
    base_env = {s: get_effective_stat(char, s) for s in sys_stats}
    base_env.update({"target_" + s: get_effective_stat(t, s) for s in sys_stats})
    base_env["current_health"] = get_current(char)
    base_env["max_health"] = get_max(char)
    base_env["target_current_health"] = get_current(t)
    base_env["target_max_health"] = get_max(t)
    best, best_dmg = movepool[0], -1.0
    for _mv in movepool:
        env = dict(base_env)
        env["move_power"] = float(_mv.get("power", 0))
        _cat = gc.get("categories", {}).get(_mv.get("category"))
        if _cat:
            env["offense"] = get_effective_stat(char, _cat["offense"])
            env["defense"] = get_effective_stat(t, _cat["defense"])
        env = {str(k).lower(): float(v) for k, v in env.items()}
        try:
            _base = max(0, int(float(eval(formula_eval, {"__builtins__": None, "math": math}, env))))
        except Exception:
            _base = 0.0
        _d = _base * _move_type_multiplier(_mv, t, gc) * _move_stab_multiplier(_mv, char, gc)
        if _d > best_dmg:
            best, best_dmg = _mv, _d
    return best


def _act_move_select(ctx):
    """무브 선택 Phase (Phase 8a) — movepool에서 그리디(기대 데미지 최대)로 무브 선택.
    movepool 미보유 시 current_move=None → 단일 global 공식 경로 유지(default=identity).
    선택 본체는 공유 순수 코어 _select_move_pure(행동순서 예측기와 동일 경로)에 위임한다."""
    ctx["current_move"] = _select_move_pure(
        ctx["active_char"], ctx.get("current_target"),
        ctx.get("sys_stats"), ctx.get("game_config"), ctx.get("formula_str"))


def _act_damage_calc(ctx):
    """데미지 공식 eval (On_Attack 패시브 포함) — get_effective_stat 사용
    exec 환경에 3대 헬퍼 (add_state, add_target_state, add_attacker_state) 노출.
    """
    char = ctx["active_char"]
    t = ctx["current_target"]
    sys_stats = ctx["sys_stats"]
    formula_str = ctx["formula_str"]
    passive = ctx["passive_logic"]

    # On_Attack 패시브 (공격 시점 트리거)
    if passive:
        exec(passive, {}, {
            "character": char, "target": t, "trigger": "On_Attack",
            "add_state":          lambda s: _track_state(ctx, char, s),
            "add_target_state":   lambda s: _track_state(ctx, t, s),
            "add_attacker_state": lambda s: _track_state(ctx, char, s),
        })

    # ── get_effective_stat 으로 버프/디버프 반영된 스탯 사용 ──
    eval_env_raw = {s: get_effective_stat(char, s) for s in sys_stats}
    eval_env_raw.update({"target_" + s: get_effective_stat(t, s) for s in sys_stats})
    eval_env_raw["current_health"] = get_current(char)
    eval_env_raw["max_health"] = get_max(char)
    eval_env_raw["target_current_health"] = get_current(t)
    eval_env_raw["target_max_health"] = get_max(t)

    # ── Phase 8a: 무브 활성 시 move_power / offense / defense 주입 ──
    _move = ctx.get("current_move")
    if _move:
        _gc = ctx.get("game_config") or {}
        eval_env_raw["move_power"] = float(_move.get("power", 0))
        _cat = _gc.get("categories", {}).get(_move.get("category"))
        if _cat:
            eval_env_raw["offense"] = get_effective_stat(char, _cat["offense"])
            eval_env_raw["defense"] = get_effective_stat(t, _cat["defense"])

    eval_env = {str(k).lower(): float(v) for k, v in eval_env_raw.items()}
    formula_eval = str(formula_str).lower() if formula_str else "0"

    import math
    ctx["raw_dmg"] = max(0, int(float(eval(formula_eval, {"__builtins__": None, "math": math}, eval_env))))
    ctx["dmg"] = ctx["raw_dmg"]

    # ── Stochasticity: 명중 판정 ──
    stoch = ctx.get("stochasticity")
    if stoch:
        if not stoch.roll_hit(char, t, ctx):
            ctx["dmg"] = 0
            ctx["add_log"](f"  -> [Phase: DAMAGE_CALC] ❌ 공격이 빗나갔습니다!")
            _broadcast_phase_event("DAMAGE_CALC", ctx, targets=t)
            return
        
        # ── Stochasticity: 데미지 분산 ──
        ctx["dmg"] = int(stoch.apply_damage_variance(ctx["dmg"], ctx))

    _broadcast_phase_event("DAMAGE_CALC", ctx, targets=t)

def _move_type_multiplier(move, target, game_config):
    """무브 타입 vs 방어자 타입 상성 배율 — game_config['type_table'] 기반 (Phase 8b).
    type_table 미설정 시 1.0 (default=identity)."""
    table = (game_config or {}).get("type_table") or {}
    mtype = move.get("type") if move else None
    if not table or not mtype:
        return 1.0
    row = table.get(mtype, {})
    mult = 1.0
    for col in (game_config or {}).get("type_columns", []):
        dt = target.get("gimmicks", {}).get(col)
        if dt is not None and dt in row:
            mult *= float(row[dt])
    return mult


def _move_stab_multiplier(move, char, game_config):
    """STAB — 무브 타입이 공격자 타입 중 하나와 일치하면 stab_factor 배율 (Phase 8b).
    stab_factor 미설정/1.0 시 1.0 (default=identity)."""
    sf = float((game_config or {}).get("stab_factor", 1.0))
    mtype = move.get("type") if move else None
    if sf == 1.0 or not mtype:
        return 1.0
    # Protean 등 동적 타입(current_type)이 설정돼 있으면 그것을 공격자 타입으로 우선 사용
    if char.get("current_type"):
        atypes = [char.get("current_type")]
    else:
        atypes = [char.get("gimmicks", {}).get(c)
                  for c in (game_config or {}).get("type_columns", [])]
    return sf if mtype in atypes else 1.0


def _act_element_mult(ctx):
    """속성 상성 배율 적용 — 무브+game_config 활성 시 N-type 상성표·STAB 사용,
    아니면 레거시 element_chart (default=identity)."""
    t = ctx["current_target"]
    move = ctx.get("current_move")
    game_config = ctx.get("game_config") or {}

    if move and game_config.get("type_table"):
        # Phase 8b — 무브 타입 기반 N-type 상성 + STAB
        char = ctx["active_char"]
        elem_mult = (_move_type_multiplier(move, t, game_config)
                     * _move_stab_multiplier(move, char, game_config))
    else:
        # 레거시 — element_chart 6속성
        atk_elem = ctx["atk_elem"]
        t_gimmicks = t.get('gimmicks', {})
        t_element_col = next((c for c in t_gimmicks if 'element' in c.lower()), None)
        def_elem = t_gimmicks.get(t_element_col, "Neutral") if t_element_col else "Neutral"
        elem_mult = get_element_multiplier(atk_elem, def_elem)

    ctx["elem_mult"] = elem_mult
    ctx["dmg"] = int(ctx["dmg"] * elem_mult)
    _broadcast_phase_event("ELEMENT_MULT", ctx, targets=t)

def _act_crit_calc(ctx):
    """치명타 판정 — Stochasticity 모듈에 위임."""
    char = ctx["active_char"]
    t = ctx.get("current_target")
    
    stoch = ctx.get("stochasticity")
    if stoch:
        is_crit, mult = stoch.roll_critical(char, t, ctx)
        if is_crit:
            ctx["dmg"] = int(ctx["dmg"] * mult)
            ctx["add_log"](f"  -> [Phase: CRIT_CALC] ⚡ 치명타! 배율 {mult}x 적용")
    
    _broadcast_phase_event("CRIT_CALC", ctx, targets=t)

def _act_apply_damage(ctx):
    """최종 데미지를 타겟 HP에 반영"""
    t = ctx["current_target"]
    dmg = ctx["dmg"]
    elem_mult = ctx.get("elem_mult", 1.0)
    elem_text = f" (상성 {elem_mult}x 적용)" if elem_mult != 1.0 else ""

    resource_module = ctx.get("resource_module")
    if resource_module is not None:
        absorbed = resource_module.route_damage(t, dmg, ctx.get("damage_type"))
    else:
        apply_delta(t, -dmg)
        absorbed = 0
    shield_text = f" (실드 {int(absorbed)} 흡수)" if absorbed else ""

    if "sim_metrics" in ctx:
        ctx["sim_metrics"]["total_damage"] += dmg
        ctx["sim_metrics"]["damage_count"] += 1
        atk_elem = ctx.get("atk_elem", "Neutral")
        ctx["sim_metrics"]["element_damage"][atk_elem] = ctx["sim_metrics"]["element_damage"].get(atk_elem, 0) + dmg
        ctx["sim_metrics"]["element_damage_count"][atk_elem] = ctx["sim_metrics"]["element_damage_count"].get(atk_elem, 0) + 1

    ctx["add_log"](
        f"  -> [Phase: APPLY_DAMAGE] {dmg}의 피해를 입혔습니다!{elem_text}{shield_text} "
        f"{t['id']} 잔여 체력: {get_current(t)}/{get_max(t)}"
    )
    _broadcast_phase_event("APPLY_DAMAGE", ctx, targets=t)

def _act_on_hit(ctx):
    """피격 시 타겟의 On_Hit 패시브 실행 + ON_HIT 이벤트 브로드캐스트
    exec 환경에 3대 헬퍼 (add_state, add_target_state, add_attacker_state) 노출.
    - add_state:          피격자(t) 본인에게 상태 부여
    - add_target_state:   피격자(t)에게 상태 부여 (add_state와 동일 대상)
    - add_attacker_state: 공격자(char)에게 상태 역부여
    """
    t = ctx["current_target"]
    char = ctx["active_char"]

    t_gimmicks = t.get('gimmicks', {})
    _ch = ((ctx.get("game_config") or {}).get("channels") or {})
    t_passive_col = _channel_col(t_gimmicks, _ch, "passive", "passive")
    t_passive_logic = t_gimmicks.get(t_passive_col, "") if t_passive_col else ""

    if t_passive_logic and get_current(t) > 0:
        exec(t_passive_logic, {}, {
            "character": t, "attacker": char, "trigger": "On_Hit",
            "add_state":          lambda s: _track_state(ctx, t, s),
            "add_target_state":   lambda s: _track_state(ctx, t, s),
            "add_attacker_state": lambda s: _track_state(ctx, char, s),
        })
    _broadcast_phase_event("ON_HIT", ctx, targets=t)

def _act_death_check(ctx):
    """사망 판정 + ON_DEATH 이벤트 브로드캐스트"""
    t = ctx["current_target"]
    if get_current(t) <= 0:
        ctx["add_log"](f"  [Phase: DEATH_CHECK] \u2620\ufe0f {t['id']} 캐릭터 사망!")
        _broadcast_phase_event("DEATH_CHECK", ctx, targets=t)
        # 사망 시 남은 상태 이상 전부 정리
        t["active_states"] = []


def _act_turn_end_heal(ctx):
    """턴 종료 회복 메커니즘 (Leftovers류) — game_config['mechanisms']['leftovers'] 기반.
    부착 캐릭터가 턴 종료 시 vital 자원의 percent만큼 회복한다. 사망(현재값 0)이면
    회복하지 않는다. max 상한으로 클램프. 미부착/미설정 시 no-op."""
    char = ctx["active_char"]
    mechs = (ctx.get("game_config") or {}).get("mechanisms") or {}
    spec = mechs.get("leftovers")
    if not spec:
        return
    col = spec.get("gimmick_col")
    want = str(spec.get("match_value", "")).strip().lower()
    have = str(char.get("gimmicks", {}).get(col, "")).strip().lower() if col else ""
    if not col or have != want:
        return
    percent = float(spec.get("percent", 0.0625))
    rm = ctx.get("resource_module")
    vitals = rm.vital_resources() if rm else ()
    rname = vitals[0] if vitals else "HP"
    res = char.get("resources", {}).get(rname)
    if not res or res.get("current", 0) <= 0:
        return
    before = res["current"]
    res["current"] = min(res["max"], res["current"] + res["max"] * percent)
    gained = res["current"] - before
    if gained > 0:
        ctx["add_log"](
            f"  -> [Phase: ON_TURN_END] {char.get('id','?')} {rname} {int(gained)} 회복 "
            f"({int(res['current'])}/{int(res['max'])})"
        )


def _act_status_tick(ctx):
    """상태이상 턴 종료 데미지 (독·화상류) — game_config['mechanisms']['status'] 기반.
    부착 캐릭터가 턴 종료 시 vital 자원의 percent만큼 데미지를 받는다. HP는 0 미만으로
    내려가지 않는다. 미부착/미설정/사망 시 no-op."""
    char = ctx["active_char"]
    mechs = (ctx.get("game_config") or {}).get("mechanisms") or {}
    spec = mechs.get("status")
    if not spec:
        return
    col = spec.get("gimmick_col")
    want = str(spec.get("match_value", "")).strip().lower()
    have = str(char.get("gimmicks", {}).get(col, "")).strip().lower() if col else ""
    if not col or have != want:
        return
    percent = float(spec.get("percent", 0.125))
    rm = ctx.get("resource_module")
    vitals = rm.vital_resources() if rm else ()
    rname = vitals[0] if vitals else "HP"
    res = char.get("resources", {}).get(rname)
    if not res or res.get("current", 0) <= 0:
        return
    before = res["current"]
    res["current"] = max(0, res["current"] - res["max"] * percent)
    lost = before - res["current"]
    if lost > 0:
        ctx["add_log"](
            f"  -> [Phase: ON_STATUS_TICK] {char.get('id','?')} {rname} {int(lost)} 상태이상 피해 "
            f"({int(res['current'])}/{int(res['max'])})"
        )
    if res["current"] <= 0:
        ctx["add_log"](f"  [Phase: ON_STATUS_TICK] ☠️ {char.get('id','?')} 상태이상으로 쓰러짐!")


def _act_move_use(ctx):
    """무브 사용 직전 hook — Protean류 동적 타입 갱신. game_config['mechanisms']['protean'] 기반.
    부착 캐릭터가 무브를 쓸 때 자신의 current_type을 그 무브의 타입으로 갱신한다(STAB 상시 적용).
    미부착/미설정/무브에 타입 없음 시 no-op."""
    char = ctx["active_char"]
    move = ctx.get("current_move")
    mechs = (ctx.get("game_config") or {}).get("mechanisms") or {}
    spec = mechs.get("protean")
    if not spec or not move:
        return
    col = spec.get("gimmick_col")
    want = str(spec.get("match_value", "")).strip().lower()
    have = str(char.get("gimmicks", {}).get(col, "")).strip().lower() if col else ""
    if not col or have != want:
        return
    mtype = move.get("type")
    if not mtype:
        return
    if char.get("current_type") != mtype:
        char["current_type"] = mtype
        ctx["add_log"](
            f"  -> [Phase: ON_MOVE_USE] {char.get('id','?')} 타입이 {mtype}(으)로 변경 (Protean)"
        )


def _act_move_effect(ctx):
    """무브 사용 시 효과(스탯 boost 등) 적용 — game_config['move_effects'] 기반.
    선택된 무브 이름에 효과가 정의돼 있으면 active_states에 영구 boost를 부여한다.
    scope='self'면 사용자, 'target'이면 현재 타겟. 미정의 시 no-op."""
    move = ctx.get("current_move")
    if not move:
        return
    effects = (ctx.get("game_config") or {}).get("move_effects") or {}
    spec_list = effects.get(move.get("name"))
    if not spec_list:
        return
    char = ctx["active_char"]
    tgt = ctx.get("current_target")
    applied = False
    for spec in spec_list:
        # 필드 효과(F2): 무브로 진영별 해저드 설치/청소. field_state(F1 substrate)에 쓴다.
        # kind 없는 기존 spec은 아래 스탯 boost 경로로 빠진다(회귀 0).
        kind = spec.get("kind")
        if kind in ("set_hazard", "clear_hazard"):
            fs = ctx.get("field_state")
            if fs is None:
                continue
            haz = fs.setdefault("hazard", {})
            hz_team = str(spec.get("team", "Enemy"))
            if kind == "set_hazard":
                haz[hz_team] = float(spec.get("percent", 0.125))
                ctx["add_log"](
                    f"  -> [Phase: ON_MOVE_EFFECT] {char.get('id','?')} {hz_team} 진영에 "
                    f"해저드 설치 ({haz[hz_team]:.3f})"
                )
            else:
                haz[hz_team] = 0.0
                ctx["add_log"](
                    f"  -> [Phase: ON_MOVE_EFFECT] {char.get('id','?')} {hz_team} 진영 해저드 청소"
                )
            applied = True
            continue
        recipient = char if spec.get("scope", "self") == "self" else tgt
        if recipient is None:
            continue
        _track_state(ctx, recipient, {
            "id": f"move_effect_{move.get('name','?')}_{spec.get('target_stat','?')}",
            "target_stat": spec.get("target_stat"),
            "mod_type": spec.get("mod_type", "percent"),
            "value": float(spec.get("value", 0)),
            "expire_trigger": "PERMANENT",
            "expire_count": 9999,
            "source_id": char.get("id"),
        })
        applied = True
    if applied:
        ctx["add_log"](
            f"  -> [Phase: ON_MOVE_EFFECT] {char.get('id','?')} {move.get('name','?')} 효과 적용"
        )


def _apply_switch_in_effects(char, participants, game_config, add_log):
    """교체 진입 효과 — game_config['mechanisms']['trace'] 기반. 부착 캐릭터(gimmick_col 값이
    match_value와 일치)가 필드에 진입하면 상대 팀 on_field 유닛의 타입을 복사해 자신의
    current_type에 넣는다(_move_stab_multiplier가 읽어 STAB로 되먹임). 미설정/미부착/상대
    없음/타입 없음 시 no-op이라 회귀 0. 게임 중립·config 구동. 부작용은 char['current_type']
    설정 + 로그뿐 — ctx 비의존이라 자발적 교체(engine)·강제 교체(turn_manager 콜백) 양쪽에서
    같은 함수를 호출할 수 있다(S7에서 진입 즉시 타이밍에 재사용)."""
    mechs = (game_config or {}).get("mechanisms") or {}
    spec = mechs.get("trace")
    if not spec:
        return
    col = spec.get("gimmick_col")
    want = str(spec.get("match_value", "")).strip().lower()
    have = str(char.get("gimmicks", {}).get(col, "")).strip().lower() if col else ""
    if not col or have != want:
        return
    opp = next((p for p in participants
                if p.get('team') != char.get('team') and p.get('on_field', True)
                and get_current(p) > 0), None)
    if opp is None:
        return
    type_col = spec.get("type_col")
    src_type = opp.get("current_type") or (
        opp.get("gimmicks", {}).get(type_col) if type_col else None)
    if not src_type:
        return
    if char.get("current_type") != src_type:
        char["current_type"] = src_type
        add_log(f"  -> [Phase: ON_SWITCH] {char.get('id','?')} 타입이 "
                f"{src_type}(으)로 복사됨 (Trace ← {opp.get('id','?')})")


def _apply_entry_hazard(char, participants, game_config, add_log, field_state=None):
    """교체 진입 정적 해저드 — game_config['mechanisms']['hazard'] 기반. 지정 진영(team)으로
    교체 진입하는 유닛이 주 자원 max의 percent만큼 데미지를 받는다. 모듈 레벨
    get_current/get_max/apply_delta만 쓰므로 ctx·resource_module 비의존 → _fire_switch_in
    시그니처 불변. spec 미설정/team 불일치/자원 없음 시 no-op이라 회귀 0. _fire_switch_in은
    교체 진입에서만 호출되므로 초기 리드(첫 액티브)는 자연히 면제(Pokemon 해저드와 동일).
    spec 예: {"team": "Enemy", "percent": 0.125}. team="both"(대소문자 무시)면 진영 무관."""
    my_team = str(char.get("team"))
    # 정적 해저드(game_config) — team 매칭 시 percent.
    static_pct = 0.0
    mechs = (game_config or {}).get("mechanisms") or {}
    spec = mechs.get("hazard")
    if spec:
        team = spec.get("team")
        if (not team) or str(team).lower() == "both" or str(team) == my_team:
            static_pct = float(spec.get("percent", 0.125))
    # 동적 해저드(field_state.hazard) — 무브로 설치된 진영별 비율. "both" 또는 내 진영 키.
    dyn_pct = 0.0
    fhaz = (field_state or {}).get("hazard") or {}
    if fhaz:
        dyn_pct = max(float(fhaz.get("both", 0) or 0),
                      float(fhaz.get(my_team, 0) or 0))
    # 합성: 이중과세 방지로 큰 값(사용자 결정).
    percent = max(static_pct, dyn_pct)
    if percent <= 0:
        return
    before = get_current(char)
    if before <= 0:
        return
    mx = get_max(char)
    if mx <= 0:
        return
    apply_delta(char, -mx * percent)          # apply_delta는 새 current를 반환하므로 차분으로 계산
    lost = before - get_current(char)
    if lost > 0:
        add_log(f"  -> [Phase: ON_SWITCH] {char.get('id','?')} 진입 데미지 {int(lost)} (Hazard)")
    if get_current(char) <= 0:
        add_log(f"  [Phase: ON_SWITCH] ☠️ {char.get('id','?')} 진입 데미지로 쓰러짐! (Hazard)")


def _fire_switch_in(char, participants, game_config, add_log, field_state=None):
    """교체 진입 즉시 처리 — 진입 효과(Trace 등) + 진입 이벤트(상태 만료) + 진입 로그를 한 번에
    발화한다. ctx 비의존(add_log 콜백만 받음)이라 자발적 교체(engine)·강제 교체(turn_manager
    콜백) 양쪽에서 같은 함수를 부른다. 호출부가 직후 just_switched_in을 소비해 다음-턴
    _act_on_switch 이중 발화를 막는다. field_state는 전장 동적 상태(F1 substrate) — 그대로
    _apply_entry_hazard에 전달돼 F2 동적 해저드가 읽는다. F1에선 None/빈 dict라 동작 변화 0."""
    _apply_switch_in_effects(char, participants, game_config, add_log)
    _apply_entry_hazard(char, participants, game_config, add_log, field_state)
    _notify_event("ON_SWITCH", char, {"add_log": add_log}, role="actor")
    add_log(f"  -> [Phase: ON_SWITCH] {char.get('id','?')} ({char.get('name','?')}) 진입")


def _act_on_switch(ctx):
    """교체 진입 hook (ON_SWITCH) — 다음-턴 안전망(fallback). S7 이후 진입은 보통 교체 시점에
    _fire_switch_in으로 즉시 처리되고 just_switched_in이 그때 소비되므로, 이 hook은 즉시 처리를
    놓친 진입에 대한 fallback이다. 미설정 시 no-op이라 회귀 0."""
    char = ctx["active_char"]
    if not char.get("just_switched_in"):
        return
    char["just_switched_in"] = False
    _fire_switch_in(char, ctx["participants"], ctx.get("game_config"), ctx["add_log"], ctx.get("field_state"))


# ── 디폴트 액션을 글로벌 레지스트리에 등록 ──
DEFAULT_ACTION_REGISTRY.register("PASSIVE_START", _act_passive_start)
DEFAULT_ACTION_REGISTRY.register("STAT_CALC",     _act_stat_calc)
DEFAULT_ACTION_REGISTRY.register("TARGET_SELECT", _act_target_select)
DEFAULT_ACTION_REGISTRY.register("MOVE",          _act_move)
DEFAULT_ACTION_REGISTRY.register("MOVE_SELECT",   _act_move_select)
DEFAULT_ACTION_REGISTRY.register("DAMAGE_CALC",   _act_damage_calc)
DEFAULT_ACTION_REGISTRY.register("ELEMENT_MULT",  _act_element_mult)
DEFAULT_ACTION_REGISTRY.register("CRIT_CALC",     _act_crit_calc)
DEFAULT_ACTION_REGISTRY.register("APPLY_DAMAGE",  _act_apply_damage)
DEFAULT_ACTION_REGISTRY.register("ON_HIT",        _act_on_hit)
DEFAULT_ACTION_REGISTRY.register("DEATH_CHECK",   _act_death_check)
DEFAULT_ACTION_REGISTRY.register("ON_TURN_END",   _act_turn_end_heal)
DEFAULT_ACTION_REGISTRY.register("ON_STATUS_TICK", _act_status_tick)
DEFAULT_ACTION_REGISTRY.register("ON_MOVE_USE",    _act_move_use)
DEFAULT_ACTION_REGISTRY.register("ON_MOVE_EFFECT", _act_move_effect)
DEFAULT_ACTION_REGISTRY.register("ON_SWITCH",      _act_on_switch)


# ═══════════════════════════════════════════════════════════════════════════════
# run_simulation — 디스패처 기반 동적 전투 엔진
# ═══════════════════════════════════════════════════════════════════════════════

def default_stochasticity_factory(seed):
    """Monte Carlo 기본 RNG 모델 — DamageVariance(±10%). 모듈 레벨 정의(Pickling 안전)."""
    from modules.stochasticity import DamageVariance
    return DamageVariance(variance_pct=0.1, seed=seed)


def _worker_simulate_match(args):
    """
    병렬 처리 워커: Windows Pickling 에러 방지를 위해 모듈 레벨에 정의.
    반환값: Ally 승리시 1, Enemy 승리시 0. 에러 발생 시 트레이스백 문자열 반환.
    """
    try:
        (ally_party, enemy_party, combat_flow, speed_stat, sys_stats, global_formula,
         max_turns, stochasticity_factory, resource_module,
         spatial_module, range_stat, move_stat, deck_module, game_config, worker_seed) = args
        ally_copy = copy.deepcopy(ally_party)
        enemy_copy = copy.deepcopy(enemy_party)
        
        # 워커별 독립 RNG 인스턴스 생성
        stoch_instance = stochasticity_factory(worker_seed) if stochasticity_factory else None
        
        winner, _, sim_metrics = run_simulation(
            ally_copy, enemy_copy, max_turns=max_turns,
            combat_flow=combat_flow, speed_stat=speed_stat, sys_stats=sys_stats,
            global_damage_formula=global_formula, silent=True,
            stochasticity=stoch_instance,
            resource_module=resource_module,
            spatial_module=spatial_module, range_stat=range_stat, move_stat=move_stat,
            deck_module=deck_module, game_config=game_config
        )
        return (1 if winner == "Ally" else 0, sim_metrics)
    except Exception as e:
        return f"ERROR: {traceback.format_exc()}"

def run_monte_carlo(ally_party, enemy_party, combat_flow, speed_stat, sys_stats, global_formula,
                    num_simulations=10000, max_turns=100, progress_callback=None,
                    stochasticity_factory=None, resource_module=None,
                    spatial_module=None, range_stat=None, move_stat=None,
                    deck_module=None, game_config=None):
    num_chunks = 20
    chunk_size = max(1, num_simulations // num_chunks)
    tasks = []
    for i in range(num_simulations):
        worker_seed = i
        tasks.append((ally_party, enemy_party, combat_flow, speed_stat, sys_stats, global_formula,
                      max_turns, stochasticity_factory, resource_module,
                      spatial_module, range_stat, move_stat, deck_module, game_config, worker_seed))
    ally_wins = 0
    completed = 0
    errors = []
    
    total_damage = 0.0
    damage_count = 0
    element_damage_map = {}
    element_damage_count = {}
    total_buff_turns = 0.0
    buff_count = 0
    
    max_workers = os.cpu_count() or 4
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        for result in executor.map(_worker_simulate_match, tasks, chunksize=max(1, chunk_size // max_workers)):
            if isinstance(result, str) and result.startswith("ERROR:"):
                errors.append(result)
            else:
                win_res, metrics = result
                ally_wins += win_res
                total_damage += metrics["total_damage"]
                damage_count += metrics["damage_count"]
                total_buff_turns += metrics["buff_turns"]
                buff_count += metrics["buff_count"]
                for el, dmg in metrics["element_damage"].items():
                    element_damage_map[el] = element_damage_map.get(el, 0) + dmg
                    element_damage_count[el] = element_damage_count.get(el, 0) + metrics["element_damage_count"].get(el, 0)
            completed += 1
            if progress_callback and completed % chunk_size == 0:
                progress_callback(completed, num_simulations)
    if progress_callback and completed % chunk_size != 0:
        progress_callback(completed, num_simulations)
        
    if errors:
        return {"status": "error", "message": errors[0]}
        
    avg_damage = total_damage / damage_count if damage_count > 0 else 0.0
    avg_buff_turns = total_buff_turns / buff_count if buff_count > 0 else 0.0
    avg_element_damage = {el: (dmg / element_damage_count[el]) for el, dmg in element_damage_map.items() if element_damage_count[el] > 0}
    
    return {
        "status": "success", 
        "win_rate": (ally_wins / num_simulations) * 100.0,
        "avg_damage": avg_damage,
        "element_damage_map": avg_element_damage,
        "avg_buff_duration": avg_buff_turns
    }

def run_simulation(ally_instances, enemy_instances, max_turns=100,
                   combat_flow=None, speed_stat=None, sys_stats=None, global_damage_formula=None, silent=False,
                   action_registry=None, turn_manager_cls=None,
                   win_condition=None,
                   stochasticity: StochasticityModule = None,
                   resource_module=None,
                   spatial_module=None, range_stat=None,
                   move_stat=None, deck_module=None, game_config=None):
    logs = []
    def add_log(msg): 
        if not silent: logs.append(msg)

    # ── 0. Inject missing state (Backward compatibility for single match in UI) ──
    # [제거됨] Streamlit 의존성 완벽 차단을 위해 st.session_state 로드 로직 전체 삭제


    if not combat_flow: combat_flow = DEFAULT_COMBAT_FLOW
    if not sys_stats: sys_stats = []
    if not global_damage_formula: global_damage_formula = "0"
    if game_config is None: game_config = {}

    # ── Stochasticity 결정 ──
    stochasticity_instance = stochasticity or NoVariance()
    resource_module = resource_module or ResourceModule()
    spatial_module = spatial_module or SpatialModule()
    if win_condition is None:
        win_condition = ResourceDepletion(resource_module.vital_resources())

    # ── 레지스트리/매니저 결정 ──
    registry = action_registry or DEFAULT_ACTION_REGISTRY
    TurnManagerCls = turn_manager_cls or SequentialTurnManager

    # ── 1. 참가자 초기화 (active_states 배열 보장) ──
    participants = []
    for i, inst in enumerate(ally_instances):
        if inst:
            p = {**inst, "id": f"A{i+1}", "team": "Ally"}
            p['resources'] = copy.deepcopy(inst.get('resources', {}))
            p['position'] = copy.deepcopy(inst.get('position'))
            p['deck'] = copy.deepcopy(inst.get('deck', []))
            p['hand'] = []
            p['discard'] = []
            p.setdefault("active_states", [])
            participants.append(p)
    for i, inst in enumerate(enemy_instances):
        if inst:
            p = {**inst, "id": f"E{i+1}", "team": "Enemy"}
            p['resources'] = copy.deepcopy(inst.get('resources', {}))
            p['position'] = copy.deepcopy(inst.get('position'))
            p['deck'] = copy.deepcopy(inst.get('deck', []))
            p['hand'] = []
            p['discard'] = []
            p.setdefault("active_states", [])
            participants.append(p)

    # ── 1b. 액티브/예비(reserve) 회전 — active_count 기반 on_field 지정 ──
    # 게임 중립 프리미티브. active_count 미설정/비정상 시 팀 크기로 → 전원 on_field
    # (현행 전원-동시 동작, 회귀 0). 특정 게임 분기 없음.
    _gc_field = game_config or {}
    try:
        _ac_cfg = int(_gc_field.get("active_count"))
    except (TypeError, ValueError):
        _ac_cfg = None
    for _team_name in ("Ally", "Enemy"):
        _team_members = [p for p in participants if p['team'] == _team_name]
        _ac = _ac_cfg if (_ac_cfg and _ac_cfg > 0) else len(_team_members)
        for _ri, _p in enumerate(_team_members):
            _p['roster_idx'] = _ri
            _p['on_field'] = _ri < _ac

    if not any(p['team'] == 'Ally' for p in participants) or \
       not any(p['team'] == 'Enemy' for p in participants):
        add_log("❌ 전투 시뮬레이션을 시작하려면 양 팀 모두 최소 한 명 이상의 캐릭터가 배치되어야 합니다.")
        return "None", logs, {}

    sim_metrics = {
        "total_damage": 0.0,
        "damage_count": 0,
        "element_damage": {},
        "element_damage_count": {},
        "buff_turns": 0.0,
        "buff_count": 0
    }

    # ── 2. Combat Flow 파싱 → 정규화 키 리스트 ──
    all_actions = []  # [(key, original_label), ...]
    for phase in combat_flow:
        for item in phase.get("items", []):
            key = _parse_action_key(item)
            if key and registry.has(key):
                all_actions.append((key, item))

    # Fail-safe: TARGET_SELECT가 없으면 암묵적으로 삽입
    action_keys_only = [k for k, _ in all_actions]
    if _PIVOT_KEY not in action_keys_only:
        # 첫 번째 per-target 액션 직전에 삽입
        insert_idx = next(
            (i for i, (k, _) in enumerate(all_actions) if k in _TARGET_LEVEL_KEYS),
            len(all_actions)
        )
        all_actions.insert(insert_idx, (_PIVOT_KEY, "Determine Targeting (타겟팅 결정)"))

    # MOVE 자동 삽입 — TARGET_SELECT 직전 (Phase 4b)
    if "MOVE" not in [k for k, _ in all_actions]:
        _ts_idx = next((i for i, (k, _) in enumerate(all_actions) if k == _PIVOT_KEY), 0)
        all_actions.insert(_ts_idx, ("MOVE", "Move Toward Target (이동)"))

    # MOVE_SELECT 자동 삽입 — TARGET_SELECT 직후, per-target 첫 액션 (Phase 8a)
    if "MOVE_SELECT" not in [k for k, _ in all_actions]:
        _ms_idx = next((i for i, (k, _) in enumerate(all_actions) if k == _PIVOT_KEY), -1)
        all_actions.insert(_ms_idx + 1, ("MOVE_SELECT", "Select Move (무브 선택)"))

    # ON_MOVE_USE 자동 삽입 — MOVE_SELECT 직후, 무브 사용 직전 동적 타입 hook
    if "ON_MOVE_USE" not in [k for k, _ in all_actions]:
        _mu_idx = next((i for i, (k, _) in enumerate(all_actions) if k == "MOVE_SELECT"), -1)
        all_actions.insert(_mu_idx + 1, ("ON_MOVE_USE", "Use Move (무브 사용)"))

    # ON_MOVE_EFFECT 자동 삽입 — ON_MOVE_USE 직후, 무브 효과(boost 등) 적용 hook
    if "ON_MOVE_EFFECT" not in [k for k, _ in all_actions]:
        _me_idx = next((i for i, (k, _) in enumerate(all_actions) if k == "ON_MOVE_USE"), -1)
        all_actions.insert(_me_idx + 1, ("ON_MOVE_EFFECT", "Move Effect (무브 효과)"))

    # ON_TURN_END 자동 삽입 — 흐름 끝, 캐릭터 턴 종료 동적 메커니즘 hook
    if "ON_TURN_END" not in [k for k, _ in all_actions]:
        all_actions.append(("ON_TURN_END", "Turn End Effects (턴 종료 효과)"))

    # ON_STATUS_TICK 자동 삽입 — ON_TURN_END 직후, 턴 종료 상태이상 데미지 hook
    if "ON_STATUS_TICK" not in [k for k, _ in all_actions]:
        all_actions.append(("ON_STATUS_TICK", "Status Tick (상태이상 처리)"))

    # ON_SWITCH 자동 삽입 — 흐름 맨 앞, 교체로 진입한 유닛의 진입 효과 hook
    if "ON_SWITCH" not in [k for k, _ in all_actions]:
        all_actions.insert(0, ("ON_SWITCH", "On Switch In (교체 진입 효과)"))

    # 피벗 기준으로 캐릭터 단위 / 타겟 단위 분리
    pre_target_actions = []
    per_target_actions = []
    post_target_actions = []
    pivot_found = False
    for key, label in all_actions:
        if key in _POST_LEVEL_KEYS:
            post_target_actions.append((key, label))
        elif key == _PIVOT_KEY:
            pre_target_actions.append((key, label))
            pivot_found = True
        elif not pivot_found:
            pre_target_actions.append((key, label))
        else:
            per_target_actions.append((key, label))

    # ── 3. 전투 개시 로그 (활성 흐름 표시) ──
    flow_str = " → ".join(k for k, _ in all_actions)
    add_log(f"⚔️ 전투가 시작됩니다! [Active Flow: {flow_str}]")

    # ── 전장 동적 상태(field_state) — 전투마다 새 dict. build_ctx가 클로저로 캡처해 매 ctx에
    #    같은 참조를 넣는다. game_config(정적)와 분리 → 병렬 워커 재사용 누수 없음(F1 substrate).
    #    F1에선 아무도 쓰지 않아 빈 채로 남아 동작 변화 0. F2(동적 해저드)부터 채운다.
    field_state = {}

    # ── ctx 빌더 ──
    def build_ctx(active_char, turn, participants_list):
        gimmicks = active_char.get('gimmicks', {})
        _ch = (game_config or {}).get("channels") or {}

        passive_col = _channel_col(gimmicks, _ch, "passive", "passive")
        passive_logic = gimmicks.get(passive_col, "") if passive_col else ""

        trigger_col = _channel_col(gimmicks, _ch, "trigger", "trigger")
        trigger_val = gimmicks.get(trigger_col, "Active_Cast") if trigger_col else "Active_Cast"

        target_col_g = _channel_col(gimmicks, _ch, "target", "target")
        target_val = gimmicks.get(target_col_g, "Single_Target") if target_col_g else "Single_Target"

        formula_col = _channel_col(gimmicks, _ch, "formula", "formula")
        local_formula = gimmicks.get(formula_col) if formula_col else None
        formula_str = (str(local_formula)
                       if local_formula and str(local_formula).strip()
                       and str(local_formula).strip() != "None"
                       else global_damage_formula)

        element_col = _channel_col(gimmicks, _ch, "element", "element")
        atk_elem = gimmicks.get(element_col, "Neutral") if element_col else "Neutral"
        damage_type_col = _channel_col(gimmicks, _ch, "damage_type",
                                       ("damage_type", "dmg_type"))
        damage_type = gimmicks.get(damage_type_col) if damage_type_col else None
        
        attack_range = get_effective_stat(active_char, range_stat) if range_stat else None
        move_range = get_effective_stat(active_char, move_stat) if move_stat else None

        ctx = {
            "active_char":   active_char,
            "participants":  participants_list,
            "add_log":       add_log,
            "turn":          turn,
            "sys_stats":     sys_stats,
            "passive_logic": passive_logic,
            "trigger_val":   trigger_val,
            "target_val":    target_val,
            "formula_str":   formula_str,
            "atk_elem":      atk_elem,
            "damage_type":   damage_type,
            "sim_metrics":   sim_metrics,
            "stochasticity": stochasticity_instance,
            "resource_module": resource_module,
            "spatial_module": spatial_module,
            "attack_range":   attack_range,
            "move_range":     move_range,
            # 아래는 액션 블록이 채우는 런타임 값
            "targets":       [],
            "current_target": None,
            "current_move":  None,
            "game_config":   game_config,
            "field_state":   field_state,
            "raw_dmg":       0,
            "dmg":           0,
            "elem_mult":     1.0,
            "battle_over":   False,
        }
        return ctx

    # ── TurnManager 인스턴스 생성 후 실행 ──
    if deck_module is not None:
        turn_executor = CardTurnExecutor(deck_module, build_ctx, sys_stats,
                                         pre_target_actions, per_target_actions)
    else:
        turn_executor = StandardTurnExecutor(pre_target_actions, per_target_actions,
                                             post_target_actions)
    # 행동 우선도 예측기 — read-only로 이번 라운드 각 on_field 유닛의 행동(교체/무브)을 미리
    # 읽어 행동 순서 정렬용 우선도 스칼라를 만든다. 교체 예정 유닛은 switch_priority 티어(공격
    # 보다 앞섬), 그 외엔 예측된 무브의 priority(P1 필드, 기본 0). 부작용 없음(데미지·스왑·로그
    # 없음). 모든 무브 우선도 0 + 교체 미설정이면 전원 0 → 정렬 키가 속도만 남아 순수 속도순
    # (회귀 0). 예측은 실행과 같은 공유 순수 코어(_candidate_targets·_select_move_pure)를 호출해
    # 싱글에서 "예측한 무브 = 실제 실행 무브"를 구조적으로 보장한다. build_ctx(turn=0)은 로그
    # 문자열에만 turn을 쓰므로 예측 결과에 영향 없음.
    def _predict_action_priority(unit):
        if _will_voluntary_switch(unit, participants, game_config):
            return int((game_config or {}).get("switch_priority", 6))
        _pctx = build_ctx(unit, 0, participants)
        _ptargets = _candidate_targets(unit, participants, _pctx["target_val"],
                                       _pctx.get("spatial_module"), _pctx.get("attack_range"))
        if not _ptargets:
            return 0
        _pmove = _select_move_pure(unit, _ptargets[0], _pctx.get("sys_stats"),
                                   _pctx.get("game_config"), _pctx.get("formula_str"))
        if _pmove is None:
            return 0
        try:
            return int(_pmove.get("priority", 0))
        except (TypeError, ValueError):
            return 0

    manager = TurnManagerCls(
        action_registry=registry,
        turn_executor=turn_executor,
        speed_stat=speed_stat,
        broadcast_phase_event=_broadcast_phase_event,
        win_condition=win_condition,
        resource_module=resource_module,
        on_active_faint=(game_config or {}).get("on_active_faint"),
        action_priority=_predict_action_priority,
        on_switch_in=lambda _char, _parts, _alog: _fire_switch_in(_char, _parts, game_config, _alog, field_state),
    )

    winner, sim_metrics = manager.run(
        participants=participants,
        max_turns=max_turns,
        sim_metrics=sim_metrics,
        build_ctx=build_ctx,
        add_log=add_log,
    )

    return winner, logs, sim_metrics
