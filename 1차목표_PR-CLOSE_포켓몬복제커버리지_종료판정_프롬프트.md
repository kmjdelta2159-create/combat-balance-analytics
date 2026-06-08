# 1차목표 PR-CLOSE — 포켓몬 복제 커버리지 종료판정 문서

## 목적

1차목표는 최종목표로 가는 과정에서 **포켓몬 전투 복제에 필요한 기능군을 구현하고 검증하는 것**이다.

최근 작업으로 DB-log IR 검증축과 RE 도구축이 많이 닫혔다.

- action/move trace
- switch trace
- faint incoming trace
- initial on-field
- damage vs hp_delta
- resource delta score
- observed resource filter
- state snapshot score
- 통합 backtest smoke
- mechanism detect alias / modeled 판정 정규화
- mechanism commit canonical 호환

이제 필요한 것은 새 기능을 무작정 더 붙이는 것이 아니라, **1차목표 기준에서 현재 커버리지를 정확히 판정하는 문서**다.

이번 PR은 코드 변경이 아니라 종료판정/커버리지 문서를 작성한다.

## 산출물

루트에 다음 문서를 새로 만든다.

```text
1차목표_포켓몬복제_커버리지_종료판정.md
```

## 금지

- `.py` 코드 수정 금지.
- 테스트를 새로 고치거나 기능을 추가하지 말 것.
- 과장 금지.
- “포켓몬 완전 복제 완료”라고 쓰지 말 것.
- “DB-log replay smoke가 맞았으니 모든 포켓몬 기능 완료” 같은 과잉 결론 금지.
- 비-스탯 정보 게임까지 된다는 식의 범위 확장 금지.

## 문서가 답해야 할 질문

### 1. 1차목표 정의

문서 첫머리에 아래 정의를 명확히 적는다.

```text
최종목표: DB 로그와 전문가 개입을 통해 스탯 기반 턴제 전투 게임을 범용적으로 복제하는 시뮬레이터.
1차목표: 그 최종목표로 가는 첫 실증 대상으로 포켓몬 전투를 복제할 수 있는 기능군과 검증 루프를 확보하는 것.
```

중요:

- 포켓몬은 최종 대상이 아니라 첫 실증 대상.
- DB-log IR/backtest는 목표 그 자체가 아니라 복제 기능을 검증하는 도구.
- “한 로그 맞추기”가 아니라 “포켓몬식 전투 기능군을 generic 구조로 담을 수 있는가”가 기준.

### 2. 현재 완료 축

아래 축별로 “완료/부분완료/미완료/조건부”를 표로 정리한다.

#### A. 전투 실행 core

- 턴/페이즈 구조
- 행동 순서 / speed
- priority overlay
- trace move
- trace switch
- faint incoming replacement
- initial active/on-field
- deterministic state capture

#### B. 포켓몬 전투 규칙 표현력

- 타입 상성
- STAB
- critical
- damage random factor
- burn/status damage
- toxic progressive
- weather damage/heal
- entry hazard
- contact effects
- recoil
- fixed damage
- healing moves
- self-faint
- item swap
- stat stage
- switch-in effects
- ability/item triggered effects

#### C. DB-log 검증 IR

- battle/participant ID preservation
- move trace from DB role columns
- switch trace from DB role columns
- faint incoming from DB role columns
- state snapshot score
- action damage score
- damage vs hp_delta distinction
- resource state snapshot
- action resource delta score
- observed-resource filter
- strict-extra mode
- integrated smoke

#### D. RE/user intervention loop

- mechanism detect
- modeled/unmodeled 판정
- alias/canonical handling
- condition inference
- commit to EFFECTS block
- Streamlit surface
- catalog-only false positive 방지

#### E. cross-game/generic evidence

- FF7 known-answer 하니스
- generic damage/resource/state IR가 포켓몬 전용이 아닌지
- 어디까지가 입증됐고 어디부터는 아직 주장하면 안 되는지

### 3. 검증 명령과 결과

가능하면 아래 명령을 실제로 실행하고 결과를 문서에 요약한다.

```powershell
python -X utf8 test_i13.py
python -X utf8 test_i14.py
python -X utf8 test_i15_integration_smoke.py
python -X utf8 test_mechanism_detect_aliases.py
python -X utf8 test_mechanism_commit_canonical.py
python -X utf8 run_mechdetect.py
python -X utf8 run_mechcommit.py
```

환경상 `python`이 없으면 bundled python 경로를 써도 된다.

문서에는 “무엇을 증명하는 테스트인지”를 같이 적는다.

### 4. 아직 1차목표에 남은 꼬리

아래를 반드시 별도 섹션으로 정리한다.

#### 필수로 남았는지 여부 판단

각 항목을 아래 중 하나로 분류한다.

- `1차 종료 전 필수`
- `코퍼스가 부르면 처리`
- `2차 이후`
- `이미 구현/검증됨`

검토 항목:

- Substitute
- Transform
- Protect류
- charge/recharge
- lock-in move
- forced switch / phazing
- pivot move
- PP / move availability
- item consumption
- ability suppression/change
- terrain/room
- complex multi-turn volatile status
- doubles/multi-target
- AI/controller policy
- full teambuild/sets inference

중요:

- “포켓몬 전체 세대 완전 복제” 기준으로 쓰지 말 것.
- 1차목표는 generic 복제 시스템의 첫 실증으로서 포켓몬 주요 기능군과 검증 루프를 확보하는 것이다.

### 5. UI 표현력 판정

사용자가 이전에 물었던 질문에 답해야 한다.

```text
지금 부족한 게 UI표현력인가, 복제쪽 결함인가?
```

문서에서는 다음 구분을 명확히 한다.

- 복제 core의 큰 축은 어디까지 닫혔는가
- UI는 미관 문제가 아니라 “정의/수정/검수 가능한 surface” 문제다
- 지금 남은 UI는 full redesign인지, mismatch/report 정리인지, mechanism edit surface인지
- 1차 종료 전 필수 UI와 2차 이후 UI를 분리한다

### 6. 최종 판정

마지막에 아래 형식으로 결론을 낸다.

```text
판정: 1차목표는 [완료 / 조건부 완료 / 미완료]로 본다.

근거:
- ...

조건:
- ...

다음 액션:
1. ...
2. ...
3. ...
```

주의:

- 무조건 “완료”로 몰지 말 것.
- `조건부 완료`가 맞으면 그렇게 쓴다.
- 조건부라면 남은 조건을 구체적으로 적는다.

## 권장 결론 형태

현재까지의 흐름상, 무리 없는 결론은 대략 다음 중 하나일 가능성이 높다.

```text
조건부 완료:
포켓몬 복제를 위한 핵심 실행/검증/RE 루프는 닫혔다.
다만 포켓몬 전체 메커니즘 완전복제가 아니라, 선택 코퍼스 기준으로 남은 꼬리를 식별하고 처리하는 상태다.
```

또는

```text
거의 완료:
1차목표를 “포켓몬 주요 싱글 전투 기능군 + DB-log/trace 검증 루프 확보”로 보면 완료에 가깝다.
1차목표를 “임의 포켓몬 전투 전체 완전 복제”로 잡으면 아직 미완료다.
```

문서 작성자는 코드와 테스트 결과를 보고 스스로 판정한다.

## 완료 기준

- `1차목표_포켓몬복제_커버리지_종료판정.md`가 생성됨.
- 테스트 실행 결과가 요약됨.
- 완료/부분완료/남은 꼬리가 표로 정리됨.
- 1차목표와 최종목표의 관계가 정확히 반영됨.
- 다음 액션이 3개 이하로 정리됨.

## 보고 형식

작업 후 아래를 요약한다.

1. 생성한 문서
2. 실행한 검증 명령
3. 최종 판정 한 줄
4. 1차 종료 전 남은 필수 조건이 있는지
