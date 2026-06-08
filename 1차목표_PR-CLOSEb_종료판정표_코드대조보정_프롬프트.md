# 1차목표 PR-CLOSEb — 종료판정표 코드대조 보정

## 목적

`1차목표_포켓몬복제_커버리지_종료판정.md`의 최종 결론은 대체로 맞지만, B절
`포켓몬 전투 규칙 표현력` 표에 실제 코드 상태와 맞지 않는 판정이 있다.

이번 작업은 **코드 변경이 아니라 종료판정 문서 보정**이다.

## 배경

현재 문서에는 다음처럼 적혀 있다.

```text
| contact effects | 부분완료 | EFFECTS/특성 구조에 종속 |
| ability/item triggered effects | 부분완료 | 등록된 EFFECTS 조건부 지원 |
| self-faint | 미완료 | |
| item swap | 미완료 | |
```

하지만 실제 코드 검수 결과, `self-faint`와 `item swap`은 이미 구현되어 있고 전투 루프에서
동작한다. `contact effects`와 `ability/item triggered effects`도 "엔진 구조 미완료"가 아니라
`등록된 EFFECTS/CONTACT_MOVES 기준 완료, 미등록 항목은 코퍼스 확장형 데이터/메커니즘 추가`
라고 보는 편이 정확하다.

## 코드 근거

다음 코드를 기준으로 문서를 보정하라.

- `modules/reference_gen5.py`
  - `EFFECTS`에 `Rough Skin`, `Iron Barbs`, `Rocky Helmet` 등록.
  - `Explosion`, `Self-Destruct`가 `effect.type == "self_faint"`로 등록.
  - `Trick`이 `effect.type == "swap_item"`로 등록.
  - `CONTACT_MOVES`가 접촉 조건 판정용으로 존재.
- `modules/engine.py`
  - `_act_effect_dispatch()`가 `game_config["mechanisms"]["effects"]`를 phase별로 dispatch.
  - `_eff_cond_ok()`가 `condition.contact`를 `current_move.contact`로 판정.
  - `_eff_swap_item()`이 Trick류 아이템 교환 및 `item_stat_mults` 보정을 수행.
  - `effect.type == "self_faint"` 처리에서 사용자 HP를 0으로 만든다.
- `modules/step2_system_definition.py`
  - UI/정의 surface에서 지원 effect type 목록에 `self_faint`, `swap_item`이 포함되어 있다.

## 직접 검수 결과

다음 직접 프로브가 통과했다.

```text
Explosion self_faint OK
Trick swap_item OK
Contact Rough Skin OK
```

확인 의미:

- `Explosion` 사용 후 사용자 HP가 0이 된다.
- `Trick` 사용 후 actor/target의 item이 교환된다.
- `Body Slam(contact=True)`으로 `Rough Skin` 보유자를 타격하면 공격자 HP가 1/8 감소한다.

## 정규 검증 결과

현재 작업트리에서 다음 검증도 통과했다.

```text
python -X utf8 -m py_compile modules/engine.py modules/per_battle_backtest.py modules/step6_dashboard.py modules/mechanism_detect.py modules/mechanism_commit.py run_mechdetect.py run_mechcommit.py test_i13.py test_i14.py test_i15_integration_smoke.py test_mechanism_detect_aliases.py test_mechanism_commit_canonical.py
python -X utf8 test_i13.py
python -X utf8 test_i14.py
python -X utf8 test_i15_integration_smoke.py
python -X utf8 test_mechanism_detect_aliases.py
python -X utf8 test_mechanism_commit_canonical.py
python -X utf8 run_mechdetect.py
python -X utf8 run_mechcommit.py
```

요약:

- I13/I14/I15 통합 DB-log IR 검증 통과.
- mechanism detect/commit canonical 검증 통과.
- `run_mechdetect.py`의 미모델(NO) 목록은 비어 있음.
- `run_mechcommit.py`는 Hail canonical 경고 없이 EFFECTS block을 출력함.

## 수정 지시

`1차목표_포켓몬복제_커버리지_종료판정.md`만 수정하라.

### 1. B절 표 판정 보정

다음 취지로 바꾸라.

```text
| contact effects | 구조 완료 / 등록분 완료 | Rough Skin/Iron Barbs/Rocky Helmet + CONTACT_MOVES 기준. 미등록 접촉무브는 코퍼스 확장형 데이터 추가 |
| ability/item triggered effects | 구조 완료 / 등록분 완료 | registered EFFECTS 조건부 지원. 신규 특성/도구는 RE 루프에서 추가 |
| self-faint | 완료 | Explosion/Self-Destruct |
| item swap | 완료 | Trick, item_stat_mults 보정 포함 |
```

표현은 문서 톤에 맞게 다듬어도 되지만, `self-faint`와 `item swap`을 `미완료`로 남기면 안 된다.

### 2. "아직 1차목표에 남은 꼬리" 해석 보정

남은 꼬리 표의 의미를 다음처럼 분명히 하라.

- 남은 꼬리는 "엔진 핵심 결함"이 아니다.
- 선택 코퍼스가 실제로 호출할 때 RE 루프/사용자 개입으로 추가할 catalog-tail/mechanism-tail이다.
- 이미 구현된 `Explosion`, `Self-Destruct`, `Trick`, 접촉 반동은 남은 꼬리로 다시 분류하지 않는다.

### 3. 검수 보정 메모 추가

문서 어딘가에 짧게 다음 내용을 추가하라.

- PR-CLOSEb에서 코드대조 검수 결과, `self-faint`, `item swap`, 등록된 contact effects는 실제 전투 루프에서 동작 확인됨.
- 정규 검증 명령도 통과함.
- 최종 판정은 기존처럼 `조건부 완료` 유지.

## 금지

- 엔진 코드나 테스트 코드는 수정하지 마라.
- 문서 결론을 `미완료`로 후퇴시키지 마라.
- "포켓몬 전체 세대 완전 복제"와 "1차 목표의 선택 코퍼스 복제 가능성"을 혼동하지 마라.

## 완료 조건

- `1차목표_포켓몬복제_커버리지_종료판정.md`에서 `self-faint`와 `item swap`이 더 이상 `미완료`가 아니다.
- contact/ability/item 효과가 "구조 구현"과 "코퍼스별 카탈로그 확장"으로 분리되어 설명된다.
- 최종 판정은 `조건부 완료`로 유지된다.
- 문서 수정 외 코드 변경이 없다.
