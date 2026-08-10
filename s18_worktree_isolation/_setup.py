"""Helper to set up s18 demo state (tasks + worktrees) using harness functions."""
import json, time, random, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import code_annotated as H

# Create two tasks
t1 = H.create_task(
    subject="Fibonacci sequence generator",
    description="Implement a simple Python function that calculates the "
                "Fibonacci sequence up to a given number n and writes it to a "
                "file called fibonacci_output.txt in the current directory."
)
t2 = H.create_task(
    subject="Multiplication table generator",
    description="Implement a simple Python script that generates a "
                "multiplication table (1-10) and writes it to a file called "
                "multiplication_table.txt in the current directory."
)
print("CREATED:", t1.id, "|", t2.id)

# Create worktrees bound to tasks
print(H.create_worktree("alice-work", t1.id))
print(H.create_worktree("bob-work", t2.id))

# Print final task JSON
for tid in (t1.id, t2.id):
    print(H.get_task_json(tid))
