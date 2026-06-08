import os
import sys
import ast

def get_helpers_from_ast():
    with open("modules/step2_system_definition.py", "r", encoding="utf-8") as f:
        source = f.read()
    
    parsed = ast.parse(source)
    helper_nodes = [node for node in parsed.body if isinstance(node, ast.FunctionDef) and node.name in ["_step2_readiness_state", "_step2_optional_summary", "_short_list"]]
    
    import types
    mod = types.ModuleType("step2_helpers")
    
    for node in helper_nodes:
        code = compile(ast.Module(body=[node], type_ignores=[]), filename="<ast>", mode="exec")
        exec(code, mod.__dict__)
        
    return mod

def test_step2_helpers():
    helpers = get_helpers_from_ast()
    
    _step2_readiness_state = helpers._step2_readiness_state
    
    # 1. target/stats/formula OK
    res1 = _step2_readiness_state("Is_Victorious", ["HP"], "attack - defense", True)
    assert res1["target_ok"] is True
    assert res1["stats_ok"] is True
    assert res1["formula_text_ok"] is True
    assert res1["formula_eval_ok"] is True
    assert res1["can_start"] is True

    # 2. target 없음
    res2 = _step2_readiness_state(None, ["HP"], "attack - defense", True)
    assert res2["target_ok"] is False
    assert res2["can_start"] is False
    assert "타겟 컬럼 선택 안됨" in res2["blocking_reasons"]

    # 3. formula eval 실패
    res3 = _step2_readiness_state("Is_Victorious", ["HP"], "attack - defense", False)
    assert res3["formula_text_ok"] is True
    assert res3["formula_eval_ok"] is False
    assert res3["can_start"] is False
    assert "데미지 공식 검증 실패" in res3["blocking_reasons"]

def test_step2_layout_markers():
    with open("modules/step2_system_definition.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    assert 'ui_step2_target_col' in content
    assert 'ui_step2_base_stats' in content
    assert 'ui_step2_gimmicks' in content
    assert 'with tabs[3]:' in content
    assert 'blocking_reasons' in content
    assert 'disabled=not _readiness["can_start"]' in content

if __name__ == "__main__":
    test_step2_helpers()
    test_step2_layout_markers()
    print("test_step2_system_definition_layout.py passed")
