# 1차목표 PR-CORPUS1 — 선택 코퍼스 백테스트 리포트 하니스

> **폐기 / 보류:** 이 프롬프트는 기존 Showdown 리플레이 HTML 하니스를 주 경로로 삼고 있어
> 현재 앱의 DB 로그 입력 전제와 맞지 않는다. Step1 업로드는
> `csv/xlsx/xls/json/tsv/txt/parquet`를 받으며, 최종 목표도 DB 로그 기반이다.
> 이 파일 대신 `1차목표_PR-CORPUS1b_DB로그코퍼스백테스트리포트_프롬프트.md`를 사용하라.

## 목적

1차목표 종료판정의 남은 조건은 “포켓몬을 임의 상황까지 완전 복제했다”가 아니라,
**선택 코퍼스가 주어졌을 때 현재 복제 엔진/RE 루프가 어디까지 맞고, 어디서 갈라지는지
반복적으로 측정할 수 있는가**이다.

현재 단일 리플레이용 도구는 있다.

- `run_xval.py`
- `run_mechdetect.py`
- `run_mechcommit.py`
- `modules/fullbattle_run.py`
- `modules/fullbattle_diff.py`

이번 PR은 새 전투 규칙을 구현하기 전에, 여러 리플레이/코퍼스를 한 번에 돌려
다음 항목을 표로 남기는 **코퍼스 백테스트 리포트 하니스**를 만든다.

- 데이터 결측
- 풀런 가능 여부
- 첫 구조적 divergence
- 구조적 divergence 수
- 미모델 메커니즘 후보 수
- 다음 조치 분류

이 작업은 “코퍼스가 부르는 꼬리”를 식별하기 위한 진입점이다.

## 현재 직접 확인한 샘플 실행 결과

### 1. `Gen5OU-2026-newatmons-bantyranitar.html`

```text
HP 표기: 퍼센트(max=100)
등장 종 10
등장 무브 22
BASE 결측 0
SETS 결측 0
MOVES 결측 0

풀배틀 divergence:
첫 구조적 divergence: T0 Magnezone [missing]
총 6건 (구조적 6건)
```

### 2. `Gen5OU-2015-05-11-reymedy-leftiez.html`

```text
HP 표기: 퍼센트(max=100)
등장 종 12
등장 무브 20
BASE 결측 0
SETS 결측 0
MOVES 결측 0

풀배틀 divergence:
첫 구조적 divergence: T0 Gengen [missing]
총 55건 (구조적 25건)
```

### 3. `OUMonotype-2014-01-29-kdarewolf-onox.html`

```text
HP 표기: 퍼센트(max=100)
등장 종 6
등장 무브 11
BASE 결측 5
SETS 결측 5
MOVES 결측 8

엔진 풀런 보류: 종족값/무브/세트 데이터 결측
```

이 세 결과를 수동으로 읽는 대신, 같은 정보를 자동 표로 뽑아야 한다.

## 수정 대상

가능하면 신규 파일만 추가한다.

- 신규: `run_corpus_backtest.py`
- 신규 가능: `test_corpus_backtest_report.py`

필요한 경우에만 아래 파일에 작은 순수 helper를 추가해도 된다.

- `run_xval.py`

수정 금지:

- `modules/engine.py`
- `modules/fullbattle_run.py`
- `modules/fullbattle_diff.py`
- `modules/mechanism_detect.py`
- `modules/mechanism_commit.py`
- `modules/reference_gen5.py`

## 구현 지시

### 1. `run_corpus_backtest.py` 추가

CLI 형태:

```bash
python -X utf8 run_corpus_backtest.py
python -X utf8 run_corpus_backtest.py Gen5OU-*.html
python -X utf8 run_corpus_backtest.py Gen5OU-2026-newatmons-bantyranitar.html OUMonotype-2014-01-29-kdarewolf-onox.html
```

기본 입력:

```text
*.html
```

단, 너무 넓게 잡히는 것이 부담이면 현재 루트의 세 샘플 HTML만 기본으로 잡아도 된다.

### 2. 각 파일별 report row 생성

각 HTML 파일마다 다음 정보를 계산하라.

```text
file
hp_mode                         # percent / absolute
species_count
move_count
missing_base_count
missing_set_count
missing_move_count
missing_base
missing_set
missing_move
run_status                      # ran / data_blocked / error
turn_range
total_divergences
structural_divergences
first_divergence_turn
first_divergence_id
first_divergence_kind
first_divergence_log
first_divergence_engine
modeled_mechanism_count
unmodeled_mechanism_count
unmodeled_mechanisms
next_action
```

`next_action` 분류 예:

- `fill_reference_data`: BASE/SETS/MOVES 결측이 있으면
- `inspect_initial_mapping`: 첫 divergence가 T0 missing이면
- `inspect_mechanism_tail`: 미모델 메커니즘이 있으면
- `inspect_damage_or_state_tail`: 데이터는 충분하지만 구조 divergence가 있으면
- `passed_or_low_divergence`: 구조 divergence가 없거나 매우 적으면
- `error`: 실행 예외

분류명은 달라도 되지만 의미는 보존하라.

### 3. 내부 재사용

가능하면 기존 함수를 재사용하라.

- `modules.showdown_trace.parse_replay`
- `run_xval.data_needs`
- `modules.fullbattle_run.run_and_diff`
- `modules.fullbattle_run.format_report`
- `modules.mechanism_detect.detect_mechanisms`

`run_xval.py`의 `XVAL_SET_OVERRIDE`가 특정 전투 전용이면, 그대로 복사해 전역 적용하지 말고
해당 파일명에만 조건부 적용하라.

예:

```python
if basename == "Gen5OU-2026-newatmons-bantyranitar.html":
    set_override = {...}
else:
    set_override = None
```

### 4. 출력

콘솔에 사람이 읽을 수 있는 요약을 출력하라.

예:

```text
=== Corpus Backtest Summary ===
file                                      status        data_missing  structural  first
Gen5OU-2026-newatmons-bantyranitar.html  ran           0/0/0         6           T0 Magnezone missing
Gen5OU-2015-05-11-reymedy-leftiez.html   ran           0/0/0         25          T0 Gengen missing
OUMonotype-2014-01-29-kdarewolf-onox.html data_blocked 5/5/8         -           fill_reference_data
```

그리고 파일 출력도 남겨라.

권장 경로:

```text
검증_코퍼스/corpus_backtest_summary.csv
검증_코퍼스/corpus_backtest_summary.md
```

디렉터리가 없으면 생성한다.

### 5. 리포트 해석 문구

Markdown 리포트 상단에 다음 의미를 짧게 남겨라.

- 이 리포트는 최종 게임 완전 복제 판정표가 아니다.
- 선택 코퍼스가 요구하는 데이터/메커니즘/상태 divergence를 분류하는 도구다.
- 결측 데이터는 엔진 결함이 아니라 reference data 추가 작업으로 분리한다.
- 구조 divergence는 다음 PR에서 tail mechanism 또는 mapping 보정으로 닫는다.

## 테스트

가능하면 `test_corpus_backtest_report.py`를 추가하라.

테스트 범위:

1. data-needs summary row가 결측 count를 정확히 담는다.
2. `next_action` 분류가 결측 데이터면 `fill_reference_data`가 된다.
3. first divergence가 T0 missing이면 `inspect_initial_mapping`이 된다.
4. unmodeled mechanism 목록이 있으면 `inspect_mechanism_tail`이 된다.
5. Markdown/CSV output writer가 임시 디렉터리에 파일을 만든다.

실행 검증:

```bash
python -X utf8 -m py_compile run_corpus_backtest.py test_corpus_backtest_report.py
python -X utf8 test_corpus_backtest_report.py
python -X utf8 run_corpus_backtest.py Gen5OU-2026-newatmons-bantyranitar.html Gen5OU-2015-05-11-reymedy-leftiez.html OUMonotype-2014-01-29-kdarewolf-onox.html
```

기존 회귀:

```bash
python -X utf8 test_i15_integration_smoke.py
python -X utf8 test_mechanism_detect_aliases.py
python -X utf8 test_mechanism_commit_canonical.py
```

## 금지

- 이번 PR에서 엔진 동작을 수정하지 마라.
- 이번 PR에서 reference data를 대량 추가하지 마라.
- 이번 PR에서 특정 divergence를 억지로 숨기지 마라.
- 포켓몬 전용 분기를 엔진에 넣지 마라.
- “데이터 결측”과 “엔진 구조 결함”을 섞어 말하지 마라.

## 완료 조건

- 여러 HTML 코퍼스를 한 번에 실행할 수 있다.
- 데이터 결측으로 풀런 불가한 파일과 풀런 가능한 파일이 구분된다.
- 풀런 가능한 파일의 첫 구조적 divergence와 divergence 수가 표로 남는다.
- 미모델 메커니즘 후보 수가 함께 남는다.
- `검증_코퍼스/corpus_backtest_summary.csv`와 `.md`가 생성된다.
- 기존 I15 및 mechanism tests가 통과한다.
