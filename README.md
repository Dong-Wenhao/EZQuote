# EZQuote

EzQuote MVP 1.6.1 is a local quotation workspace and WhatsApp Web Chrome extension for building-materials stores. It supports Chinese, English and Malay throughout inquiry review, product matching, pricing, owner approval and customer replies.

The default workflow uses local rules and historical business statistics. No AI or WhatsApp API key is required. The backend uses FastAPI and SQLite; the interface and extension use plain HTML, CSS and JavaScript.

## Run the application

Install Python 3.10+ (3.12 recommended), then run this command from the repository root:

```bash
python run.py
```

On macOS / Linux, use `python3 run.py` if `python` is unavailable. The launcher creates `.venv`, installs runtime dependencies and opens the workspace. Keep the terminal open; press `Ctrl+C` to stop. Windows users can also double-click `Start Windows.bat`; macOS / Linux users can run `Start Mac Linux.command`.

On first launch, create a shop and separate owner and staff passwords. The account names are `boss` and `staff`.

## Load the WhatsApp extension

1. Open `chrome://extensions` in Chrome and enable **Developer mode**.
2. Choose **Load unpacked** and select this project's `extension/` folder.
3. Keep the local backend running and refresh WhatsApp Web.
4. Select an inquiry or use its quotation entry, then sign in as `staff` in the side panel. Use a separate workspace tab for the `boss` account.

The backend and extension use local port 8765. Each computer runs its own backend and keeps its own data. The GitHub repository provides source code; the application runs on the computer where it is installed.

## Try the complete workflow

1. Sign in as `boss`, open **Settings → Business data**, and check and import `samples/business_demo.xlsx`.
2. As `staff`, start a new quotation and enter:

   > Hi boss, I need 20 bags cement for plastering. Prefer fast setting. Deliver to Shah Alam. How much?

3. Review the matched product, quantity and delivery area, confirm the source, and submit for owner approval.
4. With the fresh sample workbook, the original total is **RM495.00** and the suggested total is **RM471.20**. The owner can accept it or adjust the price within the business rules.
5. After approval, download the PDF and Excel files, choose a reply language, and check the chat draft before sending. Attach the PDF separately.
6. Record the customer's outcome to include it in later pricing suggestions.

See the [user guide](docs/USER_GUIDE.md) for the complete demonstration, manual corrections, backups and operating limits. The [business data format](docs/DATA_FORMAT.md) explains the workbook. Optional AI connections and mobile approvals are covered in [integrations](docs/INTEGRATIONS.md).

## Project layout

| Path | Contents |
| --- | --- |
| `extension/` | Chrome extension and workspace interface |
| `backend/` | APIs, parsing, pricing, approvals and exports |
| `mobile/` | Optional mobile approval interface |
| `assets/` | PDF font and its license |
| `samples/` | Synthetic demonstration workbooks and product data |
| `tests/` | Backend regressions, extension checks and browser tests |
| `docs/` | User guide, data format, integrations and testing instructions |
| `tools/build_release.py` | Release ZIP packaging and integrity checks |

## Development

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
node tests/extension_checks.mjs
```

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell or `.venv\Scripts\activate.bat` in cmd. Node.js is used for development checks; ordinary application use does not require it. See [testing](docs/TESTING.md) for browser tests and release packaging, and [API.md](API.md) for endpoint contracts.

Runtime data is kept in the ignored `data/` directory by default. Stop the service before backing it up. Preserve `data/` and `.venv/` when updating an installation; do not share personal data or credentials in a submission package.

The Noto Sans SC font uses the [SIL Open Font License](assets/OFL.txt). This repository does not include an open-source license covering the application as a whole.
