import sys

with open('modules/step2_system_definition.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
for i, line in enumerate(lines):
    if 'st.markdown("#### 1. 예측 데미지/회복 변수 탐지")' in line:
        start_idx = i
        break

if start_idx != -1:
    new_lines = lines[:start_idx]
    
    code = """                if st.session_state.get("input_mode") == "structured_battle_package":
                    st.info("💡 이 전투 데이터 패키지는 리플레이 이벤트 기반 검증을 우선 사용합니다.\\n데미지 수식을 수동으로 정의하려면 아래에서 입력할 수 있습니다.")
"""
    new_lines.append(code)
    new_lines.extend(lines[start_idx:])
    
    with open('modules/step2_system_definition.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print('Patched formula message successfully')
else:
    print('Failed to find formula tab')
