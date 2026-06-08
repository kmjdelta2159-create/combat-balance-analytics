# DB 로그 코퍼스 백테스트 리포트

- 이 리포트는 DB 로그 기반 코퍼스 검증 리포트다.
- HTML 리플레이 검증은 별도 legacy/reference harness이며 주 경로가 아니다.
- 결측 컬럼/schema 문제는 엔진 결함이 아니라 입력 매핑 문제로 분리한다.
- mismatch는 복제본과 관측 DB 로그가 갈라진 첫 지점이다.

|file|format|rows|columns|status|target_col|battle_count|actual_count|predicted_count|accuracy_pct|outcome_accuracy_pct|outcome_mismatches|correct|errors|state_checks|state_mismatches|action_damage_checks|action_damage_mismatches|action_resource_delta_checks|action_resource_delta_mismatches|first_mismatch_score_type|first_mismatch_turn|first_mismatch_id|first_mismatch_kind|first_mismatch_resource|first_mismatch_expected|first_mismatch_actual|speed_stat|max_turns|formula|trace_moves_enabled|state_trace_enabled|damage_trace_enabled|resource_delta_trace_enabled|next_action|error|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|battle_log.csv|csv|224|29|ran|result|1|1|0|0.0|0.0|1|0|0|117|68|0|0|0|0|state|1|p1:Gengen|status||'tox'|''|None|100|0|True|True|False|False|inspect_mismatch||
