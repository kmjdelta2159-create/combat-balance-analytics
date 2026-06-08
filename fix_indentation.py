lines = open('modules/step2_system_definition.py', 'r', encoding='utf-8').readlines()

# find Tag Dictionary Mapping
tag_start = -1
for i, line in enumerate(lines):
    if 'with st.expander("🏷️ Tag Dictionary Mapping (태그 정규화)", expanded=False):' in line:
        tag_start = i
        break

# find the next section "with st.expander("🔄 Logic Execution Order", expanded=False):"
leo_start = -1
for i, line in enumerate(lines):
    if 'with st.expander("🔄 Logic Execution Order", expanded=False):' in line:
        leo_start = i
        break

# find the end of logic execution order section (before "# ── Phase 8d")
ch_start = -1
for i, line in enumerate(lines):
    if '# ── Phase 8d: 기믹 채널 명시 매핑 ──' in line:
        ch_start = i
        break

print(f"Tag start: {tag_start}, LEO start: {leo_start}, CH start: {ch_start}")

if tag_start != -1 and leo_start != -1:
    # Indent the content between tag_start+1 and leo_start
    for i in range(tag_start+1, leo_start):
        if lines[i].strip() != '':
            lines[i] = '    ' + lines[i]

if leo_start != -1 and ch_start != -1:
    # Logic execution order does not need indentation if it doesn't have a 'with' block, but it DOES have 'with st.expander("🔄 Logic Execution Order", expanded=False):'
    for i in range(leo_start+1, ch_start):
        if lines[i].strip() != '':
            lines[i] = '    ' + lines[i]

with open('modules/step2_system_definition.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
