# DB코퍼스_PR-ADAPT7 - replay stack regression lock

## 목적

ADAPT6 기능은 통과했다.

현재 코드로 실제 DB를 다시 변환하고 백테스트하면 다음 결과가 나온다.

```text
status=ran
battle_count=1
accuracy_pct=100.0
outcome_mismatches=0
state_checks=117
state_mismatches=0
action_damage_mismatches=0
action_resource_delta_mismatches=0
next_action=passed_or_low_mismatch
```

이번 PR의 목적은 ADAPT4b~ADAPT6에서 만든 observed replay stack을 회귀 테스트로 잠그고, stale summary 산출물 때문에 검수가 혼동되지 않도록 최종 smoke 절차를 정리하는 것이다.

이번 PR은 새 기능 확장 PR이 아니다.  
이미 통과한 `.db` replay path를 안전하게 고정하는 마감 PR이다.

## 현재 상태

완료된 작업:

- ADAPT1d: roster-only species/nickname false positive 보정
- ADAPT2: SQLite `.db` 직접 입력 지원
- ADAPT3: `.db`, `.zip`, extracted folder 입력 파이프라인 검수
- ADAPT4b: observed status trace replay
- ADAPT5: observed HP trace replay
- ADAPT6: observed switch trace replay

ADAPT6 기존 산출물 폴더:

```text
.codex_tmp\adapt6_switch_trace
```

주의:

`.codex_tmp\adapt6_switch_trace\backtest\db_corpus_backtest_summary.csv`는 한때 다음 stale 값을 보였다.

```text
state_mismatches=26
first_mismatch_turn=16
first_mismatch_id=p2:Latios
first_mismatch_kind=missing
```

하지만 현재 코드로 같은 입력을 다시 백테스트하면 통과한다.

```powershell
python -X utf8 run_db_corpus_backtest.py --schema ".codex_tmp\adapt6_switch_trace\schema.json" --out-dir ".codex_tmp\adapt6_switch_trace_rerun" --max-battles 1 ".codex_tmp\adapt6_switch_trace\battle_log.csv"
```

재실행 결과:

```text
accuracy_pct=100.0
outcome_mismatches=0
state_mismatches=0
next_action=passed_or_low_mismatch
```

새 verify 산출물도 통과한다.

```text
.codex_tmp\adapt6_switch_trace_verify\backtest\db_corpus_backtest_summary.csv
```

## 확정된 replay stack

현재 schema/log config에는 다음 기능이 켜져 있어야 한다.

```json
{
  "trace_moves_enabled": true,
  "state_trace_enabled": true,
  "observed_status_trace_enabled": true,
  "observed_hp_trace_enabled": true,
  "observed_switch_trace_enabled": true
}
```

각 기능의 역할:

```text
observed_status_trace
- StatusApplied / StatusCured를 discrete event로 replay한다.
- 예: p1:Gengen tox

observed_hp_trace
- PokemonSwitched / DamageApplied / HealApplied / PokemonFainted의 HP absolute event를 replay한다.
- 예: p1:Nanami turn 2 HP 403 -> 253 -> 278

observed_switch_trace
- PokemonSwitched를 기반으로 active transition을 replay한다.
- 예: p2:Latios -> p2:Metagross
```

## 작업 범위

### 1. 실제 DB replay regression test 추가

파일 후보:

```text
test_showdown_db_extract_adapter.py
test_db_corpus_backtest_report.py
```

가능하면 작은 fixture 기반으로 다음을 검증한다.

- observed status trace가 first status mismatch를 제거한다.
- observed HP trace가 first HP mismatch를 제거한다.
- observed switch trace가 missing participant mismatch를 제거한다.

실제 다운로드 DB 파일에 의존하는 테스트는 기본 unit test에 넣지 않는다.  
대신 mock extract/SQLite fixture를 만들어 검증한다.

필수 assertion 예시:

```python
assert schema["log_schema"]["observed_status_trace_enabled"] is True
assert schema["log_schema"]["observed_hp_trace_enabled"] is True
assert schema["log_schema"]["observed_switch_trace_enabled"] is True
```

가능하면 `build_battles_from_log_schema(...)` 결과의 `battle_gc`에 다음이 들어가는지 확인한다.

```python
assert "_observed_status_trace" in battle_gc
assert "_observed_hp_trace" in battle_gc
assert "trace_actions" in battle_gc
assert battle_gc["trace_actions"]["switch"]
```

### 2. ADAPT6 real DB smoke를 공식 산출 폴더로 갱신

현재 stale summary 혼동을 줄이기 위해, 실제 smoke 산출물을 다음 폴더로 다시 생성한다.

```text
.codex_tmp\adapt7_replay_stack_lock
```

명령:

```powershell
$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'

& $py -X utf8 convert_showdown_db_extract.py --input "C:\Users\kmjde\Downloads\pokemon_showdown_production_style.db" --out-dir ".codex_tmp\adapt7_replay_stack_lock"

& $py -X utf8 run_db_corpus_backtest.py --schema ".codex_tmp\adapt7_replay_stack_lock\schema.json" --out-dir ".codex_tmp\adapt7_replay_stack_lock\backtest" --max-battles 1 ".codex_tmp\adapt7_replay_stack_lock\battle_log.csv"
```

### 3. backtest summary stale 혼동 방지

stale 산출물을 코드에서 완전히 방지하기 어렵다면, 최소한 결과 보고에 다음을 명확히 적는다.

```text
.codex_tmp\adapt6_switch_trace\backtest summary는 stale일 수 있음.
현재 기준 공식 검수 산출물은 .codex_tmp\adapt7_replay_stack_lock.
```

가능하면 `run_db_corpus_backtest.py`가 summary를 쓸 때 out-dir을 새로 만들거나 기존 summary를 덮어쓰는지 확인한다.

불필요한 대형 리팩터링은 하지 않는다.

### 4. report/README성 요약 작성

가능하면 짧은 결과 요약 문서를 생성한다.

예시 파일명:

```text
DB코퍼스_ADAPT_replay_stack_검수요약.md
```

내용:

```text
ADAPT1d~ADAPT6 완료
실제 DB smoke: 100% / state_miss 0
적용된 trace replay:
- status
- HP
- switch
남은 주의:
- 현재 smoke는 1 battle 기준
- 더 많은 Showdown DB 샘플로 확장 검증 필요
```

이 요약 문서는 선택 사항이다. 코드 변경보다 테스트/검증이 우선이다.

## 금지 사항

- 원본 `.db` 파일 수정 금지
- expected state snapshot 전체를 actual state에 복사 금지
- outcome 강제 보정 금지
- damage formula 전체 구현 금지
- UI/UX 작업 금지
- ADAPT4b status trace를 되돌리거나 무력화 금지
- ADAPT5 HP trace를 되돌리거나 무력화 금지
- ADAPT6 switch trace를 되돌리거나 무력화 금지
- `.db`, `.zip`, extracted folder 입력 파이프라인 리팩터링 금지
- 요청 없으면 git stage/commit 금지

## 필수 검증

PowerShell 기준:

```powershell
$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'

& $py -X utf8 -m py_compile modules/showdown_db_adapter.py modules/per_battle_backtest.py modules/engine.py run_db_corpus_backtest.py
& $py -X utf8 test_showdown_db_extract_adapter.py
& $py -X utf8 test_db_corpus_backtest_report.py
& $py -X utf8 test_i15_integration_smoke.py

& $py -X utf8 convert_showdown_db_extract.py --input "C:\Users\kmjde\Downloads\pokemon_showdown_production_style.db" --out-dir ".codex_tmp\adapt7_replay_stack_lock"

& $py -X utf8 run_db_corpus_backtest.py --schema ".codex_tmp\adapt7_replay_stack_lock\schema.json" --out-dir ".codex_tmp\adapt7_replay_stack_lock\backtest" --max-battles 1 ".codex_tmp\adapt7_replay_stack_lock\battle_log.csv"
```

## 통과 기준

다음은 반드시 만족해야 한다.

```text
py_compile 통과
test_showdown_db_extract_adapter.py 통과
test_db_corpus_backtest_report.py 통과
test_i15_integration_smoke.py 통과
실제 DB 변환 성공
adapter_report.json roster_only_entities == []
백테스트 status == ran
accuracy_pct == 100.0
outcome_mismatches == 0
state_mismatches == 0
next_action == passed_or_low_mismatch
```

## 산출물

작업 완료 후 다음을 보고한다.

```text
1. 변경 파일 목록
2. 추가/보강한 regression test 목록
3. 공식 smoke 산출물 경로
4. 백테스트 핵심 수치
5. stale summary 여부 정리
6. 다음 권장 작업
```

## 다음 단계 판단

ADAPT7이 통과하면 DB replay stack은 1-battle smoke 기준 완료로 본다.

이후 선택지는 둘 중 하나다.

```text
1. 확장 검증
   - 더 많은 Showdown DB 샘플로 multi-battle smoke
   - zip/db/folder 입력 간 동일성 검증 확대

2. UI/UX
   - 화면에서 .db 파일 선택
   - 변환 실행
   - adapter_report/backtest_summary 표시
   - mismatch / passed 상태 표시
```
