with open("modules/step2_system_definition.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
state = "normal"

for i, line in enumerate(lines):
    stripped = line.strip()

    # Transition to Move
    if state == "normal" and stripped == 'st.markdown("## 🎯 Move System (무브/어빌리티)")':
        # Pop previous line if it is st.divider()
        while len(new_lines) > 0 and 'st.divider()' in new_lines[-1]:
            new_lines.pop()
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + 'st.divider()\n')
        new_lines.append(indent + 'st.markdown("## ⚙️ 시스템 세부 정의 (선택) — 펼쳐서 정밀 조정")\n')
        new_lines.append(indent + 'st.caption("아래 항목은 모두 선택입니다. 데이터 맵핑만 끝내면 맵핑 승인으로 진행할 수 있습니다.")\n')
        new_lines.append(indent + 'with st.expander("🎯 Move System (무브/어빌리티)", expanded=False):\n')
        state = "move"
        continue

    # Transition to Tag
    if state == "move" and stripped == 'st.markdown("## 🏷️ Tag Dictionary Mapping (태그 정규화)")':
        while len(new_lines) > 0 and 'st.divider()' in new_lines[-1]:
            new_lines.pop()
        
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent[:-4] if len(indent)>=4 else indent) # Because it was previously indented 12 spaces, we want to indent it 12 spaces. wait, `line` is NOT indented with 4 extra spaces! It has its original indent, which is 12 spaces. The new `with` should have 12 spaces, and its content 16 spaces.
        # So `indent` is 12 spaces!
        new_lines.append(indent + 'with st.expander("🏷️ Tag Dictionary Mapping (태그 정규화)", expanded=False):\n')
        state = "tag"
        continue

    # Transition to Logic
    if state == "tag" and stripped == 'st.markdown("## 🔄 Logic Execution Order (기획 의도/White-Box 확립)")':
        while len(new_lines) > 0 and 'st.divider()' in new_lines[-1]:
            new_lines.pop()
        
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + 'with st.expander("🔄 Logic Execution Order (기획 의도/White-Box 확립)", expanded=False):\n')
        state = "logic"
        continue

    # Transition to End
    if state == "logic":
        # Look ahead 1 line to check if we are at the divider before Phase 8d
        if 'st.divider()' in line and i+2 < len(lines) and 'Phase 8d' in lines[i+2]:
            state = "end"
            new_lines.append(line)
            continue
        # Also safeguard
        if '# ── Phase 8d' in line or 'with st.expander("🧩 기믹 채널 매핑' in line:
            state = "end"
            new_lines.append(line)
            continue

    # Indentation logic
    if state in ["move", "tag", "logic"]:
        if line.strip() == "":
            new_lines.append(line)
        else:
            new_lines.append("    " + line)
    else:
        new_lines.append(line)

with open("modules/step2_system_definition.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Done")
