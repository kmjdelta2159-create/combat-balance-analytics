# 1차목표 PR-CLOSEd — 종료판정 표현 정밀화

## 배경

PR-CLOSEc 결과로 `1차목표_포켓몬복제_커버리지_종료판정.md`가 CORPUS1~4b 이후의 DB-log 검증 루프를 잘 반영했다.

최신 테스트도 통과했다.

다만 문서 표현 중 몇 곳이 실제 의도보다 과하게 읽힐 수 있다.

문제는 코드 결함이 아니라 종료판정 문서의 표현 정확도다.

## 보정 목표

1차 목표의 판정 의미를 다음처럼 유지한다.

```text
포켓몬의 모든 예외 규칙을 사전 등록했다는 뜻이 아니라,
포켓몬 복제에 필요한 핵심 전투 구조와 DB-log 기반 검증/개입 루프가 완성됐다는 뜻에서 조건부 완료다.
```

그러나 문서가 “모든 contact/ability/item 카탈로그가 완전 등록됨” 또는 “제품 루프가 완벽히 끝남”처럼 오해되지 않게 표현을 정밀화한다.

## 수정 대상

파일:

- `1차목표_포켓몬복제_커버리지_종료판정.md`

## 수정 요구사항

### 1. contact / ability-item 상태 표현 되돌리기

현재:

```md
| contact effects | 완료 | Rough Skin/Iron Barbs/Rocky Helmet + CONTACT_MOVES 기준. 미등록 항목은 RE 루프 처리 |
| ability/item triggered effects | 완료 | registered EFFECTS 조건부 지원. 신규 특성/도구는 RE 루프에서 추가 |
```

권장:

```md
| contact effects | 구조 완료 / 등록분 완료 | Rough Skin/Iron Barbs/Rocky Helmet + CONTACT_MOVES 기준. 미등록 항목은 RE 루프 처리 |
| ability/item triggered effects | 구조 완료 / 등록분 완료 | registered EFFECTS 조건부 지원. 신규 특성/도구는 RE 루프에서 추가 |
```

이유:

- 이전 PR-CLOSEb에서 의도적으로 `구조 완료 / 등록분 완료`로 정리했던 항목이다.
- 현재 구현은 등록된 contact/effect 카탈로그와 이를 확장하는 RE 루프가 완료된 것이지, 모든 포켓몬 특성/도구/접촉 카탈로그를 사전 등록했다는 의미가 아니다.

### 2. “완벽히” 표현 완화

현재 문서에 있는 과한 표현을 완화한다.

예시:

```md
UI가 export한 JSON이 실제 CLI에서 완벽히 호환되는지 검증
```

권장:

```md
UI가 export한 JSON이 실제 CLI 입력 계약과 호환되는지 검증
```

현재:

```md
이 루프는 이제 단순 기능 목록이 아니라 아래 형태로 닫혀서 완벽히 연결되어 있다:
```

권장:

```md
이 루프는 이제 단순 기능 목록이 아니라 아래 형태의 일관된 계약으로 연결되어 있다:
```

### 3. trailing whitespace 제거

`git diff --check`가 다음을 보고한다.

```text
1차목표_포켓몬복제_커버리지_종료판정.md:142: trailing whitespace.
```

해당 trailing whitespace를 제거한다.

### 4. 유지해야 하는 내용

다음 내용은 유지한다.

- DB 로그가 주 입력이라는 전제
- HTML/Replay가 주 경로가 아니라는 설명
- Streamlit은 최종 제품 UI가 아니라 검증 콘솔이라는 설명
- Streamlit 교체는 1차 목표 필수 조건이 아니라 1차 이후 제품화/이주 작업이라는 분리
- CORPUS1~4b 검증 루프 반영
- `조건부 완료` 최종 판정

## 금지사항

- `조건부 완료`를 `완전 완료`로 바꾸지 말 것.
- HTML/replay를 주 입력처럼 다시 쓰지 말 것.
- contact/ability/item 계열을 “전부 완료”처럼 과장하지 말 것.
- 테스트 목록을 제거하거나 약화하지 말 것.

## 검증 명령

문서 보정 후 아래를 확인한다.

```powershell
git diff --check -- "1차목표_포켓몬복제_커버리지_종료판정.md"

$py='C:\Users\kmjde\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -X utf8 test_db_corpus_fixture_manifest.py
& $py -X utf8 test_step6_export_schema_cli_roundtrip.py
& $py -X utf8 test_step6_db_corpus_schema_export.py
& $py -X utf8 test_db_corpus_backtest_report.py
& $py -X utf8 test_step6_mismatch_report.py
& $py -X utf8 test_i15_integration_smoke.py
& $py -X utf8 test_mechanism_detect_aliases.py
& $py -X utf8 test_mechanism_commit_canonical.py
```

## 완료 기준

- 종료판정 문서가 과장 없이 정확해진다.
- `contact effects`, `ability/item triggered effects`는 `구조 완료 / 등록분 완료`로 표현된다.
- “완벽히” 표현이 제거되거나 완화된다.
- `git diff --check`가 trailing whitespace를 보고하지 않는다.
- 최신 corpus/export/regression 테스트가 통과한다.
