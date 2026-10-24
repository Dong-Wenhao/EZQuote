# EZQuote Technical Tools Declaration

This unsigned technical declaration is based on inspection of the EZQuote MVP 1.6.1 repository and its recorded local validation. It describes implemented components and distinguishes optional integrations from verified use. It is not a completed or signed official competition form.

## Application and development tools

| Tool | Version or source of version information | Purpose and scope |
| --- | --- | --- |
| Python | Python 3.10+ required; 3.12 recommended | Application runtime. Local validation used Python 3.12.14. |
| FastAPI | 0.152.0, pinned in `requirements.txt` | Authenticated backend APIs for imports, inquiry review, quotations, approvals and exports. |
| Uvicorn | 0.54.0, pinned in `requirements.txt` | Local ASGI application server. |
| SQLite | Python standard-library `sqlite3`; runtime library version depends on the installation | Local accounts, sessions, quotation revisions, approvals, customer outcomes and activity records. |
| HTML, CSS and JavaScript | Source files in `extension/` and `mobile/` | Workspace, Chrome extension and optional mobile approval interface. The extension uses Manifest V3. |
| openpyxl | 3.1.5, pinned in `requirements.txt` | Reads product and business workbooks and writes quotation ledgers. Product prices come from the imported data, not a language model. |
| ReportLab | 4.4.9, pinned in `requirements.txt` | Generates PDF quotations from approved snapshots. |
| Noto Sans SC font asset | `assets/NotoSansSC.ttf`; license notice in `assets/OFL.txt` | Chinese text in PDF exports. The bundled font retains the SIL Open Font License 1.1. |
| pytest | 9.1.1, pinned in `requirements-dev.txt` | Backend regression tests using synthetic inputs and isolated data. |
| httpx | 0.28.1, pinned in `requirements-dev.txt` | Development tests and local API test clients. |
| PyMuPDF | 1.26.6, pinned in `requirements-dev.txt` | Development checks of generated PDF content. |
| Node.js and Playwright | Node.js 20+ for browser checks; Playwright 1.62.1 in `package.json` | Development-only extension and browser checks. Ordinary application startup does not require Node.js. |
| GitHub | Repository and Git commit history | Source distribution and version history. |
| OpenAI Codex | Development assistance during repository preparation | Used for repository setup, documentation translation and organization, submission preparation, and validation. This assistance is separate from model calls made by the application. Codex is not an end-user runtime dependency. |

Direct Python package versions are specified in [requirements.txt](../requirements.txt) and [requirements-dev.txt](../requirements-dev.txt). Browser-check dependencies are in [package.json](../package.json).

## GenAI, APIs and hosting disclosure

| Service or capability | Implemented state | Verified-use statement |
| --- | --- | --- |
| Default requirement and pricing workflow | Local multilingual rules, catalog matching, stock validation and historical statistics | The demonstrated complete business workflow runs without LLM API calls. Prices, discounts, delivery charges and margin checks are calculated by application code. |
| Optional OpenAI integration | The legacy catalog parser can call the OpenAI Responses API for structured inquiry extraction. It is disabled by default. The configurable default model name is `gpt-5.4-mini`. | Provider-response handling is covered by synthetic tests. No evidence of a successful live model call was supplied for this submission preparation. |
| Qwen | No Qwen provider or endpoint is implemented in the current repository. | Do not describe Qwen as an integrated or demonstrated service. |
| Optional WhatsApp Cloud API | Implemented owner-notification queue, configurable Meta Graph API version (default `v26.0`), and signed mobile approval links. Disabled by default. | Local tests use synthetic provider responses. Live account authorization, message delivery and receipt have not been established by the supplied evidence. |
| Cloudflare Tunnel | Optional `cloudflared` launcher support exposes the separate mobile approval gateway. | A local mobile gateway was tested. No public tunnel use was verified in the supplied evidence. |
| Replit | No Replit deployment URL or proof-of-use material was supplied. The current application is configured for local access. | External team use is unconfirmed. Replit use or deployment must be evidenced before it is claimed. |
| RunPod | No RunPod integration or proof-of-use material was supplied. | External team use is unconfirmed. Declare “Not used” only after team confirmation; provide proof only if it was actually used. |

In optional OpenAI mode, the request contains the selected inquiry and candidate catalog identifiers and descriptions, excluding catalog prices. The application requests `store: false`, validates returned evidence against the inquiry, and falls back to local rules when the request or output fails. This setting is not a claim about all provider retention policies. A model cannot approve quotations or determine final prices.

## Data, human control and privacy

- Included products, workbooks, customers, accounts and external-provider responses used in validation are synthetic demonstration inputs.
- The extension processes the inquiry actively selected by the user; it does not bulk-upload chat history in the background. Staff review the source, products, quantities and delivery information before submission.
- The owner accepts or adjusts a quotation within the business rules before final PDF and ledger generation. Staff check customer replies before sending them; the PDF is attached separately.
- Runtime data is stored locally under `data/` by default and is excluded from Git. Optional provider credentials are saved in local connection settings and are not protected by a hardware-backed key store. Do not distribute personal runtime data, credentials, cookies or browser profiles.
- The prototype does not process payments, file taxes, or provide legal or financial advice. Inventory is an imported snapshot; the application does not reserve or deduct stock automatically.

## Validation and limits

Recorded local validation covers 331 backend cases, 10 extension logic groups, 8 browser smoke groups and 7 complete business/mobile workflow groups. It includes real local services, quotation submission and approval, PDF/Excel downloads, pricing limits and customer-outcome feedback.

Chrome API bridges, WhatsApp page content and external-provider responses in these checks are synthetic. These results do not establish native Chrome/real WhatsApp integration, live Meta delivery, paid model calls, public cloud deployment or first-time installation on a clean Windows machine. See [testing instructions](../docs/TESTING.md) for reproduction commands and scope.

The project code is licensed under the Apache License 2.0; bundled font assets retain their own notices. See [LICENSE](../LICENSE) and [assets/OFL.txt](../assets/OFL.txt).
