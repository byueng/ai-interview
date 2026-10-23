# 当前架构（v2.1）

核对日期：2026-10-21。[路线图](roadmap.md) · [发布说明](releases/v2.1.0.md)

Vue 3 前端通过 FastAPI 调用 LangGraph。src/runtime.py 组装 InMemorySaver 与执行图；src/agent_system 统一承载 Agent、模型配置与提示词。图仍为 START → InterviewAgent → END，每次请求生成一轮回复，尚非多 Agent 系统。

## 会话与事件

- GET /interview/begin 创建 UUID；GET /interview/sessions/{session_id} 读取配置、历史与轮次；POST /interview/sessions/{session_id}/end 结束会话。
- POST /interview/personal_information_config 更新配置并保存预设。POST /interview/stream 接收消息，输出 SSE message/error/done；这是节点更新，不是 token 流。
- 服务层检查会话存在、配置、24 小时闲置过期、结束状态及轮次；同会话操作互斥。前端支持刷新恢复、标签页隔离和主动新建。
- 检查点仍在单进程内存，后端重启后失效；JSON 快照没有接入自动恢复。结束会话与取消正在执行的模型调用不是同一契约。

## 预设与数据

interview_routes 与 preset_routes 分开注册，公开 URL 仍为 /interview/read_preset、/interview/load_preset、/interview/del_preset。preset_service 处理文件，interview_service 协调应用到会话。前端已有列表、加载和删除。默认数据根为 src/data，可通过 DATA_DIR 覆盖；预设与快照含用户内容，不应加入发布。

## 简历与人物志

简历上传 UI 发送原始 PDF，约定 POST /interview/sessions/{session_id}/resume；对应后端尚未实现，旧 /interview/upload_resume 返回 501。解析及简历上下文接入未完成。

人物志由前端 scripts/character-journal.mjs 在开发/构建前导出 accepted 内容至 public/character-journal；来源默认在 src/data/character-journal。缺失来源目录可导出空集合，但已接受清单的缺失文件会使构建失败。原始素材、工作流记录与公开导出需要分开管理。

## 验证边界

tests/ 包含后端模拟模型与 HTTP/生命周期测试，src/frontend/tests 包含接口、简历及人物志测试。本次执行结果见发布说明；真实模型、跨重启持久化、多用户授权和完整多 Agent 流程均不作为已验收能力。
