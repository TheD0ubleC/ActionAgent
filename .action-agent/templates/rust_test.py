"""
run = true
name = "Rust test"
reason = "Run Rust tests"
timeout = 900
priority = 10

[commands]
before = [
  "rustc --version",
  "cargo --version"
]
run = [
  "cargo test"
]
after = []

[output]
mode = "both"
path = ".action-agent/output/rust-test.log"
artifact = true
commit = false

[execution]
cwd = "."
shell = "bash"
continue_on_error = false
reset_on = "success"
after = "always"
"""
