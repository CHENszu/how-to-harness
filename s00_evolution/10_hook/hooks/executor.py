import os
import subprocess
from openai import OpenAI
from typing import Any, Dict
from .events import HookEvent
from .schemas import HookResult, CommandHookDefinition, PromptHookDefinition, DisclaimerHookDefinition
from .loader import HookRegistry

class HookExecutor:
    def __init__(self, registry: HookRegistry):
        self.registry = registry
        # 共享一个 client 给 Prompt Hook 使用
        self.client = OpenAI(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/v1")
        )
        self.model_id = os.getenv("MODEL_ID", "deepseek-chat")

    def execute(self, event: HookEvent, context: Dict[str, Any]) -> HookResult:
        """
        依次执行注册在特定事件上的所有 Hook。
        如果遇到配置了 block_on_failure 的 Hook 并且执行失败，则拉停流水线，返回拦截。
        """
        hooks = self.registry.get_hooks(event)
        if not hooks:
            return HookResult(blocked=False)
            
        print(f"  [HookExecutor] 🚦 触发卡点: {event.value}, 共有 {len(hooks)} 个质检员...")

        for idx, hook in enumerate(hooks):
            print(f"    - [{idx+1}] 正在执行质检 ({hook.type}, priority={hook.priority})")
            
            try:
                if hook.type == "command":
                    self._execute_command(hook, context)
                elif hook.type == "prompt":
                    self._execute_prompt(hook, context)
                elif hook.type == "disclaimer":
                    self._execute_disclaimer(hook, context)
                    
            except Exception as e:
                print(f"    ❌ 质检未通过: {e}")
                if hook.block_on_failure:
                    print(f"    🚨 拦截生效：此质检员拥有一票否决权，流水线终止！")
                    return HookResult(blocked=True, error=str(e))
                else:
                    print(f"    ⚠️ 警告：质检未通过，但未配置拦截，流水线继续。")
                    
        return HookResult(blocked=False)

    def _execute_command(self, hook: CommandHookDefinition, context: Dict[str, Any]):
        # 将 context 转换为环境变量，让 command 可以获取
        env = os.environ.copy()
        for k, v in context.items():
            env[f"HOOK_CTX_{k.upper()}"] = str(v)
            
        result = subprocess.run(
            hook.command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            env=env
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"命令执行失败: {result.stderr.strip()}")

    def _execute_prompt(self, hook: PromptHookDefinition, context: Dict[str, Any]):
        # 将 context 格式化给大模型看
        ctx_str = "\n".join([f"- {k}: {v}" for k, v in context.items()])
        prompt = (
            f"请你作为系统质检员，严格审查以下操作上下文：\n{ctx_str}\n\n"
            f"【审查规则】: {hook.prompt}\n\n"
            "如果你认为操作安全合规，请严格且仅输出 'PASS'。\n"
            "如果你认为操作违规，请输出 'REJECT: <拒绝原因>'"
        )
        
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        
        result = response.choices[0].message.content.strip()
        if not result.startswith("PASS"):
            raise RuntimeError(f"模型审查拒绝: {result}")

    def _execute_disclaimer(self, hook: DisclaimerHookDefinition, context: Dict[str, Any]):
        prompt = (
            f"{hook.condition_prompt}\n\n"
            f"用户输入: {context.get('user_input', '')}\n\n"
            "请只回答 YES 或 NO。"
        )
        
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        
        result = response.choices[0].message.content.strip().upper()
        if "YES" in result:
            print(f"    ✅ 触发金融合规策略，已强制追加免责声明。")
            if "final_message" in context:
                context["final_message"] += f"\n\n{hook.disclaimer_text}"
