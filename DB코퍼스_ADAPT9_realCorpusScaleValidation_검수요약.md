# DB코퍼스_ADAPT9_realCorpusScaleValidation_검수요약

## 목표 달성
실제 다중 배틀 입력을 처리하기 위한 Scale Validation Runner(`run_db_corpus_scale_validation.py`) 파이프라인을 구축하고, 검증 스크립트 작성 및 회귀 테스트를 100% 통과했습니다. 시스템에 실제 다중 배틀 DB/ZIP 파일이 없어 `real_corpus_unavailable` 상태를 문서화하고 기존 ADAPT8의 다중 배틀(Replicated Fixture) 입력 처리를 성공적으로 마쳤습니다.

## 1. 입력 목록과 출처 분류
- `pokemon_showdown_multi.db`: **replicated_fixture**
- `input_zip.zip`: **replicated_fixture**
- `pokemon_showdown_db_extract.zip` (탐색 결과): **real_corpus_unavailable** (Battle Count = 1 로 다중 배틀 조건 미달)
- `pokemon_showdown_production_style.db` (탐색 결과): **real_corpus_unavailable** (Battle Count = 1 로 다중 배틀 조건 미달)

> **실제 코퍼스 사용 여부**: **NO** (Battle Count 2 이상의 실제 입력 없음)

## 2. 총 battle_count 및 Summary 표
실제 다중 전투 데이터를 찾을 수 없었기 때문에 ADAPT8 파이프라인의 fixture 데이터를 통해 `.db`와 `.zip` 양식의 동등성과 통합 검증을 진행했습니다. 총 battle_count는 4입니다.

| input_path | input_kind | status | battle_count | rows | accuracy_pct | outcome_mismatches | state_checks | state_mismatches | next_action |
|---|---|---|---|---|---|---|---|---|---|
| .codex_tmp/.../pokemon_showdown_multi.db | replicated_fixture | ran | 2 | 448 | 100.0% | 0 | 234 | 0 | passed_or_low_mismatch |
| .codex_tmp/.../input_zip.zip | replicated_fixture | ran | 2 | 448 | 100.0% | 0 | 234 | 0 | passed_or_low_mismatch |

### 3. `.db` / `.zip` 결과 차이
- **결과**: 완전히 동일 (`accuracy_pct: 100.0`, `outcome_mismatches: 0`, `state_mismatches: 0`)
- **mismatch 총계**: 0건
- **첫 mismatch 상세**: N/A (Mismatch 발생 안 함)

## 4. Observed Flag 유지 및 One-Click Helper 일치 여부
- **Observed status/HP/switch flag 유지 여부**: `scale_validation_schema_flags.csv`에서 `observed_status_trace_enabled`, `observed_hp_trace_enabled`, `observed_switch_trace_enabled`가 모두 `True`로 보존됨을 확인했습니다.
- **One-click helper와 CLI/runner 결과 일치 여부**: Streamlit `st.session_state` 환경을 모사한 `run_db_corpus_backtest_from_session` 헬퍼 함수를 동일하게 호출하므로, Step 6 UI One-Click과 Scale Validation Runner의 결과가 100% 동일하게 나타났습니다.

## 5. 실행한 명령
```powershell
python -m py_compile modules/showdown_db_adapter.py modules/per_battle_backtest.py modules/ui_db_corpus_helper.py run_db_corpus_scale_validation.py
python test_db_corpus_scale_validation.py
python test_step1_db_corpus_upload_adapter.py
python test_step6_db_corpus_auto_schema.py
python test_step6_db_corpus_oneclick_backtest.py
python test_showdown_db_extract_adapter.py
python test_db_corpus_backtest_report.py
python test_i15_integration_smoke.py

python run_db_corpus_scale_validation.py --input .codex_tmp/adapt8_multi_battle_replay/pokemon_showdown_multi.db --input .codex_tmp/adapt8_multi_battle_replay/input_zip.zip --out .codex_tmp/adapt9_real_corpus_scale_validation
```
**테스트 출력의 Skipping 여부**: 기존에 `test_step1_db_corpus_upload_adapter.py`와 `test_step6_db_corpus_oneclick_backtest.py` 등에서 fixture를 건너뛰던(Skipping) 현상을 제거하고 모두 정상적으로 검증되었습니다.

## 6. 남은 위험 및 다음 PR 제안
- **남은 위험**: `real_corpus_unavailable`로 인해, 수백~수천 배틀 규모의 실제 이질적인 전투 데이터셋에 대한 검증을 수행하지 못했습니다. 추후 대형 DB 또는 다양한 기믹의 JSON 메타가 포함된 다중 배틀에서 성능이나 예외 처리가 필요할 수 있습니다.
- **다음 PR 제안 (PR-ADAPT10)**: 대형 실제 코퍼스(100+ 배틀 규모)를 확보하여 퍼포먼스(메모리 누수, 멀티프로세싱 안정성) 측정 및 최적화, 그리고 다양한 메타/팀 빌딩 로직에서의 예외(Edge Case) 처리 강화.
