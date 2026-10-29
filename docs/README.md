# 项目文档

当前版本：v2.2.0，包含会话级简历上传与文本分析、Docker 一键启动。下一版本目标：v2.3.0，按六阶段迁移到共享评价与多 Agent 协作。

- [项目首页](../README.md)：功能与模型配置。
- [架构说明](architecture.md)：当前模块职责、接口和边界。
- [v2.3 路线图](roadmap.md)：全部遗留事项，按 P0/P1 排序，最多七组验收清单。
- [v2.2 路线图归档](archive/v2.2.0-roadmap.md)：保留发布整理前的清单原文。
- [v2.1 原路线图归档](archive/v2.1.0-roadmap.md)：从 Git bd2e4ac 恢复原文，历史描述不作为当前实现结论。
- 运行指南：[Docker 两阶段部署工作流](setup/README.docker.md) · [Windows](setup/README.windows.md) · [macOS](setup/README.macos.md) · [Linux](setup/README.linux.md)。
- 发布说明：[v2.2.0](releases/v2.2.0.md) · [v2.1.0](releases/v2.1.0.md) · [v2.0.0](releases/v2.0.0.md) · [v1.1.0](releases/v1.1.0.md) · [v1.0.0](releases/v1.0.0.md)。
- [日常更新记录](updates/README.md)：保留当时修改与测试范围。

## 维护规则

当前实现集中在架构说明，活动待办集中在 roadmap；发布时归档旧清单原文，再将未完成和未验证事项迁移至下一版并保持优先级。区分实现、模拟测试、真实模型联调与人工验收；发布阻塞未解除时不得声称已正式发布。
