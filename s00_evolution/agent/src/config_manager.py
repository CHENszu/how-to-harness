import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".coco", "config.json")

def load_config() -> dict:
    """加载本地配置，如果不存在则返回默认配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    
    # 默认配置
    return {
        "persona": "normal",
        "model": "deepseek-chat"
    }

def save_config(config_data: dict):
    """保存配置到本地文件"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)