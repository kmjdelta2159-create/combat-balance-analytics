# Phase 11.0 — L3 Plugin System 설계안

> **상태**: 사용자 검토 대기. 합의되면 11.0 Antigravity 프롬프트 작성 진입.
>
> **결정 사항 (사용자 위임 → 보조자 판단)**
> - Plugin contract: `typing.Protocol`
> - Discovery: 명시적 등록 (register_plugin 또는 game_profile에 import path)
> - 11.0 스코프: 본 문서가 정의하는 Foundation (코드 전 설계 합의)

---

## 0. 왜 이 문서가 먼저인가

핸드오프 §7 Step 3 인용:
> Phase 11 시작 전 사용자와 합의할 것: 형식화의 깊이, 우선 대상 메커니즘, 기존 game_config 호환성

사용자 결정: **완전 plugin 시스템 + 4 메커니즘 모두 1급 시민화**. 이건 단일 phase가 아니라 6 sub-phases 프로젝트. 11.0(Foundation)이 11.1~11.5의 인터페이스를 정의하므로, 11.0이 흔들리면 후속 phase 프롬프트가 다 흔들린다. → 코드 작성 전 설계 합의가 비용 절감.

회귀 불변 원칙: 기존 `game_config` dict 사용자(Phase 8a~8d 산출물)는 100% 그대로 동작. 어댑터 레이어로 보장.

---

## 1. 핵심 목표 (Phase 11 전체)

역설계 ↔ 사용자 개입 슬라이더의 **사용자 개입 쪽 끝** 지원 강화. 사용자가 자기 게임 메커니즘을 형식적으로 기술하면 도구가 그걸 직접 실행 가능한 인프라.

구체적으로:
- 현재 `game_config` dict(잡탕)를 `GameProfile` Pydantic 모델로 격상 — 인터페이스 형식화
- 4 메커니즘(상태이상·우선도·다중히트/명중·날씨)을 1급 entity로 추상화
- L3 plugin이 메커니즘을 등록할 수 있는 protocol + registry
- 기존 raw `exec(passive_logic)` 의존도 단계적 폐기 (병행 지원하다 deprecation)

---

## 2. 아키텍처 개관

```
                     ┌──────────────────────────────────┐
                     │  사용자 게임 (예: pokemon_clone) │
                     │  - implements GamePlugin Protocol│
                     └──────────────┬───────────────────┘
                                    │ register
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                         L3 Plugin Layer                          │
│  ┌───────────────────────┬────────────────────┬───────────────┐ │
│  │ StatusEffectRegistry  │ WeatherRegistry    │ ActionHooks   │ │
│  └───────────────────────┴────────────────────┴───────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │ injected at hook points
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  L2 Pluggable Modules (engine.py, stochasticity, resource, ...)  │
│  - GameProfile 받아 동작                                          │
│  - hook point에서 plugin에 callback 위임                          │
└─────────────────────────────────────────────────────────────────┘
```

L1 Universal Core는 변경 없음. L2 모듈이 GameProfile + registry를 받는 형태로 확장. L3는 신규.

---

## 3. 인터페이스 명세

### 3.1 `GameProfile` Pydantic 모델

```python
# modules/plugin/profile.py
from pydantic import BaseModel, Field
from typing import Optional

class MoveCategoryDef(BaseModel):
    offense: str   # 스탯명
    defense: str   # 스탯명

class StatusEffectDef(BaseModel):
    """11.1 — 형식이 정해지면 여기에 채움."""
    pass

class WeatherDef(BaseModel):
    """11.4 — 형식이 정해지면 여기에 채움."""
    pass

class GameProfile(BaseModel):
    # ── 기존 game_config 키 형식화 (Phase 8a/8b/8d 호환) ──
    categories: dict[str, MoveCategoryDef] = Field(default_factory=dict)
    type_table: dict[str, dict[str, float]] = Field(default_factory=dict)
    type_columns: list[str] = Field(default_factory=list)
    stab_factor: float = 1.0
    channels: dict[str, Optional[str]] = Field(default_factory=dict)
    
    # ── 신규 Phase 11 ──
    plugins: list[str] = Field(default_factory=list)  # import path 리스트
    status_effects: dict[str, StatusEffectDef] = Field(default_factory=dict)
    weather: dict[str, WeatherDef] = Field(default_factory=dict)
    
    class Config:
        extra = "allow"  # 미정의 키도 보존 (사용자 게임 커스텀 필드 허용)
```

회귀 불변 핵심: **모든 필드에 기본값**. 빈 `GameProfile()`은 Phase 8d 이전 상태와 의미적 동일.

### 3.2 `GamePlugin` Protocol

```python
# modules/plugin/__init__.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class GamePlugin(Protocol):
    """L3 게임 플러그인 contract. 모든 메서드는 선택 — 구현 안 하면 no-op."""
    
    name: str  # 표시 이름 (UI에 노출)
    
    def register_status_effects(self, registry: "StatusEffectRegistry") -> None:
        """이 게임의 상태이상을 등록. 미구현 시 호출 안 됨."""
        ...
    
    def register_weather(self, registry: "WeatherRegistry") -> None:
        """이 게임의 날씨/필드를 등록."""
        ...
    
    def register_action_hooks(self, dispatcher: "ActionDispatcher") -> None:
        """파이프라인 hook point에 callback 등록."""
        ...
```

`@runtime_checkable` + Protocol → 사용자는 우리 패키지를 import할 필요 없음. 시그니처만 맞으면 plugin 자격. 모든 메서드는 `hasattr` 체크로 optional.

### 3.3 Registry

```python
# modules/plugin/registry.py
from typing import Callable, Optional

class StatusEffectRegistry:
    def __init__(self):
        self._effects: dict[str, type] = {}
    
    def register(self, name: str, effect_class: type) -> None:
        """name이 이미 있으면 RuntimeError — silent override 금지."""
        if name in self._effects:
            raise RuntimeError(f"Status effect '{name}' already registered")
        self._effects[name] = effect_class
    
    def get(self, name: str) -> Optional[type]:
        return self._effects.get(name)
    
    def all_names(self) -> list[str]:
        return list(self._effects.keys())

class WeatherRegistry:
    # 동형 구조
    ...

class ActionDispatcher:
    """엔진의 hook point에 callback 등록받음."""
    HOOK_POINTS = (
        "PASSIVE_START", "STAT_CALC", "MOVE_SELECT", "TARGET_SELECT",
        "DAMAGE_CALC", "ELEMENT_MULT", "CRIT_CALC", "APPLY_DAMAGE",
        "ON_HIT", "DEATH_CHECK",
    )
    
    def __init__(self):
        self._hooks: dict[str, list[Callable]] = {hp: [] for hp in self.HOOK_POINTS}
    
    def register_hook(self, hook_point: str, callback: Callable) -> None:
        if hook_point not in self._hooks:
            raise ValueError(f"Unknown hook point: {hook_point}")
        self._hooks[hook_point].append(callback)
    
    def dispatch(self, hook_point: str, ctx: dict) -> None:
        for cb in self._hooks.get(hook_point, []):
            cb(ctx)
```

### 3.4 Plugin loader

```python
# modules/plugin/loader.py
import importlib
from typing import Optional

def load_plugin(import_path: str) -> Optional[object]:
    """'mypackage.plugins.pokemon' → 모듈 로드 → GamePlugin protocol 만족하는 객체 반환.
    
    규약: 모듈은 `plugin` 이름의 GamePlugin instance를 노출해야 함.
    """
    try:
        mod = importlib.import_module(import_path)
    except ImportError as e:
        raise RuntimeError(f"Plugin import failed: {import_path}: {e}")
    
    plugin = getattr(mod, "plugin", None)
    if plugin is None:
        raise RuntimeError(f"Plugin module {import_path} has no 'plugin' attribute")
    if not isinstance(plugin, GamePlugin):
        raise RuntimeError(f"Plugin {import_path} doesn't satisfy GamePlugin protocol")
    return plugin

def load_all_plugins(profile: GameProfile) -> tuple[StatusEffectRegistry, WeatherRegistry, ActionDispatcher]:
    """GameProfile.plugins에 나열된 모든 plugin을 로드하고 registry에 등록."""
    se_reg = StatusEffectRegistry()
    w_reg = WeatherRegistry()
    dispatcher = ActionDispatcher()
    for import_path in profile.plugins:
        plugin = load_plugin(import_path)
        if hasattr(plugin, "register_status_effects"):
            plugin.register_status_effects(se_reg)
        if hasattr(plugin, "register_weather"):
            plugin.register_weather(w_reg)
        if hasattr(plugin, "register_action_hooks"):
            plugin.register_action_hooks(dispatcher)
    return se_reg, w_reg, dispatcher
```

---

## 4. 파이프라인 hook point 매핑

11.1~11.4 메커니즘이 엔진 9단계 파이프라인 어디에 inject되는지 사전 합의.

| Hook point | 11.1 Status | 11.2 Priority | 11.3 Multi-hit/Acc | 11.4 Weather |
|---|---|---|---|---|
| PASSIVE_START | tick (독·화상 피해) | — | — | weather tick |
| STAT_CALC | modifier (공격 -1 등) | — | — | weather stat boost |
| MOVE_SELECT | — | priority 정렬 | accuracy roll | weather move 가용성 |
| TARGET_SELECT | target override (혼란) | — | — | — |
| DAMAGE_CALC | — | — | hit_count 루프 | weather dmg modifier |
| ELEMENT_MULT | — | — | — | weather 속성 부스트 |
| CRIT_CALC | crit 차단 (특정 상태) | — | — | weather crit modifier |
| APPLY_DAMAGE | flinch/sleep on hit | — | hit별 누적 적용 | — |
| ON_HIT | status inflict | — | — | — |
| DEATH_CHECK | faint 처리 | — | — | — |

**원칙**: 엔진은 각 단계 끝에 `dispatcher.dispatch("XXX", ctx)`를 호출. plugin이 ctx를 mutate. **plugin이 없으면 dispatch는 no-op**. 회귀 불변.

---

## 5. 마이그레이션 전략 — 기존 game_config 100% 호환

세 단계 (회귀 위험 0).

### 5.1 어댑터
```python
# modules/plugin/adapter.py
def game_config_to_profile(cfg: Optional[dict]) -> GameProfile:
    """기존 dict → GameProfile. Pydantic이 미정의 키는 Config.extra='allow'로 흡수."""
    if cfg is None:
        return GameProfile()
    return GameProfile(**cfg)
```

### 5.2 엔진 측 호환 wrapper
```python
# engine.py
def run_simulation(..., game_config=None, ...):
    # 기존 시그니처 유지
    profile = (game_config_to_profile(game_config) 
               if isinstance(game_config, dict) 
               else (game_config or GameProfile()))
    # 내부에선 profile 사용. build_ctx 등은 profile.channels, profile.type_table로 접근.
    ...
```

dict 접근 패턴(`game_config.get("channels")`)은 `profile.channels`로 1:1 매핑. 코드 변경 최소.

### 5.3 Streamlit 측
- step2의 game_config 조립부 변경 없음 (그대로 dict로 만들어 session_state['game_config']에 저장)
- 신규: plugin 선택 UI → session_state['game_config']['plugins'] = [...] 추가
- 엔진 호출 시 dict가 자동으로 GameProfile로 wrap됨

→ 기존 사용자는 plugins 안 쓰면 100% 그대로.

---

## 6. Streamlit UI 변화 (Step 2)

Phase 8d의 `🧩 기믹 채널 매핑` expander 직후에 새 expander:

```
🔌 게임 플러그인 (Game Plugin) — 고급
    [활성화 토글]
    [Import path 입력란 — 예: mypackage.plugins.pokemon]
    [+ 추가 버튼]
    [등록된 plugin 리스트 (테이블)]
        - plugin name
        - 상태 (loaded / error)
        - 등록된 status effects 개수
        - 등록된 weather 개수
        - 등록된 hooks 개수
    [로드 테스트 버튼 — 즉시 import 시도]
```

plugin 파일 자체를 업로드하는 것도 후속 고려 가능 (보안: exec 위험). 우선은 import path만.

---

## 7. 본 phase(11.0) 산출물 — Antigravity 프롬프트가 만들 것

**신규 파일** (4개):
1. `modules/plugin/__init__.py` — `GamePlugin` Protocol, 공개 export
2. `modules/plugin/profile.py` — `GameProfile`, `MoveCategoryDef`, `StatusEffectDef` (스텁), `WeatherDef` (스텁)
3. `modules/plugin/registry.py` — `StatusEffectRegistry`, `WeatherRegistry`, `ActionDispatcher`
4. `modules/plugin/loader.py` — `load_plugin`, `load_all_plugins`, `game_config_to_profile`

**수정 파일** (2개):
1. `modules/engine.py` — `run_simulation`/`build_ctx`이 GameProfile도 받기 (dict 호환). 각 액션 함수 끝에 `dispatcher.dispatch("...", ctx)` 호출 추가 (현재는 dispatcher 안 와도 됨 — 옵셔널 인자).
2. `modules/step2_system_definition.py` — `🔌 게임 플러그인` expander 추가, plugin 로드 테스트 버튼.

**검증 자산** (샌드박스에서 내가 작성):
- 빈 plugin (no-op) — Protocol 만족, 모든 메서드 미구현
- 1개 메서드만 구현하는 mini plugin (예: register_status_effects만)
- pytest 스타일 단위 테스트 — load_plugin / registry 중복 등록 / dispatcher no-op

**의존성 추가**: `pydantic>=2.0`. `requirements.txt` 갱신.

---

## 8. 11.1~11.5 후속 phase 골격 (합의용 미리보기)

### 11.1 Status Effects 1급화
- `StatusEffectDef` 본체 (apply_logic / tick_logic / expire_logic / interactions)
- `StatusEffect` runtime 클래스 + 캐릭터 instance에 부착
- engine PASSIVE_START / STAT_CALC / TARGET_SELECT / ON_HIT에서 effect 실행
- raw `exec(passive_logic)` 폐기 시작 (병행 지원 → deprecation warning)
- Pokemon reference: poison/burn/sleep/paralysis/freeze 구현

### 11.2 Move Priority
- 무브 dict에 `priority: int = 0`
- `turn_manager`가 speed 정렬 전 priority 정렬 (high → low)
- plugin이 dynamic priority modifier 등록 가능 (장갑 트릭 등)

### 11.3 Multi-hit + Accuracy
- 무브 dict에 `hit_count: int | tuple[int, int] = 1`, `accuracy: float = 1.0`
- stochasticity 확장: `roll_accuracy()`, `roll_hit_count()`
- engine MOVE_SELECT에서 accuracy roll → 빗나가면 skip
- engine APPLY_DAMAGE를 hit_count 루프로

### 11.4 Weather/Field
- `WeatherDef` 본체 (apply / tick / expire / modifiers)
- `BattleState`에 `weather`, `field`, `terrain` slot
- engine 다수 단계에서 weather modifier 적용
- Pokemon reference: rain/sun/sandstorm/hail

### 11.5 Reference plugin: pokemon_clone
- 위 4 메커니즘을 다 쓰는 데모 plugin
- Pokemon known-answer 충실도 95.8% 천장 재돌파 시도
- 종결 검증

각 phase = 별도 Antigravity 프롬프트 + 핸드오프 §4 검증 사이클.

---

## 9. 추정 작업량

| Phase | Antigravity 프롬프트 | 검증 | 사용자 검토 |
|---|---|---|---|
| 11.0 | ~3K 라인 신규 + 200 라인 수정 | 단위 테스트 + UI 회귀 | 합의 1회 (현재 단계) |
| 11.1 | ~1.5K 라인 (가장 큼) | Pokemon poison/burn 정량 | — |
| 11.2 | ~300 라인 | turn order 변경 정량 | — |
| 11.3 | ~500 라인 | accuracy/multi-hit 정량 | — |
| 11.4 | ~1K 라인 | weather effect 정량 | — |
| 11.5 | ~2K 라인 (plugin 본체) | 95.8% 천장 재현 시도 | 종결 |

Phase 11 전체 = 8~10주 추정 (검증 사이클 포함).

---

## 10. 검토 포인트 — 사용자 푸시백 환영

수정/거부/추가 의견을 받고 싶은 곳:
1. **Plugin 모듈의 `plugin` 변수 규약** — 모듈이 `plugin` 이름으로 인스턴스 노출해야 함. 다른 이름 선호?
2. **GameProfile에 `plugins: list[str]`** — 한 게임에 plugin 여러 개 허용. 1개로 제한할까?
3. **ActionDispatcher hook point 이름** — engine.py의 9단계 이름과 매칭. 추가/이름 변경 의견?
4. **StatusEffectDef / WeatherDef를 11.0에서 스텁으로** — 본체는 11.1/11.4에서 구체화. 11.0에서 미리 합의할까?
5. **plugin UI에 파일 업로드** — 보안 위험(임의 코드 exec). 현재 import path만 제안. 업로드 필요?
6. **dispatcher.dispatch 호출 위치** — 9단계 끝마다. priority/accuracy처럼 단계 *전*에 inject 필요한 케이스는 별도 hook?

---

## 11. 다음 액션

본 문서 합의 후:
1. 내가 11.0 Antigravity 프롬프트 작성 (`Phase11.0_Foundation_프롬프트.md`)
2. 라운드트립 무결성 + py_compile 검증
3. 사용자에게 전달 → Antigravity 납품 → §4 방법론으로 검증
4. 11.1 진입

검토 결과를 알려주면 푸시백 반영하여 본 문서를 v2로 갱신하거나, 합의면 11.0 프롬프트 작성에 들어간다.
