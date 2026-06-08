# DB Corpus Backtest Report

- This is a DB-log-based corpus validation report.
- HTML replay validation is a separate legacy/reference harness and not the main path.
- Missing columns or schema issues are isolated as input mapping problems, not engine defects.
- 'Mismatch' indicates the first point of divergence between the replay and the observed DB log.

|file|format|rows|columns|status|target_col|battle_count|actual_count|predicted_count|accuracy_pct|outcome_accuracy_pct|outcome_mismatches|correct|errors|state_checks|state_mismatches|action_damage_checks|action_damage_mismatches|action_resource_delta_checks|action_resource_delta_mismatches|first_mismatch_score_type|first_mismatch_turn|first_mismatch_id|first_mismatch_kind|first_mismatch_resource|first_mismatch_expected|first_mismatch_actual|speed_stat|max_turns|formula|trace_moves_enabled|state_trace_enabled|damage_trace_enabled|resource_delta_trace_enabled|next_action|error|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|battle_log.csv|csv|224|35|ran|result|1|1|0|0.0|0.0|1|0|0|88|26|0|0|0|0|state|16|p2:Latios|missing||''|''|None|100|0|True|True|False|False|inspect_mismatch||
