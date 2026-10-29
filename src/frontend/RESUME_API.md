# 配置与简历统一保存

`POST /interview/personal_information_config` 接收 `multipart/form-data`：

- `session_id`：已创建的会话 UUID。
- `config`：JSON 字符串，包含 `candidate_config` 和 `interviewer_config`。
- `file`：可选 PDF 文件。前端通过 FormData 提交，不手动指定 Content-Type。

成功返回 HTTP 200：

```json
{"session_id": "当前会话 UUID", "resume": "服务器上的 PDF 路径或 null"}
```

`resume` 无文件时为 JSON `null`，有文件时为路径字符串。旧的数字 `200` 响应和独立的 `/interview/sessions/{session_id}/resume` 上传接口已移除。

选择 PDF 只更新前端待保存状态。点击“保存并进入面试室”时，一次请求保存配置、PDF 和预设；成功后才跳转。保存失败时保留所选文件，可重新提交。配置未改变但选择了新 PDF，也会提交。

PDF 保存到 `DATA_DIR/swap/{session_id}/简历.pdf`（默认 `src/data/swap`），同一会话再次提交 PDF 会替换旧文件。保存阶段只校验扩展名、非空、PDF 文件头和 10 MiB 大小限制，不调用模型。没有附带 PDF 时保留当前会话已保存的简历。

`CandidateConfig.resume` 保存服务器返回的路径，不再保存 UploadFile 对象。客户端传入的路径不会被采纳；服务器只使用当前会话的路径或新上传文件的路径。刷新页面可从会话快照恢复已保存状态，未提交的文件选择不会跨刷新保留。

预设 JSON 只保存可复用的面试配置，`resume` 为 null，不引用临时缓存。加载预设保留当前会话已有简历，不继承其他会话的文件。生命周期清理仍未实现。

一次 HTTP 请求不等于跨文件系统与 LangGraph 的事务：文件已暂存但配置更新失败，或配置已更新但预设保存失败时，接口返回明确错误，前端不跳转。重试使用当前会话并替换同名 PDF。

开发代理 `/interview` 指向 `http://127.0.0.1:7022`。后端未启用热重载时，修改接口后需要重启；内存会话也需要重新创建。

## 预设去重与简历分析

保存前按完整可复用配置比对已有预设（忽略简历路径，并统一语言别名和表单空白）。配置相同则复用文件，不覆盖、不追加编号；配置不同才另存新文件。加载预设本身不写预设文件，已有重复文件不自动删除。同进程并发保存通过锁避免重复创建。

首次对话时，`InterviewAgent.sync_resume` 在后台线程中读取当前会话的 PDF，用 pypdf 校验文件及加密状态，再用 pdfminer.six 提取各页文字（支持缺少 ToUnicode 但使用标准 Adobe CJK 字符集的字体），以普通 `HumanMessage` 文本传给现有 LLM。分析提示词放在 SystemMessage 中，提取文字作为待分析材料。仅支持包含文字层的 PDF；加密、损坏或无可提取文字的文件会报错，纯扫描件需先进行 OCR。

首轮启动后台分析并生成开场回复；后续轮次等待分析完成，将非空结果写入 `TaskState.resume_evalute`，供面试提示词复用。等待分析的轮次遇到分析失败时停止生成回复。PDF 原文和提取文字不写入会话消息历史或预设。

模型使用 Chat Completions 接收文本，无需支持 PDF 文件附件。


`/interview/stream` 通过 SSE `progress` 事件报告阶段，数据包含当前 `session_id` 和 `stage`。后续轮次仍需等待后台简历分析时发送 `parsing_resume`（前端显示“解析简历中，请等待”）。进度不会作为聊天内容，完成或失败后清除等待状态。
