# DB코퍼스 ADAPT replay stack 검수 요약

## 진행 경과
- **완료 단계:** ADAPT1d ~ ADAPT6
- **실제 DB smoke 검수 결과:** 
  - Accuracy: 100%
  - State Mismatch: 0
  - Outcome Mismatch: 0
  - Status: ran
  - First Mismatch: 없음 (전체 통과)

## 적용된 Trace Replay 목록
1. **Status Trace (`observed_status_trace`)**
   - `StatusApplied` / `StatusCured` 이벤트를 기반으로 관측된 상태 이상(예: `tox`)을 재현 엔진에 직접 주입.
   - 첫 번째 mismatch였던 `p1:Gengen status expected 'tox' actual ''` 제거.
   
2. **HP Trace (`observed_hp_trace`)**
   - `PokemonSwitched`, `DamageApplied`, `HealApplied`, `PokemonFainted` 등의 이벤트를 절대적 HP 수치로 반영.
   - HP mismatch(`p1:Nanami turn 2 HP expected 278 actual 403`) 및 Fainted 상태 타이밍 동기화 완료.

3. **Switch Trace (`observed_switch_trace`)**
   - `PokemonSwitched`를 바탕으로 한 턴 내 발생한 교체 및 기절 후 등장(`faint_incoming`) 이벤트를 추적하여 강제 교체.
   - 누락 불일치(`p2:Latios missing`, `p2:Metagross missing` 등)를 엔진 레벨의 ACTION_END 훅에서 HP와 함께 연계하여 완벽히 해소.

## 주의 및 권장 사항
- 현재 테스트 및 Smoke 산출물은 `1 battle` 기준으로 검증되었습니다.
- 본 리포트의 결과는 최신 검수 산출물인 `.codex_tmp\adapt7_replay_stack_lock`을 기준으로 합니다. (이전 `.codex_tmp\adapt6_switch_trace`의 summary는 stale 데이터일 수 있으므로 혼동에 주의하십시오)
- **다음 권장 작업:** 더 많은 Showdown DB 샘플로 multi-battle smoke 테스트를 진행하여 확장 검증을 수행하거나, `.db` 파일 입력을 위한 UI/UX 파이프라인 연동 작업을 추천합니다.
