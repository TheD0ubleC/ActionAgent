<p align="right">
  <b>English</b> |
  <a href="./docs/README.zh-CN.md">简体中文</a> |
  <a href="./docs/README.ja.md">日本語</a>
</p>

<div align="center">

# ActionAgent

<img src="https://img.shields.io/github/license/TheD0ubleC/ActionAgent?style=flat-square" />
<img src="https://img.shields.io/github/forks/TheD0ubleC/ActionAgent?style=flat-square" />

[Quick Start](#how-to-start) · [Example Prompts](#example-prompts) · [Safety Guidance and Avoidance](#safety-guidance-and-avoidance) · [Troubleshooting](#troubleshooting) · [Future Goals](#future-goals)

</div>

## Why ActionAgent is needed

> Web-based AI is great at writing code, analyzing problems, and generating scripts, but its built-in environment `limits` what it can do. It cannot directly `access the network`, `install dependencies`, `execute commands`, or `switch platforms`, and it is difficult for it to simulate a real CI / build environment.

For example, when you want AI to help you with things like:

- Cloning a real GitHub repository and building it completely
- Installing project dependencies and system tools
- Accessing real network APIs and verifying service status
- Testing separately on Windows, macOS, and Linux
- Verifying differences between architectures such as x86_64 and ARM64
- Running long tests, builds, or benchmarks
- Saving complete logs, test reports, and build artifacts

#### **The problem ActionAgent solves is: giving web-based AI an operable external execution environment.**

It does not make AI directly execute commands inside the chat window. Instead, AI modifies a dedicated ActionAgent repository through GitHub, writes “what should be executed” as a task, and then hands it off to a GitHub Actions Runner for execution.

```text
You provide a goal
↓
Web-based AI connects to GitHub
↓
AI modifies your ActionAgent repository
↓
GitHub Actions starts a temporary Runner
↓
ActionAgent discovers and executes the task
↓
Logs, reports, and artifacts are saved
↓
ActionAgent writes `.action-agent/result.json`
↓
AI reads the result file, log excerpt, and referenced logs, then reports back to you
```

You can think of ActionAgent as:

```text
ActionAgent = a remote execution workbench for web-based AI
```

Compared with a web-based sandbox, a GitHub Actions Runner is closer to a temporary cloud machine. It can install dependencies, execute system commands, access the network, switch operating systems and architectures, and save execution results as a stable result file, logs, or artifacts.

By default, ActionAgent commits a bounded log excerpt in `.action-agent/result.json` when a task runs and keeps full logs as artifacts. If there are no `run = true` tasks, it exits without changing repository state. Tasks can opt in to committing full logs with `[output].commit = true` when the complete repository-visible log is needed.

This means web-based AI is no longer limited to “writing commands for you.” Within an authorized scope, it can hand tasks to a real Runner for execution and continue analyzing based on real output.

## What it can do

ActionAgent is suitable for letting web-based AI execute tasks that are difficult to complete in ordinary built-in environments:

- Request real network APIs and verify APIs, service status, and download links
- Install project dependencies such as Python, Node, Rust, Go, and .NET
- Install system tools such as `apt`, `brew`, and `choco`
- Compile complete projects instead of only checking code snippets
- Run real tests, build tests, integration tests, and smoke tests
- Verify platform differences on Windows, macOS, and Linux
- Verify architecture differences on x86_64 and ARM64 runners
- Connect to servers you are authorized to access through SSH and execute commands
- Save long logs, build artifacts, test results, and debugging output

Within the permissions, platforms, timeouts, network conditions, and safety boundaries of GitHub Actions, ActionAgent can serve as a remote execution entry point for web-based AI.

## How to start

> The following examples are based on ChatGPT. Other web-based AI tools may use different GitHub connection methods.

### 1. Create your own ActionAgent repository

First, fork this repository to create your own ActionAgent repository:

[Click here to fork ActionAgent](https://github.com/TheD0ubleC/ActionAgent/fork)

After forking, make sure that:

- You have write access to this repository
- GitHub Actions is enabled
- The ActionAgent workflow in the repository can run
- If runtime state needs to be committed automatically, the workflow has permission to write repository contents

### 2. Connect GitHub in ChatGPT

Connect the GitHub App in ChatGPT and authorize ChatGPT to access your ActionAgent repository.

You can find Apps in ChatGPT settings, search for the GitHub App, and connect your GitHub account.

When connecting, please note:

- Select your ActionAgent repository
- Do not select the business project repository you want to build or test
- Business projects are usually cloned by ActionAgent inside a task

### 3. Select the ActionAgent repository in the chat

When repository operations are needed, if the interface supports explicit GitHub invocation, you can type:

```text
@GitHub
```

Then search for the ActionAgent repository. If it shows that the index hasn't been built yet, click on the ActionAgent repository, and then on the page that pops up, click `Trigger index on GitHub`. After that, just wait for 5 minutes before continuing.

### 4. Let ChatGPT learn the ActionAgent rules first

Send:

```text
@GitHub Please read the AGENTS.md in the ActionAgent repository and learn how to use ActionAgent.  
Once you've finished learning, please report back to me directly—don't execute any tasks or modify any files.
```

After ChatGPT reports that it has finished learning, you can send additional requests to execute tasks.

## Example prompts

| Need | Prompt |
| ---- | ------ |
| Network test | `Use ActionAgent to ping www.google.com and check whether the network is reachable.` |
| Project build | `Use ActionAgent to clone https://github.com/Kinal-Lang/Kinal, perform a Linux x86_64 build, and upload the build output as an artifact.` |
| Repository testing | `Use ActionAgent to clone this repository, install dependencies, run tests, and save the logs to .action-agent/output/.` |
| Runner environment check | `Use ActionAgent to check the current Runner system information and whether Python, Node, Git, and Docker are available.` |
| Server operations | `Use ActionAgent to connect to my Ubuntu server using SSH information configured in GitHub Secrets, and check CPU, memory, disk, and load usage.` |

## Handling sensitive information with Secrets

It is not recommended to send server passwords, tokens, cookies, private keys, or other sensitive information directly to AI, and you should not write them into task files.

Recommended approach:

1. Open GitHub Settings in your ActionAgent repository
2. Go to Secrets and variables
3. Add the required Secrets, such as:
   - `SSH_HOST`
   - `SSH_USER`
   - `SSH_PRIVATE_KEY`
   - `API_TOKEN`

4. Tell the AI the exact Secret names you added, such as `SSH_HOST`, `SSH_USER`, or `SSH_PRIVATE_KEY`

The AI should prepare ActionAgent to use those names before writing the task, without asking for the Secret values.

Please note:

- ChatGPT should not see the actual contents of Secrets
- Secrets should only be used during Runner execution
- Using Secrets is not a way to bypass safety rules
- The target server, repository, API, or domain must still be owned by you or explicitly authorized for you to operate

## Safety guidance and avoidance

ActionAgent gives web-based AI stronger execution capabilities, so boundaries must be clearer.

Please follow these rules:

- ActionAgent is better suited for private repositories
- Do not print secrets, tokens, cookies, or private keys in tasks
- Do not let tasks output full environment variables
- Do not blindly execute `curl xxx | bash`
- Do not run infinite loops
- Do not perform unauthorized penetration testing, scanning, brute forcing, or exploitation
- Do not perform destructive operations against third-party systems
- Before connecting to servers or executing dangerous operations, confirm that the target belongs to you or that you are authorized
- Do not occupy public GitHub Actions resources for large numbers of long-running tasks

If ChatGPT refuses to perform a request, it usually means the request may involve:

- Unauthorized targets
- Plaintext sensitive information
- High-risk server operations
- Commands that may cause damage
- Actions disallowed by safety policies

In that case, adjust the task first. For example:

- Use GitHub Secrets to pass sensitive information
- Clearly state that the target is owned by you or that you are authorized
- Reduce the task's permissions
- Perform read-only checks first
- Avoid destructive commands
- Split large tasks into smaller, more auditable tasks

## Troubleshooting

If ActionAgent does not run, check:

- Whether you have forked it into your own repository
- Whether ChatGPT is connected to and has selected the ActionAgent repository
- Whether GitHub Actions is enabled
- Whether the workflow has permission to commit runtime state
- Whether `.action-agent/scratch.py` or `.action-agent/tasks/*.py` contains `run = true`
- Whether the task file starts with valid TOML metadata
- Whether `.action-agent/result.json` was updated
- Whether there are errors in the GitHub Actions logs
- Whether logs or artifacts were generated in `.action-agent/output/`

If you think ActionAgent itself has a problem, please submit an Issue with the following information:

- Your task file content
- `AGENTS.md`
- `.action-agent/run.toml`
- `.action-agent/result.json`
- GitHub Actions logs
- Logs from `.action-agent/output/`
- Reproduction steps

### Future goals

- Use GitHub Actions to reverse-proxy the capabilities of web-based AI into user-controlled local environments, such as Codex and OpenCode, squeezing every last drop of value from AI subscriptions — connecting web-based conversations to local Agents.

---

<div style="display: flex;gap: 8px;justify-content: center;">

### [Submit Issue](https://github.com/TheD0ubleC/ActionAgent/issues)

### |

### [Submit Pull Request](https://github.com/TheD0ubleC/ActionAgent/pulls)

### |

### [Back to top](#ActionAgent)

</div>
<div align="center">

**ActionAgent follows the MIT License. You are welcome to fork, use, and improve it, but please pay attention to safety boundaries and usage guidelines.**

</div>
