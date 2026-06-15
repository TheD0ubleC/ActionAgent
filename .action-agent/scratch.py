"""
run = true
name = "Scratch write test"
reason = "Verify ActionAgent scratch write without network command"
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

from pathlib import Path

output_dir = Path(".action-agent/output")
output_dir.mkdir(parents=True, exist_ok=True)
message = "ActionAgent non-network write test succeeded."
print(message)
(output_dir / "write-test.txt").write_text(message + "\n", encoding="utf-8")
