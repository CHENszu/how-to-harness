from collections import defaultdict
from typing import Dict, List
from .events import HookEvent
from .schemas import HookDefinition

class HookRegistry:
    def __init__(self):
        self._hooks: Dict[HookEvent, List[HookDefinition]] = defaultdict(list)

    def register(self, event: HookEvent, hook: HookDefinition):
        self._hooks[event].append(hook)
        # 按照优先级从高到低排序 (数字越大越先执行)
        self._hooks[event].sort(key=lambda h: h.priority, reverse=True)

    def get_hooks(self, event: HookEvent) -> List[HookDefinition]:
        return self._hooks.get(event, [])
