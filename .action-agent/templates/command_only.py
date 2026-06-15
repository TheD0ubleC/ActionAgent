"""
run = true
name = "Command-only task"
reason = "Run arbitrary commands"
timeout = 300
priority = 10

[commands]
before = []
run = [
  "echo hello from ActionAgent",
  "pwd",
  "ls -la"
]
after = []

[output]
mode = "both"
path = ".action-agent/output/command-only.log"
artifact = true
commit = false

[execution]
cwd = "."
shell = "bash"
continue_on_error = false
reset_on = "success"
after = "always"
"""
