# 교차검증 PR-X5 — 과데미지 진단 (게이트된 데미지 덤프, 엔진 무수정·진단 전용)

> X4 후 잔여 구조적 ★의 핵심 = **유령 기절**(Clefable T16·18·Scrafty T24–26·Reuniclus T29).
> 엔진이 이 수비수들을 *로그보다 과하게* 때려 죽인다. **클린룸으로 세트가 옳음을 확정**:
> Clefable Brave Bird 41%(max roll)·Scrafty EQ 33%·Reuniclus Crunch 76% — 전부 로그(32/19/72%)
> 재현, 셋 다 생존. 그런데 엔진은 100%+(즉사)로 **비균일 과타**(×2.4·×3·×1.4). 세트도 maxhp도
> (퍼센트 배관 정상) 아니다 → 데미지 파이프라인 내부(off/def/power/elem/crit/roll) 어딘가다.
> 추측을 멈추고 **계기를 박아 그 셀들의 데미지 분해를 런타임에서 뜬다.** 수정은 원인 확정 후
> 별도 PR.
>
> **게이트(절대)**: 디버그 출력은 `game_config['dmg_debug']` 플래그가 켜질 때만. 기본 off →
> 한 줄도 안 찍힘 → 골든·held-out 동작 무변(회귀0). 이 PR은 *데미지 계산 로직을 바꾸지 않는다* —
> 관측 print만 추가.

## 변경 1 — `engine._act_damage_calc`에 디버그 스냅샷 (플래그 시에만)

raw_dmg 산출 직후(현재 `ctx["dmg"] = ctx["raw_dmg"]` 줄 ~612 아래)에 off/def/power/raw를 stash:

```python
    if (ctx.get("game_config") or {}).get("dmg_debug"):
        ctx["_dbg"] = {
            "off": eval_env_raw.get("offense"), "def": eval_env_raw.get("defense"),
            "pow": eval_env_raw.get("move_power"), "raw": ctx["raw_dmg"],
        }
```

## 변경 2 — `engine._act_apply_damage`에 분해 출력 (플래그 시에만)

`_act_apply_damage` 끝(현재 add_log 뒤, broadcast 전후)에서, 플래그면 한 줄 print:

```python
    if (ctx.get("game_config") or {}).get("dmg_debug"):
        d = ctx.get("_dbg", {})
        print(f"[DMGDBG] T{ctx.get('turn')} {ctx.get('active_char',{}).get('id','?')}"
              f"→{t.get('id','?')} {(ctx.get('current_move') or {}).get('name','?')}: "
              f"pow={d.get('pow')} off={d.get('off')} def={d.get('def')} raw={d.get('raw')} "
              f"elem={ctx.get('elem_mult')} final={dmg} "
              f"maxhp={get_max(t)} hp후={get_current(t)}")
```

> raw=공식 base(post-roll, pre-elem/crit), elem=STAB×타입, final=실제 적용 데미지. off/def=실제
> 사용된 공격/방어 스탯(부스트 반영). maxhp·hp후로 즉사 여부 확인. 크리는 final/raw/elem 비율로
> 역산(×2면 크리).

## 변경 3 — `fullbattle_run.run_and_diff`에 `dmg_debug` 패스스루 (한 줄)

`run_and_diff(..., set_override=None, dmg_debug=False)` 인자 추가 → `setup_for_engine`(또는
호출부)에서 `gc["dmg_debug"] = dmg_debug`. 기본 False → gc에 안 들어가거나 False → print 없음.

## 변경 4 — `run_dmg_diag.py` 신설 (앱사이드, run_xval 복제 + 플래그 on)

`run_xval.py`를 복제하되 `run_and_diff(... dmg_debug=True ...)`로 호출. 데이터-니즈 print는 생략
가능. 전 데미지 셀의 `[DMGDBG]`가 찍힌다(전투 짧아 ~30줄).

```python
# run_dmg_diag.py — 과데미지 진단: 데미지 분해를 런타임에서 덤프
import os, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
DEFAULT = os.path.join(HERE, "Gen5OU-2026-newatmons-bantyranitar.html")

def main():
    from modules.showdown_trace import parse_replay
    from modules.fullbattle_run import run_and_diff
    import modules.reference_gen5 as r5
    with open(sys.argv[1] if len(sys.argv) > 1 else DEFAULT, encoding="utf-8") as f:
        trace = parse_replay(f.read())
    OVR = {'Garchomp': {'nature': 'Jolly', 'evs': (0,252,0,0,4,252), 'item': None, 'ability': 'Rough Skin'}}
    run_and_diff(trace, r5, hp_tol=10, resync=True, hp_mode="percent",
                 set_override=OVR, dmg_debug=True)

if __name__ == "__main__":
    try: main()
    except Exception:
        print("=== run_dmg_diag 에러 ==="); traceback.print_exc(); sys.exit(1)
```

## 검증 (적용 후)

1. **골든 회귀0**: `python run_b4.py` 출력이 PR-X5 전과 완전 동일(플래그 off → print 없음·로직 무변).
2. **진단 실행**: `python run_dmg_diag.py` → `[DMGDBG]` 줄들 출력. **전체를 붙여달라.** 특히:
   - T16 `Skarmory→Clefable Brave Bird`
   - T24 `Gliscor→Scrafty Earthquake`
   - T29 `Scrafty→Reuniclus Crunch`
   각 줄의 pow/off/def/raw/elem/final/maxhp를 클린룸 기대치와 대조해 *어느 인자가 부푸는지* 확정.

## 기대 대조표 (클린룸 — 이것과 엔진 덤프를 맞댄다)

| 셀 | pow | off(기대) | def(기대) | raw(기대) | elem(기대) | final(기대) | maxhp(기대) |
|---|---|---|---|---|---|---|---|
| T16 Sk→Cl BraveBird | 120 | 196 | 183 | 109 | 1.5 | ~164(롤) | 394 |
| T24 Gl→Sc Earthquake | 100 | 226 | 266 | 73 | 1.5 | ~110 | 334 |
| T29 Sc→Re Crunch(+2) | 80 | 432 | 273 | 108 | 3.0 | ~324 | 424 |

엔진 덤프가 이와 어디서 갈리는지(off↑? def↓? elem이 2배? final이 raw×elem보다 큼=크리? maxhp가
작음?)가 곧 원인이다. 그걸 확정한 뒤 수정 PR(X6)을 쓴다 — 지금은 진단만.
