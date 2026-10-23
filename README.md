# EZQuote

EzQuote MVP 1.6.1 是面向建材门店的三语报价工作台，支持中文、英文、马来语：整理询价、核对商品与库存、生成价格建议、老板审批、导出 PDF / Excel，以及记录客户成交结果。

项目包含 FastAPI 后端、SQLite 本地存储、原生网页界面和 WhatsApp Web Chrome 扩展。默认使用本地规则与历史统计，无需 AI 或 WhatsApp API 密钥。

## 快速启动

需要 Python 3.10+，推荐 Python 3.12。进入本仓库根目录：

```bash
python run.py
```

macOS / Linux 若没有 `python` 命令，可使用 `python3 run.py`。启动器会自动创建 `.venv`、安装运行依赖并打开本地工作台。保持终端运行，按 `Ctrl+C` 停止。Windows 也可双击 `Start Windows.bat`；macOS / Linux 可运行 `Start Mac Linux.command`。

首次启动时自行设置店名、老板密码和员工密码。老板进入「设置 → 经营数据」，检查并导入 `samples/business_demo.xlsx`，即可体验完整报价流程。详细步骤见 [使用说明](README_先读我.md)。

这是本地应用，服务和扩展固定使用本机端口 8765。把源码上传 GitHub 不会自动发布成公网网站；在云环境中可运行服务和测试，真实 WhatsApp 扩展需在自己的电脑上加载并运行本地后端。

## 目录

| 路径 | 内容 |
| --- | --- |
| `backend/` | API、需求核对、定价、审批与文件导出 |
| `extension/` | 工作台界面与 WhatsApp Web 扩展 |
| `mobile/` | 可选手机审批界面 |
| `samples/` | 合成演示数据与 Excel 模板 |
| `tests/`、`independent-results/`、`retest-results/` | 自动化测试与回归用例 |
| `assets/` | PDF 中文字体及其许可 |
| `tools/` | 发布打包与样例生成工具 |
| `docs/`、根目录说明文件 | 原始需求、使用指南、版本记录 |
| `qa-results/` | 上传包附带的历史验证记录 |

## 开发与验证

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest tests independent-results retest-results -q
node tests/extension_checks.mjs
```

完整后端回归会生成 `independent-results/remaining-*.json`，并刷新 `qa-results/long-inquiry-current.json`。后者在仓库中保留的是交付历史证据；请先备份该文件，将本轮输出另存后恢复备份，或在项目临时副本中运行完整回归。日常执行 `python -m pytest tests -q` 不会刷新这份历史记录。

Windows PowerShell 用 `.venv\Scripts\Activate.ps1` 激活环境，cmd 用 `.venv\Scripts\activate.bat`。

扩展逻辑检查需要 Node.js；浏览器测试还需要 Node.js 20+、Playwright 和 Chromium。浏览器脚本会自行启动测试服务，运行前停止占用 8765 / 8766 端口的项目进程，并顺序执行各脚本。以下为 macOS / Linux Bash 示例，使用已安装的 Chromium：

```bash
npm install --no-package-lock
TEST_PYTHON="$PWD/.venv/bin/python" BROWSER_EXECUTABLE=/path/to/chromium node tests/browser_smoke.mjs
TEST_PYTHON="$PWD/.venv/bin/python" BROWSER_EXECUTABLE=/path/to/chromium node tests/copilot_browser.mjs
```

若尚未安装 Chromium，先运行 `npx playwright install chromium`，再运行脚本时可省略 `BROWSER_EXECUTABLE`。Windows PowerShell 先设置 `$env:TEST_PYTHON = "$PWD\.venv\Scripts\python.exe"`，按需用 `$env:BROWSER_EXECUTABLE = "浏览器完整路径"` 指定浏览器，再执行 `node tests/browser_smoke.mjs`。

接口说明见 [API.md](API.md)，原包的测试范围和实机验证边界见 [VERIFICATION.md](VERIFICATION.md)。`qa-results/` 为原包历史记录，本次导入记录另见 [docs/仓库导入说明.md](docs/仓库导入说明.md)。

## 数据与扩展

运行数据默认保存在 `data/`，可用 `WA_QUOTE_DATA` 指定其他目录。停止服务后备份整个数据目录；数据库、账号、密钥、本地依赖和导出文件不提交到 Git。每台电脑的数据独立。

在 Chrome 扩展管理页启用开发者模式，加载本仓库的 `extension/` 目录，然后刷新 WhatsApp Web。扩展仅处理主动选择的询价；回复由使用者核对后发送。手机网关、真实 AI 和 WhatsApp 通知均为可选功能，配置见 [接入说明](接入AI与手机通知_1.2.md)。

字体使用 SIL Open Font License，见 [assets/OFL.txt](assets/OFL.txt)。本仓库未附带应用整体的开源许可证。
