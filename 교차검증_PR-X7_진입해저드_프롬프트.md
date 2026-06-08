# 교차검증 PR-X7 — 진입 해저드 (SR 타입스케일 + Spikes 층/접지)

> X6 후 잔여 최대 버킷 = **진입 해저드 스위치인**(Jirachi T8·10·11·Abomasnow T9·Skarmory T12).
> 교체로 진입한 유닛이 Stealth Rock·Spikes 데미지를 못 받는다. 엔진엔 진입 해저드 기계가 *이미
> 있으나*(`_apply_entry_hazard`·`_fire_switch_in`) (1) `field_state['hazard']`가 트레이스에서
> 안 채워지고 (2) 평탄 percent만 계산한다(SR 타입스케일·Spikes 층/접지 없음). 진단: 골든도
> 트레이스-리플레이 경로엔 정적 해저드가 미설정이라 **양쪽 다 진입 해저드 미작동** — 이 PR은
> 골든 잔차 #1(switch-in-turn)·#4(SR 타입스케일)도 함께 닫는 일반 메커니즘이다.
>
> **게이트**: 골든 ★ *증가 없음*(이상적으로 진입 해저드/SR 셀이 닫혀 감소). 이 PR은 골든을
> 의도적으로 개선하므로 엄밀 회귀0이 아니라 **회귀 ≤ 0**. ★가 늘면 중단·진단.

## 클린룸 검증 (6 진입 셀 — 전부 로그 정합)

`field_state['hazard']`를 SR(0.125 × Rock 타입곱) + Spikes(층수, 접지만)로 계산:

| 진입 | 타입 | SR(Rock곱) | Spikes | 합 | 로그 |
|---|---|---|---|---|---|
| Jirachi(p2) | Steel/Psychic | 6.25%(×0.5) | 12.5%(1층) | 18.8% | 18% |
| Abomasnow(p2) | Grass/Ice | 25%(×2) | 12.5%(1층) | 37.5% | 37% |
| Skarmory(p1) | Steel/Flying | 12.5%(×1) | 0(SR만) | 12.5% | 12% |
| Garchomp(p1) | Dragon/Ground | 6.25%(×0.5) | 0 | 6.2% | 6% |
| Gliscor(p2) | Ground/Flying | 12.5%(×1) | **0(Flying 면역)** | 12.5% | 12% |
| Scrafty(p1) | Dark/Fighting | 6.25%(×0.5) | 0 | 6.2% | 5% |

## 변경 1 — `reference_gen5.TYPE`에 Rock 공격 행 (SR 타입곱용)

```python
    'Rock': {'Flying': 2.0, 'Bug': 2.0, 'Fire': 2.0, 'Ice': 2.0,
             'Fighting': 0.5, 'Ground': 0.5, 'Steel': 0.5},
```

## 변경 2 — `showdown_trace`가 `-sidestart`/`-sideend`를 이벤트로 emit

파싱 루프에서 `-sidestart`/`-sideend` 라인을 이벤트로(상태 emit과 동형, PR-E′2c처럼):

```python
    # -sidestart|p2: name|move: Stealth Rock  또는  |p2: name|Spikes
    if tag == "-sidestart" and len(parts) >= 4:
        sp_side, _ = _slot(parts[2] + ":")  # 'p2: ban tyranitar' → 'p2'
        sp_side = parts[2].split(":")[0].strip()
        name = parts[3].replace("move:", "").strip()
        events.append({"action": "sidestart", "actor_side": sp_side,
                       "name": name, "turn": turn})
    if tag == "-sideend" and len(parts) >= 4:
        sp_side = parts[2].split(":")[0].strip()
        name = parts[3].replace("move:", "").strip()
        events.append({"action": "sideend", "actor_side": sp_side,
                       "name": name, "turn": turn})
```
(현행 `turn`·`events`·`parts`·`_slot` 변수명에 맞춰 삽입. 기존 이벤트 불변 → 추가만 = 골든 파싱 무변.)

## 변경 3 — `fullbattle_run.build_hazard_by_turn` + 공급

```python
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
```

`setup_for_engine`에서 weather 옆에 공급:
```python
    gc["hazard_by_turn"] = build_hazard_by_turn(trace)   # 진입 해저드 타임라인(PR-X7)
```

## 변경 4 — engine 턴 루프: `field_state['hazard']` 공급 (weather 옆, 가드)

weather 공급 줄(`field_state["weather"] = ...weather_by_turn...`) 바로 아래:
```python
        _hz = ((game_config or {}).get("hazard_by_turn") or {}).get(turn)
        if _hz is not None:
            field_state["hazard"] = _hz      # 미설정 시 미터치 → 회귀0(set_hazard 무브경로 보존)
```

## 변경 5 — engine `_apply_entry_hazard`: 구조형 SR+Spikes 계산 (평탄 호환)

`_apply_entry_hazard` 위에 헬퍼 추가 + dyn_pct 계산을 헬퍼로 교체:

```python
def _hazard_entry_pct(char, hz, game_config):
    """hz가 숫자=구버전 평탄. dict{'sr','spikes'}=구조형: SR(0.125×Rock타입곱)+Spikes(층/접지)."""
    if not isinstance(hz, dict):
        return float(hz or 0)
    g = char.get("gimmicks") or {}
    types = [t for t in (g.get("t1"), g.get("t2")) if t]
    tt = (game_config or {}).get("type_table") or {}
    pct = 0.0
    if hz.get("sr"):
        rock = tt.get("Rock", {}); m = 1.0
        for t in types: m *= float(rock.get(t, 1.0))
        pct += 0.125 * m
    sp = int(hz.get("spikes", 0) or 0)
    if sp and ("Flying" not in types) and char.get("ability") != "Levitate":
        pct += {1: 1/8, 2: 1/6, 3: 1/4}.get(sp, 1/4)
    return pct
```
그리고 `_apply_entry_hazard`의 동적 해저드 블록을 교체:
```python
    fhaz = (field_state or {}).get("hazard") or {}
    if fhaz:
        dyn_pct = max(_hazard_entry_pct(char, fhaz.get("both", 0), game_config),
                      _hazard_entry_pct(char, fhaz.get(my_team, 0), game_config))
```
(나머지 `percent = max(static_pct, dyn_pct)` 이하 그대로. 정적 미설정 → percent=dyn.)

> 퍼센트 모드: `_apply_entry_hazard`는 `get_max(char)`(=394 등 실값, X6 후) × percent로 데미지 →
> 절대 데미지, snapshot이 퍼센트 환산. SR/Spikes pct는 maxhp 무관(불변) → 퍼센트·절대 양쪽 정합.

## 검증 (적용 후, 순서대로)

1. **골든 회귀 ≤ 0**: `python run_b4.py` → ★ *증가 없음*. 골든 진입 해저드/SR 셀(잔차 #1·#4)이
   닫히거나 동일. 늘면 중단·진단.
2. **클린룸 타입곱**(엔진 무관): TYPE['Rock']로 6셀 곱이 위 표와 일치(Jirachi 0.5·Abomasnow 2·
   Skarmory 1·Garchomp 0.5·Gliscor 1·Scrafty 0.5).
3. **run_xval 재실행**: `python run_xval.py` → 진입 해저드 ★(Jirachi T8·10·11·Abomasnow T9·
   Skarmory T12) 소거. ★가 17에서 추가 감소. Jirachi T11 faint도 해저드로 HP 낮아져 정합 가능.
4. **run_dmg_diag**(선택): 진입 직후 HP가 로그 퍼센트와 일치하는지.

## 예상 잔여 (X7 후 — 교차검증 거의 완결)

- **Seismic Toss 고정데미지**(T20·22): 카탈로그된 유일한 언어확장.
- **Brave Bird recoil**(Skarmory 자기반동): 무브 내재 반동 1건.
- Ice Shard 과소(Garchomp T10, lockedmove)·턴0 아티팩트·롤.

이 PR로 교차검증 잔여가 *언어확장 1(Seismic Toss) + 작은 꼬리*로 좁혀진다 — 2-가드 완결,
그리고 골든 잔차 #1·#4까지 부수적으로 닫는다(일반 메커니즘의 양방향 이득).
