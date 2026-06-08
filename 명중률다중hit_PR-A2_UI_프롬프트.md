# PR-A2 — 명중률·다중 hit UI (move_props JSON 편집기)

## 목적
step2 메커니즘 expander에 `move_props` JSON 편집기를 추가한다. 엔진(PR-A1)은 이미
`mechanisms.move_props[무브명].{accuracy, hits}`를 정적으로 읽어 per-move 명중 판정과
균등 다중 hit을 처리한다. UI에 편집 자리만 없어 현재는 라이브 스크립트/직접 config로만
값을 넣을 수 있다. 이 PR로 `weather_defs`/`status_gates`와 **동형 패턴**의 JSON 편집기를
붙여 ① 갈래(명중률·다중hit)의 UI 경로를 닫는다.

## 대상 파일
`modules/step2_system_definition.py` — **1 FIND/REPLACE**.
엔진(`engine.py`)·stochasticity·turn_manager·resource는 **무변경**(A1에서 이미 적용·검증).

## 엔진이 읽는 스키마(불변 — UI는 이 형태를 산출만)
정적 `game_config["mechanisms"]["move_props"]` = `{무브명: {...}}`, 무브별 키:
- `accuracy` (선택) — 명중 확률. 0~1. 1보다 크면 %로 간주해 100으로 나눔. 미설정/빈값이면
  현행 명중 모듈(`roll_hit`)로 폴백(회귀 0). 엔진 `_act_damage_calc` L629~ 참조.
- `hits` (선택) — 다중 타격 횟수. 정수=고정, `[lo,hi]` 또는 `"lo-hi"`=균등 랜덤(시드
  `roll_range`), 미설정=1(단타·회귀 0). 엔진 `_resolve_n_hits` L731~ 참조.

저장은 기존 `weather_defs`/`status_gates`와 동일하게 `_mech_cfg`(=`_gc["mechanisms"]`)
재사용. 새 저장 경로·새 의존성 없음.

---

## FIND/REPLACE

### FIND
```python
                if isinstance(_sg_parsed, dict) and _sg_parsed:
                    _mech_cfg["status_gates"] = _sg_parsed

            # ── 무브 효과 + 전략 정책 (전략 의사결정 모델) ──
```

### REPLACE
```python
                if isinstance(_sg_parsed, dict) and _sg_parsed:
                    _mech_cfg["status_gates"] = _sg_parsed

            _mp_on = st.checkbox("무브 속성 정의 (move_props) — per-move 명중률·다중 hit",
                                 value=False, key="ui_mech_moveprops_on")
            if _mp_on:
                _mp_json = st.text_area(
                    "무브 속성 JSON (키 = 무브 이름, 추출된 무브의 이름과 일치)",
                    value='{\n  "Thunder": {"accuracy": 0.7},\n  "Fury Swipes": {"hits": [2, 5]},\n  "Double Kick": {"hits": 2, "accuracy": 1.0}\n}',
                    height=170, key="ui_mech_moveprops_json",
                    help="accuracy=명중 확률(0~1, 1보다 크면 %로 간주해 100으로 나눔; 미설정이면 현행 명중 모듈 사용). "
                         "hits=다중 타격 횟수(정수=고정, [lo,hi] 또는 \"lo-hi\"=균등 랜덤, 미설정=1). 엔진은 정적으로 읽음(병렬 안전)."
                )
                try:
                    _mp_parsed = json.loads(_mp_json) if _mp_json.strip() else {}
                except (ValueError, TypeError):
                    _mp_parsed = None
                    st.warning("무브 속성 JSON 파싱 실패 — 형식을 확인하세요.")
                if isinstance(_mp_parsed, dict) and _mp_parsed:
                    _mech_cfg["move_props"] = _mp_parsed

            # ── 무브 효과 + 전략 정책 (전략 의사결정 모델) ──
```

---

## 앵커 근거
- FIND 3행은 `status_gates` 저장부 마지막 두 줄 + 직후의 `무브 효과` 섹션 주석.
  `_mech_cfg["status_gates"] = _sg_parsed`(count==1), `# ── 무브 효과 + 전략 정책
  (전략 의사결정 모델) ──`(count==1)로 유일.
- 새 `move_props` 블록을 `status_gates` 저장 직후·`무브 효과` 주석 직전에 삽입한다.
  들여쓰기 12칸(=expander 내부, `weather_defs`/`status_gates`와 동일 레벨).
- 신규 위젯 키 `ui_mech_moveprops_on`/`ui_mech_moveprops_json` — 기존 파일 충돌 0.
- `json`은 파일 상단에서 이미 import됨(`weather_defs`/`status_gates`가 `json.loads` 사용).

## 회귀 0 보장
- `move_props` 미설정/빈 dict/파싱 실패면 `_mech_cfg["move_props"]`를 쓰지 않음 →
  엔진은 `.get("move_props") or {}` → 무브별 `.get(name) or {}` → accuracy/hits 모두
  미설정 → 명중은 `roll_hit` 폴백, hits는 1(단타). 기존 전투와 비트 동일.
- 다른 메커니즘 편집기(hazard/weather_defs/status_gates)·무브효과 폼·저장부 무변경.

## 검증 의무(적용자)
1. **앵커 유일성**: 적용 전 `grep -c '_mech_cfg\["status_gates"\] = _sg_parsed'
   modules/step2_system_definition.py` == 1, `grep -c '무브 효과 + 전략 정책 (전략 의사결정 모델)'`
   == 1 확인.
2. **컴파일**: 적용 후 `python -c "import ast; ast.parse(open('modules/step2_system_definition.py',encoding='utf-8').read())"`.
   (bash 마운트 truncation 의심 시 Read/Grep으로 삽입 블록이 완결됐는지 재확인 — 신규
   `_mech_cfg["move_props"] = _mp_parsed` 라인 존재·들여쓰기 12칸.)
3. **바이트 재확인**: `grep -n 'ui_mech_moveprops_json\|move_props' modules/step2_system_definition.py`
   로 편집기 블록 4개 라인(체크박스·text_area·키·저장) 노출 확인.
4. **라이브(앱)**: step2에서 "무브 속성 정의 (move_props)" 체크 → 기본 JSON 그대로 저장 →
   전투 실행 시 기대 로그:
   - 명중 무브(예 `Thunder` acc 0.7): 빗나가면 `❌ 공격이 빗나갔습니다!`(약 30% 빈도).
   - 다중 무브(예 `Fury Swipes` hits [2,5]): 명중 시 `다중 명중 N회`(N∈2..5, 균등) +
     총 데미지가 per-hit×N로 보고.
   - `move_props` 미설정 무브: 로그·데미지 현행과 동일(회귀 0).
   깨진/빈 JSON 입력 시 `무브 속성 JSON 파싱 실패` 경고 + 저장 안 됨(엔진 회귀 0).

## 클린룸 검증 결과(작성 시 수행)
- REPLACE 조각을 함수 본문으로 dedent해 `ast.parse` → OK.
- 기본 JSON `json.loads` → `{Thunder:{accuracy:0.7}, Fury Swipes:{hits:[2,5]},
  Double Kick:{hits:2, accuracy:1.0}}` 파싱, 엔진 키 형태(accuracy:number, hits:int|list) 호환.
- hits 해석 모사: Thunder→1(단타·명중만), Fury Swipes→[2,5] 균등, Double Kick→고정2. 일치.
