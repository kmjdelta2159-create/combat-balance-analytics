# 교차검증 PR-X1 — run_xval 코퍼스 인자화 (패스1: 데이터-니즈 + 퍼센트HP 하니스)

> 목표: 아직 맞춰본 적 없는 held-out gen5 싱글(`Gen5OU-2026-newatmons-bantyranitar.html`)에
> *일반 스키마 그대로*를 던져 과적합을 잰다(로드맵 2-가드). 이 PR은 **패스1** — held-out 전투를
> 돌리는 하니스를 세우고, 그 전투가 요구하는 *데이터 결측*을 리포트한다. 실제 divergence 3분해
> (스키마 평결)는 데이터를 채운 패스2에서. (설계: `교차검증_설계안.md`.)
>
> **불변(절대 수정 금지)**: 일반 스키마 — `reference_gen5.EFFECTS`·`CONTACT_MOVES`·
> `ABILITY_TYPE_IMMUNITY`·`TYPE`·디스패처(`engine._act_effect_dispatch`/`_eff_*`)·`SETS`·`BASE`·
> `MOVES`. 이 PR은 *하니스 배관*만 더한다. 골든(절대-HP) 경로는 한 글자도 바뀌면 안 된다(회귀0).

## 배경 — 왜 패스1이 데이터-니즈인가

`reference_gen5`는 **일반 스키마**(메커니즘 언어)와 **이 한 판에 역설계된 데이터**(`SETS`·`BASE`·
`MOVES`)로 갈린다. held-out 전투는 종·무브가 다르므로 데이터층이 비어 있다. 실측:

- `BASE`(종족값) 결측 종 **8/10**: Abomasnow·Clefable·Gliscor·Latias·Magnezone·Reuniclus·
  Scrafty·Skarmory. (Garchomp·Jirachi만 보유. Jellicent는 teampreview에만 있고 미출전 →
  `nick2species` 부재라 집계 밖.)
- `MOVES` 결측 무브 **19/22**: Sunny Day·Magic Coat·Knock Off·U-turn·Spikes·Swords Dance·
  Outrage·Ice Shard·Roost·Calm Mind·Whirlwind·Brave Bird·Ice Beam·Soft-Boiled·Seismic Toss·
  Bulk Up·Rest·Amnesia·Crunch.
- 또 이 전투는 **HP Percentage Mod**(퍼센트 HP, `max=100`) — 골든(절대 HP)과 표기가 다르다.
  래더 기본값이므로 "임의 싱글" 일반화에 반드시 필요한 하니스 기능.

즉 종족값/무브 결측으로 엔진 풀런은 아직 불가다. 패스1은 *무엇이 비었는지를 정확히 출력*하고
(=패스2 데이터 쇼핑리스트), 데이터가 채워지면 같은 스크립트가 그대로 돌도록 퍼센트HP 배관까지
세워 둔다.

## 변경 1 — `run_xval.py` 신설 (프로젝트 루트, 앱사이드)

`run_b4.py`를 본떠 만들되 **코퍼스 인자화 + 데이터-니즈 리포트 + 퍼센트HP 게이트**. 골자:

```python
"""교차검증 run — held-out gen5 리플레이에 일반 스키마를 던져 과적합을 잰다.
패스1: 데이터-니즈(BASE/MOVES/SETS 결측) 리포트 + (데이터 충분 시) 퍼센트HP-aware 풀런.
프로젝트 루트에서: python run_xval.py [코퍼스.html]   (기본=newatmons-bantyranitar)"""
import os, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
DEFAULT = os.path.join(HERE, "Gen5OU-2026-newatmons-bantyranitar.html")

def data_needs(trace, ref):
    species = sorted(set(trace["nick2species"].values()))
    moves = sorted({e["move"] for e in trace["events"]
                    if e.get("action") == "move" and e.get("move")})
    miss_base = [s for s in species if s not in ref.BASE]
    miss_set  = [s for s in species if s not in ref.SETS]
    miss_move = [m for m in moves if m not in ref.MOVES]
    return species, miss_base, miss_set, miss_move

def main():
    from modules.showdown_trace import parse_replay
    import modules.reference_gen5 as r5
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    with open(path, encoding="utf-8") as f:
        trace = parse_replay(f.read())
    species, miss_base, miss_set, miss_move = data_needs(trace, r5)
    pct = any("Percentage" in str(r) for r in trace.get("meta", {}).get("rules", []))
    print(f"=== 교차검증 데이터-니즈 ({os.path.basename(path)}) ===")
    print(f"HP 표기: {'퍼센트(max=100)' if pct else '절대'}")
    print(f"등장 종 {len(species)}: {species}")
    print(f"BASE(종족값) 결측 {len(miss_base)}: {miss_base}")
    print(f"SETS(특성/도구/EV) 결측 {len(miss_set)}: {miss_set}")
    print(f"MOVES(위력/타입) 결측 {len(miss_move)}: {miss_move}")
    if miss_base:
        print("\n→ 엔진 풀런 보류: 종족값 결측. 패스2에서 BASE/MOVES/SETS를 채운 뒤 재실행.")
        print("  (스키마는 손대지 않는다 — 데이터만 lazy 추가, 로드맵 §C.)")
        return
    # --- 데이터 충분: 퍼센트HP-aware 풀런 (패스2에서 도달) ---
    from modules.fullbattle_run import run_and_diff, format_report
    res = run_and_diff(trace, r5, hp_tol=10, resync=True,
                       hp_mode=("percent" if pct else "absolute"))
    print(format_report(res))

if __name__ == "__main__":
    try: main()
    except Exception:
        print("=== run_xval 에러 (트레이스백 전체를 붙여주세요) ==="); traceback.print_exc()
        sys.exit(1)
```

`trace["meta"]`에 `rules`가 없으면 `parse_replay`가 `meta`에 룰 목록을 담도록 한 줄 보강(아래
변경 3). 못 담으면 `pct`는 `_hp` 결과로도 판정 가능(모든 max==100) — 둘 중 되는 쪽.

## 변경 2 — 퍼센트HP 게이트 (`fullbattle_run`·`fullbattle_diff`, 플래그로 격리)

골든(절대 HP) 경로는 불변. 퍼센트는 **새 인자 `hp_mode='absolute'`(기본)**로만 활성:

- `run_and_diff(trace, ref, ..., hp_mode='absolute')` 시그니처에 `hp_mode` 추가.
- 비교는 **퍼센트 공간**에서: `hp_mode=='percent'`면
  - `engine_snapshot`이 hp를 `round(get_current(p) / maxhp * 100)`로 환산해 스냅샷(로그도 0–100이라
    같은 공간). `maxhp`는 participant에서 읽는다(`p["maxhp"]` 또는 resources.HP.max).
  - `_make_resync`가 로그 퍼센트를 절대로 되돌려 주입: `res["current"] = round(pct/100 * maxhp)`
    (엔진 내부 HP는 절대 유지, 비교만 퍼센트).
  - `divergence`의 hp 비교 임계(`hp_tol`)는 퍼센트 포인트로 해석(예: tol=10 → ±10%p).
- `hp_mode=='absolute'`면 **현행 코드 경로 그대로**(분기 없을 때와 바이트 동일하게). 즉 percent
  분기는 `if hp_mode=='percent':` 안에서만.

> 주의: 이 배관은 메커니즘이 아니다(스키마 무관). 회귀0 게이트(아래)가 골든 절대-HP 경로
> 불변을 강제한다.

## 변경 3 — `parse_replay` 룰 노출 (작게)

`parse_replay`가 `|rule|...` 라인을 모아 `trace["meta"]["rules"]`(문자열 리스트)로 담도록 한 줄.
이미 `meta`가 있으면 키만 추가. 없으면 `meta={}` 생성. (퍼센트 모드 판정용. 엔진 무관.)

## 검증 (적용 후 반드시, 순서대로)

1. **클린룸 데이터-니즈(엔진 무관, 지금 검증 가능)**: `showdown_trace`+`reference_gen5`만으로
   `data_needs(trace, r5)`를 돌려 **BASE 결측 8·MOVES 결측 19·SETS 결측 8**가 위 목록과
   일치하는지. (Garchomp·Jirachi만 BASE 보유. 등장 종 10 = nick2species 기준, 미출전 Jellicent 제외.)
2. **회귀0(골든 절대-HP 불변)**: `python run_b4.py`(골든) 출력이 PR-X1 적용 전과 **완전 동일**.
   퍼센트 분기가 절대 경로를 건드리지 않았음을 증명.
3. **run_xval 패스1 출력**: `python run_xval.py` → HP 표기 `퍼센트`, 등장 종/결측 목록 출력,
   "엔진 풀런 보류: 종족값 결측" 메시지로 깔끔히 종료(크래시 없음).
4. **스키마 불변 확인**: `reference_gen5.EFFECTS`/`CONTACT_MOVES`/`TYPE`·디스패처 diff 없음(Read).

## 다음(패스2, 이 PR 아님)

결측 데이터(종족값 9·무브 19·세트 9)를 lazy 추가하는 **데이터 PR**(reference 연구) → run_xval
풀런 → divergence를 (ㄱ)데이터결측 / (ㄴ)스키마 표현불가 신규메커니즘 / (ㄷ)롤 노이즈로 3분해.
패스1에서 이미 보이는 (ㄴ) 후보: Hail 날씨칩(우리 `EFFECTS`는 sand만)·Knock Off 도구제거·frz
동결 게이트·Rest/slp·Spikes 다층. 이들이 *스키마 한 줄*로 표현되면 합격, *언어 확장*을 요구하면
과적합 신호. 그 평결이 1차목표의 천장이다.
