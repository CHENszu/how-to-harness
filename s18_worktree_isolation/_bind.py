"""Bind tasks to the already-created worktrees."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import code_annotated as H

t1 = H.load_task("task_1786342720_1368")  # fibonacci
t2 = H.load_task("task_1786342720_5043")  # multiplication

t1.worktree = "alice-work"
t2.worktree = "bob-work"
H.save_task(t1)
H.save_task(t2)

for t in (t1, t2):
    print(json.loads(H.get_task_json(t.id)))
