# PR-H3 — 해저드 부착 UI (step2_system_definition.py)

## 역할/맥락
너는 Antigravity 에이전트다. 아래 변경을 `modules/step2_system_definition.py`에 **정확히**
적용하라. 이 PR은 "동적 메커니즘 부착" expander에 **정적 해저드** 설정 UI를 추가한다 —
체크박스로 활성화하고, 해저드가 깔린 진영(team)과 진입 데미지 비율(percent)을 받아
`_mech_cfg["hazard"]`에 넣는다. 저장은 기존 `_gc["mechanisms"] = _mech_cfg` 배선(이미 존재)을
그대로 재사용하므로 **저장부는 건드리지 않는다**.

엔진측은 PR-H1로 이미 들어가 있다: `_apply_entry_hazard`가 `game_config['mechanisms']['hazard']`
= `{"team": ..., "percent": ...}`를 읽어 지정 진영으로 교체 진입하는 유닛에게 주 자원 max의
percent만큼 데미지를 준다. team은 엔진에서 `"Ally"`/`"Enemy"`이며 `"both"`(대소문자 무시)면
진영 무관이다. 이 UI는 그 spec을 생성한다.

## 제약
- `modules/step2_system_definition.py` 한 파일만 수정. 아래 FIND/REPLACE 1건만 적용.
- FIND 문자열은 파일에 **정확히 한 번만** 나타난다(Trace expander 블록 끝 ~ 무브 효과 블록 시작
  경계). 다른 곳은 절대 건드리지 마라. 특히 저장부(`_gc["mechanisms"] = _mech_cfg`)는 손대지 마라.
- Trace 블록의 들여쓰기(12칸 = expander 본문 레벨)를 그대로 따른다. 해저드 블록도 동일 레벨.
- 적용 후
  `python -c "import ast; ast.parse(open('modules/step2_system_definition.py',encoding='utf-8').read())"`로
  컴파일을 확인하라.

## 변경 1/1 — Trace expander 다음에 해저드 블록 삽입

Trace 블록 끝(`else: st.warning(...Trace...)`)과 무브 효과 블록 시작 주석 사이에 해저드
체크박스 블록을 끼운다.

```python
# FIND
                else:
                    st.warning("기믹 컬럼이 없어 Trace 기준을 지정할 수 없습니다.")

            # ── 무브 효과 + 전략 정책 (전략 의사결정 모델) ──
```

```python
# REPLACE
                else:
                    st.warning("기믹 컬럼이 없어 Trace 기준을 지정할 수 없습니다.")

            _hz_on = st.checkbox("해저드 (교체 진입 시 진영 진입 데미지 → Stealth Rock류)",
                                 value=False, key="ui_mech_hazard_on")
            if _hz_on:
                _hz_team = st.selectbox(
                    "해저드가 깔린 진영", ["Enemy", "Ally", "both"], key="ui_mech_hazard_team",
                    help="이 진영으로 '교체로 진입하는' 유닛이 매 진입 시 데미지를 받음. both면 양 진영 모두. "
                         "초기 리드(첫 액티브)는 교체가 아니므로 면제(Pokemon 해저드와 동일)."
                )
                _hz_pct = st.number_input(
                    "진입 데미지 비율 (주 자원 max 대비)", min_value=0.0, max_value=1.0,
                    value=0.125, step=0.0625, format="%.4f", key="ui_mech_hazard_pct",
                    help="예: 0.125 = 진입 시 최대 HP의 1/8 데미지. 1.0이면 진입 즉사."
                )
                _mech_cfg["hazard"] = {
                    "team": _hz_team,
                    "percent": float(_hz_pct),
                }

            # ── 무브 효과 + 전략 정책 (전략 의사결정 모델) ──
```

## 검증 (적용 후 수행)
1. `git diff modules/step2_system_definition.py`로 변경이 위 한 지점(해저드 블록 삽입)뿐인지 확인.
   특히 `_gc["mechanisms"] = _mech_cfg` 저장부는 무변경이어야 한다.
2. 컴파일: `python -c "import ast; ast.parse(open('modules/step2_system_definition.py',encoding='utf-8').read())"`.
3. 마커 확인: `_mech_cfg["hazard"]` 1회, `ui_mech_hazard_on`/`ui_mech_hazard_team`/
   `ui_mech_hazard_pct` 각 1회.
4. 들여쓰기: 해저드 블록의 `_hz_on = st.checkbox(...)`가 Trace의 `_tr_on = st.checkbox(...)`와
   같은 열(12칸)에서 시작하는지 확인.

## 회귀/한계 메모
- 체크박스 off(기본)면 `_mech_cfg`에 hazard 키가 안 들어가므로 → `game_config['mechanisms']`에
  hazard 없음 → 엔진 `_apply_entry_hazard` no-op. 회귀 0.
- 저장 경로는 기존 `if _mech_cfg: _gc["mechanisms"] = _mech_cfg` 재사용(별도 배선 불필요).
- H1 한계 그대로: 상시 진입세(무브 설치/청소 다이내믹은 후속 H2 — 필드-상태 substrate 필요),
  진입 즉사 정리는 다음 _resolve_faint 사이클.
