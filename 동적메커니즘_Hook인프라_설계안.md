# 동적 메커니즘 hook 인프라 설계안

본 phase 작업의 출발 설계 문서다. engine.py·turn_manager.py·per_battle_backtest.py·step2_system_definition.py 정독으로 확정한 사실 위에서, 9단계 파이프라인에 동적 메커니즘이 작동할 자리를 만드는 인프라를 설계한다. 첫 실제 PR 대상은 사용자가 Leftovers로 확정했다. 이 문서는 인프라 전체를 다루되 Leftovers를 구체화하고, 후속 메커니즘은 난이도·선행조건만 정리한다.

본 문서는 검토용 설계안이다. 코드 변경은 한 줄도 들어 있지 않다. 사용자가 이 설계를 승인하면 그 다음에 Antigravity 프롬프트 빌더로 진입한다.

## 1. 정찰로 확정한 사실

행동 파이프라인은 `action_registry.py`의 단순한 key→func 맵 위에서 돈다. engine.py L606~L616이 11개 액션(PASSIVE_START, STAT_CALC, TARGET_SELECT, MOVE, MOVE_SELECT, DAMAGE_CALC, ELEMENT_MULT, CRIT_CALC, APPLY_DAMAGE, ON_HIT, DEATH_CHECK)을 등록한다. run_simulation L786~L825이 combat_flow를 파싱해 all_actions로 만든 뒤 TARGET_SELECT 피벗 기준으로 pre-target / per-target 두 묶음으로 가른다. TARGET_SELECT·MOVE·MOVE_SELECT를 자동 삽입하는 로직이 이미 있으므로(L794~L812), 새 hook 액션을 등록하고 흐름에 자동 삽입하는 길은 이미 열려 있다.

캐릭터 instance는 클래스가 아니라 평범한 dict다(per_battle_backtest L53~L70, engine L749~L770). 스탯은 최상위 키, gimmicks·resources는 하위 dict, movepool·active_states·position·deck는 선택 필드. 따라서 current_type·boost_levels·substitute_hp 같은 동적 필드 추가는 instance 초기화 지점에서 setdefault 한 줄이면 된다.

game_config 조립은 step2 L535~L562 한 곳에 모여 있다. 현재 키는 channels·categories·type_table·type_columns·stab_factor다. mechanisms 키를 끼울 자리가 명확하다.

기존 이벤트 시스템(`_broadcast_phase_event`/`_notify_event`, L183~L228)은 active_states의 수명(expire_count)을 차감·소멸시키는 일만 한다. 어떤 메커니즘 효과도 적용하지 않는다. 이건 buff/debuff의 만료 타이머지, 턴마다 무언가를 실행하는 hook이 아니다. 능동 효과(Leftovers 같은 턴 종료 회복)는 이 위에 못 얹는다 — 실제로 효과를 수행하는 액션 함수가 따로 필요하다.

`get_effective_stat`(L160~L180)은 이미 active_states를 합산하고 PERMANENT 트리거를 지원한다. 즉 영구 percent state로 누적 boost(Calm Mind류)는 인프라상 거의 표현된다. 막힌 건 무브 선택기(MOVE_SELECT, L378~L416)가 기대 데미지 최대만 골라 위력 0인 boost 무브를 절대 선택하지 않는다는 점이다. 이건 전략 의사결정 모델(§5)의 영역이다.

## 2. 네 격차의 정직한 난이도

ON_TURN_END 액션 슬롯이 통째로 비어 있다. turn_manager L129~L130이 매 캐릭터 턴 뒤 TURN_END 이벤트를 브로드캐스트하지만, TURN_END는 레지스트리 등록 액션이 아니라 이벤트 브로드캐스트일 뿐이다. StandardTurnExecutor(L38~L56)는 pre-target과 per-target만 돌리고 "내 턴 종료" 액션 자리가 없다. Leftovers는 이 빠진 슬롯을 신설해야 작동한다.

우선도 무브는 핸드오프 추정보다 무겁다. turn_manager 정렬 키는 L106~L108에서 `(-speed, id)`뿐이고 이 정렬은 라운드 시작에 한 번에 일어난다. 그런데 각 캐릭터가 어떤 무브를 쓸지는 자기 턴 안 MOVE_SELECT에서 결정된다. 진짜 무브별 우선도는 "전원 무브 선택 → 우선도·속도로 정렬 → 실행"의 2단계 턴을 요구하는데, 우리 엔진은 "정렬 먼저, 행동하며 무브 결정"이라 정렬 시점에 우선도를 읽을 수 없다. 캐릭터 고정 우선도면 정렬 키에 항 추가로 충분하지만, 무브별 우선도는 턴 모델 변경이 선행이다.

교체(switch) 모델은 자리 자체가 없다. per_battle_backtest는 한 전투를 N행으로 잘라 절반은 Ally, 절반은 Enemy로 두고 전원을 동시에 필드에 올린다(L90~L103). 트레이너-벤치 구분이 없어 누가 빠지고 들어오는 개념이 없다. 따라서 ON_SWITCH·Trace(진입 시 특성 복사)·교체 전략은 substrate가 0이다. 메가·Protean·Substitute는 기존 per-character dict 위에서 가능하지만, 교체 계열은 전투 모델(active/bench 분리) 신설이 선행돼야 한다.

Calm Mind류 누적 boost는 인프라상 거의 되지만 무브 선택기가 막는다(§1 마지막 단락).

## 3. 인프라 3종 추가 (모든 후속 메커니즘의 공통 토대)

### 3-1. 턴 종료 액션 슬롯 (executor 일반화)

StandardTurnExecutor를 pre/per 2슬롯에서 pre/per/post 3슬롯으로 일반화한다. post-target 액션은 타겟과 무관하게 캐릭터 단위로 per-target 루프 종료 후 1회 실행된다. run_simulation의 흐름 분리(L814~L825)에 post 그룹을 추가하고, 새 hook 키(ON_TURN_END)를 그 그룹으로 라우팅한다. 자동 삽입 로직(L794~L812 패턴)을 따라 ON_TURN_END가 흐름에 없으면 캐릭터 턴 끝에 자동 삽입한다.

이 슬롯은 Leftovers뿐 아니라 상태이상의 턴 종료 데미지(독·화상), 보호막 자연 감쇠 등 후속 메커니즘이 공유한다. 일반화가 핵심이다.

### 3-2. instance 동적 상태 필드

instance 초기화(engine L749~L770의 참가자 루프, per_battle_backtest L53의 _row_to_inst)에서 동적 필드를 setdefault로 보장한다. 1차로는 Leftovers에 필드가 필요 없다(회복은 resources["HP"]를 직접 다룬다). 후속을 위한 필드 예약만 설계에 명시한다 — current_type(Protean), boost_levels(누적 boost 캡), substitute_hp(보조 HP 풀), status_condition(상태이상 토큰), mega_evolved(플래그). 이 필드들은 해당 메커니즘 PR에서 실제로 도입하고, 인프라 PR에서는 자리만 잡는다.

### 3-3. game_config["mechanisms"] 키 + step2 입력 UI

step2 L535~L562의 _gc 조립 블록에 mechanisms 키를 추가한다. step2에 "메커니즘 부착" expander를 신설해 사용자가 메커니즘을 부착한다.

부착 키잉에 설계 결정이 하나 있다. per_battle_backtest의 _row_to_inst는 instance name을 "log_row"로 덮어써(L53) 캐릭터 이름이 백테스트 instance에 남지 않는다. 따라서 캐릭터 이름으로 메커니즘을 부착하면 정확도 측정(백테스트)에는 반영되지 않고 라이브 단일 매치에만 적용된다. 백테스트까지 반영하려면 행에 보존되는 gimmick 컬럼 값으로 부착해야 한다(예: 사용자가 지정한 item 컬럼 == "Leftovers"). 1차 PoC는 gimmick 컬럼 값 기반 부착으로 설계해 백테스트 정확도에 반영되게 한다. 이 결정은 사용자 확인이 필요한 지점이다.

## 4. 첫 PR — Leftovers 구체 설계

대상 메커니즘은 턴 종료 시 max HP의 고정 비율(Pokemon 기본값 1/16 = 6.25%)을 회복한다. 사망 상태(HP 0 이하)면 회복하지 않는다. max를 넘기지 않는다.

엔진 변경은 세 가지다. 첫째, executor에 post-target 슬롯 신설(§3-1). 둘째, 새 액션 `_act_turn_end_heal`를 작성해 레지스트리에 ON_TURN_END 키로 등록한다. 이 액션은 ctx의 active_char가 mechanisms에서 leftovers 부착 대상인지 game_config로 판정하고, 대상이면 resources["HP"]를 percent만큼 회복한다. 셋째, run_simulation 흐름 분리에 ON_TURN_END 자동 삽입을 추가한다.

step2 변경은 메커니즘 부착 expander에 Leftovers 항목 추가다 — 부착 기준 gimmick 컬럼과 트리거 값, 회복 비율(기본 0.0625) 입력. game_config["mechanisms"]["leftovers"]에 저장한다.

검증은 표준 워크플로를 따른다. outputs/에 레퍼런스 하니스를 짜 Leftovers 부착 instance 한 쌍을 N턴 돌려 회복량이 정확히 max*percent씩 누적되는지, 미부착 instance는 회복 0인지, 사망 시 회복 멈추는지 단위 검증한다. Antigravity 납품 후에는 Grep 마커 확인, 변경 구역 Read 정독, 라인 수 산술, 라운드트립 MD5, 클린룸 py_compile으로 전사 무결성을 본다.

회복이 정확도(67.4% 권역)에 주는 영향은 미정이다. Leftovers는 장기전 유리 쪽으로 승부를 미세 조정하는 메커니즘이라 단발 데미지 모델엔 신호가 약할 수 있다. 측정은 합성 데이터 안에서만 의미가 있고, 외부 PS replay 같은 실제 데이터 수치는 여전히 미측정 상태다. PoC의 목적은 정확도 도약이 아니라 동적 hook 인프라가 실제로 작동함을 증명하는 것이다.

## 5. 후속 메커니즘 로드맵

인프라(§3)가 서고 Leftovers가 검증되면 다음을 한 개씩 PR한다. 각 PR은 엔진 hook + step2 입력 UI + 빌더·라운드트립·검증을 포함한다.

상태이상(독·화상)은 Leftovers와 같은 ON_TURN_END 슬롯을 재사용한다(회복 대신 데미지). 가장 가까운 후속이다. Protean은 ON_MOVE_USE hook 신설 + current_type 필드 + `_move_type_multiplier`/`_move_stab_multiplier`(L477~L502)가 current_type를 우선 참조하게 수정한다. Calm Mind류 누적 boost는 인프라상 거의 되지만 무브 선택기가 막으므로 전략 모델과 함께 가야 의미가 있다. Substitute는 APPLY_DAMAGE(L543~L569)에서 substitute_hp를 우선 흡수하게 한다 — resource.py의 라우팅 계층이 substrate로 쓸 수 있는지 추가 정찰이 필요하다. 우선도 무브와 교체 계열(Trace·메가 진화 타이밍 포함)은 턴 모델 변경이 선행이라 가장 뒤다.

전략 의사결정 모델 확장(§4-3 of 핸드오프)은 별도 축이다. 현재 MOVE_SELECT의 그리디(기대 데미지 최대)를 교체·boost·Substitute 타이밍까지 고려하는 정책으로 확장하는 일인데, 인프라와 메커니즘 라이브러리가 어느 정도 차고 난 다음이다. 그전에도 그리디로 메커니즘 작동 자체는 검증할 수 있다.

## 6. 정직한 한계 (흐리지 않는다)

이 인프라는 동적 차원의 "자리"를 만든다. 자리를 만드는 것과 Pokemon을 시뮬레이터로 복제하는 것은 다르다. Leftovers 하나가 작동해도 도구는 여전히 "시뮬레이터의 뼈대 + 정적 데미지 계산기 + 동적 메커니즘 한 종"이다. 교체 모델이 부재하는 한 Pokemon의 전투 흐름 전체는 재현되지 않는다. 측정값은 모두 통제 합성 환경 안 수치이고 외부 실제 데이터 수치는 미측정이다. 진행 보고에서 도구 위치를 과대 표현하지 않는다.

## 7. 다음 행동

이 설계안 승인 여부를 묻는다. 승인되면 첫 PR(Leftovers)의 Antigravity 프롬프트 빌더로 진입한다 — outputs/에 레퍼런스 하니스부터 짜고, executor 3슬롯 일반화와 ON_TURN_END 액션의 정확한 변경 컨텍스트를 Grep·Read로 확정한 뒤, find/replace 블록을 하니스에서 자동 추출해 .md를 조립하고 라운드트립 MD5로 전사 오류를 0으로 만든다. §3-3의 부착 키잉 결정(gimmick 컬럼 기반)도 함께 확인받는다.
