# Linux 快速开始

[项目首页](../../README.md) · [macOS](README.macos.md) · [Windows](README.windows.md) · **Linux**

本指南面向 Linux 上的 bash、zsh 等 POSIX shell，使用 uv 管理 Python 依赖，使用 npm 运行前端。命令已按当前源码、`pyproject.toml`、`uv.lock` 和前端脚本静态核对；**尚未在 Linux 主机实际执行安装、启动、测试或模型联调**。

## 1. 准备环境

- Python 3.12：与仓库 `.python-version` 一致。
- uv：管理后端虚拟环境与锁定依赖。
- Node.js 22 与 npm：安装并运行前端。
- 可用的模型服务地址、模型名称和 API Key。

先进入下载或克隆后的仓库根目录，即包含 `pyproject.toml` 的目录。可先确认工具可用：

```bash
python3.12 --version
uv --version
node --version
npm --version
```

在仓库根目录安装锁定的后端依赖：

```bash
uv sync --locked --python 3.12
```

`--locked` 要求依赖与仓库中的 `uv.lock` 一致；不要用未锁定的安装结果替代它。若系统没有 `python3.12` 命令，请先安装或配置 Python 3.12，再执行此步骤。

## 2. 配置模型与数据目录

在仓库根目录创建或编辑 `.env`，例如：

```bash
nvim .env
```

按项目首页的[模型配置](../../README.md#模型配置)填写模型字段。快照和面试预设默认写入 `src/data`，会在首次使用时自动创建，无需手工建目录。若要覆盖默认位置，在 `.env` 中设置可选的 `DATA_DIR`：

```dotenv
API_KEY=your_api_key
BASE_URL=https://your-provider.example/v1
MODEL_NAME=your_model_name
TEMPERATURE=0.8
# DATA_DIR=/absolute/path/to/ai-interview-data
```

`API_KEY`、`BASE_URL`、`MODEL_NAME` 为必填项，`TEMPERATURE` 可省略。`DATA_DIR` 可以使用绝对路径或相对后端进程当前工作目录的路径；旧的小写 `data_dir` 仍兼容，但新配置应优先使用 `DATA_DIR`。已有 `.env` 时只补充缺失项，不要覆盖有效密钥。

> `.env` 已被 Git 忽略。不要将真实密钥、面试内容或导出的 JSON 文件提交到仓库或粘贴到公开日志。

## 3. 启动后端

从仓库根目录执行：

```bash
cd src
uv run main.py
```

- 后端地址：[http://127.0.0.1:7022](http://127.0.0.1:7022)
- API 文档：[http://127.0.0.1:7022/docs](http://127.0.0.1:7022/docs)

保持此终端运行。入口启用了开发热重载，后端重启会清空内存会话。请使用 `main.py`，不要使用仍为占位实现的 `interview_agent` 命令。

## 4. 启动前端

打开第二个终端，从仓库根目录执行：

```bash
cd src/frontend
npm ci
npm run dev
```

打开 Vite 输出的本地地址。开发代理会将 `/interview` 转发到 `http://127.0.0.1:7022`，无需额外设置 API 地址；前后端必须同时运行。

随后按[开始面试](../../README.md#开始面试)操作。后端重启后，请刷新页面并重新提交配置。

## 5. 基本检查

完成依赖安装后，可在另一个终端从仓库根目录执行后端测试：

```bash
cd src
PYTHONPATH=. uv run python -m unittest discover -s ../tests -v
```

前端测试与构建检查，另开终端并从仓库根目录执行：

```bash
cd src/frontend
npm test
npm run build
```

启动后可在浏览器访问 `/docs`，并确认前端加载后能建立会话、提交配置和接收事件。后端测试使用模拟模型；前端测试使用模拟请求；构建成功仅说明类型检查与打包通过。它们都不等于真实模型调用或完整 HTTP 业务验收。

## 验证状态与当前限制

- **已静态核对**：本指南的 Python、uv、npm、后端入口、端口、Vite 代理、数据目录和测试命令均来自当前 worktree 源码与项目配置。
- **未在 Linux 执行**：依赖安装、后端/前端启动、自动化测试、浏览器访问和真实模型联调。因此本指南不是 Linux 实机验收记录。
- **当前代码限制**：会话检查点只保留在当前进程，后端重启后不能继续使用旧会话；真实模型调用的可用性取决于供应商配置与凭据。
