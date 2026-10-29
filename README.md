# AI-Interview

基于 **LangGraph、FastAPI 和 Vue** 的 AI 模拟面试项目。通过配置目标岗位、教育背景、面试语言和面试官角色，在浏览器中开展多轮面试对话。

当前整理为 v2.1.0，包含会话生命周期、预设复用和多页面前端。发布检查尚有阻塞，详见版本说明；下一阶段重点为完整面试流程与多 Agent 分工。项目面向本地开发与个人练习，尚不是生产级多用户服务。

[快速开始](#快速开始) · [当前边界](#当前边界) · [项目文档](docs/README.md) · [版本说明](docs/releases/v2.1.0.md)

## 当前能力

- **可配置面试**：设置目标岗位、学历、语言、面试官身份与面试要求。
- **多轮对话**：面试官根据配置和已有消息生成回复，每次请求执行一轮 Agent 调用。
- **会话状态管理**：使用 UUID 标识面试，通过 LangGraph 检查点管理当前进程内的配置、消息历史和轮次。
- **SSE 事件响应**：前端接收面试回复、错误和完成事件；当前按节点更新返回，并非逐 token 输出。
- **本地 JSON 导出**：保存执行前状态快照与面试配置预设，用于调试和后续复用功能开发。

以上是当前源码中的实现范围，不代表所有异常场景、并发行为和真实模型供应商均已完成验收。详细职责与数据流见[架构说明](docs/architecture.md)。

## 技术栈

| 层次       | 技术与用途                                                              |
| ---------- | ----------------------------------------------------------------------- |
| 前端       | Vue 3、TypeScript、Vite：面试配置、对话展示与事件流消费                 |
| HTTP 服务  | FastAPI、Pydantic、Uvicorn：接口组织、请求校验与服务运行                |
| Agent 编排 | LangGraph：状态管理、消息合并与单轮执行                                 |
| 模型接入   | LangChain `ChatOpenAI`：调用兼容 OpenAI Chat Completions 接口的模型服务 |
| 当前存储   | `InMemorySaver` 保存进程内检查点；JSON 文件保存快照与预设               |

## 快速开始

### Docker 一键运行

安装并启动 Docker 后，从仓库根目录执行：

```bash
./scripts/deploy.sh init  # 首次创建 .env，已有配置不会覆盖
nvim .env                 # 首次填写 API_KEY、BASE_URL、MODEL_NAME
./scripts/deploy.sh up
```

之后只需 `./scripts/deploy.sh up`；macOS 也可以双击仓库中的 `start.command`。
启动成功访问 [http://127.0.0.1:8080](http://127.0.0.1:8080)，停止使用 `./scripts/deploy.sh down`，文件数据会保留。
无需在宿主机安装 Python、uv 或 Node。Windows 可使用指南中的原生 Compose 命令。

设计、两阶段验收与排障见 **[Docker 部署工作流](docs/setup/README.docker.md)**。

### 本地开发

需要直接调试源码时，按操作系统选择运行指南：

**[macOS →](docs/setup/README.macos.md) · [Windows →](docs/setup/README.windows.md) · [Linux →](docs/setup/README.linux.md)**

| 平台                                    | Python 环境管理 | 说明                                             |
| --------------------------------------- | --------------- | ------------------------------------------------ |
| [macOS](docs/setup/README.macos.md)     | uv              | 原有本地开发流程，使用 zsh / bash                |
| [Windows](docs/setup/README.windows.md) | venv + pip      | 使用 PowerShell，不需要 uv；                     |
| [Linux](docs/setup/README.linux.md)     | uv              | bash / zsh 流程已静态核对，尚未在 Linux 实机验收 |

三份指南分别提供依赖安装、服务启动与开发检查命令。模型配置和使用说明在本页统一维护，避免重复与不同步。

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

`API_KEY`、`BASE_URL`、`MODEL_NAME` 为必填项；`TEMPERATURE` 可省略，默认 `0.8`。`env.example` 提供完整字段模板，复制后填写即可。配置从项目根目录 `.env` 加载，也可通过进程环境变量提供。本地启动时快照与预设默认写入 `src/data`，可通过 `DATA_DIR` 改写位置（旧的小写 `data_dir` 仍兼容）；Docker 使用挂载到 `/app/data` 的独立命名卷。

> `.env` 已列入 Git 忽略规则，请勿将真实密钥写入源码、提交记录或公开日志。发送的面试配置与对话内容会交给所配置的模型服务处理。

### 开始面试

Docker 启动后打开脚本输出的地址；本地开发按所选平台指南同时启动前后端，打开 Vite 输出的地址。

1. 打开页面，等待会话初始化完成。
2. 填写岗位、学历、面试官身份与面试要求，选择面试语言。
3. 点击“加载配置”，成功后输入第一条消息并发送。
4. 根据面试官回复继续作答；修改配置后需要重新加载。

同一标签页刷新可从仍存活的后端会话恢复配置、历史与轮次；新标签页创建独立会话。后端重启后，请刷新页面并重新提交配置，不要继续使用旧会话 ID。

## 当前边界

- **记忆不是持久化存储**：检查点仅保存在当前进程内，不支持跨重启恢复或多个 worker 共享状态；JSON 导出尚未接入恢复流程。
- **预设支持复用**：已实现列表、加载回填和删除；预设按岗位名称保存，同名岗位会覆盖旧文件。
- **能力仍在扩展**：辅助总结、评分与评估 Agent、简历上传后端与解析、执行中取消尚未形成完整功能（上传前端与结束会话已实现）。
- **尚无多用户安全体系**：没有完整的账户与权限控制；UUID 不等于访问授权，当前服务不应直接作为公网多用户服务使用。
- **异常与并发仍需验收**：缺失配置、失效会话、文件写入失败、重复提交和并发请求等边界仍需完善。

状态快照可能包含面试配置和对话内容，预设也以明文 JSON 保存。当前本地忽略规则正在调整，发布时应排除预设、会话快照及人物志原始阅读材料，不能整目录加入版本控制。

旧版 Interview Simulator 的题库、SQLite 和评分等历史能力，不代表已迁移到当前版本。活动计划与验收清单统一见[路线图](docs/roadmap.md)。

## 开发检查

检查命令见 [macOS 开发检查](docs/setup/README.macos.md#开发检查)、[Windows 开发检查](docs/setup/README.windows.md#开发检查)或 [Linux 基本检查](docs/setup/README.linux.md#基本检查)。

后端测试使用模拟模型，不代表真实模型或完整 HTTP 链路验收。

前端接口测试使用模拟请求；构建成功只说明类型检查与打包通过。实际使用仍需验证会话创建、配置提交、多轮回复及正常结束事件。本次前端 30 项测试通过，人物志封面改用 v001 后构建通过；后端回归仍未取得通过结果，详见版本说明。

## 项目结构与文档

```text
ai-interview/
├── README.md             # 项目介绍与本地运行入口
├── compose.yaml          # 第一阶段：前后端容器、网络和数据卷
├── deploy/               # Dockerfile 与 Nginx 配置
├── start.command         # 第二阶段：macOS 双击启动入口
├── pyproject.toml        # Python 项目配置
├── uv.lock               # Python 依赖锁定
├── env.example           # 模型与部署配置模板
├── src/
│   ├── main.py           # 后端启动入口
│   ├── runtime.py        # 运行时资源组装
│   ├── schemas.py        # 请求、配置与图状态模型
│   ├── backend/          # 路由、业务服务与文件写入
│   ├── agent_system/     # Agent、执行图、提示词与模型配置
│   ├── frontend/         # Vue 前端
│   └── data/             # 本地生成数据，不纳入版本控制
├── tests/                # 后端测试
├── scripts/              # 一键部署与验收入口
└── docs/                 # 平台运行指南、架构、路线图与版本记录
    └── setup/            # macOS / Windows / Linux 快速开始
```

- [文档导航](docs/README.md)：查找各类文档及维护规则。
- [当前架构](docs/architecture.md)：接口、模块职责、会话状态和数据流。
- [路线图](docs/roadmap.md)：后续任务与验收清单。
- [v2.1.0 发布说明](docs/releases/v2.1.0.md)：本阶段的变更与发布时边界。
