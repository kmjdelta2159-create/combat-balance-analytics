# PR-P3b (무브 우선도 결정 프리패스 — 예측기 배선) Antigravity 프롬프트

## ⚠️ 적용 순서
이 PR은 **PR-P3a 적용 후**에 적용한다. P3b는 P3a가 만든 공유 순수 코어
`_candidate_targets`·`_select_move_pure`를 호출하므로, P3a가 먼저 들어가 있어야 한다.
(P3a 미적용 상태에서 적용하면 런타임에 NameError가 난다.)

## 목적
행동 순서 정렬용 클로저를 교체한다. 현행 `_switch_action_priority`는 교체 여부만 반영하고
비-교체 유닛에 0을 반환해 무브 우선도(P1 필드)가 정렬에 안 들어간다. 이를 `_predict_action_priority`
로 바꿔, 비-교체 유닛은 **예측된 무브의 priority**를 반환하게 한다. turn_manager의 스칼라
안정정렬이 (교체 티어 ≫ 무브 우선도) 한 숫자로 "교체 먼저 → 우선도 무브 → 속도순"을 처리하므로
**turn_manager는 손대지 않는다.**

## 제약
- `modules/engine.py` **한 파일만** 수정. turn_manager.py·move_extraction.py·step2 등 손대지 말 것.
- 아래 find/replace **2건만** 적용. 곁가지 수정 금지.

## 적용 1 — 정렬 클로저 교체

다음 블록을 **정확히** 찾아서:

```python
    # 교체 우선 정렬용 행동 우선도 예측기 — 이번 턴 교체할 유닛을 행동 순서 앞으로.
    def _switch_action_priority(unit):
        if _will_voluntary_switch(unit, participants, game_config):
            return int((game_config or {}).get("switch_priority", 6))
        return 0
```

다음으로 **교체**:

```python
    # 행동 우선도 예측기 — read-only로 이번 라운드 각 on_field 유닛의 행동(교체/무브)을 미리
    # 읽어 행동 순서 정렬용 우선도 스칼라를 만든다. 교체 예정 유닛은 switch_priority 티어(공격
    # 보다 앞섬), 그 외엔 예측된 무브의 priority(P1 필드, 기본 0). 부작용 없음(데미지·스왑·로그
    # 없음). 모든 무브 우선도 0 + 교체 미설정이면 전원 0 → 정렬 키가 속도만 남아 순수 속도순
    # (회귀 0). 예측은 실행과 같은 공유 순수 코어(_candidate_targets·_select_move_pure)를 호출해
    # 싱글에서 "예측한 무브 = 실제 실행 무브"를 구조적으로 보장한다. build_ctx(turn=0)은 로그
    # 문자열에만 turn을 쓰므로 예측 결과에 영향 없음.
    def _predict_action_priority(unit):
        if _will_voluntary_switch(unit, participants, game_config):
            return int((game_config or {}).get("switch_priority", 6))
        _pctx = build_ctx(unit, 0, participants)
        _ptargets = _candidate_targets(unit, participants, _pctx["target_val"],
                                       _pctx.get("spatial_module"), _pctx.get("attack_range"))
        if not _ptargets:
            return 0
        _pmove = _select_move_pure(unit, _ptargets[0], _pctx.get("sys_stats"),
                                   _pctx.get("game_config"), _pctx.get("formula_str"))
        if _pmove is None:
            return 0
        try:
            return int(_pmove.get("priority", 0))
        except (TypeError, ValueError):
            return 0
```

## 적용 2 — manager 생성부 kwarg 교체

다음 줄을 **정확히** 찾아서:

```python
        action_priority=_switch_action_priority,
```

다음으로 **교체**:

```python
        action_priority=_predict_action_priority,
```

## 적용 후 자가 점검 (보고만, 코드 변경 금지)
1. `def _predict_action_priority(` 1회 존재, `_switch_action_priority` 0회(완전 제거).
2. manager 생성부에 `action_priority=_predict_action_priority,` 존재.
3. `_predict_action_priority`가 `_candidate_targets(`·`_select_move_pure(`·`build_ctx(`를 호출.
4. `modules/engine.py` 구문 오류 없이 import/compile 됨.
5. turn_manager.py·move_extraction.py·step2 **변경 없음**.

## 회귀 0 / 정확성 근거
- 모든 무브 우선도 0 + switch_policy 미설정이면 예측기가 전원 0 반환 → 정렬 키 전부 0 →
  안정정렬이 속도순 보존 → 현행과 완전 동일.
- 예측기는 부작용 없음(데미지·on_field·로그 미변경). 실행과 같은 순수 코어를 호출해 싱글에서
  예측=실행. 보조자 측 하니스(verify_priority_p3b.py)에서 ① 회귀 0 ② 우선도 역전 선행
  ③ 교체 최선행 ④ 부작용 0 ⑤ 음수 우선도 후행 검증 완료.
- 한계(설계안 §5): 멀티 액티브(더블+)에서는 예측이 실행과 어긋날 수 있음(싱글 밖). 검증
  범위는 싱글이라 현재 무관.

## 라이브 확인 권장
switch가 아닌 **우선도 무브** 설정 전투에서, 느린 유닛이 우선도 무브로 빠른 유닛보다 먼저
행동하는 로그를 확인하면 end-to-end 발화가 실증된다.
