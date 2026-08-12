import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class SkillDefinition:
    name: str
    description: str
    content: str
    command_name: str

class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition):
        self._skills[skill.name] = skill
        if skill.command_name != skill.name:
            self._skills[skill.command_name] = skill

    def get_skill(self, name: str) -> Optional[SkillDefinition]:
        return self._skills.get(name)

    def list_skills(self) -> List[SkillDefinition]:
        unique_skills = {s.name: s for s in self._skills.values()}
        return sorted(list(unique_skills.values()), key=lambda x: x.name)

def parse_skill_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content."""
    metadata = {}
    body = content
    
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            body = parts[2].strip()
            
            for line in frontmatter.split('\n'):
                line = line.strip()
                if ':' in line:
                    key, val = line.split(':', 1)
                    metadata[key.strip()] = val.strip()
                    
    return metadata, body

def load_skills(skills_dir: str) -> SkillRegistry:
    registry = SkillRegistry()
    
    if not os.path.exists(skills_dir):
        return registry
        
    for item in os.listdir(skills_dir):
        skill_path = os.path.join(skills_dir, item)
        if os.path.isdir(skill_path):
            md_path = os.path.join(skill_path, "SKILL.md")
            if os.path.exists(md_path):
                with open(md_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                metadata, _ = parse_skill_frontmatter(content)
                name = metadata.get("name", item)
                description = metadata.get("description", f"Skill: {name}")
                
                skill = SkillDefinition(
                    name=name,
                    description=description,
                    content=content,  # 淇濈暀瀹屾暣鍐呭
                    command_name=item
                )
                registry.register(skill)
                
    return registry
