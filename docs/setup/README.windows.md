# Windows 快速开始

[项目首页](../../README.md) · [macOS](README.macos.md) · **Windows**

本指南面向 Windows PowerShell，使用 Python 自带的 `venv` 和 `pip`，无需安装 uv。不要将这些命令直接粘贴到 CMD 或 Git Bash。

> 验证状态：已按当前项目配置整理步骤，尚未在 Windows 实机完成安装、启动与业务联调。Linux 将另行测试。

## 1. 准备环境

- Python 3.12，并确保可以通过 `py -3.12` 调用。
- Node.js 22 与 npm。
- 可用的模型服务地址、模型名称和 API Key。

安装完成后重新打开 PowerShell，检查环境：

```powershell
py -3.12 --version
node --version
npm.cmd --version
```

若 `py` 不可用，请先检查 Python 安装与启动器配置；不要在未确认版本的情况下改用系统中其他版本的 Python。

在 PowerShell 中进入下载或克隆后的仓库根目录，即包含 `pyproject.toml` 的目录。下例路径需替换为自己的实际路径：

```powershell
Set-Location "C:\projects\ai-interview"
```

## 2. 创建虚拟环境并安装后端依赖

在仓库根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

`pip install -e .` 根据 `pyproject.toml` 安装项目及其依赖，适用于本地开发，不需要另建 `requirements.txt`。此流程不会读取 `uv.lock`，实际解析出的依赖版本可能与 macOS 锁定环境不同。参见 [pip 本地项目安装说明](https://pip.pypa.io/en/stable/topics/local-project-installs/)。

后续始终直接调用 `.venv` 中的 Python，无需运行激活脚本或修改 PowerShell 执行策略。虚拟环境不能跨平台搬运；如果从 macOS 复制项目，请勿复制其 `.venv`，应在 Windows 重新创建。参见 [Python venv 文档](https://docs.python.org/3.12/library/venv.html)。

## 3. 配置模型

在仓库根目录创建或编辑 `.env`，例如使用记事本：

```powershell
notepad .env
```

按项目首页的[模型配置](../../README.md#模型配置)填写并保存。文件名必须是 `.env`，不能是 `.env.txt`；保存为 UTF-8，已有配置时不要覆盖有效密钥。

## 4. 启动后端

从仓库根目录执行：

```powershell
Set-Location .\src
..\.venv\Scripts\python.exe .\main.py
```

数据目录会自动初始化，默认固定写入 `src/data`，不再依赖启动命令所在目录。如需写到其他位置，在 `.env` 中设置 `DATA_DIR`。这里的 `..\.venv` 指向仓库根目录中的虚拟环境。

- 后端地址：[http://127.0.0.1:7022](http://127.0.0.1:7022)
- API 文档：[http://127.0.0.1:7022/docs](http://127.0.0.1:7022/docs)

保持终端运行。入口启用了开发热重载，后端重启会清空内存会话。请使用 `main.py`，不要使用仍为占位实现的 `interview_agent` 命令。

## 5. 启动前端

打开第二个 PowerShell 窗口，先进入仓库根目录，再执行：

```powershell
Set-Location .\src\frontend
npm.cmd ci
npm.cmd run dev
```

这里使用 `npm.cmd` 调用 npm，避免 PowerShell 选择 `npm.ps1` 时可能遇到的脚本执行策略限制。

打开 Vite 输出的本地地址。开发代理已将 `/interview` 转发到 `http://127.0.0.1:7022`，无需额外设置 API 地址。前后端须同时运行。

随后按[开始面试](../../README.md#开始面试)操作。后端重启后，请刷新页面并重新提交配置。

## 开发检查

完成依赖安装后，在另一个 PowerShell 窗口从仓库根目录执行后端测试：

```powershell
Set-Location .\src
..\.venv\Scripts\python.exe -m unittest discover -s ..\tests -v
```

前端测试与构建检查，另开 PowerShell 窗口并从仓库根目录执行：

```powershell
Set-Location .\src\frontend
npm.cmd test
npm.cmd run build
```

上述命令尚待 Windows 实机验证；即使模拟测试与构建通过，也不等于真实模型或完整 HTTP 链路验收通过。验证范围见[开发检查说明](../../README.md#开发检查)。
