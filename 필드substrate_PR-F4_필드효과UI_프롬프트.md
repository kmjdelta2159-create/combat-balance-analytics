# PR-F4 — 필드 효과 UI: 무브 해저드 설치/청소 (step2_system_definition.py)

## 역할/맥락
너는 Antigravity 에이전트다. 아래 변경을 `modules/step2_system_definition.py`에 **정확히**
적용하라. 이 PR은 무브 효과 폼에 **해저드 설치/청소 무브** 설정 UI를 추가한다 — 무브를 골라
"이 무브를 쓰면 지정 진영에 해저드를 깐다/청소한다"를 `_move_effects_cfg`에 `kind` 든 spec으로
넣는다. 엔진측은 PR-F2로 이미 들어가 있다(`_act_move_effect`가 `kind:"set_hazard"/"clear_hazard"`
를 만나면 `ctx["field_state"]["hazard"]`에 설치/청소).

저장은 기존 `_move_effects_cfg` → `_gc["move_effects"]` 배선을 그대로 재사용한다(별도 배선 불필요).

## 제약
- `modules/step2_system_definition.py` 한 파일만. 아래 FIND/REPLACE 1건만 적용.
- FIND는 파일에 정확히 1회. 기존 boost 효과 블록(`_me_on`)과 `_move_effects_cfg` 저장부는
  건드리지 마라 — 해저드 설치는 **별도 체크박스 + 별도 무브 선택**으로 격리(boost와 충돌 방지).
- 들여쓰기: 무브효과 블록(`_me_on = st.checkbox`)과 같은 12칸 레벨.
- 적용 후 `python -c "import ast; ast.parse(open('modules/step2_system_definition.py',encoding='utf-8').read())"`.

## 변경 1/1 — 무브효과 블록과 전략정책 셀렉트 사이에 해저드 설치 UI 삽입

`_me_on` 블록의 else(경고) 끝과 `_move_policy_sel` 사이에 해저드 설치/청소 블록을 끼운다.

```python
# FIND
                else:
                    st.warning("추출된 무브 또는 기본 스탯이 없어 무브 효과를 지정할 수 없습니다.")
            _move_policy_sel = st.selectbox(
```

```python
# REPLACE
                else:
                    st.warning("추출된 무브 또는 기본 스탯이 없어 무브 효과를 지정할 수 없습니다.")

            _hzm_on = st.checkbox("해저드 설치/청소 무브 (무브로 진영에 진입 데미지 설치 → 동적 해저드)",
                                  value=False, key="ui_mech_hazardmove_on")
            if _hzm_on:
                if _move_names:
                    _hzm_move = st.selectbox("해저드 무브 선택", _move_names, key="ui_mech_hzm_move",
                                             help="이 무브를 사용하면 아래 설정대로 해저드를 설치/청소함.")
                    _hzm_kind = st.selectbox("동작", ["set_hazard (설치)", "clear_hazard (청소)"],
                                             key="ui_mech_hzm_kind")
                    _hzm_team = st.selectbox("대상 진영", ["Enemy", "Ally", "both"],
                                             key="ui_mech_hzm_team",
                                             help="이 진영으로 교체 진입하는 유닛이 데미지를 받음(설치). both면 양 진영.")
                    _hzm_kind_val = "set_hazard" if _hzm_kind.startswith("set") else "clear_hazard"
                    _hzm_spec = {"kind": _hzm_kind_val, "team": _hzm_team}
                    if _hzm_kind_val == "set_hazard":
                        _hzm_pct = st.number_input(
                            "설치 데미지 비율 (주 자원 max 대비)", min_value=0.0, max_value=1.0,
                            value=0.125, step=0.0625, format="%.4f", key="ui_mech_hzm_pct",
                            help="예: 0.125 = 진입 시 최대 HP의 1/8. 정적 해저드와 겹치면 큰 값 적용."
                        )
                        _hzm_spec["percent"] = float(_hzm_pct)
                    _move_effects_cfg.setdefault(_hzm_move, []).append(_hzm_spec)
                else:
                    st.warning("추출된 무브가 없어 해저드 무브를 지정할 수 없습니다.")
            _move_policy_sel = st.selectbox(
```

## 검증 (적용 후 수행)
1. `git diff modules/step2_system_definition.py`로 변경이 위 한 지점뿐인지 확인. 기존 boost
   블록·`_gc["move_effects"]` 저장부 무변경.
2. 컴파일: `python -c "import ast; ast.parse(open('modules/step2_system_definition.py',encoding='utf-8').read())"`.
3. 마커: `ui_mech_hazardmove_on` 1회, `ui_mech_hzm_move`/`ui_mech_hzm_kind`/`ui_mech_hzm_team`
   각 1회, `_move_effects_cfg.setdefault(_hzm_move, []).append(_hzm_spec)` 1회.
4. 들여쓰기: `_hzm_on = st.checkbox(...)`가 `_me_on = st.checkbox(...)`와 같은 12칸.
5. 동작(폼 시뮬): 체크 on + set_hazard + Enemy + 0.25 → `_move_effects_cfg[무브]`에
   `{"kind":"set_hazard","team":"Enemy","percent":0.25}` 포함. clear_hazard 선택 시 percent 키
   없음. 체크 off → `_move_effects_cfg`에 해저드 spec 미추가(회귀 0).

## 회귀/한계 메모
- 해저드 설치는 별도 무브로 격리(`setdefault().append()`) — 같은 무브에 boost+해저드를 둘 수도
  있으나 기본 UI는 분리. boost 블록 무변경 → 회귀 0.
- 저장은 기존 `_gc["move_effects"] = _move_effects_cfg` 재사용(이미 존재). 엔진 F2가 kind를 읽음.
- 동적 해저드는 단일 전투 범위(F1: 전투마다 새 field_state). 정적(H1/H3)과 겹치면 max 합성(F2).
- 무브가 실제로 선택돼야 설치가 발화한다 — setup_first 정책(전략 정책 셀렉트)과 함께 쓰면
  진입 유닛이 효과 무브를 먼저 고른다.
