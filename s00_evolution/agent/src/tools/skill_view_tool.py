import os
from typing import Any, Dict
from .base import BaseTool

class SkillViewTool(BaseTool):
    name: str = "skill_view"
    description: str = "读取指定技能的完整文档内容 (Tier 2 完整内容加载机制)。"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "要查看的技能名称（如 'docx'）"
            }
        },
        "required": ["skill_name"]
    }

    def execute(self, skill_name: str, **kwargs) -> str:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        skill_md_path = os.path.join(project_root, "skills", skill_name, "SKILL.md")
        
        if not os.path.exists(skill_md_path):
            return f"未找到技能 '{skill_name}' 的 SKILL.md 文档。"
            
        try:
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"读取技能文档失败: {e}"
