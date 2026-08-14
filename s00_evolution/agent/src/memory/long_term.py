import os
import json
import logging
import threading
import copy
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(MEMORY_DIR)
DATA_DIR = os.path.join(os.path.dirname(SRC_DIR), ".coco")

# 确保 data 目录存在
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

USER_MEMORY_FILE = os.path.join(DATA_DIR, "user_memory.json")
PROJECT_MEMORY_FILE = os.path.join(DATA_DIR, "project_memory.json")

def load_memory(filepath: str) -> List[str]:
    """加载指定的记忆文件（返回字符串列表）"""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载记忆失败 {filepath}: {e}")
        return []

def save_memory(filepath: str, data: List[str]):
    """保存指定的记忆文件"""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存记忆失败 {filepath}: {e}")

def trigger_memory_consolidation(engine_messages: List[Dict[str, Any]], model: str, base_url: str, api_key: str):
    """
    异步分析当前会话，提取新记忆，并与旧记忆进行冲突检测、融合提炼 (Hook机制)
    """
    if len(engine_messages) < 3:
        return # 对话太短，没必要提取
        
    # 拷贝消息以防在其他线程中被修改
    recent_history = copy.deepcopy(engine_messages[1:][-20:])
    
    def _consolidation_task():
        # 读取现有的长记忆库
        old_user_memory = load_memory(USER_MEMORY_FILE)
        old_project_memory = load_memory(PROJECT_MEMORY_FILE)
        
        # 将对话历史转化为纯文本，避免大模型代入猫娘角色
        history_text = ""
        for msg in recent_history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str):
                history_text += f"[{role}]: {content}\n"
                
        # 构造 Hook 融合 Prompt
        prompt = f"""
        请作为一个客观的记忆管理程序，分析以下对话历史，并更新长期记忆库。
        
        【现有用户记忆】(关于用户的偏好、事实)：
        {json.dumps(old_user_memory, ensure_ascii=False)}
        
        【现有项目记忆】(关于项目状态、代码上下文)：
        {json.dumps(old_project_memory, ensure_ascii=False)}
        
        【最新对话历史】：
        {history_text}
        
        任务要求（Hook机制）：
        1. 提取：从最新对话中提取新的用户记忆和项目记忆。
        2. 冲突覆盖：如果新信息与【现有记忆】发生冲突（如用户改变了主意、状态发生变化），必须以新信息为准，删除或覆盖旧记忆。
        3. 融合提炼：如果某一类别的记忆条目过于碎片化或数量过多，请将它们融合成更精炼的总结性描述。
        4. 保持不变：对于没有冲突的有效旧记忆，请原样保留。
        
        请严格以 JSON 格式输出更新后的完整记忆库，格式如下：
        {{
          "user_memory": ["偏好/事实1", "偏好/事实2"],
          "project_memory": ["上下文1", "上下文2"]
        }}
        不要输出任何其他说明文字。
        """
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1
        }
        
        # 深色模型通常支持 response_format，如果是兼容接口加了比较保险
        if "deepseek" not in model.lower():
            payload["response_format"] = {"type": "json_object"}
            
        try:
            import httpx
            import re
            headers = {"Authorization": f"Bearer {api_key}"}
            
            with httpx.Client(timeout=45.0) as client:
                response = client.post(base_url, headers=headers, json=payload)
                response.raise_for_status()
                
                result_text = response.json()["choices"][0]["message"]["content"]
                
                # 增强的 JSON 解析
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if not json_match:
                    with open(os.path.join(DATA_DIR, "memory_error.log"), "a", encoding="utf-8") as f:
                        f.write(f"融合记忆失败，未找到JSON格式: {result_text}\n")
                    return
                    
                new_memory_db = json.loads(json_match.group(0))
                
                # 保存拆分后的记忆
                if "user_memory" in new_memory_db and isinstance(new_memory_db["user_memory"], list):
                    save_memory(USER_MEMORY_FILE, new_memory_db["user_memory"])
                if "project_memory" in new_memory_db and isinstance(new_memory_db["project_memory"], list):
                    save_memory(PROJECT_MEMORY_FILE, new_memory_db["project_memory"])
                    
        except Exception as e:
            with open(os.path.join(DATA_DIR, "memory_error.log"), "a", encoding="utf-8") as f:
                f.write(f"融合长期记忆后台任务失败: {e}\n")

    # 启动后台线程执行，daemon=False 保证主线程退出时会等待它执行完，但不会阻塞 UI 打印
    thread = threading.Thread(target=_consolidation_task, daemon=False)
    thread.start()
