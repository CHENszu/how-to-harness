import os
import re
from typing import Any, Dict
from .base import BaseTool

class SkillsListTool(BaseTool):
    name: str = "skills_list"
    description: str = "扫描 skills 目录，读取每个技能的 YAML 元数据并返回简要列表 (Tier 1 按需加载机制)。"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {},
        "required": []
    }

    def execute(self, **kwargs) -> str:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        skills_dir = os.path.join(project_root, "skills")
        
        if not os.path.exists(skills_dir):
            return "未找到 skills 目录。"
            
        skills_info = []
        for item in sorted(os.listdir(skills_dir)):
            skill_path = os.path.join(skills_dir, item)
            if os.path.isdir(skill_path):
                skill_md_path = os.path.join(skill_path, "SKILL.md")
                if os.path.exists(skill_md_path):
                    try:
                        with open(skill_md_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
                            if match:
                                frontmatter = match.group(1).strip()
                                # 尝试提取 description
                                desc_match = re.search(r'description:\s*(.*)', frontmatter)
                                desc = desc_match.group(1).strip() if desc_match else "无描述"
                                skills_info.append(f"- **{item}**: {desc}")
                            else:
                                skills_info.append(f"- **{item}**: 无 YAML 元数据")
                    except Exception as e:
                        skills_info.append(f"- **{item}**: 读取失败 ({e})")
                        
        if not skills_info:
            return "未找到任何技能配置 (SKILL.md)。"
            
        return "可用的技能列表：\n" + "\n".join(skills_info)
