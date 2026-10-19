# macOS 快速开始

[项目首页](../../README.md) · **macOS** · [Windows](README.windows.md)

沿用项目原有的 macOS 本地开发流程，使用 zsh / bash 和 uv。以下命令不作为 Linux 已验证的安装说明；Linux 将另行测试。

## 1. 准备环境

- Python 3.12：与仓库 `.python-version` 一致。
- uv：管理后端虚拟环境与依赖。
- Node.js 22 与 npm：安装并运行前端。
- 可用的模型服务地址、模型名称和 API Key。

先在终端进入下载或克隆后的仓库根目录，即包含 `pyproject.toml` 的目录。后续步骤会注明工作目录。

在仓库根目录安装后端依赖：

```bash
uv sync --locked --python 3.12
```

## 2. 配置模型

在仓库根目录创建或编辑 `.env`，例如使用 Neovim：

```bash
nvim .env
```

按项目首页的[模型配置](../../README.md#模型配置)填写并保存。已有配置时不要覆盖有效密钥。

## 3. 启动后端

从仓库根目录执行：

```bash
cd src
uv run main.py
```

数据目录会自动初始化，默认固定写入 `src/data`，不再依赖启动命令所在目录。如需写到其他位置，在 `.env` 中设置 `DATA_DIR`。

- 后端地址：[http://127.0.0.1:7022](http://127.0.0.1:7022)
- API 文档：[http://127.0.0.1:7022/docs](http://127.0.0.1:7022/docs)

保持终端运行。入口启用了开发热重载，后端重启会清空内存会话。请使用 `main.py`，不要使用仍为占位实现的 `interview_agent` 命令。

## 4. 启动前端

打开第二个终端，从仓库根目录执行：

```bash
cd src/frontend
npm ci
npm run dev
```

打开 Vite 输出的本地地址。开发代理已将 `/interview` 转发到 `http://127.0.0.1:7022`，无需额外设置 API 地址。前后端须同时运行。

随后按[开始面试](../../README.md#开始面试)操作。后端重启后，请刷新页面并重新提交配置。

## 开发检查

完成依赖安装后，在另一个终端从仓库根目录执行后端测试：

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

上述命令是检查入口，不表示当前版本已全部通过。模拟测试、构建与真实业务验收的区别见[开发检查说明](../../README.md#开发检查)。
