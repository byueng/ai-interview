# 会话隔离与生命周期

实现及验收日期：2026-10-20。对应 [roadmap 第二节](roadmap.md#2-会话隔离与生命周期基础完成后)。

## 生命周期契约

| 操作 | 后端语义 | 页面行为 |
| --- | --- | --- |
| 新建 | `GET /interview/begin` 生成新 UUID，初始化空历史、轮次 0、`active` 和活动时间 | 首次打开、新标签页、点击“新建会话”创建独立会话；成功后替换本标签页缓存，清空配置和消息 |
| 继续 | `GET /interview/sessions/{session_id}` 返回后端配置、完整消息、成功回复轮次和 `expires_at` | 刷新、历史导航、点击“继续会话”按缓存 ID 读取；恢复后可以接着发送 |
| 结束 | `POST /interview/sessions/{session_id}/end` 标记 `ended`；重复结束成功且不再次修改 | 保留当前页面已显示的历史，禁止发送和配置提交；刷新后提示已结束，需主动新建 |
| 过期 | 最近活动时间起满 24 小时视为过期；请求时判定 | 提示过期，需主动新建；不自动重发旧消息 |
| 重启 | `InMemorySaver` 随进程消失；旧 ID 返回不存在 | 刷新或继续提示失效，需主动新建；不拿旧 ID 重建空状态 |

“新建”不隐式结束此前会话；要结束需显式点击“结束会话”。新建失败保留旧缓存。前端使用 `sessionStorage`，普通新导航即使继承 opener 的缓存也创建新 ID；`reload` / `back_forward` 才尝试恢复。浏览器禁用存储时当前页面仍能工作，刷新无法继续原会话。

活动时间在创建、配置写入、预设加载、已接纳的对话输入及正常对话完成时更新。读取/刷新不延长有效期。模型失败可能已保存输入；该输入也算活动。已接纳的执行可以跨过过期时间完成，成功后刷新活动时间。当前过期为逻辑失效，已结束/过期检查点保留在进程内至重启，不承诺后台清理或历史归档。

普通 JSON 接口的未知 ID 为 404；结束/过期为 410；正在处理请求、未配置为 409。UUID 格式不合法由 FastAPI 返回 422。`/stream` 已开始 SSE 后，以上业务失败以 `error` 事件返回，且不发送 `done`。不能仅凭 HTTP 200 判断成功。

## 同会话并发与重复提交

`interview_service.py` 按 Graph 和 UUID 维护短期占用集合。单进程单事件循环内，检查与占用之间没有 `await`：同会话的对话、配置、加载预设、读取状态、结束均互斥；冲突立即拒绝，不排队。不同会话可同时执行。占用在成功、异常、取消、显式关闭流时释放。

客户端 `chat_round` 是它所知的已完成回复数，必须等于后端轮次，不可覆盖后端轮次。第一次传 0，每次成功回复加 1；成功后再提交原轮次直接拒绝，不重复调用模型、不追加消息。这里采用“拒绝重复”的策略，不提供请求 ID 或响应重放。

输入消息 ID 固定为 `<session_id>:human:<chat_round>`。模型失败或取消后，LangGraph 可能已保存 HumanMessage；同轮重试通过 `add_messages` 替换该输入，不多追加一次。若模型回复已提交但客户端未收到 `done`，应先点击“继续会话”同步后端历史和轮次，再决定下一次发送。断流不保证整个执行回滚，也不等于结束面试。

## 检查点类型边界

配置写入和加载预设均调用 `model_dump(mode="json")`，将 `Candidate` / `Interviewer` 转为 JSON 字典，`resume: Path` 转为字符串。`InterviewAgent.load_prompt()` 在使用边界以 `model_validate()` 恢复校验后的局部对象。检查点内不保存这两个自定义 Pydantic 实例。

测试在 `LANGGRAPH_STRICT_MSGPACK=true` 下恢复同一 saver 的检查点，再构建新 Graph 连续执行；验证字典类型、标准消息类型、配置、历史和轮次。未扩大 `allowed_msgpack_modules`，未开启 pickle fallback，未关闭安全校验。当前不迁移进程外旧检查点，因为生产仍使用内存 saver。

## 自动化与浏览器验收

2026-10-20 验证结果：34 项后端测试（严格反序列化模式）、19 项前端测试、TypeScript 检查及生产构建全部通过；`git diff --check` 通过。

| 验收项 | 证据 |
| --- | --- |
| A/B 配置、模型输入、消息及轮次隔离 | `tests/test_session_lifecycle.py::test_interleaved_sessions_keep_model_input_and_history_isolated`；真实浏览器交错 A1 → B1 → A2 |
| 并发、重复请求、取消、失败重试 | 同文件 duplicate / conflict / failure / cancellation / closing 测试；真实 Graph 和 saver |
| 新建、继续、结束、过期、重启失效 | 同文件生命周期测试，含 TTL 边界前一秒和到期时刻、全新 saver 重启模拟 |
| 检查点恢复兼容性 | 同文件 `test_checkpoint_restore_uses_json_configs_without_custom_revivers`；严格模式运行全部后端测试 |
| 刷新和标签页缓存策略 | `src/frontend/tests/api.test.mjs`；刷新复用、新导航即使复制缓存也新建、失败不偷偷更换 ID |
| 页面与真实 HTTP 后端联调 | 下述浏览器验收；Uvicorn + Vite + LangGraph + 内存 saver，只有模型使用本地确定性替身 |

执行命令（从项目根目录；依赖安装后）：

```sh
LANGGRAPH_STRICT_MSGPACK=true PYTHONPATH=src uv run python -m unittest discover -s tests -v
npm --prefix src/frontend ci
npm --prefix src/frontend test
npm --prefix src/frontend run build
git diff --check
```

本次后端实际使用已有 Python 3.12 虚拟环境 `/Users/apple/program/ai-interview/.venv/bin/python`，代码通过 `PYTHONPATH=src` 指向当前 worktree；前端 Node 21.7.3 / npm 10.5.0。安装提示该 Node 版本不在 Vite 支持范围内，但本次 19 项测试及类型检查/生产构建通过；后续环境应采用 Vite 所声明支持的 Node 版本。

浏览器复现：为 `data_dir` 设置独立临时目录，在项目根目录运行 `PYTHONPATH=src:tests uv run uvicorn lifecycle_server:make_app --factory --host 127.0.0.1 --port 7022`；另一个终端运行 `npm --prefix src/frontend run dev -- --host 127.0.0.1`。该入口仅用于验收，不接入真实模型或外部凭据。

本次浏览器操作及观察：

1. A 标签页配置“浏览器岗位A / 本科 / 面试官A”，发送 A1；刷新后仍显示原配置、A1 及回复、第 1 轮。后端读取的 UUID 前后均为 `c5462790-a00c-4d7c-9e3f-746a2f6023bd`。
2. 新开 B 标签页，初始配置和历史为空，UUID 为 `5da2c640-4a23-4c04-b5b9-3276c29750af`；配置“浏览器岗位B / 硕士 / 面试官B”，发送 B1。
3. A 继续发送 A2，显示第 2 轮及两组 A 消息；B 保持第 1 轮，仅含 B 消息。
4. 结束 A：页面显示“会话已结束”，发送/继续/结束按钮禁用；刷新读取原 ID 返回 410，提示主动新建。
5. 点击新建：得到 `7612ace9-6058-4f74-85bf-52efdb048074`，页面为空；B 点击继续仍恢复自己的配置和 B1。
6. 停止并重新启动本次 Uvicorn 测试进程，B 刷新读取原 ID 返回 404，页面提示“会话不存在或已失效，请重新创建会话”，不自动创建。

验证范围：真实 ASGI/HTTP/浏览器及 Graph 检查点行为已测；真实外部模型没有调用。过期使用可控时间自动化测试，未等待真实 24 小时。持久化、多 worker 及账户归属仍是 roadmap 的条件性计划；UUID 是状态定位键，不构成身份认证或访问授权。
