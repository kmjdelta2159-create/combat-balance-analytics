with open("modules/step2_system_definition.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.strip() == "":
        pass # drop empty lines entirely to be safe from indentation
    elif line.lstrip().startswith('with st.expander("🏷️ Tag Dictionary Mapping (태그 정규화)", expanded=False):'):
        # Fix indentation to 12 spaces
        new_lines.append("            with st.expander(\"🏷️ Tag Dictionary Mapping (태그 정규화)\", expanded=False):\n")
        continue
    elif line.lstrip().startswith('with st.expander("🔄 Logic Execution Order (기획 의도/White-Box 확립)", expanded=False):'):
        # Fix indentation to 12 spaces
        new_lines.append("            with st.expander(\"🔄 Logic Execution Order (기획 의도/White-Box 확립)\", expanded=False):\n")
        continue
    elif line.strip() == "with st.expander(\"🎯 Move System (무브/어빌리티)\", expanded=False):":
        new_lines.append("            with st.expander(\"🎯 Move System (무브/어빌리티)\", expanded=False):\n")
        continue
        
    new_lines.append(line)

with open("modules/step2_system_definition.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Fixed indentation")
