# UI 정리 설계안 — step2(System Definition) 탭 구조화

> 문제: `render_system_definition()`(modules/step2_system_definition.py, 약 121~1072) 한 함수에
> 6개 대형 섹션이 세로로 쌓여 *끝없는 스크롤*. 메커니즘 RE 패널(PR-T3)까지 얹혀 더 길어졌다.
> 정리안 = **`st.tabs`로 묶어 스크롤을 탭 전환으로**. *이 문서는 계획만* — 적용은 보고 결정.

## 0. 현재 구조 (라인 기준)

| 라인 | 섹션 | 성격 |
|---|---|---|
| 125 | 가드 `return`(CSV 없음) | 상단 가드 |
| 127 | 🔬 트레이스 메커니즘 RE (PR-T3) | 메커니즘 |
| ~150 | 🎛️ Game Profile(모듈 탐지) | 개요 |
| 155–303 | 🔍 Data Mapping & Live Formula Validator | 데이터·공식 |
| 306–411 | 🎯 Move System(무브표·라우팅·타입상성표·STAB) | 무브·타입 |
| 413–460 | 🏷️ Tag Dictionary Mapping | 태그 |
| 462–487 | 🔄 Logic Execution Order(페이즈 드래그) | 실행순서 |
| 488–517 | 🧩 Channel Mapping(expander) | 채널 |
| 518–828 | 🍃 동적 메커니즘 부착 + Switch 모델 | 메커니즘 |
| 829 | 🚀 파이프라인 시작 버튼 | 하단 액션 |
| 913 / 1072 | `return False/True` | 하단 반환 |

중간 `return` 없음(가드 125·하단 913/1072만). 안전.

## 1. 핵심 안전점 — `st.tabs`는 스코프가 아니다

`with tab:` 블록 안에서 만든 변수(매핑 결과·`is_valid`·세션값)는 **블록 밖(하단 버튼)에서 그대로
접근된다** — `st.tabs`는 *레이아웃 컨테이너*일 뿐 파이썬 스코프를 만들지 않는다. 따라서 섹션을
탭으로 감싸도 하단 버튼(829)의 `is_valid` 계산·`return`(1072)이 깨지지 않는다. 이게 탭화가
가능한 이유다.

## 2. 제안 구조 — 4탭

가드(125) → Game Profile(개요, 탭 위 유지) → **`tabs = st.tabs([...])`** → 하단 버튼·nav·return.

| 탭 | 담는 섹션(현 라인) | 이유 |
|---|---|---|
| **📊 데이터·공식** | Data Mapping & Formula Validator (155–303) | 컬럼 매핑·데미지식·SR |
| **🎯 무브·타입** | Move System (306–411) | 무브표·카테고리 라우팅·타입상성표·STAB |
| **⚙️ 메커니즘·태그** | 🔬 메커니즘 RE(127) + Tag Dictionary(413–460) + Channel Mapping(488–517) + 동적 메커니즘·Switch(518–828) | 발동형/태그/채널/동적 — *메커니즘 축* 한곳 |
| **🔄 실행순서** | Logic Execution Order (462–487) | 페이즈 White-Box |

- **Game Profile**은 탭 위 개요로 유지(전 탭 공통 컨텍스트).
- **하단**(파이프라인 시작·이전/다음·return)은 탭 밖 그대로 — 어느 탭에서든 보이는 고정 액션.
- 메커니즘 RE(127)가 Data Mapping(155) 위에 있던 걸 ⚙️탭으로 이동(메커니즘 축 응집).

## 3. 리팩터 접근 (적용 시)

1. 가드(125) 아래, Game Profile 호출 뒤에 `t_data, t_move, t_mech, t_logic = st.tabs([...])`.
2. 각 섹션 블록을 해당 `with t_*:` 안으로 이동 + **한 단계 들여쓰기**(약 700줄). *로직·위젯 key·
   순서 무변* — 순수 레이아웃 이동.
3. 하단 버튼·nav·return은 탭 밖(현 위치) 유지.
4. 섹션 간 의존(예: Move System에서 만든 매핑을 Logic이 읽음)은 스코프 무관(§1)이라 무영향.

> 위험: 700줄 재들여쓰기 = 들여쓰기 오류·key 누락 위험. 완화 = *기능 무변(레이아웃만)* 원칙 +
> 위젯 key·세션 키 diff 0 확인. Streamlit이라 샌드박스 검증 불가 → 앱 로드·각 탭 캡처로 확인.

## 4. 검증 (적용 후, 앱사이드)

1. 앱 로드 에러 없음(`import` OK). 2. step2에 4탭 표시·각 탭에 해당 섹션 전부. 3. 매핑→
   파이프라인 시작 버튼 동작(is_valid 계산 무변). 4. 다음 단계 진행 정상(return 무변). 각 탭 캡처.

## 5. 더 가벼운 대안 (탭화가 부담이면)

무거운 섹션만 `st.expander(expanded=False)`로: 타입상성표(380)·Logic Execution(462)·동적
메커니즘(518). 재들여쓰기 최소·안전, 단 탭만큼 깔끔하진 않음.

## 6. 별개 — 검출기 작은 정련(메커니즘 RE, UI와 무관)

골든 업로드에서 본 것: `sandstorm`↔`sand`(정규화 키 불일치로 모델드 오판)·`psn`(EFFECTS 미보유)·
`Life Orb`·`move: Wish`(미모델). 검출기 `_norm`에 별칭(sandstorm→sand) 추가 + modeled 판정에
별칭 반영하면 오판이 준다. UI 정리와 분리된 1줄짜리 후속(PR-T1b 후보).
