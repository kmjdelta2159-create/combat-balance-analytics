"""
Action Registry — 전투 액션 함수를 동적으로 등록/조회하는 레지스트리.
플러그인이 런타임에 새 액션을 추가할 수 있게 한다.
"""

class ActionRegistry:
    """액션 키와 실행 함수를 매핑하는 레지스트리."""
    
    def __init__(self):
        self._actions = {}
    
    def register(self, key: str, func: callable, override: bool = False):
        """액션 등록. override=False일 때 기존 키 덮어쓰기 방지."""
        if key in self._actions and not override:
            raise ValueError(f"Action '{key}' already registered. Use override=True to replace.")
        self._actions[key] = func
    
    def get(self, key: str):
        """등록된 함수 반환. 없으면 None."""
        return self._actions.get(key)
    
    def has(self, key: str) -> bool:
        return key in self._actions
    
    def keys(self) -> list:
        return list(self._actions.keys())
    
    def unregister(self, key: str):
        """액션 제거. 플러그인 비활성화 시 사용."""
        self._actions.pop(key, None)


# 글로벌 디폴트 레지스트리 (step6_dashboard.py에서 기본 액션 등록)
DEFAULT_ACTION_REGISTRY = ActionRegistry()
