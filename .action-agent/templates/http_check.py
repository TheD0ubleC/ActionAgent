"""
run = true
name = "HTTP smoke check"
reason = "Check whether a URL responds"
timeout = 120
priority = 10

[commands]
before = []
run = [
  "python - <<'PY'\nimport urllib.request\nurl='https://example.com'\nwith urllib.request.urlopen(url, timeout=10) as r:\n    print('status:', r.status)\n    print('content-type:', r.headers.get('content-type'))\n    print(r.read(200).decode('utf-8', errors='replace'))\nPY"
]
after = []

[output]
mode = "both"
path = ".action-agent/output/http-check.log"
artifact = true
commit = false

[execution]
cwd = "."
shell = "bash"
continue_on_error = false
reset_on = "success"
after = "always"
"""
