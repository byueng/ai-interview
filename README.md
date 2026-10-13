# AI-Interview

基于 **LangGraph、FastAPI 和 Vue** 的 AI 模拟面试项目。通过配置目标岗位、教育背景、面试语言和面试官角色，在浏览器中开展多轮面试对话。

当前处于 v2.0 重构阶段，重点是面试官 Agent、会话状态管理和前后端对话链路。项目面向本地开发与个人练习，尚不是生产级多用户服务。

[快速开始](#快速开始) · [当前边界](#当前边界) · [项目文档](docs/README.md) · [版本说明](docs/releases/v2.0.0.md)

## 当前能力

- **可配置面试**：设置目标岗位、学历、语言、面试官身份与面试要求。
- **多轮对话**：面试官根据配置和已有消息生成回复，每次请求执行一轮 Agent 调用。
- **会话状态管理**：使用 UUID 标识面试，通过 LangGraph 检查点管理当前进程内的配置、消息历史和轮次。
- **SSE 事件响应**：前端接收面试回复、错误和完成事件；当前按节点更新返回，并非逐 token 输出。
- **本地 JSON 导出**：保存执行前状态快照与面试配置预设，用于调试和后续复用功能开发。

以上是当前源码中的实现范围，不代表所有异常场景、并发行为和真实模型供应商均已完成验收。详细职责与数据流见[架构说明](docs/architecture.md)。

## 技术栈

| 层次 | 技术与用途 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Vite：面试配置、对话展示与事件流消费 |
| HTTP 服务 | FastAPI、Pydantic、Uvicorn：接口组织、请求校验与服务运行 |
| Agent 编排 | LangGraph：状态管理、消息合并与单轮执行 |
| 模型接入 | LangChain `ChatOpenAI`：调用兼容 OpenAI Chat Completions 接口的模型服务 |
| 当前存储 | `InMemorySaver` 保存进程内检查点；JSON 文件保存快照与预设 |

## 快速开始

请按操作系统选择运行指南：

**[macOS →](docs/setup/README.macos.md) · [Windows →](docs/setup/README.windows.md)**

| 平台 | Python 环境管理 | 说明 |
| --- | --- | --- |
| [macOS](docs/setup/README.macos.md) | uv | 原有本地开发流程，使用 zsh / bash |
| [Windows](docs/setup/README.windows.md) | venv + pip | 使用 PowerShell，不需要 uv；尚待 Windows 实机验证 |
| Linux | 待确定 | 稍后测试，暂不提供已验证的运行指南 |

两份指南分别提供依赖安装、服务启动与开发检查命令。模型配置和使用说明在本页统一维护，避免重复与不同步。

### 模型配置

在仓库根目录创建或编辑 `.env`。已有配置时只修改所需项，不要覆盖有效密钥。

配置格式如下，所有占位值都需要替换：

```dotenv
API_KEY=your_api_key
BASE_URL=https://your-provider.example/v1
MODEL_NAME=your_model_name
TEMPERATURE=0.8
```

`BASE_URL` 应填写供应商提供的 API 基础地址，而不是网页地址或完整的 `/chat/completions` 路径。模型名称与参数兼容性取决于所选服务。

`API_KEY`、`BASE_URL`、`MODEL_NAME` 为必填项；`TEMPERATURE` 可省略，默认 `0.8`。当前 `env.example` 仅列出部分字段，不能直接作为完整配置使用。配置从项目根目录 `.env` 加载，也可通过进程环境变量提供。

> `.env` 已列入 Git 忽略规则，请勿将真实密钥写入源码、提交记录或公开日志。发送的面试配置与对话内容会交给所配置的模型服务处理。

### 开始面试

按所选平台指南同时启动前端与后端，打开 Vite 在终端输出的本地地址。

1. 打开页面，等待会话初始化完成。
2. 填写岗位、学历、面试官身份与面试要求，选择面试语言。
3. 点击“加载配置”，成功后输入第一条消息并发送。
4. 根据面试官回复继续作答；修改配置后需要重新加载。

页面刷新会重新初始化会话，不会自动恢复之前的对话。后端重启后，请刷新页面并重新提交配置，不要继续使用旧会话 ID。

## 当前边界

- **记忆不是持久化存储**：检查点仅保存在当前进程内，不支持跨重启恢复或多个 worker 共享状态；JSON 导出尚未接入恢复流程。
- **预设暂时只能保存**：未实现加载与回填；预设按岗位名称保存，同名岗位会覆盖旧文件。
- **能力仍在扩展**：辅助总结、评分与评估 Agent、简历上传解析、面试中断尚未形成完整功能。
- **尚无多用户安全体系**：没有完整的账户与权限控制；UUID 不等于访问授权，当前服务不应直接作为公网多用户服务使用。
- **异常与并发仍需验收**：缺失配置、失效会话、文件写入失败、重复提交和并发请求等边界仍需完善。

状态快照可能包含面试配置和对话内容，预设也以明文 JSON 保存。`src/data` 已被 Git 忽略，分享文件前仍需自行检查敏感信息。

旧版 Interview Simulator 的题库、SQLite 和评分等历史能力，不代表已迁移到当前版本。活动计划与验收清单统一见[路线图](docs/roadmap.md)。

## 开发检查

检查命令见 [macOS 开发检查](docs/setup/README.macos.md#开发检查)或 [Windows 开发检查](docs/setup/README.windows.md#开发检查)。

后端测试使用模拟模型，不代表真实模型或完整 HTTP 链路验收。

前端接口测试使用模拟请求；构建成功只说明类型检查与打包通过。实际使用仍需验证会话创建、配置提交、多轮回复及正常结束事件。本 README 不声明上述检查已在当前版本全部通过。

## 项目结构与文档

```text
ai-interview/
├── README.md             # 项目介绍与本地运行入口
├── pyproject.toml        # Python 项目配置
├── uv.lock               # Python 依赖锁定
├── env.example           # 部分环境变量示例
├── src/
│   ├── main.py           # 后端启动入口
│   ├── runtime.py        # 运行时资源组装
│   ├── schemas.py        # 请求、配置与图状态模型
│   ├── backend/          # 路由、业务服务与文件写入
│   ├── interview_agent/  # Agent、执行图、提示词与模型配置
│   ├── frontend/         # Vue 前端
│   └── data/             # 本地生成数据，不纳入版本控制
├── tests/                # 后端测试
└── docs/                 # 平台运行指南、架构、路线图与版本记录
    └── setup/            # macOS / Windows 快速开始
```

- [文档导航](docs/README.md)：查找各类文档及维护规则。
- [当前架构](docs/architecture.md)：接口、模块职责、会话状态和数据流。
- [路线图](docs/roadmap.md)：后续任务与验收清单。
- [v2.0.0 发布说明](docs/releases/v2.0.0.md)：本阶段的变更与发布时边界。
