# 当前架构说明

核对日期：2026-10-20
范围：当前后端源码中的实现；不将历史版本功能、设计草案或测试记录视为已完成的端到端能力。

[文档导航](README.md) · [路线图](roadmap.md) · [v2.0.0 发布说明](releases/v2.0.0.md)

## 1. 系统组成

当前后端使用 FastAPI 提供 HTTP 接口，以 LangGraph 编排单轮面试执行，通过 LangChain 模型客户端调用模型。应用内共享编译后的 Graph，会话状态由 checkpointer 按会话 ID 区分，而不是为每个网页创建一个应用或 Agent 实例。

| 模块 | 主要职责 |
| --- | --- |
| `src/main.py` | 启动 Uvicorn；当前监听本机 `127.0.0.1:7022`，启用开发热重载 |
| `src/runtime.py` | 创建 `InMemorySaver`、编译 Graph，并组装运行时资源 |
| `src/backend/cli.py` | 创建 FastAPI 应用并注册路由 |
| `src/backend/interview_routes.py` | 处理会话创建、配置写入及 SSE 事件包装 |
| `src/backend/preset_routes.py` | 处理现有预设列表、加载和删除 URL；当前不改动对外路径 |
| `src/backend/interview_service.py` | 构建会话配置、执行单轮对话、导出快照，并协调预设应用到会话 |
| `src/backend/preset_service.py` | 校验、保存、读取、列出和删除可复用预设文件 |
| `src/backend/storage.py` | 从 `data_dir` 创建统一的辅助数据目录 |
| `src/backend/file.py` | 读写 JSON 文件 |
| `src/schemas.py` | 定义请求模型、面试配置和 `TaskState` |
| `src/interview_agent/graph_builder.py` | 定义 `START → InterviewAgent → END` 执行链路 |
| `src/interview_agent/agent.py` | 组装提示词和消息、调用模型、返回状态增量 |

## 2. 接口与调用顺序

正常业务顺序为：创建会话 → 提交面试配置 → 使用同一会话 ID 发起后续对话。

| 接口 | 当前行为 | 成功响应 |
| --- | --- | --- |
| `GET /interview/begin` | 生成 UUID，路由调用 `aupdate_state` 写入会话 ID | 包含 `session_id` 的 JSON 对象 |
| `POST /interview/personal_information_config` | 接收 `session_id`、`candidate`、`interviewer`，更新对应状态 | JSON 数字 `200` |
| `POST /interview/stream` | 接收 `AgentRequest`，导出执行前快照并执行本轮对话 | SSE 事件流 |
| `GET /interview/read_preset` | 返回已有预设文件名列表 | `{ "files": [...] }` |
| `POST /interview/load_preset` | 读取预设并写入指定会话的配置 | `{ "preset_config": {...} }` |
| `POST /interview/del_preset` | 删除指定预设文件 | JSON 数字 `200` |
| `POST /interview/upload_resume` | 仅有占位函数 | 尚无有效业务处理 |

`AgentRequest` 当前要求 `session_id`、`role`、`message`、`chat_round` 和 `dtime`。业务执行将 `message` 包装为 `HumanMessage`；不会按请求中的 `role` 切换消息类型，也不使用请求中的 `chat_round` 覆盖图内轮次。完整字段和校验规则以 `src/schemas.py` 为准。

## 3. 单轮执行与状态更新

一次 `/stream` 请求按以下顺序处理：

1. 读取该会话已有状态，保存面试者和面试官预设。
2. `run_turn` 导出执行前状态快照。
3. 提交本轮 `session_id` 和新增 `HumanMessage`，Graph 根据 `thread_id` 加载已有状态，通过 `add_messages` 合并消息。
4. `InterviewAgent` 检查配置，按轮次选择开场或后续提示词，将系统提示词与消息历史交给模型的 `ainvoke`。
5. Agent 返回新增 `AIMessage` 和递增后的 `chat_round`，由 Graph 合并更新并保存检查点。
6. 路由将节点更新包装为 SSE `message`，正常完成后发送 `done`。

当前每次 Graph 执行只生成一次面试官回复，不会自动循环完成整场面试。`chat_round` 表示已完成的 Agent 回复次数；模型调用失败不会产生该次成功回复增量。

`AssessAgent`、`EvaluateAgent` 和 `AssiantAgent` 尚未接入执行图，不构成已实现的多 Agent 协作。`resume` 当前是可选 `Path` 字段，Agent 只将其转为字符串，不读取或解析简历文件内容。

## 4. 会话与存储边界

| 概念 | 当前职责与边界 |
| --- | --- |
| `session_id` | 业务会话标识；UUID 本身不是身份认证或访问授权 |
| `configurable.thread_id` | 由会话 UUID 的字符串构造，用于定位检查点 |
| `TaskState` | 保存消息、轮次、面试者配置和面试官配置等业务状态 |
| `InMemorySaver` | 在当前进程内保存检查点；不能跨重启恢复或在多个 worker 间共享状态 |

不同会话 ID 用于区分状态，同一 ID 用于续接已有状态。页面数量本身不决定会话隔离；重复请求和并发行为仍需专门验收。

JSON 导出是辅助文件存储，不是当前 checkpointer 的持久化实现。`data_dir` 是统一的存储根目录；预设文件由预设服务负责，面试服务只在“保存当前会话配置”或“将已读取预设写入会话”时协调调用：

- **状态快照**：写入 `data/state_status/<session_id>.json`，保存本轮消息提交前的快照；同一会话再次导出会覆盖旧文件，不是完整历史归档。
- **面试预设**：写入 `data/interview_preset/<position>.json`，仅保存 `candidate_config` 和 `interviewer_config`；同名岗位按编号保留多份文件。读取、列表和删除仍使用既有 `/interview/*preset` 路径。
- **序列化**：状态快照先使用 `jsonable_encoder` 转换数据；预设使用 Pydantic 的 JSON 模式导出；同步 JSON 文件操作均经 `asyncio.to_thread` 调用。
- **路径**：以上目录均由 `data_dir` 配置派生；服务会创建缺失的父目录。
- **恢复**：预设可读取并回填到已创建会话；尚未从 JSON 文件恢复 Graph 检查点。

## 4.1 当前路由拆分范围

已按职责拆分两个 `APIRouter`：会话相关操作保留在 `interview_routes.py`，预设管理操作位于 `preset_routes.py`。为了不新增接口、也不打断现有前端调用，预设路由暂时继续注册为 `/interview/read_preset`、`/interview/load_preset`、`/interview/del_preset`。

`/presets` 前缀、旧路径兼容策略、自动保存是否改为显式保存，以及 OpenAPI/调用方同步仍是路线图 3.1 的后续验收项；本次文件重组不代表这些接口迁移已完成。

## 5. SSE 与异常边界

当前使用 `stream_mode="updates"` 输出节点状态增量；模型通过 `ainvoke` 返回完整回复，因此不是逐 token 输出，也不是完整状态快照流。

- `message`：节点更新，经 JSON 兼容转换后发送。
- `error`：路由 `try` 块内捕获的处理失败；发送后结束，不再发送 `done`。
- `done`：正常执行结束，携带会话 ID。

预设保存位于该 `try` 块之外，其失败尚未纳入同一套 SSE 错误处理。请求模型校验和流内业务异常属于不同阶段；日志中的 HTTP `200` 不能单独证明整个流成功结束。

## 6. 验证口径

本说明基于源码核对，不新增测试通过结论。[2026-10-09 开发日志](archive/2026-10-09-单次对话Agent开发日志.md)中的模拟测试结果仅对应当时实现。当前版本的业务闭环、文件输出、会话隔离和异常路径验收统一记录在[路线图](roadmap.md)。
