"""
Resource System — 캐릭터 자원(HP 등)의 데이터 모델과 접근자.

Phase 3.0: 데이터 모델 + 접근자만 제공한다. 동작(재생/소비/실드 흡수/상한 클램프,
임의 자원 데미지, 자원 기반 승리 조건)은 Phase 3.5에서 ResourceModule로 추가한다.

자원 저장 형태 (캐릭터 dict의 'resources' 키):
    char['resources'] = { "HP": {"current": float, "max": float}, ... }
순수 중첩 dict이므로 copy.deepcopy / pickle 에 안전하다 (멀티프로세싱 호환).
"""

PRIMARY_RESOURCE = "HP"


def init_resources(char, hp_value):
    """캐릭터에 자원 dict를 생성한다. Phase 3.0은 HP 단일 자원만 초기화."""
    hp = float(hp_value)
    char['resources'] = {PRIMARY_RESOURCE: {"current": hp, "max": hp}}
    return char


def get_current(char, name=PRIMARY_RESOURCE):
    """자원의 현재값. 자원이 없으면 0.0."""
    return char.get('resources', {}).get(name, {}).get('current', 0.0)


def get_max(char, name=PRIMARY_RESOURCE):
    """자원의 최대값. 자원이 없으면 0.0."""
    return char.get('resources', {}).get(name, {}).get('max', 0.0)


def apply_delta(char, delta, name=PRIMARY_RESOURCE):
    """자원 현재값에 증감(delta)을 적용. 0 미만으로는 내려가지 않는다.
    상한 클램프는 Phase 3.5에서 추가 (3.0은 데미지 차감 동작만 보존)."""
    res = char.setdefault('resources', {}).setdefault(name, {"current": 0.0, "max": 0.0})
    res['current'] = max(0, res['current'] + delta)
    return res['current']


def is_alive(char, vital_resources=("HP",)):
    """vital 자원이 모두 0 초과이면 생존으로 판정."""
    return all(get_current(char, r) > 0 for r in vital_resources)


class ResourceModule:
    """자원 시스템 동작 — 턴당 재생과 생존 판정. 설정(specs) 기반.

    specs 형식: { resource_name: {"role": "vital"|"pool", "regen": float} }
    순수 데이터 속성(dict)만 가지므로 pickle/deepcopy 안전 →
    멀티프로세싱 워커에 인스턴스를 직접 전달해도 된다(팩토리 불필요).
    """

    def __init__(self, specs=None, damage_type_map=None):
        # 기본값 = HP 단일 vital 자원, 재생 0 → 현행 엔진 동작과 완전히 동일.
        self.specs = specs if specs is not None else {"HP": {"role": "vital", "regen": 0.0}}
        # damage_type → 자원이름 라우팅 맵. 빈 dict면 전부 vital(HP)로 라우팅.
        self.damage_type_map = damage_type_map if damage_type_map is not None else {}

    def vital_resources(self):
        """role 이 vital 인 자원 이름들의 튜플."""
        return tuple(n for n, s in self.specs.items() if s.get("role") == "vital")

    def on_turn_start(self, char):
        """턴 시작 시 자원 재생. [0, max] 범위로 클램프."""
        resources = char.get("resources", {})
        for name, spec in self.specs.items():
            regen = spec.get("regen", 0.0)
            if not regen:
                continue
            res = resources.get(name)
            if res:
                res["current"] = max(0, min(res["max"], res["current"] + regen))

    def is_alive(self, char):
        """이 모듈의 vital 자원 기준으로 캐릭터 생존 판정."""
        return is_alive(char, self.vital_resources())

    def route_damage(self, target, dmg, damage_type=None):
        """데미지를 타겟에 적용한다. damage_type으로 대상 자원을 결정하고,
        대상이 vital 자원이면 shield가 specs 선언 순서대로 먼저 흡수한다.
        damage_type 미지정/미매핑 시 vital 자원(HP)으로 라우팅된다.
        반환: shield가 흡수한 총량 (shield 미흡수 시 0)."""
        resources = target.get("resources", {})
        vitals = self.vital_resources()
        # damage_type → 대상 자원 결정 (미매핑/타겟에 미존재 시 vital 자원으로)
        dest = self.damage_type_map.get(damage_type) if damage_type else None
        if not dest or dest not in resources:
            dest = vitals[0] if vitals else PRIMARY_RESOURCE
        remaining = dmg
        # 대상이 vital 자원일 때만 shield가 먼저 흡수
        if dest in vitals:
            for name, spec in self.specs.items():
                if remaining <= 0:
                    break
                if spec.get("role") != "shield":
                    continue
                res = resources.get(name)
                if not res or res["current"] <= 0:
                    continue
                absorbed = min(res["current"], remaining)
                res["current"] -= absorbed
                remaining -= absorbed
        apply_delta(target, -remaining, dest)
        return dmg - remaining
