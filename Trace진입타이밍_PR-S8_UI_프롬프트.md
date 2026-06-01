# PR-S8 (Trace 부착 UI) Antigravity 프롬프트

## ⚠️ 적용 순서
PR-S6·S7 적용 후. S8은 step2에 Trace를 켜는 입력만 추가한다 — 엔진 쪽 `_apply_switch_in_effects`
(S6)와 진입 즉시 타이밍(S7)이 이미 있어야 효과가 난다.

## 목적
`modules/step2_system_definition.py`의 동적 메커니즘 부착 expander에 **Trace 부착 UI**를 추가한다 —
Protean·Leftovers와 같은 양식(체크박스 + 기준 기믹 컬럼 + 매치값 + 복사할 타입 컬럼)으로
`game_config['mechanisms']['trace']` spec을 만든다. 저장은 기존 `_gc["mechanisms"] = _mech_cfg`
배선을 그대로 쓰므로 **저장 핸들러 변경 불필요** — 이 PR은 find/replace 1건이다.

## 제약
- `modules/step2_system_definition.py` 한 파일만, find/replace 1건만. 엔진·turn_manager 손대지 말 것.
- 위젯 key는 신규 고유값(`ui_mech_trace_on`, `ui_mech_trace_col`, `ui_mech_trace_val`,
  `ui_mech_trace_val_txt`, `ui_mech_trace_type_col`) 그대로.
- 생성하는 spec 키는 엔진이 읽는 것과 정확히 일치할 것: `gimmick_col`, `match_value`, `type_col`.

## 적용 — Protean 블록 뒤에 Trace 부착 UI 추가

찾기:

```python
                    _mech_cfg["protean"] = {
                        "gimmick_col": _pt_col,
                        "match_value": str(_pt_match),
                    }
                else:
                    st.warning("기믹 컬럼이 없어 Protean 기준을 지정할 수 없습니다.")
```

교체:

```python
                    _mech_cfg["protean"] = {
                        "gimmick_col": _pt_col,
                        "match_value": str(_pt_match),
                    }
                else:
                    st.warning("기믹 컬럼이 없어 Protean 기준을 지정할 수 없습니다.")

            _tr_on = st.checkbox("Trace (교체 진입 시 상대 타입 복사 → STAB)", value=False, key="ui_mech_trace_on")
            if _tr_on:
                if gimmicks:
                    _tr_col = st.selectbox(
                        "Trace 기준 기믹 컬럼", list(gimmicks), key="ui_mech_trace_col",
                        help="이 컬럼의 값이 아래 'Trace 값'과 일치하는 캐릭터가 교체로 진입할 때 상대 on_field 유닛의 타입을 복사함."
                    )
                    _tr_vals = (sorted(df[_tr_col].dropna().astype(str).unique().tolist())
                                if _tr_col in df.columns else [])
                    if _tr_vals:
                        _tr_match = st.selectbox("Trace 값", _tr_vals, key="ui_mech_trace_val")
                    else:
                        _tr_match = st.text_input("Trace 값", value="Trace", key="ui_mech_trace_val_txt")
                    _tr_type_col = st.selectbox(
                        "복사할 타입이 든 기믹 컬럼 (상대의 이 값을 복사)", list(gimmicks),
                        key="ui_mech_trace_type_col",
                        help="상대 on_field 유닛의 이 기믹 컬럼 값을 진입 유닛의 current_type으로 복사. 상대가 Protean 등 동적 타입(current_type)을 가지면 그것을 우선 사용."
                    )
                    _mech_cfg["trace"] = {
                        "gimmick_col": _tr_col,
                        "match_value": str(_tr_match),
                        "type_col": _tr_type_col,
                    }
                else:
                    st.warning("기믹 컬럼이 없어 Trace 기준을 지정할 수 없습니다.")
```

## 적용 후 자가 점검 (보고만, 코드 변경 금지)
1. `ui_mech_trace_on` 1회, `_mech_cfg["trace"]` 1회 존재.
2. 생성 spec 키가 `gimmick_col`·`match_value`·`type_col` 3개 — 엔진 `_apply_switch_in_effects`가
   읽는 키와 일치.
3. 저장 핸들러는 기존 `if _mech_cfg: _gc["mechanisms"] = _mech_cfg` 그대로(변경 없음).
4. `modules/step2_system_definition.py` 구문 오류 없이 compile.
5. 엔진·turn_manager 변경 없음.

## 회귀 0 근거
- Trace 체크박스 기본 False → `_mech_cfg["trace"]` 미생성 → `mechanisms`에 trace 키 없음 →
  엔진 핸들러 no-op → 현행 동작 동일.
- 기존 Protean/Leftovers/상태이상 UI·저장 배선 불변.

## 라이브 확인 (S6+S7+S8 end-to-end)
step2에서 Trace 체크 → 기준 기믹 컬럼/값 + 복사할 타입 컬럼 지정 → 액티브 수 1(싱글)·예비 보유로
교체가 일어나는 전투를 단일 실행. Trace 부착 캐릭터가 진입하는 **그 시점에** "타입이 …(으)로
복사됨 (Trace ←…)" 로그가 뜨고, 이후 그 캐릭터의 STAB가 복사된 타입 기준으로 바뀌면 진입 즉시
타이밍 + Trace가 전부 실증된다.
