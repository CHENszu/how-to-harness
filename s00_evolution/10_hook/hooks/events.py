from enum import Enum

class HookEvent(str, Enum):
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    BEFORE_REPLY = "before_reply"
    STOP = "stop"
    NOTIFICATION = "notification"
