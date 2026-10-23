# EZQuote

EzQuote MVP 1.6.1 is a trilingual quotation workspace for building-materials stores. It supports Chinese, English and Malay: organize inquiries, check products and stock, generate pricing suggestions, obtain owner approval, export PDF / Excel files, and record customer outcomes.

The project includes a FastAPI backend, local SQLite storage, a plain web interface and a WhatsApp Web Chrome extension. The default workflow uses local rules and historical statistics, without AI or WhatsApp API keys.

## Quick start

Python 3.10+ is required; Python 3.12 is recommended. From the repository root, run:

```bash
python run.py
```

On macOS / Linux, use `python3 run.py` if the `python` command is unavailable. The launcher automatically creates `.venv`, installs runtime dependencies and opens the local workspace. Keep the terminal running and press `Ctrl+C` to stop. On Windows, you can also double-click `Start Windows.bat`; on macOS / Linux, run `Start Mac Linux.command`.

On first launch, set your shop name and separate owner and staff passwords. As the owner, open Settings → Business data, check and import `samples/business_demo.xlsx`, then try the complete quotation workflow. See the [user guide](README_先读我.md) for detailed steps.

This is a local application; the service and extension use local port 8765. Uploading the source to GitHub does not publish a public website. The cloud environment can run the service and tests; real WhatsApp extension use requires loading the extension on your own computer and running the local backend there.

## Directory layout

| Path | Contents |
| --- | --- |
| `backend/` | APIs, requirement review, pricing, approval and file exports |
| `extension/` | Workspace interface and WhatsApp Web extension |
| `mobile/` | Optional mobile approval interface |
| `samples/` | Synthetic demonstration data and Excel templates |
| `tests/`, `independent-results/`, `retest-results/` | Automated tests and regression cases |
| `assets/` | Chinese PDF font and its license |
| `tools/` | Release packaging and sample-generation tools |
| `docs/` and root documentation files | Original requirements, user guides and release notes |
| `qa-results/` | Historical verification records included in the uploaded package |

## Development and validation

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest tests independent-results retest-results -q
node tests/extension_checks.mjs
```

The complete backend regression suite generates `independent-results/remaining-*.json` and refreshes `qa-results/long-inquiry-current.json`. The latter is retained in the repository as historical delivery evidence. Back it up first, save the current output separately and restore the backup, or run the complete suite in a temporary copy of the project. The regular `python -m pytest tests -q` command does not refresh that historical record.

On Windows, activate the environment with `.venv\Scripts\Activate.ps1` in PowerShell or `.venv\Scripts\activate.bat` in cmd.

Extension logic checks require Node.js. Browser tests additionally require Node.js 20+, Playwright and Chromium. Browser scripts start their own test services. Stop project processes occupying ports 8765 / 8766 before running them, and execute the scripts sequentially. These macOS / Linux Bash examples use an existing Chromium installation:

```bash
npm install --no-package-lock
TEST_PYTHON="$PWD/.venv/bin/python" BROWSER_EXECUTABLE=/path/to/chromium node tests/browser_smoke.mjs
TEST_PYTHON="$PWD/.venv/bin/python" BROWSER_EXECUTABLE=/path/to/chromium node tests/copilot_browser.mjs
```

If Chromium is not installed, first run `npx playwright install chromium`; you can then omit `BROWSER_EXECUTABLE` when running the scripts. In Windows PowerShell, first set `$env:TEST_PYTHON = "$PWD\.venv\Scripts\python.exe"`, optionally set `$env:BROWSER_EXECUTABLE = "full path to browser"`, and run `node tests/browser_smoke.mjs`.

See [API.md](API.md) for the API contract and [VERIFICATION.md](VERIFICATION.md) for the original package's test coverage and real-device validation limits. `qa-results/` contains historical records from that package; see the separate [repository import notes](docs/仓库导入说明.md) for this import's results.

## Data and extension

Runtime data is stored in `data/` by default; use `WA_QUOTE_DATA` to select another directory. Stop the service before backing up the entire data directory. Databases, accounts, keys, local dependencies and exported files are excluded from Git. Each computer keeps its own data.

Enable Developer mode on Chrome's extension management page, load this repository's `extension/` directory, then refresh WhatsApp Web. The extension processes inquiries that the user actively selects; the user checks replies before sending them. The mobile gateway, real AI and WhatsApp notifications are optional. See the [connection guide](接入AI与手机通知_1.2.md) for configuration.

The font is distributed under the SIL Open Font License; see [assets/OFL.txt](assets/OFL.txt). This repository does not include an open-source license covering the application as a whole.
