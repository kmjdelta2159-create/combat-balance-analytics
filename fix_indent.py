with open("modules/step2_system_definition.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
in_fix_zone = False
for i, line in enumerate(lines):
    if not in_fix_zone and line.lstrip().startswith("st.divider()"):
        if i+1 < len(lines) and lines[i+1].strip() == "":
            if i+2 < len(lines) and lines[i+2].lstrip().startswith("c_btn, c_json = st.columns(2)"):
                in_fix_zone = True

    if in_fix_zone:
        if line.startswith("    "):
            new_lines.append(line[4:])
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open("modules/step2_system_definition.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Fixed")
