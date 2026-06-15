"""
run = true
name = "Ping google.com"
reason = "Test external network reachability using ping"
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
continue_on_error = true
reset_on = "success"
after = "always"
"""

import platform
import subprocess
from pathlib import Path

output_dir = Path(".action-agent/output")
output_dir.mkdir(parents=True, exist_ok=True)
log_path = output_dir / "ping-google.txt"

system = platform.system().lower()
cmd = ["ping", "-n", "4", "google.com"] if "windows" in system else ["ping", "-c", "4", "google.com"]

try:
    result = subprocess.run(cmd, text=True, capture_output=True, timeout=30)
    output = "$ " + " ".join(cmd) + "\n\n" + result.stdout + result.stderr + f"\nexit_code={result.returncode}\n"
except Exception as exc:
    output = "$ " + " ".join(cmd) + f"\n\nERROR: {exc!r}\n"

print(output)
log_path.write_text(output, encoding="utf-8")
