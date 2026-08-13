from typing import Any, Dict
from pydantic import BaseModel

class BaseTool(BaseModel):
    """工具基类"""
    name: str
    description: str
    parameters: Dict[str, Any]

    def execute(self, **kwargs) -> str:
        raise NotImplementedError("Subclasses must implement execute method")
