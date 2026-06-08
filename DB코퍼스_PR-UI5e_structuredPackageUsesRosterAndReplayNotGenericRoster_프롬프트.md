# DB코퍼스 PR-UI5e structuredPackageUsesRosterAndReplayNotGenericRoster 프롬프트

## 역할

너는 이 저장소의 UI/UX 및 플로우 구현을 직접 수정하는 Antigravity 구현 에이전트다. Codex는 검수와 프롬프트 작성만 담당한다.

이번 작업은 `pokemon_showdown_db_extract.zip`을 일반 Step2 UI에 통합한 뒤, 데이터 의미가 잘못 해석되는 문제를 해결한다.

## 현재 실패 화면

사용자 스크린샷 기준 현재 상태:

1. Step2 필수 매핑
   - Target: `result`
   - Stats: `HP`
   - Gimmicks: `species`
   - 결측치 424건

2. Step2 공식 검증
   - 변수 chip: `HP`, `species`
   - damage formula 없음
   - 자동 추정 실패

3. Dashboard
   - One-click backtest: Battles `0 / 0`, Accuracy `0.0%`
   - Ally table Hero에 `smogtours-gen5ou-59402`가 들어감
   - HP `0.0`, species `None`
   - Enemy도 비어 있음
   - 예측 승률 `N/A`

이건 정상 복제 흐름이 아니다.

## 원인 판단

`pokemon_showdown_db_extract.zip`은 일반 캐릭터 스탯 테이블이 아니다.

패키지 안에는:

- `battle_events.csv`
- `battle_roster_pokemon.csv`
- `battle_players.csv`
- `battles.csv`
- `battle_rules.csv`
- `schema.sql`

같은 구조화된 전투 패키지가 있다.

현재 구현은 이 패키지를 일반 Step2 UI에 넣으면서, 최종 `df`를 일반 캐릭터/스탯 테이블처럼 해석하고 있다. 그래서 battle id가 Hero처럼 들어가고, HP가 0이며, 로스터/이벤트/상태 추적이 Dashboard에 반영되지 않는다.

즉, UI는 통합해도 되지만 **데이터 소스의 의미까지 일반 CSV처럼 바꾸면 안 된다.**

## 목표

DB/ZIP 전투 데이터 패키지는 일반 UI 흐름을 사용하되, 내부 데이터는 다음처럼 분리해서 사용해야 한다.

- Step2 editable UI: 자동 schema/mapping을 보여주고 수정 가능
- Roster/party/dashboard: `battle_roster_pokemon.csv` 기반
- Replay/backtest validation: `battle_events.csv` + schema 기반
- Generic character table fallback: 구조화 패키지에서 로스터 추출이 실패했을 때만 사용

즉, `battle_id`가 Hero가 되거나 HP가 전부 0인 Dashboard는 실패다.

## P0. DB/ZIP 패키지 데이터 소스 분리

DB/ZIP 패키지 변환 시 session_state에 다음을 명확히 보존하라.

권장:

```python
st.session_state["structured_package_mode"] = True
st.session_state["db_corpus_raw_tables"] = {
    "battle_events": ...,
    "battle_roster_pokemon": ...,
    "battle_players": ...,
    "battles": ...,
}
st.session_state["db_corpus_schema"] = ...
st.session_state["bb_last_log_schema"] = ...
```

이미 비슷한 값이 있으면 기존 키를 재사용하되, Dashboard/Step3에서 참조 가능해야 한다.

## P0. Step2는 editable mapping UI로 유지하되 데이터 의미를 보존

Step2는 일반 파일과 같은 UI를 유지한다.

하지만 default 값은 다음 기준으로 잡아라.

- target/result: `battles` 또는 summary의 winner/result 기준
- stats: Pokemon stat columns가 있으면 `hp_base`, `atk_base`, `def_base`, `spatk_base`, `spdef_base`, `spd_base` 등
- gimmicks: `species`, `type`, `ability`, `item`, side/team 관련 column
- health stat: `HP` 또는 `hp_base`
- event schema: `battle_events`의 turn/actor/target/move/state columns

주의:

- `Stats: HP` 하나만 잡고 끝내지 마라.
- `species` 하나만 gimmick으로 잡고 끝내지 마라.
- 자동값이 부족하면 "로스터 테이블에서 stat columns를 찾지 못함"처럼 정확히 표시하라.

## P0. Dashboard는 로스터 테이블 기반으로 구성

현재 Dashboard가 battle id를 Hero로 표시하고 있다. 이건 실패다.

DB/ZIP 구조화 패키지 모드에서는 Dashboard party/roster 구성 시:

1. `battle_roster_pokemon.csv` 또는 동등한 raw roster table을 우선 사용
2. side/player 기준으로 Ally/Enemy를 나눔
3. species/name을 Hero로 표시
4. stat columns가 있으면 stat으로 표시
5. stat columns가 없으면 실제 stat 부재를 명확히 표시하고 0으로 조용히 채우지 말 것

수용 기준:

- Hero column에 `smogtours-gen5ou-59402` 같은 battle id가 나오면 실패
- Ally/Enemy table에 실제 Pokemon species가 보여야 함
- HP가 전부 0으로만 채워지면 실패
- `None` species가 기본값처럼 반복되면 실패

## P0. Backtest 0/0 방지

One-click backtest가 `0 / 0`으로 나오면 시연 실패다.

필수:

- DB/ZIP 패키지 모드에서 backtest 입력이 실제 `battle_events`와 schema를 사용하도록 연결
- `battle_count`, `event_count`, `participant_count`가 adapter report와 일치하는지 확인
- backtest 실행 후 최소 1 battle 이상이 집계되어야 함

수용 기준:

- `pokemon_showdown_db_extract.zip` 기준 backtest가 `0 / 0`이면 실패
- 실행 전 상태라면 "아직 실행 전"으로 명확히 표시
- 실행 후에도 0이면 원인 메시지 표시

## P0. Step3 replay validation은 기존 helper를 정확히 호출

Step3 replay validation은 `battle_events` + schema를 사용해야 한다.

필수:

- `run_db_corpus_backtest_from_session` 함수 정의 확인
- Step6에서 정상 동작하는 호출 방식 재사용
- `session_state_like` 누락 TypeError 제거
- Step2에서 사용자가 수정한 schema를 Step3 검증에 반영

## P0. Formula tab 처리

DB/ZIP 패키지 모드에서 formula tab을 그대로 보여줄 수는 있지만, 사용자에게 잘못된 인상을 주면 안 된다.

권장:

- formula tab 상단에 안내:

```text
이 전투 데이터 패키지는 리플레이 이벤트 기반 검증을 우선 사용합니다.
데미지 수식을 수동으로 정의하려면 아래에서 입력할 수 있습니다.
```

- formula가 없다고 Step2 전체를 막지 말 것
- replay validation 가능 조건과 formula validation 조건을 분리

## 교수 시연 수용 기준

시연 파일:

- `pokemon_showdown_db_extract.zip`

필수 결과:

1. Step2에서 자동값이 채워지고 수정 가능
2. 자동값이 `HP/species`만으로 빈약하게 끝나지 않음
3. Dashboard에서 실제 Pokemon roster가 보임
4. battle id가 Hero로 표시되지 않음
5. backtest가 `0 / 0`으로 끝나지 않음
6. Step3 replay validation이 TypeError 없이 실행됨

## 테스트 요구사항

필수 실행:

```powershell
python -m py_compile main.py modules/step1_upload.py modules/step2_system_definition.py modules/step5_discrepancy.py modules/step6_dashboard.py modules/ui_db_corpus_helper.py
python test_step1_db_corpus_upload_adapter.py
python test_step6_db_corpus_auto_schema.py
python test_step6_db_corpus_oneclick_backtest.py
python test_db_corpus_ui_state.py
python test_i15_integration_smoke.py
```

추가 테스트 작성/보강:

- `test_structured_package_roster_source.py`
- `test_structured_package_dashboard_not_battle_id.py`
- `test_structured_package_backtest_nonzero.py`

필수 케이스:

- zip 패키지에서 roster table이 session_state에 보존됨
- Dashboard source가 roster table을 우선 사용
- Hero 값에 battle id가 들어가지 않음
- `pokemon_showdown_db_extract.zip` backtest summary가 battle_count 1 이상
- Step3 replay validation 함수 호출 TypeError 없음

## 실제 화면 검수

필수 스크린샷:

- `.codex_tmp/ui5e_structured_roster_replay/step2_prefilled_schema.png`
- `.codex_tmp/ui5e_structured_roster_replay/step3_replay_validation.png`
- `.codex_tmp/ui5e_structured_roster_replay/dashboard_roster_not_battle_id.png`
- `.codex_tmp/ui5e_structured_roster_replay/dashboard_backtest_nonzero.png`

검수 체크리스트:

- Dashboard Hero에 battle id가 없는가
- 실제 Pokemon species가 보이는가
- Ally/Enemy가 side/player 기준으로 나뉘는가
- backtest가 0/0이 아닌가
- Step3 replay validation 에러가 없는가

## 검수요약 문서

루트에 아래 파일을 작성하라.

- `DB코퍼스_UI5e_structuredPackageUsesRosterAndReplayNotGenericRoster_검수요약.md`

포함:

- 수정 파일
- 원인 분석
- raw table/session_state 보존 방식
- Dashboard roster source 변경
- backtest 0/0 방지 방식
- Step3 replay validation 호출 방식
- 테스트 결과
- 스크린샷 경로
- 남은 이슈

## 완료 보고 형식

```text
UI5e 완료 보고

1. 수정 파일
- ...

2. 구조화 패키지 데이터 소스
- raw tables:
- roster source:
- event source:

3. Step2
- prefill:
- 수정 가능:

4. Step3
- replay validation:
- TypeError 해결:

5. Dashboard
- Hero battle id 제거:
- 실제 roster 표시:
- backtest nonzero:

6. 테스트 결과
- ...

7. 스크린샷
- ...

8. 남은 이슈
- ...
```
