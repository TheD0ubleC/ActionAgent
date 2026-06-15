"""
run = true
name = "Inspect environment"
reason = "Check available tools in the ActionAgent runner"
timeout = 120
priority = 10

[commands]
before = []
run = [
  "uname -a",
  "pwd",
  "python --version",
  "git --version",
  "node --version || true",
  "npm --version || true",
  "dotnet --version || true",
  "cargo --version || true",
  "go version || true",
  "java -version || true"
]
after = []

[output]
mode = "both"
path = ".action-agent/output/inspect-environment.log"
artifact = true
commit = false

[execution]
cwd = "."
shell = "bash"
continue_on_error = false
reset_on = "always"
after = "always"
"""
