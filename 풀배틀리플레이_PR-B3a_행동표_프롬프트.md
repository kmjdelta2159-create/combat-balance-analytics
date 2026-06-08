# PR-B3a — 트레이스 행동표 + run-prep (battle_setup 확장, 클린룸)

## 목적
풀배틀 리플레이의 **행동 주입 데이터 면**(엔진 무관). 트레이스에서 (turn, 행위자)별 행동을
분류·해석해 엔진이 바로 먹을 **trace_actions**(move/target 오버라이드 + 자발교체) + 기절-교체
incoming 큐 + 리드/team/on_field/roster_idx를 조립한다. 엔진 수정은 **PR-B3b**(앱사이드);
이 PR은 그 입력을 만드는 클린룸 조각이라 지금 검증·납품 가능. `battle_setup.py`에 함수 2개
추가, 다른 파일 무변경.

## 대상
**기존 파일 확장** `modules/battle_setup.py` — `build_trace_actions` + `prepare_run` 추가
(append). 기존 `build_participants`/`build_battle_spec` 무변경.

## 설계 근거 (gen5 골든 로그로 검증됨 — switch 24건의 정밀 분류)
트레이스 switch는 단일 종류가 아니다. on-field·HP·기절 타임라인을 복원해 분류해야 엔진
주입 경로가 갈린다(핸드오프 "정직한 난점"):
- **리드(2)**: turn 0 등장 = 초기 on_field 셋업(행동 아님).
- **기절-교체(7)**: 나가는 유닛이 이미 기절 → 엔진 `_resolve_faint` 경로(PR-B3c). 단 *어느
  예비가 들어오는지*는 로그가 지정(엔진 기본은 roster_idx[0]) → incoming 큐로 공급.
- **피벗 무브 교체(1, Volt Switch)**: 무브가 데미지 후 교체를 유발 = 무브효과 메커니즘.
  B3 범위 밖 → B4 divergence가 T3에서 지목할 후속(효과-스키마).
- **자발교체(14)**: 살아있는 on-field 유닛이 공격 대신 교체 선택 → `_maybe_voluntary_switch`
  트레이스 분기(PR-B3b).
- **무브(36)**: move/target 오버라이드. 무브 dict(power/category/type)는 ref.MOVES로 해석.

검증: gen5 골든 로그에서 move 36 + 자발 14 + 기절incoming 7 + 피벗 1 + 리드 2, 모든 target·
incoming이 빌드된 participant id로 resolve(dangling 0), 데미지 무브 자가타격 0.

## 추가할 함수 (전체 — 바이트 그대로, battle_setup.py 끝에 append)

```python
# 피벗(데미지 후 자기 교체) 무브 — 교체를 무브가 유발(자발교체와 구분). B3 범위 밖(B4 후속).
PIVOT_MOVES = {"Volt Switch", "U-turn"}


def build_trace_actions(trace, ref, pivot_moves=PIVOT_MOVES):
    """트레이스 → (turn, 행위자 id)별 행동 분류. on-field·HP·기절 타임라인 복원으로 switch를
    리드/기절교체/피벗/자발로 가른다. 무브 dict는 ref.MOVES로 해석. 엔진 무관.

    반환 dict:
      move_actions    {(turn, actor_id): {'move': {name,power,category,type}, 'target': id}}
      vol_switch      {(turn, actor_id): incoming_id}            # 자발교체(엔진 selector)
      faint_incoming  [{turn, side, outgoing, incoming}, ...]    # 기절교체 incoming(엔진 faint 경로)
      pivot_switch    {(turn, actor_id): incoming_id}            # 피벗(B4 후속)
      leads           {side: nick}                                # 초기 on_field
    """
    onfield = {}
    hp = {}
    fainted = set()
    move_actions = {}
    vol = {}
    faint_incoming = []
    pivot = {}
    leads = {}
    moves_by_ta = {}
    for e in trace["events"]:
        if e.get("action") == "move":
            moves_by_ta.setdefault((e["turn"], e["actor"]), set()).add(e["move"])
    for e in trace["events"]:
        a = e.get("action")
        tn = e.get("turn")
        if a == "move":
            for w in e.get("faints", []):
                hp[w] = 0
                fainted.add(w)
            for h in e.get("hits", []):
                if h.get("cur") is not None:
                    hp[h["who"]] = h["cur"]
            tgt = e.get("target") or (e["hits"][0]["who"] if e.get("hits") else None)
            md = ref.MOVES.get(e["move"])
            mv = {"name": e["move"], "power": (md[0] if md else 0),
                  "category": (md[1] if md else None), "type": (md[2] if md else None)}
            move_actions[(tn, e["actor"])] = {"move": mv, "target": tgt}
        elif a == "env":
            if e.get("cur") is not None:
                hp[e["who"]] = e["cur"]
            if e.get("cur") == 0:
                fainted.add(e["who"])
        elif a == "faint":
            fainted.add(e["who"])
            hp[e["who"]] = 0
        elif a == "switch":
            side = e["actor_side"]
            inc = e["actor"]
            out = onfield.get(side)
            if out is None or tn == 0:
                leads[side] = inc                                   # 리드(셋업)
            elif out in fainted or hp.get(out, 1) == 0:
                faint_incoming.append({"turn": tn, "side": side,
                                       "outgoing": out, "incoming": inc})   # 기절교체
            elif moves_by_ta.get((tn, out), set()) & pivot_moves:
                pivot[(tn, out)] = inc                               # 피벗(B4 후속)
            else:
                vol[(tn, out)] = inc                                 # 자발교체
            onfield[side] = inc
            if e.get("hp") is not None:
                hp[inc] = e["hp"]
            fainted.discard(inc)
    return {"move_actions": move_actions, "vol_switch": vol,
            "faint_incoming": faint_incoming, "pivot_switch": pivot, "leads": leads}


def prepare_run(trace, ref):
    """B2 participants + B3 trace_actions를 엔진이 바로 먹을 형태로 조립.
    participant에 team(Ally/Enemy)·on_field(리드)·roster_idx(진영 등장순) 부여, game_config에
    trace_actions(move/switch)·trace_faint_incoming·switch_policy(trace) 주입.
    반환: (participants, battle_spec, trace_actions_dict)."""
    parts = build_participants(trace, ref)
    spec = build_battle_spec(trace, ref)
    ta = build_trace_actions(trace, ref)
    side2team = {"p1": "Ally", "p2": "Enemy"}
    idx = {}
    leads = set(ta["leads"].values())
    for p in parts:
        sd = p.get("side")
        p["team"] = side2team.get(sd, sd)
        p["on_field"] = (p["id"] in leads)
        idx[sd] = idx.get(sd, 0)
        p["roster_idx"] = idx[sd]
        idx[sd] += 1
    gc = spec["game_config"]
    gc["trace_actions"] = {"move": ta["move_actions"], "switch": ta["vol_switch"]}
    gc["trace_faint_incoming"] = ta["faint_incoming"]
    gc["switch_policy"] = {"type": "trace"}   # 트레이스 구동 — hp_threshold 정책 대체
    return parts, spec, ta
```

## API
- `build_trace_actions(trace, ref) -> {move_actions, vol_switch, faint_incoming, pivot_switch, leads}`
  — switch 정밀 분류 + 무브 해석. 엔진 무관.
- `prepare_run(trace, ref) -> (participants, battle_spec, trace_actions)` — 엔진 실행 직전
  완성 셋업(team/on_field/roster_idx + game_config 주입).

## 검증 (클린룸·gen5 골든 로그, 작성 시 수행 — 적용자 재현용)
`reference_gen5` 주입(PR-B2):
- `build_trace_actions`: move **36**, vol_switch **14**, faint_incoming **7**, pivot **1**,
  leads **2**. 모든 target·incoming·outgoing이 `nick2species` 닉으로 resolve(미해결 **0**),
  데미지 무브 자가타격 **0**.
- `prepare_run`: participants **12**, on_field(리드) **2**(Gengen·Rotom-Wash), team Ally/Enemy,
  roster_idx 전부 부여, game_config trace_actions(move 36 / switch 14)·faint_incoming 7·
  switch_policy{type:trace}. participant id로 dangling 참조 **0**.

적용자 검증:
1. `ast.parse` OK.
2. ```python
   from modules.showdown_trace import parse_replay
   from modules.battle_setup import build_trace_actions, prepare_run
   import modules.reference_gen5 as r5
   t = parse_replay(open('Gen5OU-2015-05-11-reymedy-leftiez.html', encoding='utf-8').read())
   ta = build_trace_actions(t, r5)
   assert len(ta['move_actions'])==36 and len(ta['vol_switch'])==14
   assert len(ta['faint_incoming'])==7 and len(ta['leads'])==2
   parts, spec, _ = prepare_run(t, r5)
   assert len([p for p in parts if p['on_field']])==2
   assert len(spec['game_config']['trace_actions']['move'])==36
   ```
3. 기존 모듈 import·동작 무변경.

## 회귀 0
battle_setup에 함수 2개 추가(기존 함수 무변경). 엔진 미호출(클린룸). game_config에 키를
*담기만* 함 — 엔진이 이 키를 읽는 분기는 PR-B3b에서 추가되며 그 전까지 무시됨(현 엔진 동작
무변경).

## 다음 (PR-B3b·B3c 예고)
- **B3b(엔진, 앱사이드)**: `_maybe_voluntary_switch`(trace 분기) + `_act_target_select`(move/
  target 오버라이드) + `_act_move_select`(로그 무브 사용). game_config['trace_actions'] 없으면
  no-op(회귀0). FIND/REPLACE 앵커는 Read/Grep으로 고정됨.
- **B3c(turn_manager, 앱사이드)**: `_resolve_faint`가 trace_faint_incoming의 outgoing→incoming
  지정대로 예비 진입(엔진 기본 roster_idx[0] 대체). 없으면 현행 유지(회귀0).
- **피벗(Volt Switch)·턴내 교체 순서**: B4 divergence가 라운드 단위로 지목할 후속(효과-스키마/
  ordering). 의도된 잔차.
그 뒤 **B4**: prepare_run → 엔진 턴루프 실행 → fullbattle_diff로 라운드별 divergence(앱 실행).
