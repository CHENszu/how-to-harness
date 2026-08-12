from typing import Literal, Union
from pydantic import BaseModel, Field

class BaseHookDefinition(BaseModel):
    priority: int = 0
    block_on_failure: bool = False

class CommandHookDefinition(BaseHookDefinition):
    type: Literal["command"] = "command"
    command: str

class PromptHookDefinition(BaseHookDefinition):
    type: Literal["prompt"] = "prompt"
    prompt: str

class DisclaimerHookDefinition(BaseHookDefinition):
    type: Literal["disclaimer"] = "disclaimer"
    condition_prompt: str
    disclaimer_text: str

HookDefinition = Union[CommandHookDefinition, PromptHookDefinition, DisclaimerHookDefinition]

class HookResult(BaseModel):
    blocked: bool = False
    error: str | None = None
