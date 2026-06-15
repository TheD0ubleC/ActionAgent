"""
run = true
name = "Node test"
reason = "Run Node.js tests/build"
timeout = 600
priority = 10

[commands]
before = [
  "node --version",
  "npm --version",
  "npm ci"
]
run = [
  "npm test",
  "npm run build"
]
after = []

[output]
mode = "both"
path = ".action-agent/output/node-test.log"
artifact = true
commit = false

[execution]
cwd = "."
shell = "bash"
continue_on_error = false
reset_on = "always"
after = "always"
"""
