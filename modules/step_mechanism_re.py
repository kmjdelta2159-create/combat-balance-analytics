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
    if st.button("🧩 EFFECTS 후보 블록 생성", key="mre_commit") or decisions:
        if not decisions:
            st.warning("커밋할 메커니즘을 하나 이상 체크하라."); return
        eff = commit(decisions)
        lines = ["    %r: %r," % (k, v) for k, v in eff.items()]
        st.code("# reference EFFECTS dict에 붙여넣기\n" + "\n".join(lines), language="python")
        st.caption("이 블록을 reference의 EFFECTS에 추가하면 디스패처가 발동한다. "
                   "프랙션·조건은 위에서 확정한 값.")
