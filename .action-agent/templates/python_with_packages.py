"""
run = true
name = "Python task with packages"
reason = "Install packages before running Python logic"
timeout = 300
priority = 10

[commands]
before = [
  "python -m pip install --upgrade pip",
  "python -m pip install requests beautifulsoup4"
]
run = ["python .action-agent/scratch.py"]
after = []

[output]
mode = "both"
path = ".action-agent/output/python-with-packages.log"
artifact = true
commit = false

[execution]
cwd = "."
shell = "bash"
continue_on_error = false
reset_on = "always"
after = "always"
"""

import requests
from bs4 import BeautifulSoup

response = requests.get("https://example.com", timeout=10)
print("status:", response.status_code)
print("title:", BeautifulSoup(response.text, "html.parser").title)
