import sys

with open('modules/step2_system_definition.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if 'win_idx = X[y_binary == 1].index.tolist()' in line:
        start_idx = i
    if 'st.success("✅ 승률 예측 모델 학습이 완료되었습니다!")' in line:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    new_lines = lines[:start_idx]
    
    indent = '                    '
    new_lines.append(indent + "st.session_state['numeric_cols'] = numeric_cols\n")
    new_lines.append(indent + "unique_classes = pd.Series(y_binary).dropna().unique()\n")
    new_lines.append(indent + "if len(unique_classes) < 2:\n")
    new_lines.append(indent + "    msg = '결과 컬럼에 한 종류의 값만 있어 예측 모델 학습을 건너뜁니다.'\n")
    new_lines.append(indent + "    if st.session_state.get('input_mode') == 'structured_battle_package':\n")
    new_lines.append(indent + "        msg = '현재 결과 컬럼이 단일 클래스라 승률 예측 모델 학습은 건너뜁니다.\\n전투 재현 검증은 리플레이 이벤트 기반으로 진행됩니다.'\n")
    new_lines.append(indent + "    st.info(f'ℹ️ {msg}')\n")
    new_lines.append(indent + "else:\n")
    
    for i in range(start_idx, end_idx + 1):
        new_lines.append('    ' + lines[i])
        
    new_lines.extend(lines[end_idx + 1:])
    
    with open('modules/step2_system_definition.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print('Patched successfully')
else:
    print('Failed to find indices')
