"""
run = true
name = "Scratch Python task"
reason = "Temporary Python task"
timeout = 300
priority = 10

[commands]
before = []
run = ["python .action-agent/scratch.py"]
after = []

[output]
mode = "both"
path = ".action-agent/output/scratch.log"
artifact = true
commit = false

[execution]
cwd = "."
shell = "bash"
continue_on_error = false
reset_on = "success"
after = "always"
"""

print("write Python logic here")
