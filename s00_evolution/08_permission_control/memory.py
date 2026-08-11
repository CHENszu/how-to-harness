import os
import re
import datetime
from pathlib import Path

# 模拟 OpenHarness 的持久化存储目录
MEMORY_DIR = Path(__file__).parent / ".memory"

def init_memory_dir():
    if not MEMORY_DIR.exists():
        MEMORY_DIR.mkdir(parents=True)

def save_memory(title: str, content: str, importance: int = 1):
    """
    保存长期记忆到本地 Markdown 文件，带有简单的 Frontmatter 风格元数据
    """
    init_memory_dir()
    # 生成安全的文件名
    safe_title = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fa5]+', '_', title)
    file_path = MEMORY_DIR / f"{safe_title}.md"
    
    now = datetime.datetime.now().isoformat()
    # 模拟 YAML Frontmatter
    frontmatter = (
        "---\n"
        f"title: {title}\n"
        f"importance: {importance}\n"
        f"updated_at: {now}\n"
        "---\n\n"
    )
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(frontmatter + content)
        
    return f"✅ 已成功将记忆【{title}】永久保存到本地知识库。"

def search_memory(query: str, top_k: int = 3) -> str:
    """
    启发式检索：基于 OpenHarness 源码逻辑简化版。
    打分维度：标题命中(高权重) + 正文命中 + 重要性分。
    """
    if not MEMORY_DIR.exists():
        return ""
        
    # 1. 简单的分词器 (提取字母、数字组合以及独立的汉字)
    query_lower = query.lower()
    ascii_tokens = set(re.findall(r'[a-zA-Z0-9_]+', query_lower))
    han_chars = set(re.findall(r'[\u4e00-\u9fff]', query_lower))
    tokens = ascii_tokens | han_chars
    
    if not tokens:
        return ""
        
    results = []
    
    # 2. 遍历所有记忆文件并打分
    for file_path in MEMORY_DIR.glob("*.md"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue
            
        content_lower = content.lower()
        
        # 提取标题和重要性
        title_match = re.search(r'title:\s*(.+)', content)
        title = title_match.group(1).strip() if title_match else file_path.name
        title_lower = title.lower()
        
        importance_match = re.search(r'importance:\s*(\d+)', content)
        importance = int(importance_match.group(1)) if importance_match else 1
        
        # --- 启发式打分 (Heuristic Scoring) ---
        score = 0.0
        
        # A. 标题命中 (权重 2.0)
        title_hits = sum(1 for t in tokens if t in title_lower)
        score += title_hits * 2.0
        
        # B. 正文命中 (权重 1.0)
        body_hits = sum(1 for t in tokens if t in content_lower)
        score += body_hits * 1.0
        
        # C. 重要性加成
        if title_hits > 0 or body_hits > 0:
            score += importance * 0.4
            
        if score > 0:
            results.append((score, title, content))
            
    if not results:
        return ""
        
    # 3. 按分数降序排序并截取 Top K
    results.sort(key=lambda x: x[0], reverse=True)
    
    # 4. 组装返回给大模型的文本
    memory_texts = []
    for score, title, content in results[:top_k]:
        # 清理掉 frontmatter 以节省 prompt 空间，直接展示内容
        body = re.sub(r'^---.*?---\n+', '', content, flags=re.DOTALL)
        memory_texts.append(f"【记忆: {title}】(相关度: {score:.1f})\n{body}\n")
        
    return "\n".join(memory_texts)
