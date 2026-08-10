"""Mark tasks as completed - reflecting that the work is done."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import code_annotated as H

for tid in ("task_1786342720_1368", "task_1786342720_5043"):
    task = H.load_task(tid)
    if task.status == "pending":
        task.status = "in_progress"
        task.owner = "agent"
        H.save_task(task)
    H.complete_task(tid)

for t in H.list_tasks():
    print(t.id, t.subject, "->", t.status, "| wt:", t.worktree)
