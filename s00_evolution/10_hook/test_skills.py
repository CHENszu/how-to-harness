import os
from dotenv import load_dotenv
from tools import ToolRegistry, BashTool, WebSearchTool, SaveMemoryTool, WriteFileTool, SkillsListTool, SkillViewTool
from engine import run_agent_loop
from skills_loader import load_skills

def test():
    registry = ToolRegistry()
    registry.register(WebSearchTool())
    
    skills_dir = os.path.join(os.path.dirname(__file__), "skills")
    skill_registry = load_skills(skills_dir)
    registry.register(SkillsListTool(skill_registry))
    registry.register(SkillViewTool(skill_registry))
    
    print("Registered tools:", registry._tools.keys())
    
    list_tool = registry.get_tool("skills_list")
    print(list_tool.execute())
    
    view_tool = registry.get_tool("skill_view")
    print(view_tool.execute(name="algorithmic-art")[:200])

if __name__ == "__main__":
    test()