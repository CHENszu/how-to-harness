"""权限管控逻辑 (Permission Control)"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional

class PermissionMode(str, Enum):
    """支持的三种权限模式"""
    DEFAULT = "default"      # 默认：变更类工具需确认
    PLAN = "plan"            # 规划：禁止变更类工具
    FULL_AUTO = "full_auto"  # 全自动：允许所有工具

@dataclass(frozen=True)
class PermissionDecision:
    """权限检查结果"""
    allowed: bool
    requires_confirmation: bool = False
    reason: str = ""

@dataclass
class PermissionSettings:
    """权限配置"""
    mode: PermissionMode = PermissionMode.DEFAULT
    denied_tools: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)

class PermissionChecker:
    """评估工具调用是否符合权限规则"""
    def __init__(self, settings: PermissionSettings):
        self._settings = settings

    def evaluate(
        self,
        tool_name: str,
        *,
        is_read_only: bool,
        command: Optional[str] = None
    ) -> PermissionDecision:
        
        # 1. 明确禁用的工具
        if tool_name in self._settings.denied_tools:
            return PermissionDecision(allowed=False, reason=f"工具 {tool_name} 在黑名单中，已被禁用。")
            
        # 2. 如果配置了白名单，且工具不在白名单内
        if self._settings.allowed_tools and tool_name not in self._settings.allowed_tools:
            return PermissionDecision(allowed=False, reason=f"工具 {tool_name} 不在白名单中。")

        # 3. 全自动模式：放行一切
        if self._settings.mode == PermissionMode.FULL_AUTO:
            return PermissionDecision(allowed=True, reason="全自动模式，允许所有操作。")

        # 4. 只读工具：始终放行
        if is_read_only:
            return PermissionDecision(allowed=True, reason="只读工具，允许操作。")

        # 5. PLAN 模式：严格禁止非只读工具（变更类工具）
        if self._settings.mode == PermissionMode.PLAN:
            return PermissionDecision(
                allowed=False, 
                reason="当前为 PLAN (规划) 模式，禁止执行变更类工具。"
            )

        # 6. DEFAULT 模式：非只读工具（变更类工具）需要用户确认
        reason = "变更类工具在 DEFAULT 模式下需要用户确认。"
        
        # 如果是 bash，且有敏感安装命令，给予特殊提示
        if tool_name == "bash" and command:
            install_markers = ("npm install", "pip install", "apt-get", "poetry install")
            if any(marker in command.lower() for marker in install_markers):
                reason += " ⚠️ 检测到包安装或环境更改命令，请谨慎确认。"
                
        return PermissionDecision(
            allowed=False,
            requires_confirmation=True,
            reason=reason
        )
