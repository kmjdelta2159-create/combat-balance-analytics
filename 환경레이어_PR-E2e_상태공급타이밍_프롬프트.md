# PR-E′2e — 상태 공급 타이밍 수정 (resync status를 log[T]에서 공급)

## 목적
맹독/화상 틱이 **1턴 늦게** 적용되는 버그를 닫는다. 진단(run_tedge_diag)으로 확정:
- T7 Hippowdon: item='Leftovers'·status='tox'·tox_stage=1·actorHP=partHippHP=324. 즉 턴엔드는
  돌았고 Leftovers(+26)도 발동했으나 **맹독이 stage 1(−26)** — 로그는 stage 2(−52). Leftovers
  +26과 맹독 −26이 상쇄돼 324로 보였다(상대 교체는 무관, 미끼였음).

근본 원인: resync가 status를 **log[T−1]**(직전 턴 끝)에서 공급한다. 맹독은 T6 *중에* 걸려
log[5]엔 없고 log[6]에 있다. 그래서 엔진은 T6에 맹독을 못 봐 미틱하고(stage 0 유지), T7에야
stage 1로 시작 → 로그보다 한 턴씩 밀린다. 화상도 동일(T8 부여 → 엔진은 T9부터).

수정: **status를 log[T]**(현재 턴 끝-상태)에서 공급한다. 비휘발 상태는 부여된 그 턴의 턴엔드에
틱하므로 log[T]가 정확하다. HP·on_field는 진입 상태가 맞으니 **log[T−1] 유지**.

## 검증 제약
순수 함수(fullbattle_run resync 훅)라 클린룸 검증됨. 엔진 무변경. 앵커는 Read 확인(91~102).

## 대상
`modules/fullbattle_run.py`(1건: _make_resync 훅 status 소스). 엔진·reference 무변경.

## 설계 근거 (클린룸 검증됨)
관측 status 타임라인 + on-field로 맹독/화상 stage를 두 방식으로 시뮬:
- **현행(log[T−1])**: Hippowdon tox T7 s1·T8 s2 / Rotom-Wash brn T9·T10. → 로그(T6 s1·T7 s2 /
  T8·T9)보다 1턴 밀림.
- **수정(log[T])**: Hippowdon tox **T6 s1·T7 s2** / Rotom-Wash brn **T9**. → T6/T7 맹독이 로그와
  일치. burn T9 유지(회귀0).
- 남는 엣지(이번 범위 밖): 교체로 *그 턴 진입/이탈*한 유닛의 틱(T8 Rotom-W 진입 burn·T13 재진입
  맹독·T16 Latios 모래). 엔진이 턴엔드를 라운드시작 on-field 유닛에만 돌리는 더 깊은 구조 문제
  (= switch-in-turn 잔류). 별도 후속.

## FIND/REPLACE — modules/fullbattle_run.py

### F1 — resync 훅: status를 log[T]에서, HP/on_field는 log[T-1] 유지
**FIND**:
```python
    def hook(turn, participants):
        prev = log_snaps.get(turn - 1)
        pof = onfield_tl.get(turn - 1)
        if prev is None:
            return
        for p in participants:
            pid = p.get("id")
            st = prev.get(pid)
            if st and st.get("hp") is not None:
                res = p.setdefault("resources", {}).setdefault("HP", {"current": 0, "max": 0})
                res["current"] = st["hp"]
            if st is not None:
                p["status"] = st.get("status")   # 상태 공급(burn 등 디스패처 status 키용, PR-E′2b)
```
**REPLACE**:
```python
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
                res["current"] = st["hp"]
            cst = (cur or {}).get(pid)                            # 상태는 log[T](부여 턴에 틱)
            p["status"] = cst.get("status") if cst is not None else None
```

## 검증 (적용 후)
1. **클린룸(이미 통과)** — log[T] 공급 시 Hippowdon 맹독 T6 s1·T7 s2, Rotom-Wash burn T9 유지.
2. **앱사이드 — 풀배틀**: 루트에서 `python run_b4.py`.
   - 기대(닫힘): **T7 Hippowdon −26/−26** (맹독 stage2 −52 + Leftovers +26 = −26 = 로그). 이전 −26/0.
   - burn T9 Rotom-Wash −33 유지(회귀 없음). 엔진 마지막 캡처 턴 = 27 유지.
   - **남는 ★**(교체-진입-턴): T8 Rotom-Wash(진입 burn 미틱)·T13(재진입 맹독)·T16 Latios(모래).
     이건 별도 구조 엣지로 다음에.
   - 출력 붙여주면 함께 읽고 switch-in-turn 잔류 수정 또는 다음 버킷(Psyshock/Trick)으로.
3. **회귀0**: 다른 게임은 log_snaps/onfield 미사용 시 resync 자체가 안 붙음. status 공급만
   log[T]로 바뀌고 HP·on_field·tox 리셋 로직은 동일.

## 적용 메모
- 이 수정으로 *연속 on-field* 유닛의 맹독/화상이 부여 턴부터 정확히 틱한다(주 사례 닫힘).
- **남은 switch-in-turn 잔류**: 엔진이 턴엔드(잔류 데미지)를 *라운드 시작 on-field(행동 유닛)*에만
  돌려, 교체로 그 턴 진입한 유닛은 그 턴 틱을 못 받는다. 로그는 *그 턴 끝 on-field* 유닛에 잔류를
  준다. 정확한 수정은 turn_manager가 라운드 끝에 현재 on-field 유닛 전체에 턴엔드를 돌리는 것(또는
  진입 유닛에 진입-틱). 영향: 모래·맹독·회복의 교체-진입 턴. 별도 PR로 평가.
