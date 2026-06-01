import streamlit as st
from streamlit_sortables import sort_items
import re

def render_flow_auditor():
    st.title("4. Flow Auditor")
    st.markdown("시스템 로직의 실행 순서를 사용자가 드래그 앤 드롭으로 교정하고 시뮬레이션 엔진에 실시간으로 동기화합니다.")
    
    if "df" not in st.session_state or not st.session_state.get('mapping_approved', False):
        return False, "⚠️ 2단계(Role Definition)에서 매핑 파이프라인을 완료해야 합니다."

    st.subheader("🔄 Logic Execution Order")
    st.info("💡 **가이드:** 각 로직 블록을 마우스로 클릭한 채 위아래로 드래그(Drag & Drop)하여 시스템 적용 순서를 변경할 수 있습니다.")

    if "combat_flow" not in st.session_state:
        st.session_state.combat_flow = [
            {
                "header": "Phase 1: Pre-calculation", 
                "items": ["Apply Passives (패시브 적용)", "Base Stat Calculation (기본 스탯 계산)"]
            },
            {
                "header": "Phase 2: Combat Flow", 
                "items": ["Determine Targeting (타겟팅 결정)", "Calculate Base Damage (기본 데미지 계산)", "Apply Elemental Multipliers (속성 상성 적용)", "Apply Critical Hit (치명타 적용)"]
            },
            {
                "header": "Phase 3: Resolution", 
                "items": ["Apply Damage (최종 데미지 적용)", "Trigger On-Hit Effects (피격 효과 발동)", "Check Death (사망 판정)"]
            }
        ]

    sorted_items = sort_items(st.session_state.combat_flow, multi_containers=True)

    if sorted_items:
        st.session_state.combat_flow = sorted_items
        st.success("✅ 현재 로직 실행 순서가 메모리에 임시 저장(Auto-save)되었습니다.")
        
        st.markdown("### 🔄 **[현재 적용된 전투 실행 흐름]**")
        
        flow_sequence = []
        for phase in st.session_state.combat_flow:
            for item in phase.get("items", []):
                match = re.search(r'\((.*?)\)', item)
                short_name = match.group(1) if match else item
                flow_sequence.append(f"`{short_name}`")
                
        if flow_sequence:
            st.success(" ➡️ ".join(flow_sequence))
            
    return True, ""
