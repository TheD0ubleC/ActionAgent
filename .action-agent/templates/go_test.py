"""
run = true
name = "Go test"
reason = "Run Go tests"
timeout = 600
priority = 10

[commands]
before = [
  "go version"
]
run = [
  "go test ./..."
]
after = []

[output]
mode = "both"
path = ".action-agent/output/go-test.log"
artifact = true
commit = false

[execution]
cwd = "."
shell = "bash"
continue_on_error = false
reset_on = "always"
after = "always"
"""
