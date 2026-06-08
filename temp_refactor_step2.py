import sys

with open("modules/step2_system_definition.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line.strip() == 'with st.expander("🔬 트레이스 메커니즘 RE — 자동 검출 + 수정 (효과 디스패처 EFFECTS)", expanded=False):':
        pass
    elif i > 0 and lines[i-1].strip() == 'with st.expander("🔬 트레이스 메커니즘 RE — 자동 검출 + 수정 (효과 디스패처 EFFECTS)", expanded=False):':
        pass
    elif i > 1 and lines[i-2].strip() == 'with st.expander("🔬 트레이스 메커니즘 RE — 자동 검출 + 수정 (효과 디스패처 EFFECTS)", expanded=False):':
        pass
    else:
        new_lines.append(line)

lines = new_lines
new_lines = []

state = "normal"
for i, line in enumerate(lines):
    if state == "normal" and line.rstrip() == "    if not st.session_state.get('mapping_approved', False):":
        new_lines.append(line)
        new_lines.append('        t_data, t_move, t_mech, t_logic = st.tabs([\n')
        new_lines.append('            "📊 데이터·공식", "🎯 무브·타입", "⚙️ 메커니즘·태그", "🔄 실행순서"\n')
        new_lines.append('        ])\n')
        new_lines.append('        with t_data:\n')
        state = "data"
        continue
        
    if state == "data":
        if line.lstrip().startswith('# ═══ Phase 8a — Move System'):
            state = "move"
            new_lines.append('        with t_move:\n')
            new_lines.append("    " + line)
            continue
        else:
            if line.strip() == "": new_lines.append(line)
            else: new_lines.append("    " + line)
            continue
            
    if state == "move":
        if line.lstrip().startswith('st.divider()') and i+1 < len(lines) and lines[i+1].lstrip().startswith('st.markdown("## 🏷️ Tag Dictionary Mapping'):
            state = "mech"
            new_lines.append('        with t_mech:\n')
            new_lines.append('            with st.expander("🔬 트레이스 메커니즘 RE — 자동 검출 + 수정 (효과 디스패처 EFFECTS)", expanded=False):\n')
            new_lines.append('                from modules.step_mechanism_re import render_mechanism_re\n')
            new_lines.append('                render_mechanism_re()\n')
            new_lines.append("    " + line)
            continue
        else:
            if line.strip() == "": new_lines.append(line)
            else: new_lines.append("    " + line)
            continue
            
    if state == "mech":
        if line.lstrip().startswith('st.divider()') and i+1 < len(lines) and lines[i+1].lstrip().startswith('st.markdown("## 🔄 Logic Execution Order'):
            state = "logic"
            new_lines.append('        with t_logic:\n')
            new_lines.append("    " + line)
            continue
        else:
            if line.strip() == "": new_lines.append(line)
            else: new_lines.append("    " + line)
            continue
            
    if state == "logic":
        if line.lstrip().startswith('st.divider()') and i+1 < len(lines) and lines[i+1].lstrip().startswith('c_btn, c_json = st.columns(2)'):
            state = "end"
            new_lines.append(line)
            continue
        else:
            if line.strip() == "": new_lines.append(line)
            else: new_lines.append("    " + line)
            continue
            
    if state == "end":
        new_lines.append(line)
        continue

    new_lines.append(line)

with open("modules/step2_system_definition.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Done")
