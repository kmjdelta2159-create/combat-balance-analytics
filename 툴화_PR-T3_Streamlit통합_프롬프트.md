# 툴화 PR-T3 — 수정 surface Streamlit 통합 (검출+확정을 화면 UI로)

> PR-T1(검출기)·PR-T2(수정 surface)는 CLI/config형이다. 이 PR은 그걸 **step2 안의 화면 패널**로
> 올려 비-개발자가 *트레이스 업로드 → 검출 테이블 → 조건 힌트 보고 클릭으로 확정 → EFFECTS 블록
> 복사*를 하게 한다. 로드맵 §1의 "step2 매핑UI를 메커니즘 축으로 연장"의 UI 실체.
>
> **로직은 이미 검증**(detect_mechanisms·infer_conditions·commit — T1/T2 클린룸). 이 PR은 그 위에
> `st.*` 렌더만 얹는다. Streamlit UI는 앱에서 확인(샌드박스 검증 불가). **위저드 번호 무변** —
> step2(render_system_definition) 안의 expander 한 줄로 끼워 회귀 위험 최소.

## 파일 1 — `modules/step_mechanism_re.py` (신규)

```python
# -*- coding: utf-8 -*-
"""step_mechanism_re.py — 트레이스 메커니즘 RE 수정 surface(Streamlit 패널).
검출(자동) + 조건추론(힌트) + 사용자 확정(위젯) → EFFECTS 블록. detect/infer/commit 재사용."""
import streamlit as st


def _csv(s):
    return [x.strip() for x in str(s).split(',') if x.strip()]


def render_mechanism_re(ref=None):
    """트레이스 업로드 → 메커니즘 쇼핑리스트 + 미모델 확정 → EFFECTS 블록. ref 기본 reference_gen5."""
    from modules.showdown_trace import parse_replay
    from modules.mechanism_detect import detect_mechanisms
    from modules.mechanism_commit import infer_conditions, commit
    if ref is None:
        import modules.reference_gen5 as ref

    st.caption("전투 로그(트레이스 HTML)를 올리면 발동형 메커니즘을 자동 검출하고, 미모델은 "
               "조건 힌트와 함께 확정해 EFFECTS 후보를 만든다. (추출은 자동, 확정은 사용자)")
    up = st.file_uploader("트레이스 HTML 업로드", type=["html", "htm"], key="mre_trace")
    if not up:
        st.info("Showdown 리플레이 HTML을 올리면 메커니즘 RE가 시작된다.")
        return
    try:
        trace = parse_replay(up.getvalue().decode("utf-8", errors="ignore"))
        det = detect_mechanisms(trace, ref)
    except Exception as e:
        st.error("트레이스 파싱/검출 실패: %s" % e); return

    # 1) 쇼핑리스트 테이블
    st.markdown("**검출된 메커니즘 (빈도순)**")
    st.dataframe([{
        "class": r["class"], "mechanism": r["name"], "kind": r["kind"],
        "frac": ("1/%d" % round(1/r["frac"])) if r["frac"] else "0",
        "n": r["n"], "modeled": "✅" if r["modeled"] else "❌",
    } for r in det], use_container_width=True, hide_index=True)

    # 2) 미모델만 확정 위젯
    unmod = [r for r in det if not r["modeled"]]
    if not unmod:
        st.success("미모델 메커니즘 없음 — 전부 스키마에 있음."); return
    st.markdown("**미모델 메커니즘 확정 (체크 = EFFECTS에 커밋)**")
    decisions = {}
    for r in unmod:
        name = r["name"]; sg = r["suggest"]
        ci = infer_conditions(trace, ref, name)
        with st.container(border=True):
            c1, c2 = st.columns([1, 3])
            inc = c1.checkbox("커밋", key="mre_inc_%s" % name)
            key = c1.text_input("EFFECTS 키", value=str(name).lower().replace(" ", "_"),
                                key="mre_key_%s" % name)
            c2.write("제안: `%s` / `%s` / frac 기본 %s / source `%s`"
                     % (sg["trigger"], sg["effect"]["type"], sg["effect"]["frac"], sg["source"]))
            c2.caption("면제 on-field: %s  →  not_ability 힌트(강): %s | not_types 힌트(약): %s"
                       % (ci["spared"], ci["not_ability_hint"], ci["not_types_hint"]))
            frac = c2.number_input("frac", value=float(sg["effect"]["frac"]), step=0.0625,
                                   format="%.4f", key="mre_frac_%s" % name)
            na = c2.text_input("not_ability (쉼표)", value=", ".join(ci["not_ability_hint"]),
                               key="mre_na_%s" % name)
            nt = c2.text_input("not_types (쉼표, 도메인지식 보완·오탐 제거)", value="",
                               key="mre_nt_%s" % name)
            if inc:
                spec = dict(sg); spec["effect"] = dict(sg["effect"]); spec["effect"]["frac"] = round(frac, 4)
                cond = {}
                if _csv(na): cond["not_ability"] = _csv(na)
                if _csv(nt): cond["not_types"] = _csv(nt)
                decisions[key] = {"spec": spec, "condition": cond or None}

    # 3) 커밋 → EFFECTS 블록
    if st.button("🧩 EFFECTS 후보 블록 생성", key="mre_commit"):
        if not decisions:
            st.warning("커밋할 메커니즘을 하나 이상 체크하라."); return
        eff = commit(decisions)
        lines = ["    %r: %r," % (k, v) for k, v in eff.items()]
        st.code("# reference EFFECTS dict에 붙여넣기\n" + "\n".join(lines), language="python")
        st.caption("이 블록을 reference의 EFFECTS에 추가하면 디스패처가 발동한다. "
                   "프랙션·조건은 위에서 확정한 값.")
```

## 파일 2 — `modules/step2_system_definition.py`에 패널 호출 (한 곳)

`render_system_definition()` 함수 **본문 상단**(초기 셋업 직후, 기존 폼들 앞)에 expander 추가:

```python
    with st.expander("🔬 트레이스 메커니즘 RE — 자동 검출 + 수정 (효과 디스패처 EFFECTS)", expanded=False):
        from modules.step_mechanism_re import render_mechanism_re
        render_mechanism_re()
```

> 기존 step2 흐름(CSV 매핑·move_effects 폼)은 그대로. 이 expander는 *트레이스 축*의 메커니즘 RE를
> 병렬로 제공(CSV 집계엔 없던 메커니즘 정보). 접힘 기본이라 기존 UX 무영향.

## 검증 (적용 후)

1. **로직 회귀0**: `python run_mechcommit.py`·`run_mechdetect.py`가 PR-T3 전과 동일(패널은 같은
   함수 재사용, 신규 파일 + expander 한 줄이라 무영향). `run_b4.py`도 무변.
2. **임포트 점검**: `python -c "import modules.step_mechanism_re"` 에러 없음(streamlit 설치 시).
3. **앱 UI 확인(앱사이드)**: 앱 step2에 "🔬 트레이스 메커니즘 RE" expander → 트레이스 HTML
   업로드(예: held-out gen5) → 검출 테이블 + 미모델 확정 위젯 + "EFFECTS 후보 블록 생성" → 커밋
   블록이 PR-T2 CLI 출력과 동일한지. **화면 캡처를 붙여달라.**

## 의미 — (b) 도구화 UI 완성

검출(자동) + 조건추론(힌트) + 확정(화면 위젯) + 커밋(EFFECTS 블록)이 *한 패널*에서 돈다 — 비-개발자
가 트레이스를 올려 메커니즘을 스키마로 확정하는 면. 내 X3~X7 수작업이 이제 *업로드→클릭→복사*다.
로드맵 §1 "기존 매핑UI를 메커니즘 축으로 연장"의 트레이스-리플레이 축 UI 실체화. 1차목표 (b) 기둥의
사용자-대면 완성.
