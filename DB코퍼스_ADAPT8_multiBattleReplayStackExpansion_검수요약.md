# DB코퍼스 ADAPT8 multiBattleReplayStackExpansion 검수 요약

## 1. 사용한 입력 종류
- 원본 Pokemon Showdown DB(`pokemon_showdown_production_style.db`)를 기반으로 복제 생성한 **다중 전투 Fixture**(`.codex_tmp/adapt8_multi_battle_replay/pokemon_showdown_multi.db`)를 사용.
- 전투는 동일하지만 `battle_id`가 각각 `smogtours-gen5ou-59402`, `smogtours-gen5ou-59402_copy` 인 **2개의 서로 다른 전투**가 섞인 형태.

## 2. 핵심 지표 (battle_count 등)
- **battle_count**: 2
- **participant_count**: 24
- **state_event_count**: 244
- **damage_event_count**: 108
- **roster_only_entities**: []
- **unknown_damage_actor_count**: 58

## 3. 입력형식별 핵심 report/backtest 비교표
입력형식 간 Parity를 검증하기 위해 동일한 다중 전투 Fixture를 세 가지 포맷으로 제공하고 실행했습니다.
- **SQLite DB 직접 입력** (`pokemon_showdown_multi.db`)
- **Zip 압축 입력** (`input_zip.zip`)
- **압축 해제된 폴더 입력** (`input_folder`)

| 형식 | battle_count | winner_sides | backtest accuracy | state_mismatches | outcome_mismatches |
|---|---|---|---|---|---|
| **.db** | 2 | 2개 개별 존재 | 100.0% | 0 | 0 |
| **.folder** | 2 | 2개 개별 존재 | 100.0% | 0 | 0 |
| **.zip** | 2 | 2개 개별 존재 | 100.0% | 0 | 0 |

> **Parity 결과**: 세 형식 모두 완벽히 동일한 결과를 산출하여 논리적 동등성이 증명됨. (결과 위치: `.codex_tmp/adapt8_multi_battle_replay/input_parity_report.json`)

## 4. observed status/HP/switch trace의 Payload 연결 확인
- `test_i15_integration_smoke.py` 내에 `test_scenario_h_multi_battle_replay_stack` 를 신규 작성하여, 서로 다른 두 전투의 이벤트(`PokemonSwitched`, `StatusApplied`, `DamageApplied` 등)가 섞인 Dataframe을 입력했습니다.
- 검증 결과, 각 전투 컨텍스트인 `battle_gc`에 `_observed_status_trace`, `_observed_hp_trace`, `trace_actions["switch"]` 페이로드가 누락 없이, 그리고 **서로 섞임 없이 독립적으로 연결**됨을 확인했습니다.

## 5. 최종 mismatch 수
- **state_mismatches**: 0
- **outcome_mismatches**: 0

## 6. 실행한 테스트 명령과 결과
```powershell
python -m py_compile modules/showdown_db_adapter.py modules/per_battle_backtest.py modules/engine.py run_db_corpus_backtest.py test_i15_integration_smoke.py
python test_showdown_db_extract_adapter.py
python test_db_corpus_backtest_report.py
python test_i15_integration_smoke.py
```
- 모든 컴파일 및 단위 테스트 통과 (Scenario A ~ H)
- Parity 검증 스크립트 실행 후 3가지 포맷 변환 및 백테스트에서 모두 Accuracy 100% 달성.

## 7. 남은 위험 또는 다음 PR 후보
- **남은 위험**: 현재의 다중 전투 Fixture는 동일 전투를 복제한 것으로, 실제 다양한 메타나 턴의 변수가 있는 이기종 다중 전투에서도 state mismatch 0이 유지될지는 추후 수백 개의 실제 배틀셋(DB 추출본 확장판)을 적용해 보아야 합니다.
- **다음 PR 후보**: 터미널 커맨드라인 환경을 벗어나 **UI/UX 통합**을 통해 사용자가 화면에서 `.db`를 직접 첨부하고 바로 어댑터/백테스트 리포트(`adapter_report.json`, `db_corpus_backtest_summary.csv`)를 시각적으로 받아볼 수 있는 뷰어 기능 추가.
