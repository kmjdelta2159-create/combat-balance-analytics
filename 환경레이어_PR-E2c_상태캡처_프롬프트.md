# PR-E′2c — 상태 캡처 보강 (showdown_trace status 이벤트 + build_snapshots 추적)

## 목적
PR-E′2b의 **burn 틱이 안 터지는 원인**을 닫는다. 진단 결과 디스패처는 정상인데 **스냅샷의
status가 거의 다 None**이라 status 공급이 빈 값을 전달했다. 근본 원인: `build_snapshots`는
status를 *switch 이벤트에서만* 잡고, Scald 화상 같은 `-status`(중간 부여)는 놓친다. 게다가
showdown_trace의 `-status`/`-curestatus`는 내부 `status_of`만 갱신하고 **이벤트로 안 남긴다**.

이 PR은 (a) showdown_trace가 `-status`/`-curestatus`에 status 이벤트를 emit하고 (b)
build_snapshots가 이를 추적해 턴별 status를 채운다. 엔진 무변경·순수 데이터 파이프라인.
burn(Rotom-Wash·Ferrothorn)을 즉시 unblock하고, 맹독(tox)·마비(par) 캡처도 셋업한다.

## 검증 제약
순수 파이프라인(showdown_trace·fullbattle_diff)이라 샌드박스/클린룸 완결 검증됨(아래). 엔진 무관.

## 대상
`modules/showdown_trace.py`(2건) + `modules/fullbattle_diff.py`(1건). 엔진·reference 무변경.

## 설계 근거 (클린룸 검증됨)
- 골든 로그에 `-status` 줄 다수: Rotom-Wash brn·Ferrothorn brn·Hippowdon tox·Gengen tox·
  Latios/Stoutland par + Rotom-Wash slp→`-curestatus`. 전부 switch 아닌 중간 부여라 현재 누락.
- 수정 후 클린룸: **Rotom-Wash status='brn'이 T8부터** 잡힘(이전 None) → resync가 T9 round-start에
  p['status']='brn' 공급 → 디스패처 burn 틱 −33 발동. Ferrothorn brn(T14)·Hippowdon tox(T6)도 캡처.
  등장 status 값 {tox, par, brn}.
- status 이벤트는 새 action 타입이라 기존 소비자(build_action_queue·build_trace_actions: move/
  switch/env/faint만 처리)는 무시 → 회귀0. divergence status 비교는 더 정확해질 뿐.

---

## FIND/REPLACE — modules/showdown_trace.py

### S1 — `-status`에 status 이벤트 emit
**FIND**:
```python
        elif k == '-status' and len(p) >= 4:
            _, who = _slot(p[2])
            status_of[who] = p[3]
            if cur_move is not None:
                cur_move["flags"].append("status:" + p[3])
```
**REPLACE**:
```python
        elif k == '-status' and len(p) >= 4:
            _, who = _slot(p[2])
            status_of[who] = p[3]
            events.append({"turn": turn, "action": "status", "who": who, "status": p[3]})
            if cur_move is not None:
                cur_move["flags"].append("status:" + p[3])
```

### S2 — `-curestatus`에 status 해제 이벤트 emit
**FIND**:
```python
        elif k == '-curestatus' and len(p) >= 4:
            _, who = _slot(p[2])
            status_of.pop(who, None)
```
**REPLACE**:
```python
        elif k == '-curestatus' and len(p) >= 4:
            _, who = _slot(p[2])
            status_of.pop(who, None)
            events.append({"turn": turn, "action": "status", "who": who, "status": None})
```

---

## FIND/REPLACE — modules/fullbattle_diff.py

### D1 — build_snapshots: status 이벤트 추적 + 기절 시 상태 소멸
**FIND**:
```python
        elif a == "move":
            for h in e.get("hits", []):
                if h.get("cur") is not None:
                    hp[h["who"]] = h["cur"]
            for w in e.get("faints", []):
                hp[w] = 0
                fnt.add(w)
        elif a == "env":
            if e.get("cur") is not None:
                hp[e["who"]] = e["cur"]
        elif a == "faint":
            hp[e["who"]] = 0
            fnt.add(e["who"])
```
**REPLACE**:
```python
        elif a == "move":
            for h in e.get("hits", []):
                if h.get("cur") is not None:
                    hp[h["who"]] = h["cur"]
            for w in e.get("faints", []):
                hp[w] = 0
                fnt.add(w)
                st.pop(w, None)
        elif a == "env":
            if e.get("cur") is not None:
                hp[e["who"]] = e["cur"]
        elif a == "faint":
            hp[e["who"]] = 0
            fnt.add(e["who"])
            st.pop(e["who"], None)
        elif a == "status":
            if e.get("status"):
                st[e["who"]] = e["status"]      # -status: 비휘발 상태 부여(이후 턴 carry)
            else:
                st.pop(e["who"], None)           # -curestatus: 해제
```

---

## 검증 (적용 후)
1. **클린룸(이미 통과)** — 수정 후 Rotom-Wash status='brn' T8~(이전 None), Ferrothorn brn(T14)·
   Hippowdon tox(T6) 캡처. 기존 소비자 무시(회귀0).
2. **앱사이드 — 풀배틀**: 루트에서 `python run_b4.py`.
   - 기대: **T9 Rotom-Wash burn −33이 닫힘**(이전 engΔ 0 → −33). E′2b의 burn 효과가 이제 status를
     받아 발동. (T8은 화상 부여+틱이 같은 턴이라 resync 타이밍상 한 턴 놓칠 수 있음 — 미세.)
   - **T15 Ferrothorn**도 burn −44(352/8) 분이 반영(다른 데미지와 합산).
   - **T7 Hippowdon은 여전히 ★** — 맹독(tox)은 캡처되나 *누진 틱(n/16)* 효과가 아직 없어서다(다음
     PR-E′2d). status='tox'는 들어오지만 매칭 효과 없어 no-op(정상).
   - 엔진 마지막 캡처 턴 = 27 유지. 회귀 없음.
   - 출력 붙여주면 함께 읽고 **E′2d**(맹독 누진)로 진행.
3. **회귀0**: status 이벤트는 새 action이라 build_action_queue/build_trace_actions가 무시. 엔진·
   reference 무변경. divergence status 비교만 더 정확해짐.

## 적용 메모
- 이 PR로 E′2b의 burn 효과가 비로소 데이터를 받는다(EFFECTS['brn']는 E′2b에 이미 있음). 즉
  E′2b+E′2c가 합쳐져 화상 틱이 닫힌다.
- **다음(E′2d) — 맹독 누진**: status='tox'는 이제 캡처되나 데미지가 n/16 누진(1/16→2/16…).
  디스패처에 progressive damage_frac + 턴별 stage 공급(트레이스 도출 또는 카운터)이 필요.
  Hippowdon T6 −26(1/16)·T7 −52(2/16) 닫힘 목표.
- par(마비)는 데미지 없음(행동/속도 영향) — 데미지 충실도엔 무관, 별도.
