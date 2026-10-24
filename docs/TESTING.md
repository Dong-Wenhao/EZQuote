# Testing and release packaging

The tests use synthetic accounts, products, inquiries and isolated databases. The application, extension files, sample workbooks, fonts and launchers are the same files used by the normal local workflow.

## Backend regressions

Install Python 3.10+ (3.12 recommended). From the repository root:

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip check
python -m pytest tests -q --disable-warnings --tb=short
```

On Windows, use `.venv\Scripts\Activate.ps1` in PowerShell or `.venv\Scripts\activate.bat` in cmd. Stop the development service before tests that use ports 8765 / 8766.

All 331 backend cases are in `tests/`, including the independent requirement and long-input regressions. Coverage includes quantity integrity, multilingual parsing, stock, permissions, manual corrections, review binding, pricing, approval, idempotency, PDF / Excel exports, snapshots, feedback, mobile links and launcher behavior. Tests that save diagnostic JSON write it to the ignored `test-results/` directory.

## Extension logic

Node.js runs the extension checks without installing browser dependencies:

```bash
node tests/extension_checks.mjs
```

These checks cover permissions, script syntax, translations, message origins, source binding, approved reply insertion, clarification and notification deduplication. Chrome APIs are simulated; this is not a substitute for installing the extension in a real browser.

## Browser workflows

Install Node.js 20+ and the development dependencies:

```bash
npm install --no-package-lock
npx playwright install chromium
```

The scripts start their own local services with temporary data. Keep ports 8765 / 8766 free and run scripts sequentially. From a macOS / Linux Bash terminal:

```bash
TEST_PYTHON="$PWD/.venv/bin/python" node tests/browser_smoke.mjs
TEST_PYTHON="$PWD/.venv/bin/python" node tests/copilot_browser.mjs
```

To use an existing Chromium installation, also set `BROWSER_EXECUTABLE` to its full path. Windows PowerShell can set `$env:TEST_PYTHON = "$PWD\.venv\Scripts\python.exe"` and optionally `$env:BROWSER_EXECUTABLE = "full path to browser"` before running the same Node scripts. `QA_OUTPUT` can select an output directory; otherwise scripts use their default temporary directory.

The smoke test covers setup, import, quotation submission, approval and downloads. The complete business test covers stock matching, pricing limits, edited-price approval, final PDF / Excel amounts, customer outcomes and the local mobile gateway. Additional browser checks are available through the `check:*` commands in [package.json](../package.json).

Browser checks use synthetic WhatsApp pages and provider responses. Native Chrome extension behavior, the real WhatsApp interface, real Meta delivery, paid model calls, public tunnels and first-time Windows installation require the corresponding real environment and accounts.

## Build a release

```bash
python tools/build_release.py
```

The packager writes `../output/EzQuote_MVP_v1.6.1.zip` with a `wa_quote_mvp/` root directory. It includes the complete extension, runtime code, launchers, dependencies, font notices, Apache license, samples, current documentation and images, supplied submission materials and development tests. It checks required files, version consistency, packaged extension bytes, ZIP CRC and SHA-256 hashes. Missing proposals, service proofs and public links are not created or certified by packaging.

Local data, databases, credentials, virtual environments, dependency caches and generated test outputs are excluded. Extract the complete ZIP before running `python run.py` or loading its `extension/` directory.
