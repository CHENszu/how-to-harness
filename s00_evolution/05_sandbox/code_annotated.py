import os
import shutil
import tempfile
import subprocess
from pathlib import Path

# ==========================================
# 第5部分：Sandbox 与隔离机制原型
# ==========================================

# 我们无法在普通的 Python 脚本中直接调用系统的 Docker 或 bwrap（可能没有安装），
# 所以这里我们通过纯 Python 实现 OpenHarness 中最常用的两种隔离逻辑原型：
# 1. 目录限制沙箱 (模拟 SRT 的 allowRead/denyWrite 逻辑)
# 2. Git Worktree 沙箱 (模拟多 Agent 并行开发时的源码隔离)

class LocalSandbox:
    """
    轻量级的目录沙箱。
    限制工具（如 BashTool 或 FileWriteTool）只能在指定的沙箱目录内操作。
    """
    def __init__(self, root_dir: str):
        # 强制转换为绝对路径并解析符号链接
        self.root_dir = Path(root_dir).resolve()
        
        # 如果沙箱目录不存在，则创建
        if not self.root_dir.exists():
            self.root_dir.mkdir(parents=True)
            print(f"[Sandbox] 🛡️ 创建沙箱根目录: {self.root_dir}")

    def is_safe_path(self, target_path: str) -> bool:
        """检查目标路径是否在沙箱允许的范围内"""
        try:
            # 解析目标路径的绝对路径
            resolved_target = Path(target_path).resolve()
            # 判断目标路径是否以沙箱根目录开头
            # 例如：C:\sandbox\secret.txt 是安全的，但 C:\Windows\System32 就不是
            return str(resolved_target).startswith(str(self.root_dir))
        except Exception:
            return False

    def execute_command(self, cmd: str, cwd: str = None) -> str:
        """在沙箱环境内执行命令"""
        execute_dir = cwd if cwd else str(self.root_dir)
        
        # 1. 检查工作目录是否安全
        if not self.is_safe_path(execute_dir):
            return f"❌ 安全拦截：禁止在沙箱外 ({execute_dir}) 执行命令！"
            
        # 2. 对于简单的演示，我们通过拦截包含 ".." 的命令来防止逃逸
        # (真实环境 OpenHarness 是用 bwrap 或 Docker 从系统底层拦截的)
        if ".." in cmd:
            return f"❌ 安全拦截：命令包含 '..'，存在逃逸风险！"
            
        print(f"[Sandbox] 🟢 允许执行: `{cmd}` (在 {execute_dir} 下)")
        try:
            result = subprocess.run(
                cmd, shell=True, cwd=execute_dir, 
                capture_output=True, text=True, timeout=5
            )
            return result.stdout if result.returncode == 0 else result.stderr
        except Exception as e:
            return str(e)


class WorktreeManager:
    """
    模拟 OpenHarness 中的 Git Worktree 隔离机制。
    用于在多 Agent 团队协作时，让每个 Agent 都在独立的分支和目录中写代码。
    """
    def __init__(self, base_repo_path: str):
        self.base_repo = Path(base_repo_path).resolve()
        
    def setup_base_repo(self):
        """初始化一个用于测试的假 Git 仓库"""
        if not (self.base_repo / ".git").exists():
            print(f"[Worktree] 📦 初始化主仓库: {self.base_repo}")
            self.base_repo.mkdir(parents=True, exist_ok=True)
            subprocess.run("git init", shell=True, cwd=self.base_repo, capture_output=True)
            
            # 创建一个初始提交，否则无法创建 worktree
            (self.base_repo / "main.py").write_text("print('Hello from Main Repo')")
            subprocess.run("git add . && git commit -m 'Initial commit'", shell=True, cwd=self.base_repo, capture_output=True)

    def create_agent_workspace(self, agent_name: str, branch_name: str) -> Path:
        """为 Agent 创建一个独立的 Worktree"""
        # 在系统的临时目录下创建一个独立的工作区
        worktree_path = Path(tempfile.gettempdir()) / f"openharness_wt_{agent_name}"
        
        # 如果已经存在，先清理
        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)
            subprocess.run("git worktree prune", shell=True, cwd=self.base_repo, capture_output=True)
            
        print(f"\n[Worktree] 🌿 正在为 Agent '{agent_name}' 创建独立工作区...")
        print(f"  - 目标分支: {branch_name}")
        print(f"  - 物理路径: {worktree_path}")
        
        # 执行 Git Worktree 命令：在 worktree_path 创建一个绑定到 branch_name 分支的副本
        cmd = f"git worktree add -b {branch_name} {worktree_path}"
        result = subprocess.run(cmd, shell=True, cwd=self.base_repo, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"创建 Worktree 失败: {result.stderr}")
        else:
            print("[Worktree] ✅ 创建成功！")
            
        return worktree_path


# ==========================================
# 测试与演示
# ==========================================
if __name__ == "__main__":
    print("=======================================")
    print("  🛡️ 欢迎来到 Sandbox 与隔离机制测试 🛡️")
    print("=======================================")
    
    # -----------------------------------
    # 演示 1：目录级安全沙箱
    # -----------------------------------
    print("\n--- 测试 1: 目录沙箱安全拦截 ---")
    sandbox_dir = Path(__file__).parent / "my_sandbox"
    sandbox = LocalSandbox(str(sandbox_dir))
    
    # 合法的命令
    print(sandbox.execute_command("echo 'Agent is working safely' > test.txt"))
    
    # 恶意的命令（尝试越权访问上一级目录）
    print(sandbox.execute_command("cat ../../../.env", cwd=str(sandbox_dir)))
    
    # 恶意的 cwd（尝试在沙箱外执行）
    print(sandbox.execute_command("dir", cwd="C:\\Windows"))
    
    
    # -----------------------------------
    # 演示 2：Git Worktree 多 Agent 隔离
    # -----------------------------------
    print("\n--- 测试 2: Git Worktree 隔离机制 ---")
    repo_dir = Path(__file__).parent / "my_project_repo"
    wt_manager = WorktreeManager(str(repo_dir))
    
    # 初始化主仓库
    wt_manager.setup_base_repo()
    
    # 假设我们有两个 Agent：前端专家和后端专家
    frontend_wt = wt_manager.create_agent_workspace("frontend_agent", "feature/ui-update")
    backend_wt = wt_manager.create_agent_workspace("backend_agent", "feature/api-update")
    
    print("\n[对比] 看看它们的独立性：")
    # 前端 Agent 在自己的目录下写代码
    (frontend_wt / "ui.js").write_text("console.log('UI')")
    
    # 后端 Agent 在自己的目录下写代码
    (backend_wt / "api.py").write_text("print('API')")
    
    print(f"前端目录内容: {os.listdir(frontend_wt)}")
    print(f"后端目录内容: {os.listdir(backend_wt)}")
    print(f"主仓库内容  : {os.listdir(repo_dir)}")
    
    print("\n💡 结论：这就是 OpenHarness 在 Swarm 模式下，多个 Agent 可以同时写代码却不互相打架的底层秘密！")
