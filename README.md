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

以下步骤用于本地开发，命令以 macOS / Linux shell 为例。先进入仓库根目录，再按各步骤切换目录。

### 1. 准备环境与后端依赖

- Python 3.12：与仓库 `.python-version` 保持一致。
- uv：管理 Python 环境与依赖。
- Node.js 22 与 npm：安装并运行前端依赖。
- 可用的模型服务地址、模型名称和 API Key。

在仓库根目录执行：

```bash
uv sync --locked --python 3.12
```

### 2. 配置模型

在仓库根目录创建或编辑 `.env`。已有配置时只修改所需项，不要覆盖有效密钥。

```bash
nvim .env
```

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

### 3. 启动后端

在仓库根目录执行：

```bash
cd src
mkdir -p data/state_status data/interview_preset
uv run main.py
```

当前快照写入不会自动创建父目录，因此首次使用前需要执行上述目录初始化。请保持从 `src` 目录启动，使文件统一保存到 `src/data`。

- 后端地址：[http://127.0.0.1:7022](http://127.0.0.1:7022)
- 交互式 API 文档：[http://127.0.0.1:7022/docs](http://127.0.0.1:7022/docs)

当前入口启用了开发热重载；保存后端代码触发重启时，内存中的会话状态会丢失。`pyproject.toml` 中的 `interview_agent` 命令仍是占位入口，请使用上述 `main.py` 启动服务。

### 4. 启动前端

打开另一个终端，在仓库根目录执行：

```bash
cd src/frontend
npm ci
npm run dev
```

打开 Vite 在终端输出的本地地址。开发代理已将 `/interview` 请求转发到 `http://127.0.0.1:7022`，按此方式运行无需额外设置 API 地址。

前端和后端需要同时运行；仅启动前端不能完成面试。

### 5. 开始面试

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

后端测试使用模拟模型，不代表真实模型或完整 HTTP 链路验收。在仓库根目录执行：

```bash
cd src
mkdir -p data/state_status
PYTHONPATH=. uv run python -m unittest discover -s ../tests -v
```

前端接口测试与构建检查，在另一个终端从仓库根目录执行：

```bash
cd src/frontend
npm test
npm run build
```

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
└── docs/                 # 架构、路线图、发布记录与历史归档
```

- [文档导航](docs/README.md)：查找各类文档及维护规则。
- [当前架构](docs/architecture.md)：接口、模块职责、会话状态和数据流。
- [路线图](docs/roadmap.md)：后续任务与验收清单。
- [v2.0.0 发布说明](docs/releases/v2.0.0.md)：本阶段的变更与发布时边界。
