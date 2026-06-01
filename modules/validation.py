import pandas as pd
import numpy as np

def calculate_validation_score(
    simulation_results: dict, 
    original_log: pd.DataFrame, 
    column_mapping: dict
) -> dict:
    """
    Step6 Monte Carlo 시뮬레이션 결과와 실제 업로드된 전투 로그를 항목별로 대조하여 일치율을 계산합니다.
    """
    result = {
        "damage_formula": {"score": None, "status": "unknown"},
        "element_chart":  {"score": None, "status": "unknown"},
        "win_rate":       {"score": None, "status": "unknown"},
        "buff_duration":  {"score": None, "status": "unknown"},
        "overall":        {"score": None, "status": "unknown"}
    }

    def get_status(score):
        if score is None:
            return "unknown"
        if score >= 0.90:
            return "pass"
        elif score >= 0.70:
            return "warn"
        else:
            return "fail"

    # 1. 데미지 공식 일치율 (damage_formula)
    try:
        sim_avg_damage = simulation_results.get("avg_damage", None)
        
        # 원본 로그에서 데미지 컬럼 탐색
        damage_col = column_mapping.get("damage_col")
        if sim_avg_damage is not None and damage_col and damage_col in original_log.columns:
            actual_avg_damage = original_log[damage_col].mean()
            if actual_avg_damage != 0:
                ratio = sim_avg_damage / actual_avg_damage
                # 허용 오차 ±10% 기준, 오차가 클수록 점수 하락
                damage_score = max(0.0, 1.0 - abs(1.0 - ratio))
            else:
                damage_score = None
        else:
            damage_score = None
        result["damage_formula"] = {"score": damage_score, "status": get_status(damage_score)}
    except Exception:
        pass

    # 2. 속성 상성 일치율 (element_chart)
    try:
        element_col = column_mapping.get("element_col")
        damage_col = column_mapping.get("damage_col")
        sim_element_damage = simulation_results.get("element_damage_map", None)
        
        if (element_col and element_col in original_log.columns
                and damage_col and damage_col in original_log.columns
                and sim_element_damage):
            actual_map = original_log.groupby(element_col)[damage_col].mean().to_dict()
            
            common_elements = set(actual_map.keys()) & set(sim_element_damage.keys())
            if common_elements:
                ratios = []
                for el in common_elements:
                    if actual_map[el] != 0:
                        ratios.append(abs(1.0 - sim_element_damage[el] / actual_map[el]))
                element_score = max(0.0, 1.0 - np.mean(ratios)) if ratios else None
            else:
                element_score = None
        else:
            element_score = None
        result["element_chart"] = {"score": element_score, "status": get_status(element_score)}
    except Exception:
        pass

    # 3. 승률 일치율 (win_rate)
    try:
        sim_win_rate = simulation_results.get("win_rate", None)
        target_col = column_mapping.get("target_col") or column_mapping.get("target_variable")
        
        if sim_win_rate is not None and target_col and target_col in original_log.columns:
            sim_rate = sim_win_rate / 100.0
            actual_rate = original_log[target_col].mean()
            
            # 두 승률이 얼마나 가까운지: 허용 오차 ±10%p = 1.0, 50%p 차이 = 0.0
            diff = abs(sim_rate - actual_rate)
            win_rate_score = max(0.0, 1.0 - (diff / 0.5))
        else:
            win_rate_score = None
        result["win_rate"] = {"score": win_rate_score, "status": get_status(win_rate_score)}
    except Exception:
        pass

    # 4. 버프 지속 턴 일치율 (buff_duration)
    try:
        sim_avg_buff = simulation_results.get("avg_buff_duration", None)
        buff_col = column_mapping.get("buff_duration_col")
        
        if sim_avg_buff is not None and buff_col and buff_col in original_log.columns:
            actual_avg_buff = original_log[buff_col].mean()
            if actual_avg_buff != 0:
                ratio = sim_avg_buff / actual_avg_buff
                buff_score = max(0.0, 1.0 - abs(1.0 - ratio))
            else:
                buff_score = None
        else:
            buff_score = None
        result["buff_duration"] = {"score": buff_score, "status": get_status(buff_score)}
    except Exception:
        pass

    # 5. 전체 일치율 (평균)
    try:
        scores = [v["score"] for k, v in result.items() if k != "overall" and v["score"] is not None]
        if scores:
            overall_score = sum(scores) / len(scores)
            result["overall"] = {"score": overall_score, "status": get_status(overall_score)}
    except Exception:
        pass

    return result
