<p align="right">
  <a href="../en/README.md">English</a> |
  <b>简体中文</b> |
  <a href="../ja/README.md">日本語</a>
</p>

<div align="center">

# ActionAgent

<img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" />
<img src="https://img.shields.io/github/forks/TheD0ubleC/ActionAgent?style=flat-square" />

[快速开始](#如何开始) · [结果位置](#在哪里查看结果) · [示例提示词](#示例提示词) · [安全建议与规避](#安全建议与规避) · [故障排查](#故障排查) · [未来目标](#未来目标)

</div>

## 为什么需要 ActionAgent

> 网页端 AI 很擅长写代码、分析问题、生成脚本，但自带的环境`限制`了它的能力。它无法直接`访问网络`、`安装依赖`、`执行命令`、`切换平台`，也很难模拟真实的 CI / 构建环境。

例如，当你希望 AI 帮你做这些事情时：

- 克隆一个真实 GitHub 仓库并完整构建
- 安装项目依赖和系统工具
- 访问真实网络接口并验证服务状态
- 在 Windows、macOS、Linux 上分别测试
- 在 x86_64、ARM64 等不同架构上验证
- 执行长时间测试、构建或基准测试
- 保存完整日志、测试报告和构建产物

#### **ActionAgent 解决的问题是：让网页端 AI 拥有一个可操作的外部执行环境。**

它不是让 AI 在聊天窗口里直接执行命令，而是让 AI 通过 GitHub 修改一个专用的 ActionAgent 仓库，把“要执行什么”写成任务，然后交给 GitHub Actions Runner 执行。

```text
你提出目标
↓
网页端 AI 连接 GitHub
↓
AI 修改你的 ActionAgent 仓库
↓
GitHub Actions 启动临时 Runner
↓
ActionAgent 发现并执行任务
↓
保存日志、报告和 artifact
↓
ActionAgent 写入 `.action-agent/result.json`
↓
启用 issue comment 时，ActionAgent 发布带标记的结果评论
↓
AI 读取结果评论、结果文件、日志摘录和相关日志，并向你报告
```

你可以把 ActionAgent 理解成：

```text
ActionAgent = 给网页端 AI 使用的远程执行工作台
```

相比网页端沙盒，GitHub Actions Runner 更接近一台临时云主机。它可以安装依赖、执行系统命令、访问网络、切换操作系统和架构，并把执行结果保存为稳定的结果文件、日志或 artifact。

默认情况下，ActionAgent 会发布带标记的 issue 评论，在有任务运行时把截断后的日志摘录提交到 `.action-agent/result.json`，并把完整日志保存在 artifact 中。如果没有任何 `run = true` 任务，它会直接退出，不修改仓库状态。确实需要让完整日志进入仓库时，任务可以通过 `[output].commit = true` 显式开启。

这使得网页端 AI 不再只是“给你写命令”，而是可以在授权范围内帮你把任务交给真实 Runner 执行，并基于真实输出继续分析。

## 能做什么

ActionAgent 适合让网页端 AI 执行普通内置环境很难完成的事情：

- 请求真实网络接口，验证 API、服务状态、下载链接
- 安装 Python、Node、Rust、Go、.NET 等项目依赖
- 安装系统工具，例如 `apt`、`brew`、`choco`
- 编译完整项目，而不是只检查代码片段
- 运行真实测试、构建测试、集成测试、冒烟测试
- 在 Windows、macOS、Linux 上验证平台差异
- 在 x86_64 和 ARM64 runner 上验证架构差异
- 通过 SSH 连接你有权限的服务器执行命令
- 保存长日志、构建产物、测试结果和调试输出

在 GitHub Actions 权限、平台、超时、网络和安全边界允许的范围内，ActionAgent 可以作为网页端 AI 的远程执行入口。

## 在哪里查看结果

任务完成后，建议让 AI 按这个顺序读取结果：

1. 最新的 ActionAgent 标记结果评论
2. `.action-agent/result.json`
3. GitHub Actions 的 `action-agent-output` artifact，其中包含完整日志
4. 只有任务显式设置 `[output].commit = true` 时，才查看提交到仓库的输出文件

如果没有任何任务包含 `run = true`，ActionAgent 不应该写入新的运行结果。

## 如何开始

> 以下示例基于 ChatGPT。其他网页端 AI 的 GitHub 连接方式可能不同。

### 1. 创建你自己的 ActionAgent 仓库

请先 Fork 此仓库，创建你自己的 ActionAgent 仓库：

[点击这里 Fork ActionAgent](https://github.com/TheD0ubleC/ActionAgent/fork)

Fork 后，请确认：

- 你拥有这个仓库的写入权限
- GitHub Actions 已启用
- 仓库中的 ActionAgent workflow 可以运行
- 如果需要自动提交运行状态，workflow 具有写入仓库内容的权限

### 2. 在 ChatGPT 中连接 GitHub

在 ChatGPT 中连接 GitHub App，并授权 ChatGPT 访问你的 ActionAgent 仓库。

你可以在 ChatGPT 的设置中找到 Apps / 应用，搜索 GitHub 并连接你的 GitHub 账户。

连接时请注意：

- 选择的是你的 ActionAgent 仓库
- 不是你要构建或测试的业务项目仓库
- 业务项目通常会由 ActionAgent 在任务中 clone

### 3. 在聊天中选择 ActionAgent 仓库

在需要操作仓库时，如果界面支持显式调用 GitHub，可以输入：

```text
@GitHub
```

然后搜索 ActionAgent 仓库，如果显示尚未建立索引请点击 ActionAgent 仓库，随后在弹出的页面中点击`在 GitHub 上触发索引`，随后等待 5 分钟即可继续。

### 4. 让 ChatGPT 先学习 ActionAgent 规则

发送：

```text
@GitHub 请读取 ActionAgent 仓库的 AGENTS.md，学习 ActionAgent 的使用方式。
学习完成后请直接向我报告，不要执行任务，也不要修改文件。
```

ChatGPT 报告学习完成后，就可以继续发送执行任务的请求。

## 示例提示词

| 需求             | 提示词                                                                                                                      |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------- |
| 网络测试         | `使用 ActionAgent 帮我 ping 一下 www.google.com，看看网络是否通畅。`                                                        |
| 项目构建         | `使用 ActionAgent 克隆 https://github.com/Kinal-Lang/Kinal 这个仓库，进行 Linux x86_64 构建，并把构建产物上传为 artifact。` |
| 测试仓库         | `使用 ActionAgent 克隆这个仓库，安装依赖并运行测试，把日志保存到 .action-agent/output/。`                                   |
| 检查 Runner 环境 | `使用 ActionAgent 检查当前 Runner 的系统信息、Python、Node、Git、Docker 是否可用。`                                         |
| 服务器运维       | `使用 ActionAgent 通过 GitHub Secrets 中配置的 SSH 信息连接我的 Ubuntu 服务器，并查看 CPU、内存、磁盘和负载情况。`          |

## 使用 Secrets 处理敏感信息

不推荐把服务器密码、Token、Cookie、私钥等敏感信息直接发给 AI，也不要把它们写进任务文件。

推荐做法是：

1. 在你的 ActionAgent 仓库中打开 GitHub Settings
2. 进入 Secrets and variables
3. 添加需要的 Secrets，例如：
   - `SSH_HOST`
   - `SSH_USER`
   - `SSH_PRIVATE_KEY`
   - `API_TOKEN`

4. 告诉 AI 你添加的准确 Secret 名称，例如 `SSH_HOST`、`SSH_USER` 或 `SSH_PRIVATE_KEY`

AI 应先根据这些名称准备 ActionAgent 的任务执行环境，再编写任务；它不需要也不应该询问 Secret 的真实值。

需要注意：

- ChatGPT 不应该看到 Secrets 的真实内容
- Secrets 只应该在 Runner 执行时使用
- 使用 Secrets 不是绕过安全规则
- 目标服务器、仓库、接口或域名仍必须是你拥有或明确授权操作的

## 安全建议与规避

ActionAgent 会让网页端 AI 拥有更强的执行能力，因此更需要明确边界。

请遵守：

- ActionAgent 更适合放在私人仓库中使用
- 不要在任务中打印 secrets、tokens、cookies、私钥
- 不要让任务输出完整环境变量
- 不要盲目执行 `curl xxx | bash`
- 不要运行无限循环
- 不要执行未授权的渗透测试、扫描、爆破或漏洞利用
- 不要对第三方系统执行破坏性操作
- 连接服务器或执行危险操作前，需要确认目标属于你或你拥有授权
- 不要长时间占用公共 GitHub Actions 资源执行大量任务

如果 ChatGPT 拒绝执行某个请求，通常说明该请求可能涉及：

- 未授权目标
- 明文敏感信息
- 高风险服务器操作
- 可能造成破坏的命令
- 安全策略不允许的行为

此时请优先调整任务方式，例如：

- 使用 GitHub Secrets 传递敏感信息
- 明确说明目标是你拥有或授权的
- 降低任务权限
- 先执行只读检查
- 避免破坏性命令
- 把大任务拆成更小、更可审计的任务

## 故障排查

如果 ActionAgent 没有运行，请检查：

- 是否已经 Fork 到你自己的仓库
- 是否在 ChatGPT 中连接并选择了 ActionAgent 仓库
- GitHub Actions 是否已启用
- workflow 是否有权限提交运行状态
- `.action-agent/scratch.py` 或 `.action-agent/tasks/*.py` 中是否有 `run = true`
- 任务文件顶部是否包含有效的 TOML 元数据
- GitHub Actions 日志中是否有错误
- `.action-agent/result.json` 是否已更新
- 配置的 issue 中是否发布了 ActionAgent 结果评论
- `.action-agent/output/` 是否生成了日志或 artifact

如果你认为 ActionAgent 本身存在问题，请带上以下信息提交 Issue：

- 你的任务文件内容
- `AGENTS.md`
- `.action-agent/run.toml`
- `.action-agent/result.json`
- GitHub Actions 日志
- `.action-agent/output/` 中的日志
- 复现步骤

### 未来目标

- 通过 GitHub Actions 将网页端 AI 的能力反向代理到用户的本地环境，如 Codex、OpenCode 等，榨干 AI 订阅的最后一滴价值——网页端对话接入本地 Agent。

---

<div style="display: flex;gap: 8px;justify-content: center;">

### [提交 Issue](https://github.com/TheD0ubleC/ActionAgent/issues)

### |

### [提交 Pull Request](https://github.com/TheD0ubleC/ActionAgent/pulls)

### |

### [回到顶部](#actionagent)

</div>
<div align="center">

**ActionAgent 遵循 MIT 许可证，欢迎 Fork、使用和改进，但请注意安全边界和使用规范。**

</div>
