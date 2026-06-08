"""
풀배틀 통합 run — prepare_run → 엔진 실행(트레이스 구동) → 라운드별 divergence.

A 하니스의 골드 스탠다드. per-event(데미지 1건씩)와 달리 엔진의 턴 스케줄러·전 페이즈·효과를
*전투 전체* 동안 로그대로 구동하고, 라운드별 엔진 상태를 로그 스냅샷과 대조한다. 엔진 호출은
run_and_diff 안에서 lazy import(앱 환경) — 순수 함수(engine_snapshot·capture·리포트)는 엔진
무관이라 클린룸 검증된다.

정직한 한계(B4 리포트가 드러낼 후속): 데미지 롤(0.85~1.0) 미관측이라 엔진 max-roll vs 로그
실측 HP는 롤 폭만큼 어긋난다 → 작은 hp 차이는 롤 노이즈, **구조적 신호는 faint·status·큰 hp
차이**(미모델 효과: Psyshock 방어타격·SR 타입스케일·Life Orb·status 부여·피벗·크리). 첫 구조적
divergence를 격리하는 게 이 리포트의 핵심.
"""
from modules.battle_setup import prepare_run
from modules.fullbattle_diff import build_snapshots, divergence
from modules.resource import get_current, init_resources


def _status_of(p):
    """participant active_states에서 상태이상 토큰(gate_status/status) 추출. 없으면 None."""
    for s in p.get("active_states", []):
        st = s.get("gate_status") or s.get("status")
        if st:
            return st
    return p.get("status")    # resync 주입 status 폴백(없으면 None — 회귀0)


def engine_snapshot(participants, hp_mode="absolute"):
    """엔진 participant 리스트 → {id: {hp, status, fainted}} (로그 스냅샷과 동일 스키마).
    hp_mode='percent'면 HP를 퍼센트(0~100)로 환산해 로그 퍼센트와 같은 공간에서 비교."""
    snap = {}
    for p in participants:
        cur = int(get_current(p))
        if hp_mode == "percent":
            mx = p.get("maxhp") or (p.get("resources", {}).get("HP", {}).get("max") or 1)
            hp_val = round(cur / mx * 100) if mx > 0 else 0
        else:
            hp_val = cur
        snap[p["id"]] = {"hp": hp_val, "status": _status_of(p), "fainted": cur <= 0}
    return snap


def _make_capture(history, hp_mode="absolute"):
    """on_turn_end 콜백 — 매 턴 종료 시 엔진 상태를 history[turn]에 스냅샷(마지막이 그 턴
    최종)."""
    def hook(ctx):
        history[ctx.get("turn")] = engine_snapshot(ctx["participants"], hp_mode=hp_mode)
    return hook


def build_weather_by_turn(trace):
    """트레이스 → {turn: 'rain'/'sand'/None}. move context.weather·env weather 필드의 그 턴
    값을 normalize, 결측 턴은 직전값 carry(날씨는 명시 전이까지 지속)."""
    def norm(w):
        if not w:
            return None
        s = str(w).lower()
        return "rain" if "rain" in s else ("sand" if "sand" in s else s)
    seen = {}
    for e in trace["events"]:
        tn = e.get("turn")
        if tn is None:
            continue
        w = (e.get("context") or {}).get("weather") or e.get("weather")
        if w is not None:
            seen[tn] = norm(w)
    out = {}
    cur = None
    for t in range(0, (max(seen) if seen else 0) + 1):
        if seen.get(t) is not None:
            cur = seen[t]
        out[t] = cur
    return out


def build_hazard_by_turn(trace):
    """트레이스 -sidestart/-sideend → {turn: {team: {'sr': bool, 'spikes': int}}}.
    p1→Ally·p2→Enemy. 해저드는 청소 전까지 지속 → 턴별 누적 스냅샷(weather와 동형)."""
    s2t = {"p1": "Ally", "p2": "Enemy"}
    evs = sorted([e for e in trace["events"] if e.get("action") in ("sidestart", "sideend")],
                 key=lambda e: e.get("turn") or 0)
    cur = {"Ally": {"sr": False, "spikes": 0}, "Enemy": {"sr": False, "spikes": 0}}
    maxt = max([e.get("turn") or 0 for e in trace["events"]] + [0])
    by_turn = {}
    ei = 0
    for t in range(0, maxt + 1):
        while ei < len(evs) and (evs[ei].get("turn") or 0) <= t:
            e = evs[ei]; ei += 1
            tm = s2t.get(e.get("actor_side")); nm = (e.get("name") or "").lower()
            if tm is None: continue
            if e["action"] == "sidestart":
                if "stealth rock" in nm: cur[tm]["sr"] = True
                elif "spikes" in nm: cur[tm]["spikes"] = min(3, cur[tm]["spikes"] + 1)
            else:  # sideend(청소)
                if "stealth rock" in nm: cur[tm]["sr"] = False
                elif "spikes" in nm: cur[tm]["spikes"] = 0
        by_turn[t] = {k: dict(v) for k, v in cur.items()}
    return by_turn


def _norm_stat(s):
    s = (s or "").lower()
    return {"attack": "atk", "defense": "def"}.get(s, s)


def stage_mult(n):
    """gen5 일반스탯 stage 배율: n>=0 → (2+n)/2, n<0 → 2/(2-n)."""
    return (2 + n) / 2.0 if n >= 0 else 2.0 / (2 - n)


def build_boosts_by_turn(trace):
    """트레이스 → {turn: {nick: {stat: net_stages}}}. 누적이되, 교체(switch/drag)로
    필드를 떠난 유닛은 stage 리셋(gen5 룰), 새 진입 유닛은 빈 stage로 시작."""
    onfield = {}        # side -> 현재 on-field nick
    acc = {}            # nick -> {stat: stages}
    by_turn = {}
    last = None
    for e in trace["events"]:
        tn = e.get("turn")
        if tn is None:
            continue
        if last is not None and tn != last:
            by_turn[last] = {n: dict(acc.get(n, {})) for n in onfield.values()
                             if acc.get(n)}
        a = e.get("action")
        if a in ("switch", "drag"):
            side = e.get("actor_side"); inc = e.get("actor")
            prev = onfield.get(side)
            if prev is not None and prev != inc:
                acc[prev] = {}          # 떠난 유닛 stage 리셋
            acc[inc] = {}               # 진입 유닛 새 stage
            onfield[side] = inc
        elif a == "move":
            for b in e.get("boosts", []):
                who = b.get("who"); st = _norm_stat(b.get("stat"))
                if who and st:
                    acc.setdefault(who, {})
                    acc[who][st] = acc[who].get(st, 0) + (b.get("stages") or 0)
        last = tn
    if last is not None:
        by_turn[last] = {n: dict(acc.get(n, {})) for n in onfield.values()
                         if acc.get(n)}
    return by_turn


def build_onfield_timeline(trace):
    """턴 경계마다 진영별 on-field 닉 집합 {turn: set(nick)}. switch가 그 진영 on-field 교체."""
    onf = {}
    tl = {}
    last = None
    for e in trace["events"]:
        tn = e.get("turn")
        if tn is None:
            continue
        if last is not None and tn != last:
            tl[last] = set(onf.values())
        if e.get("action") in ("switch", "drag"):
            onf[e["actor_side"]] = e["actor"]
        last = tn
    if last is not None:
        tl[last] = set(onf.values())
    return tl


def _make_resync(log_snaps, onfield_tl, gc, hp_mode="absolute"):
    """on_round_start 콜백 — 라운드 T 시작에 엔진 상태를 log[T-1]로 재동기화(HP·on_field).
    누적 desync 차단 → divergence가 라운드별 순수 예측오차가 됨.
    hp_mode='percent'면 로그 퍼센트를 절대로 역환산해 엔진 내부 HP에 주입."""
    def hook(turn, participants):
        prev = log_snaps.get(turn - 1)     # HP/on_field: 진입 상태(직전 턴 끝)
        cur = log_snaps.get(turn)          # status: 현재 턴 끝-상태 — 비휘발 상태는 부여된 그 턴에
        pof = onfield_tl.get(turn - 1)     # 틱하므로 log[T]가 정확(log[T-1]은 1턴 지연 → stage 밀림)
        if prev is None:
            return
        for p in participants:
            pid = p.get("id")
            st = prev.get(pid)
            if st and st.get("hp") is not None:
                res = p.setdefault("resources", {}).setdefault("HP", {"current": 0, "max": 0})
                if hp_mode == "percent":
                    mx = p.get("maxhp") or res.get("max") or 1
                    res["current"] = round(st["hp"] / 100 * mx)
                else:
                    res["current"] = st["hp"]
            cst = (cur or {}).get(pid)                            # 상태는 log[T](부여 턴에 틱)
            p["status"] = cst.get("status") if cst is not None else None
            # 맹독 누진 카운터 리셋(PR-E′2d) — off-field거나 비-tox면 0(다음 tox 진입 시 stage 1부터).
            # on-field+tox면 유지(턴엔드 디스패처가 증가). forced 진입은 턴엔드 없어 그 턴 무증가.
            on_f = (pof is None) or (pid in pof)
            if (not on_f) or p.get("status") != "tox":
                p["tox_stage"] = 0
            if pof is not None:
                p["on_field"] = (pid in pof)

        # PR-F2 진입 해저드 단일 책임 적용 (하니스)
        # 이번 턴(turn)에 진입하는 유닛 = onfield_tl[turn] \ onfield_tl[turn - 1]
        pof_current = onfield_tl.get(turn) or set()
        pof_prev = onfield_tl.get(turn - 1) or set()
        entered = pof_current - pof_prev
        
        if entered:
            import modules.engine as eng
            hbt = gc.get("hazard_by_turn") or {}
            window_hz = hbt.get(turn - 1) or {}  # 진입 시점(턴 시작)의 해저드 = 직전 턴 끝의 해저드
            
            for p in participants:
                if p.get("id") in entered:
                    team_hz = window_hz.get(p.get("team"))
                    if team_hz:
                        dummy_fs = {"hazard": {p.get("team"): team_hz}}
                        # _apply_entry_hazard 호출 시 add_log는 no-op (엔진 로그와 중복 방지, 또는 그대로 넘겨도 됨)
                        eng._apply_entry_hazard(p, participants, gc, lambda x: None, dummy_fs)

        # PR-F3s 스탯 스테이지 주입
        bbt = gc.get("boosts_by_turn") or {}
        window_boosts = bbt.get(turn - 1) or {}  # [R-1] 창
        stat_map = {"atk": "atk", "def": "df", "spa": "spa", "spd": "spd", "spe": "spe"}

        for p in participants:
            # 1. 기존 트레이스 부스트 제거 (매 라운드 갱신)
            p["active_states"] = [s for s in p.get("active_states", []) 
                                  if not s.get("id", "").startswith("trace_boost_")]
            
            # 2. [R-1] 상태 읽어 주입
            pid = p.get("id")
            if pid in window_boosts:
                for stat_key, stages in window_boosts[pid].items():
                    if not stages: continue
                    eng_stat = stat_map.get(stat_key, stat_key)
                    val = stage_mult(stages) - 1.0
                    p.setdefault("active_states", []).append({
                        "id": f"trace_boost_{eng_stat}",
                        "target_stat": eng_stat,
                        "mod_type": "percent",
                        "value": val,
                        "expire_trigger": "PERMANENT",
                        "expire_count": 9999,
                        "source_id": "trace_boost"
                    })
    return hook


def setup_for_engine(trace, ref, set_override=None):
    """prepare_run → 엔진 호출용 (ally_instances, enemy_instances, game_config) 조립.
    닉 보존(preserve_ids) + HP 자원 초기화 + 진영별 roster_idx 정렬."""
    parts, spec, ta = prepare_run(trace, ref, set_override=set_override)
    gc = spec["game_config"]
    gc["preserve_ids"] = True
    gc["weather_by_turn"] = build_weather_by_turn(trace)   # 발효 날씨 공급(PR-E′2b)
    gc["hazard_by_turn"] = build_hazard_by_turn(trace)   # 진입 해저드 타임라인(PR-X7)
    gc["boosts_by_turn"] = build_boosts_by_turn(trace)   # 스탯 부스트 타임라인(PR-F3s)
    for p in parts:
        init_resources(p, p["maxhp"])           # 엔진 HP 모델(resources.HP)
    ally = sorted([p for p in parts if p.get("side") == "p1"],
                  key=lambda x: x.get("roster_idx", 0))
    enemy = sorted([p for p in parts if p.get("side") == "p2"],
                   key=lambda x: x.get("roster_idx", 0))
    return ally, enemy, gc, spec


def run_and_diff(trace, ref, hp_tol=0, max_turns=100, resync=True, hp_mode="absolute", set_override=None, dmg_debug=False):
    """풀배틀 통합 run + divergence. 엔진은 lazy import(앱 환경). resync=True면 라운드별
    재동기화(누적 desync 차단 → 라운드별 순수 예측오차). hp_mode='percent'면 퍼센트 공간에서
    비교(래더 기본값). 반환: {log, engine, divergence, first}."""
    from modules.engine import run_simulation
    ally, enemy, gc, spec = setup_for_engine(trace, ref, set_override=set_override)
    gc["dmg_debug"] = dmg_debug
    history = {}
    log_snaps = build_snapshots(trace)
    extra = {}
    if resync:
        extra["on_round_start"] = _make_resync(log_snaps, build_onfield_timeline(trace), gc,
                                                hp_mode=hp_mode)
    run_simulation(
        ally, enemy, max_turns=max_turns,
        sys_stats=["atk", "df", "spa", "spd", "spe"], speed_stat="spe",
        global_damage_formula=gc.get("formula"), game_config=gc, silent=True,
        on_turn_end=_make_capture(history, hp_mode=hp_mode), **extra,
    )
    rows = divergence(log_snaps, history, hp_tol=hp_tol)
    structural = [r for r in rows if r[2] in ("faint", "status", "missing")
                  or (r[2] == "hp" and r[3] is not None and r[4] is not None
                      and r[3] < r[4])]   # 로그HP<엔진HP = 엔진이 데미지 덜 줌(미모델)
    first = min(structural, key=lambda r: r[0]) if structural else None
    return {"log": log_snaps, "engine": history, "divergence": rows,
            "structural": structural, "first": first}


def format_report(result):
    """divergence 결과 → 사람이 읽는 리포트(첫 구조적 divergence 격리 + 전체 목록)."""
    rows = result["divergence"]
    log = result["log"]
    max_turn = max(log) if log else 0
    lines = [f"=== 풀배틀 divergence 리포트 (턴 0~{max_turn}) ==="]
    if not rows:
        lines.append("divergence 없음 — 전 라운드 일치 ✅")
        return "\n".join(lines)
    first = result.get("first")
    if first:
        lines.append(f"첫 구조적 divergence: T{first[0]} {first[1]} "
                     f"[{first[2]}] 로그={first[3]} 엔진={first[4]}")
    else:
        lines.append("구조적 divergence 없음 (잔차는 롤 노이즈 추정)")
    lines.append(f"총 {len(rows)}건 (구조적 {len(result['structural'])}건):")
    for r in rows[:50]:
        tag = "★" if r in result["structural"] else " "
        lines.append(f" {tag}T{r[0]:>2} {str(r[1]):12} [{r[2]:7}] "
                     f"로그={r[3]} 엔진={r[4]}")
    return "\n".join(lines)
