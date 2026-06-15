"""
run = true
name = "Dotnet test"
reason = "Run .NET restore/build/test"
timeout = 900
priority = 10

[commands]
before = [
  "dotnet --version",
  "dotnet restore"
]
run = [
  "dotnet build --configuration Release --no-restore",
  "dotnet test --configuration Release --no-build"
]
after = []

[output]
mode = "both"
path = ".action-agent/output/dotnet-test.log"
artifact = true
commit = false

[execution]
cwd = "."
shell = "bash"
continue_on_error = false
reset_on = "always"
after = "always"
"""
