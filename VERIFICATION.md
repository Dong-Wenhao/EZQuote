# EzQuote 1.6.1 Verification record

This was the final delivery check for the 1.6 series, correcting duplicate-start and normal-stop handling. The candidate ZIP was extracted into a path containing spaces, all regressions were run, and the actual run.py launcher was used to verify an in-place upgrade from 1.6.0, reuse of the existing virtual environment and another restart. Dependencies were prepared in the test environment beforehand; first-time online installation on Windows was not verified. The environment used Linux, Python 3.12.14, Chrome Headless Shell 140.0.7339.207, a real local FastAPI service and a mobile gateway. Data, accounts, historical orders, chat DOM and external-provider responses were synthetic test inputs.

## Backend: 331 tests passed

Command executed:

    python -m pytest tests independent-results retest-results -q --disable-warnings --tb=short

Result: 331 passed, 1 warning in 39.19s. All existing 329 tests were retained, with 2 launcher regressions added to check that an occupied port does not open the wrong page or a mobile tunnel, and that normal Ctrl+C waits for child-process cleanup. Full output is in qa-results/backend-pytest.txt. The warning is the existing Starlette/httpx compatibility deprecation notice.

This release updated only the business backend's runtime version. The launcher reserves its own port first, waits for its service instance before opening a browser, and handles Ctrl+C cleanly. No business endpoints or database tables were added, and pricing, review, stock and approval contracts were unchanged. Existing checks continued to pass for numeric integrity, trilingual grammar, unexplained original text, aggregate stock, permissions, manual corrections, review binding, idempotency, PDF/Excel, historical snapshots, export recovery, migration and 40/41/1,000-segment boundaries.

This run's long-input result is in qa-results/long-inquiry-current.json, with the version read automatically from the health endpoint rather than replacing historical evidence. Performance evidence and verification notes for 1.5.4 remain in qa-results/long-inquiry-v154-after.json, verification-v154.txt and the corresponding release notes. No new performance commitment is inferred from them in this release.

## Startup and upgrade: 5 real test groups passed

Version 1.6.0 was run from an actual extracted directory. Owner and staff accounts were created, the business workbook was imported, and draft, pending-approval and RM471.20 approved quotations were saved. After stopping the service and replacing files with the new version, ordinary python run.py started 1.6.1 through the existing virtual environment. Existing users, passwords, valid sessions, business workbook, quotation states and approval snapshots were retained. Original PDF bytes were identical, and all Excel worksheet cell values matched.

Starting again clearly reported an occupied port without opening the browser, attempting a mobile tunnel or stopping the service already in use. A local probe recorded actual browser handoff calls and confirmed that only the newly ready version was opened. After upgrading, approval, return and won-outcome recording still worked; another normal stop and restart produced no traceback and retained the data. Existing .venv markers and retained files were unchanged. Full records are in qa-results/upgrade-v160-v161.json; the old duplicate-start reproduction is in launcher-v160-before.json.

## Browser: 64 groups passed

Nine scripts ran sequentially without competing for ports 8765/8766, and no unhandled JavaScript errors occurred. Existing business assertions in each script were retained. The fixed background-color assertion was updated to #f4f8f6 to match the reference palette.

| Script | Groups passed | Scope |
| --- | ---: | --- |
| browser_smoke.mjs | 8 | First-run setup, Excel import through the real interface, staff submission, owner approval, downloads, three languages and missing information |
| chat_integration.mjs | 6 | Synthetic WhatsApp source, clarification, preservation of unsaved content, submission, insertion into the correct chat and rejection after switching to a different chat |
| mobile_browser.mjs | 6 | Synthetic notification provider, real local mobile gateway, password, Malay approval, PDF and narrow screens |
| copilot_browser.mjs | 7 | Complete business import, stock recommendation, minimum-margin rejection, owner price edits, final exports, customer-outcome feedback and mobile price edits |
| guided_browser.mjs | 7 | Role-based navigation, guided review, draft restoration, returning to edit, approval returns, filters and trilingual layouts |
| semantic_browser.mjs | 6 | Complete quantities, multiple products with equal quantities, negation, continuation-line preferences, isolation of asynchronous input and actual PDF |
| self_review_browser.mjs | 10 | Full-width ranges, unusual numbers, unknown products and cancellation, correction records, caching and mobile quotation switching |
| audit_browser.mjs | 8 | Late desktop responses, edits to the same draft while waiting, source confirmation, PDF ownership and original-text coverage |
| ui_polish_browser.mjs | 6 | Real theme assets, sidebar entry, role restrictions, six viewport widths, three languages, review-in-progress/passed states, collapsed evidence, amount layout, oversized-input errors, keyboard dismissal and logout cleanup |

The interface scripts verified that the desktop new-quotation entry actually entered the workflow and checked aria-current after returning home. Staff still had only Home and Quotation records navigation; owner settings remained protected by existing role checks. The home page had no horizontal overflow in all three languages at widths of 320, 430, 768, 900, 1160 and 1440px; 900px was the sidebar breakpoint.

The review HTTP response was deliberately held to verify “Review in progress” and aria-busy, then released to reach “Review passed” and RM471.20. Original text and ordinary quantity evidence remained expandable, while incorrect quantities still showed warnings. Trilingual quotation amounts had no horizontal overflow or clipped amount cards at 320, 430 and 1160px. An input with 1,000 segments was still rejected in a controlled way, retained its original text and created no quotation; switching back to normal input recovered the workflow. Logging out hid the workspace and sidebar.

The complete-business script retained its original assertions: original total RM495, recommendation RM471.20, rejection of invalid price changes, RM471.60 after the owner changed to 4% + RM30, final PDF/Excel and trilingual replies, and a 3.17% suggestion on the next quotation after feedback. The previously corrected wait for the explicit expected amount remained effective.

Script logs are in qa-results, summarized in browser-results.json. The 1.5.4 browser summary is separately retained as browser-results-v154.json. Screenshots were used only for internal visual checks and are not included in the release package.

## Extension logic: 10 groups passed

    node tests/extension_checks.mjs

Checks passed for Manifest permissions and syntax of five JS files, English/Malay static copy, message order and origin, oversized messages, context-menu entry, badges, server approval and source checks, clarification insertion and notification deduplication. Extension APIs used a simulated bridge, and the WhatsApp page used a synthetic DOM; this does not establish real-device integration.

## Layout and delivery

- The Chinese desktop home, product, quotation and owner-approval pages, plus the Malay 320px home and mobile approval, were inspected. Green buttons, amounts, states and navigation were readable, with no overlap, clipping or horizontal overflow found. Chinese screenshots used the packaged Noto Sans SC font installed in the test environment.
- The two-page teammate Word guide was updated to EzQuote 1.6.1, including occupied-port handling, then rendered again and checked page by page.
- The ZIP packager checked versions, theme.css, required modules/samples/guides, the 64-group summary, 331-test log, actual upgrade results, CRC and per-file SHA-256. It excluded accounts, keys, data, databases, virtual environments and internal screenshots.

## Development reproduction

    python -m pip install -r requirements-dev.txt
    python -m pytest tests independent-results retest-results -q
    npm install
    node tests/extension_checks.mjs

Set TEST_PYTHON and BROWSER_EXECUTABLE for browser scripts, then execute all nine scripts in the table sequentially. For example:

    node tests/ui_polish_browser.mjs
    node tests/guided_browser.mjs
    node tests/copilot_browser.mjs

In Windows PowerShell, set the actual paths with $env:TEST_PYTHON and $env:BROWSER_EXECUTABLE. Ordinary application startup does not require Node.

## Outstanding real-device checks and limits

First-time installation on a clean Windows machine, the native Chrome extension, and real WhatsApp DOM/source binding/draft insertion still require local integration checks. No paid model, real Meta endpoint, real mobile message receipt or public tunnel was used. Mobile tests covered only a real local gateway with a synthetic provider.

Requirement organization still uses local rules for common building-materials expressions; historical suggestions use statistics and store rules. Stock is an Excel snapshot without reservations or stock movements. Customer outcomes are recorded manually, and approval is not a won sale. People check and send customer replies, with PDFs attached separately. Each computer's data is independent; retain data and .venv during upgrades.
