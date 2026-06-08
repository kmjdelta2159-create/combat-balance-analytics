# DB코퍼스 PR-ADAPT8 multiBattleReplayStackExpansion 프롬프트

## 역할

너는 이 저장소를 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수/프롬프트 작성 역할만 맡고 있으므로, 아래 요구사항을 기준으로 코드 수정, 테스트 추가, 스모크 실행, 결과 문서화를 수행해라.

## 현재 기준선

ADAPT7 결과는 통과 상태다.

- 산출물 위치: `.codex_tmp/adapt7_replay_stack_lock`
- backtest summary:
  - `accuracy_pct=100.0`
  - `outcome_mismatches=0`
  - `state_mismatches=0`
  - `state_checks=117`
  - `next_action=passed_or_low_mismatch`
- adapter report:
  - `battle_count=1`
  - `participant_count=12`
  - `state_event_count=122`
  - `damage_event_count=54`
  - `winner_side=p1`
  - `roster_only_entities=[]`
  - `unknown_damage_actor_count=29`
- schema flags:
  - `observed_status_trace_enabled=true`
  - `observed_hp_trace_enabled=true`
  - `observed_switch_trace_enabled=true`

ADAPT8의 목표는 이 기준선을 다중 전투/다중 입력형식에서도 깨지지 않게 확장하는 것이다.

## 목표

Pokemon Showdown DB 코퍼스 어댑터의 observed replay stack을 1개 전투 샘플에만 묶어두지 말고, 여러 battle_id가 섞인 입력에서도 정확히 동작하도록 확장/검증해라.

핵심은 다음 세 가지다.

1. 다중 전투 입력에서 battle_id별 변환, participant, winner, state trace, observed replay가 서로 섞이지 않을 것.
2. `.db`, `.zip`, 추출 폴더 입력이 같은 논리 결과를 낼 것.
3. 회귀 테스트가 schema flag 확인에 그치지 않고 실제 전투 객체/trace payload까지 확인할 것.

## 작업 범위

### 1. 다중 전투 fixture 또는 smoke 입력 준비

가능하면 실제 Pokemon Showdown DB extract에서 battle_id가 2개 이상인 입력을 사용해라. 현재 사용 가능한 실제 입력이 1개 전투뿐이면, 테스트용 fixture에서는 기존 전투를 서로 다른 battle_id로 복제/분리하되 다음 조건을 지켜라.

- battle_id가 서로 달라야 한다.
- seq/turn/order가 각 battle_id 안에서 독립적으로 정렬되어야 한다.
- winner_sides가 battle_id별로 보존되어야 한다.
- participant/state/move/damage row가 battle_id 밖으로 누출되지 않아야 한다.
- fixture 생성이 테스트에서 재현 가능해야 하며 임시 산출물은 `.codex_tmp/adapt8_multi_battle_replay` 아래에 둬라.

### 2. 입력형식 parity 검증

동일한 논리 입력에 대해 아래 형식들이 같은 핵심 결과를 내도록 검증해라.

- SQLite `.db` 직접 입력
- `.zip` 입력
- 압축 해제된 폴더 입력

최소 비교 항목:

- `battle_count`
- `participant_count`
- `state_event_count`
- `damage_event_count`
- `winner_sides`
- `roster_only_entities`
- backtest의 `actual_count`, `predicted_count`, `accuracy_pct`, `outcome_mismatches`, `state_mismatches`

완전히 같은 파일 byte를 요구하지 말고, 의미 있는 report/schema/backtest 필드가 동등한지 비교해라.

### 3. observed replay stack 다중 전투 안전성

다중 battle_id 입력에서 아래 observed trace가 battle_id별로 분리되어 적용되어야 한다.

- observed status trace
- observed HP trace
- observed switch trace
- faint incoming trace가 이미 연결되어 있다면 그 동작도 battle_id를 넘지 않도록 확인

특히 다음 실패를 막아라.

- battle A의 switch가 battle B의 on-field 상태에 영향을 주는 경우
- battle A의 HP/status snapshot이 battle B의 entity에 적용되는 경우
- battle_id가 다른 같은 nickname/species 때문에 entity가 오인 매칭되는 경우
- winner_side가 단일 값으로 덮여 battle별 winner_sides가 사라지는 경우

### 4. 회귀 테스트 강화

ADAPT7의 테스트가 schema flag만 확인하는 수준이면 부족하다. ADAPT8에서는 실제 trace payload가 build/simulation 입력에 들어왔는지 검증하는 테스트를 추가해라.

권장 확인 항목:

- build된 battle 객체 또는 battle_gc에 `_observed_status_trace`가 존재하고 비어 있지 않을 것
- `_observed_hp_trace`가 존재하고 비어 있지 않을 것
- switch trace action 또는 이에 대응되는 내부 구조가 존재하고 비어 있지 않을 것
- `trace_faint_incoming` 또는 faint incoming 관련 trace가 존재한다면 battle_id별로 분리되어 있을 것
- 다중 battle_id fixture에서 각 battle_id의 trace count가 0이 아니며 서로 다른 컨테이너로 유지될 것
- backtest summary가 battle별 row 또는 aggregate에서 `state_mismatches=0`을 유지할 것

테스트 이름은 기존 스타일을 따르되, 예시는 다음과 같다.

- `test_scenario_h_multi_battle_replay_stack`
- `test_showdown_db_extract_multi_battle_input_parity`
- `test_observed_trace_payload_is_attached_per_battle`

### 5. 리포트/문서화

스모크 실행 후 아래 파일을 남겨라.

- `.codex_tmp/adapt8_multi_battle_replay/adapter_report.json`
- `.codex_tmp/adapt8_multi_battle_replay/schema.json`
- `.codex_tmp/adapt8_multi_battle_replay/backtest/db_corpus_backtest_summary.csv`
- 가능하면 입력형식 parity 비교 결과 파일:
  - `.codex_tmp/adapt8_multi_battle_replay/input_parity_report.json`

그리고 저장소 루트에 검수자가 바로 읽을 수 있는 요약 문서를 작성해라.

- `DB코퍼스_ADAPT8_multiBattleReplayStackExpansion_검수요약.md`

요약 문서에는 다음을 포함해라.

- 사용한 입력 종류
- battle_count
- 입력형식별 핵심 report/backtest 비교표
- observed status/HP/switch trace가 실제 payload로 연결되었는지
- 최종 mismatch 수
- 실행한 테스트 명령과 결과
- 남은 위험 또는 다음 PR 후보

## 수용 기준

아래 조건을 모두 만족해야 한다.

- 다중 battle_id 입력에서 변환이 성공한다.
- `.db`, `.zip`, 폴더 입력의 핵심 report/backtest 결과가 동등하다.
- `adapter_report.json`의 `battle_count >= 2`인 스모크가 존재한다.
- `winner_sides`가 battle_id별로 보존된다.
- `roster_only_entities=[]`를 유지한다.
- backtest summary에서 `outcome_mismatches=0`이어야 한다.
- backtest summary에서 `state_mismatches=0`을 목표로 한다. 실제 코퍼스 확장으로 unavoidable mismatch가 생기면 첫 mismatch와 원인을 요약하고, fixture 기반 회귀 테스트에서는 반드시 0을 유지해라.
- observed status/HP/switch trace payload가 실제 battle 객체 또는 simulation 입력 구조에 붙어 있음을 테스트가 확인한다.
- ADAPT7 기준선 테스트가 깨지지 않는다.

## 실행해야 할 검증 명령

환경에 맞는 Python 명령을 사용하되, 최소한 아래 검증을 수행해라.

```powershell
python -m py_compile modules/showdown_db_adapter.py modules/per_battle_backtest.py modules/engine.py run_db_corpus_backtest.py test_i15_integration_smoke.py
python test_showdown_db_extract_adapter.py
python test_db_corpus_backtest_report.py
python test_i15_integration_smoke.py
```

새 테스트 파일을 추가했다면 그 테스트도 반드시 개별 실행해라.

## 금지/주의

- ADAPT7에서 통과한 1개 전투 기준선을 깨지 마라.
- UI/UX 변경은 이번 PR 범위에 넣지 마라. UI는 ADAPT8 통과 후 별도 PR로 넘겨라.
- unrelated refactor, pycache 커밋, 임시 스크립트 난립을 피하라.
- battle_id 없는 fallback 처리는 기존 동작을 유지하되, battle_id가 있는 입력에서는 반드시 battle_id를 우선 경계로 삼아라.
- `unknown_damage_actor_count=29` 자체를 이번 PR에서 억지로 0으로 만들지 마라. 이 PR의 목적은 replay stack 확장/회귀 잠금이다.

## 완료 보고 형식

완료 후 다음 형식으로 결과를 보고해라.

```text
ADAPT8 완료 보고
- 변경 파일:
- 추가 테스트:
- 스모크 산출물:
- battle_count:
- 입력형식 parity:
- backtest:
  - accuracy_pct:
  - outcome_mismatches:
  - state_mismatches:
- observed trace payload 검증:
- 실행한 명령:
- 남은 이슈:
```
