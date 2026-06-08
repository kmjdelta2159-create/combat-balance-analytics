# 꼬리 PR-F2b — Magic Guard 진입 해저드 면제 (F2 완성)

> F2(해저드 타이밍)가 진입 데미지를 *정확한 시점·T-1 윈도우·1회*로 적용하게 되자, 적용 자체가
> 틀린 한 부류가 드러났다: **Magic Guard**. 이 특성은 모든 간접 데미지(진입 해저드 포함)에
> 면역인데, 진입 해저드 계산이 이를 무시해 Magic Guard 몹에 데미지를 잘못 먹였다. 한 줄로 닫는다.

---

## 0. 무엇을, 왜 (실측 확정)

`run_cellclass.py` 재실행(F2 적용 후)이 새 over-damage 셀 4건을 노출:

| 셀 | log | eng | 정체 |
|---|---|---|---|
| T6 Clefable | 100 | 87 | SR을 먹음(만피여야) |
| T15 Clefable | 100 | 71 | SR+Spikes2를 먹음 |
| T14 Reuniclus | 100 | 71 | SR+Spikes2를 먹음 |
| T27 Reuniclus | 100 | 71 | SR+Spikes2를 먹음 |

`reference_gen5.py` 확인(Read/Grep): **Clefable·Reuniclus 둘 다 `ability: 'Magic Guard'`**
(L138·L142, per-corpus 역설계 확정). 우박 칩 EFFECTS는 **이미** Magic Guard를 면제한다
(L173-175 `condition.not_ability: ['Magic Guard']`). 그러나 진입 해저드 계산
`_hazard_entry_pct`(engine.py L944)는 Magic Guard를 보지 않고 Flying/Levitate(Spikes)만 본다.

→ 진입 해저드도 우박 칩과 동일하게 Magic Guard를 면제하면 4셀이 닫힌다. **데이터는 이미 옳다
(ability=Magic Guard)** — 엔진 한 줄만 추가.

---

## 1. 변경 (engine.py, 단일 함수)

`_hazard_entry_pct(char, hz, game_config)` (L944~). dict 가드 직후, 타입 계산 **전에**
Magic Guard 조기 반환을 추가한다:

```python
def _hazard_entry_pct(char, hz, game_config):
    """hz가 숫자=구버전 평탄. dict{'sr','spikes'}=구조형: SR(0.125×Rock타입곱)+Spikes(층/접지).
    Magic Guard는 모든 간접 데미지 면역 → 진입 해저드 0(우박 칩 면제와 동형, L173-175)."""
    if not isinstance(hz, dict):
        return float(hz or 0)
    if char.get("ability") == "Magic Guard":      # ← 추가: 진입 해저드 면역
        return 0.0
    g = char.get("gimmicks") or {}
    ...
```

- 한 줄(+주석). 기존 SR/Spikes/Flying/Levitate 로직 불변.
- 평탄 숫자 경로(`not isinstance(hz, dict)`)는 그대로 — 임의 게임 정적 해저드는 영향 없음
  (Magic Guard는 gen5 trace 구조형 경로에서만 의미).

---

## 2. 불변 (회귀 0)

- **데이터 불변**: SETS의 ability(Clefable·Reuniclus=Magic Guard)는 이미 옳음 — 손대지 않음.
- 우박 칩·정적 해저드·set_hazard 무브 경로 불변.
- **골든 회귀0 구조적 보장**: 골든(reymedy-leftiez)에는 Magic Guard 몹이 없다 → 이 가드는
  골든 경로에서 절대 발동 안 함 → `run_b4` 불변.

---

## 3. 검증 (앱사이드)

1. **`python run_cellclass.py`** — over-damage 4셀(T6·T15 Clefable·T14·T27 Reuniclus)이
   `[요약]`에서 사라짐. F2(해저드 타이밍) 버킷이 잔여(예: T11 Jirachi)만 남도록 감소.
2. **`python run_f2diag.py`** — [C] 발화에서 Clefable·Reuniclus 진입의 `lost=0`(면제 확인),
   다른 진입은 불변(여전히 정상 적용).
3. **`python run_b4.py`** — 골든 회귀0(불변).

---

## 4. 적용 후 보고
- 수정 라인 + `wc -l`/`tail` 무결성.
- 위 1~3 출력(특히 run_cellclass [요약] — 닫힌 셀과 잔여 버킷).
- 꼬리 갱신: F2+F2b로 닫힌 총 셀, 남은 버킷(NEW 스탯스테이지·F3·잔여).
