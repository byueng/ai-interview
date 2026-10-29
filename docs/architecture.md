# 当前架构（v2.2）

核对日期：2026-10-29。[路线图](roadmap.md) · [版本说明](releases/v2.2.0.md)

Vue 3 前端通过 FastAPI 调用 LangGraph。`src/runtime.py` 在启动时组装 `InMemorySaver` 与执行图；`src/agent_system` 承载 Agent、模型配置与提示词。发布图仅注册 InterviewAgent，路径为 `START → InterviewAgent → END`；每轮请求复用同一会话 `thread_id`，尚非多 Agent 系统。

## 会话与事件

- `GET /interview/begin` 创建 UUID；`GET /interview/sessions/{session_id}` 读取配置、历史与轮次；`POST /interview/sessions/{session_id}/end` 结束会话。
- `POST /interview/personal_information_config` 接收表单 `session_id`、JSON 字符串 `config` 和可选 PDF `file`，一次保存配置、简历及预设，返回 `{session_id, resume}`。
- `POST /interview/stream` 接收当前轮次与消息，输出 SSE `message/error/done/progress`。回复为节点更新，不是逐 token 流；简历分析等待期间可输出 `parsing_resume` 进度。
- 服务层检查会话存在、配置、24 小时闲置过期、结束状态及轮次；同会话操作互斥。前端支持刷新恢复、标签页隔离和主动新建。
- 检查点仍在单进程内存，后端重启后失效；JSON 快照没有接入恢复。结束会话、取消模型请求与浏览器断流分别处理，完整取消契约尚待完善。
- 原始供应商异常保留在服务端异常链和日志，SSE 返回稳定的通用错误，不直接向客户端拼接供应商错误文本。

## 简历分析

PDF 保存到 `DATA_DIR/swap/{session_id}/简历.pdf`，限制 10 MiB、扩展名和文件头，读取时校验会话归属并拒绝符号链接。pypdf 校验结构及加密状态，pdfminer.six 提取文字层；中文 Adobe-GB1 CID 字体回归覆盖了缺少 ToUnicode 的样例。扫描图片不进行 OCR，空文本和无法映射的 CID 输出会报错。

`InterviewAgent.sync_resume` 将提取文字作为普通 HumanMessage 发给模型，不要求供应商支持 PDF 附件。首轮启动后台分析但不等待其完成；后续轮次在需要时等待同一任务，并将分析结果写入 `TaskState.resume_evalute`。简历全文和分析结果不会作为普通对话消息追加，模型提问时通过提示词读取分析结果。

`ResumeTask` 当前按会话缓存后台任务；配置层会清除失效的 State 分析值，但任务级失效、失败重试和结束清理尚未完善。同会话更换简历或岗位后可能复用旧任务，当前应新建会话；改进计划保留在 roadmap。共享评价、按主题阅读和整场 graph 暂停／恢复均为后续设计。

## 预设与数据

interview_routes 与 preset_routes 分开注册，公开预设 URL 仍为 `/interview/read_preset`、`/interview/load_preset`、`/interview/del_preset`。相同配置复用既有预设，不同配置独立命名；预设不携带上传文件路径，加载时保留当前会话自己的简历。状态写入和文件保存不是事务，部分失败通过明确错误反馈。

默认数据根为 `src/data`，可通过 `DATA_DIR` 覆盖。预设与快照含用户内容，本次发布不新增提交这些运行数据。Docker 使用挂载到 `/app/data` 的命名卷；文件持久化不等于内存会话可恢复。

## 部署与人物志

Compose 部署后端和 Nginx 前端，默认仅绑定 `127.0.0.1:8080`。`scripts/deploy.sh` 提供初始化、启动、停止、诊断等操作，macOS 可用 `start.command`；后端只运行一个 worker。

人物志由前端 `scripts/character-journal.mjs` 在开发／构建前导出 accepted 内容至 `public/character-journal`，来源默认在 `src/data/character-journal`。缺失来源目录可导出空集合，已接受清单的缺失文件使构建失败；原始材料与发布素材的完整审阅仍在 roadmap。

## 验证边界

2026-10-29 后端 108 项、前端 34 项、Docker 启动器 6 项测试通过，生产构建与 Docker HTTP／SSE／上传／重建持久化冒烟通过。后端和容器测试使用模拟模型；真实模型、全面浏览器视觉、跨平台新机、跨重启会话恢复和多 Agent 能力不在本次通过范围内。具体命令见版本说明。
