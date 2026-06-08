import re

with open('modules/step2_system_definition.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Insert helpers
helpers = """
def _step2_completion_state(selected_target, base_stats, gimmicks, formula_text):
    target_ok = bool(selected_target and selected_target != "None")
    stats_ok = bool(base_stats and len(base_stats) > 0)
    formula_ok = bool(formula_text and str(formula_text).strip())
    can_start = target_ok and stats_ok and formula_ok
    return {
        "target_ok": target_ok,
        "stats_ok": stats_ok,
        "formula_ok": formula_ok,
        "can_start": can_start,
    }

def _step2_optional_summary(move_library_edited, game_config_like):
    moves_cnt = len(move_library_edited) if move_library_edited is not None and hasattr(move_library_edited, "__len__") else 0
    mechs_cnt = len(game_config_like.get("mechanisms", {})) if game_config_like else 0
    return {
        "moves_count": moves_cnt,
        "mechanisms_count": mechs_cnt,
    }

def render_system_definition():
"""
text = text.replace("def render_system_definition():\n", helpers)

# 2. Add summary bar at the beginning of mapping block and wrap in tabs
old_block_start = """    if not st.session_state.get('mapping_approved', False):
        if True:  # 탭 제거 — 모든 섹션 평면 렌더링
            st.markdown("## 🔍 데이터 매핑 & 공식 검증")
        
            with st.expander("원본 데이터 샘플 (맵핑 참고용)", expanded=False):"""

new_block_start = """    if not st.session_state.get('mapping_approved', False):
        # 1. 상단 요약 (Summary)
        _target = st.session_state.get("target_col", "None")
        _stats = st.session_state.get("system_stats", [])
        _gimmicks = st.session_state.get("system_gimmicks", [])
        _formula = st.session_state.get("formula_input_ui", "")
        _moves = st.session_state.get("move_library")
        _game_cfg = st.session_state.get("game_config", {})
        
        _comp = _step2_completion_state(_target, _stats, _gimmicks, _formula)
        _opt = _step2_optional_summary(_moves, _game_cfg)
        
        t_ok = "OK" if _comp["target_ok"] else "Needed"
        s_ok = len(_stats)
        g_ok = len(_gimmicks)
        f_ok = "OK" if _comp["formula_ok"] else "Needed"
        o_ok = "Auto/Set" if (_opt["moves_count"] > 0 or _opt["mechanisms_count"] > 0) else "Auto"
        
        st.markdown(f"**Step2 Setup** | [Target: {t_ok}] [Stats: {s_ok}] [Gimmicks: {g_ok}] [Formula: {f_ok}] [Optional Rules: {o_ok}]")
        st.divider()

        # 2. 탭 구성
        tabs = st.tabs(["필수 매핑", "공식 검증", "선택 규칙", "검토/시작"])
        
        with tabs[0]:
            st.markdown("## 🔍 필수 매핑")
            with st.expander("원본 데이터 샘플 (맵핑 참고용)", expanded=False):"""

text = text.replace(old_block_start, new_block_start)

# 3. Handle col1 -> tabs[0] and col2 -> tabs[1]
# We need to change `col1, col2 = st.columns([1, 1.5])` and `with col1:` and `with col2:`
# Wait, if we just replace `col1, col2 = st.columns([1, 1.5])` with nothing or just remove it,
# and replace `with col1:` with `if True:` (so indentation is kept), it's easier.
# Actually, since everything is inside tabs now, we don't need col1/col2.

text = text.replace("            col1, col2 = st.columns([1, 1.5])", "")
text = text.replace("            with col1:", "            if True: # was col1")

# Now change `with col2:` to `with tabs[1]:`
text = text.replace('            with col2:\n                st.markdown("#### 3. ⚔️ 공식 검증기")', '        with tabs[1]:\n            st.markdown("## ⚔️ 공식 검증기")\n            if True: # was col2')

# Now fix the indentation inside tabs[1]. Wait, replacing `with col2:` with `with tabs[1]:\n            if True:` perfectly preserves indentation of the inner block!

# 4. Optional rules
old_optional = """            # ═══════════════════════════════════════════════════════════════════
            # Phase 8a — Move System (무브/어빌리티 자동 추출 + 검수)
            # ═══════════════════════════════════════════════════════════════════
            st.divider()
            st.markdown("## ⚙️ 시스템 세부 정의 (선택) — 펼쳐서 정밀 조정")
            st.caption("아래 항목은 모두 선택입니다. 데이터 맵핑만 끝내면 맵핑 승인으로 진행할 수 있습니다.")
            with st.expander("🎯 Move System (무브/어빌리티)", expanded=False):"""

new_optional = """        with tabs[2]:
            st.markdown("## ⚙️ 선택 규칙")
            st.caption("아래 항목은 모두 선택(고급 설정)입니다.")
            with st.expander("🎯 Move System (무브/어빌리티)", expanded=False):"""
text = text.replace(old_optional, new_optional)

# 5. Type Matchup
# Make it a separate expander if possible.
# Currently it's:
#                         # ── Phase 8b: 타입 상성표 + STAB ──
#                         st.markdown("#### 🔯 타입 상성표")

old_type = """                        # ── Phase 8b: 타입 상성표 + STAB ──
                        st.markdown("#### 🔯 타입 상성표")"""
new_type = """                        # ── Phase 8b: 타입 상성표 + STAB ──
            with st.expander("🔯 타입 상성표", expanded=False):"""

text = text.replace(old_type, new_type)

# 6. Tag Dictionary Mapping
old_tag = """                # ═══════════════════════════════════════════════════════════════════
                # Tag Normalization — 카테고리 태그 → 엔진 표준 태그 매핑 UI
                # ═══════════════════════════════════════════════════════════════════
            st.markdown("### 🏷️ Tag Dictionary Mapping (태그 정규화)")"""

new_tag = """            # Tag Normalization
            with st.expander("🏷️ Tag Dictionary Mapping (태그 정규화)", expanded=False):"""
text = text.replace(old_tag, new_tag)

# 7. Logic Execution Order
old_leo = """            st.divider()

            st.markdown("### 🔄 Logic Execution Order (기획 의도/White-Box 확립)")"""
new_leo = """            with st.expander("🔄 Logic Execution Order", expanded=False):"""
text = text.replace(old_leo, new_leo)

# 8. Channel mapping (already an expander, just remove the divider before it if any)
text = text.replace("            st.divider()\n\n            # ── Phase 8d", "            # ── Phase 8d")

# 9. Review/Start
old_review = """            # ═══════════════════════════════════════════════════════════════════
            # Phase 9: 맵핑 승인 및 시스템 고정
            # ═══════════════════════════════════════════════════════════════════
            st.divider()
            st.markdown("## 🚀 Step 2 완료 및 파이프라인 시작")
            
            # 여기서 validation logic 수행
            validation_errors = []"""

new_review = """        with tabs[3]:
            st.markdown("## 🚀 검토/시작")
            
            st.markdown("### 요약")
            st.write(f"- **Target**: {selected_target}")
            st.write(f"- **Stats**: {len(base_stats)}개")
            st.write(f"- **Gimmicks**: {len(gimmicks)}개")
            st.write(f"- **Formula**: {'입력됨' if formula_str_eval else '미입력'}")
            
            validation_errors = []"""
text = text.replace(old_review, new_review)

with open('modules/step2_system_definition.py', 'w', encoding='utf-8') as f:
    f.write(text)
