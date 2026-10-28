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

首次对话时，`InterviewAgent.sync_resume` 读取当前会话的 PDF，以 `HumanMessage` 的 `type: file`、`filename` 和 Base64 `file_data` 传给现有 LLM。解析提示词放在 SystemMessage 中，PDF 内容作为待分析材料。

分析返回非空文本后写入 `TaskState.resume_evalute`，供本轮和后续面试提示词使用。同一配置后续轮次复用分析；重新上传简历、修改候选人配置或加载不同配置会清空分析。分析失败不继续生成面试回复。PDF/Base64 不写入会话消息历史或预设。

当前配置的 qwen3.8-max-0902 的 PDF 输入协议参考[阿里云 PDF understanding](https://help.aliyun.com/en/model-studio/pdf-understanding)：使用 Chat Completions；不能改用当前不支持该文件输入的 Responses API。切换模型时需确认文件输入能力。


`/interview/stream` 通过 SSE `progress` 事件报告阶段，数据包含当前 `session_id` 和 `stage`。实际开始 PDF 分析时发送 `parsing_resume`（前端显示“解析简历中，请等待”）；调用面试回复模型前发送 `generating_reply`（显示“面试官正在组织回复，请等待”）。复用分析时不发送解析阶段。进度不会作为聊天内容，完成或失败后清除等待状态。
