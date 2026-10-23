# EzQuote MVP 1.6.1

This version implements the team's updated complete workflow: customer requirements → trilingual requirement organization → product and stock matching → original product prices and base delivery → historical discount and delivery suggestions → owner approval with or without edits → PDF and customer replies → customer-outcome feedback.

The team's chosen API-free approach is retained. Requirement understanding uses local catalog rules, while Pricing Intelligence runs actual historical statistics and store rules. OpenAI and WhatsApp Cloud API are not called by default. The interface, approval workflow and customer replies support Chinese, English and Malay. All sample business data is synthetic.

## 1.6.1 Final-check fixes

When an older service is still running, the new launcher asks the user to close that window and keep data and .venv, rather than opening the old page. The browser opens only after this service instance has started. Windows startup failures display the relevant error instead of attributing every failure to the Python installation. A normal Ctrl+C stop waits for backend cleanup without displaying a traceback. See “1.6.1_最终交付检查.md” for final-check details.

## 1.6.0 Dark-green interface

The interface follows the team's reference image: a dark-green sidebar, pale gray-green background, white cards and mint-green amount highlights, with consistent EzQuote branding. The desktop workspace shows left navigation, overview figures, recent quotations and workflow guidance. Narrow screens use top navigation and retain the four-step quotation review. Approved, pending and returned states use green, yellow and red indicators, respectively, each reflecting the actual record state.

Product and quotation pages have revised spacing and columns. Wide screens place customer and product summaries on the left and pricing suggestions on the right; narrow screens return to a vertical layout. The WhatsApp message entry, extension icon and optional mobile approval page share the green theme. Only existing features are shown; there are no unimplemented customer, report or sending-status menus. See “1.6_界面更新说明.md” for release notes.

## Historical 1.5.4 Page polish and checklist fixes

That release retained the existing workflow and blue-and-white style, reduced blank space at the top of narrow screens, and emphasized amounts, states and primary buttons. Ordinary quantity evidence was moved into “View the original text for this line,” while unusual quantities remained prominent. The product page shows review in progress, review passed or confirmation needed. The input area adds trilingual entry tips, a character count and batch guidance; notices can be dismissed.

Two items from the team's 1.5.3 checklist were also fixed: splitting is no longer recursive, and exceeding the product count or processing budget returns 422 for the entire inquiry instead of quoting a partial subset. The complete-business browser script waits for the expected amount before asserting it. Each inquiry allows at most 40 product requirements, with separate segment budgets for delivery and greetings. See “1.5.4_优化与验收说明.md”.

## Earlier revisions

The 1.5.3 self-review fixed the addition or truncation of written quantities, omitted products joined in other ways, negation with curly apostrophes, and late desktop responses overwriting another quotation or a new draft. Unexplained original text blocks quotation creation and requires clarification followed by rewriting on separate lines. Save, approval and PDF operations remain tied to the quotation that initiated them. See “1.5.3_自查与修复说明.md” for results and limits.

The preceding 1.5.2 release addressed two omissions identified by independent retesting: unusual separators such as `20／30` trigger clarification, and unsupported formats such as `1_020` preserve the entire number instead of using its tail. Unknown products in the same sentence, such as `cement and sand`, `simen dan pasir` and `水泥和沙子`, are retained. The user must provide the missing product and quantity, or explicitly cancel the item with a recorded reason, before proceeding. See “1.5.2_复测修复说明.md” for reproduction, fixes and validation.

The self-review also fixed quantity ranges, products swallowed by delivery continuation lines, trailing negation, confirmation of manually added items, invalid-number exceptions, number handling in legacy mode, old draft caches and switching quotations within the same mobile tab. The mobile page shows manual corrections and their reasons. See “1.5_自查修订说明.md” for reproduction details, tests and functional limits. If a range or several quantities cannot be assigned unambiguously, verify them, edit the original text and organize the inquiry again.

## Fixes included

- `1,020` is recognized in full as `1020`; insufficient stock blocks the quotation instead of the quantity being truncated to `20`. Malformed numbers require manual verification.
- Twenty bags of cement and twenty bags of nails in the same sentence are retained separately. A continuation-line preference for one product is attached to that product. Conditions whose association across multiple products is unclear still require clarification.
- Common Chinese, English and Malay negation is supported. Candidates that violate conditions such as “not fast-setting” or “not this brand” are excluded first. Negating collection does not become collection. Double negation and conflicting conditions require confirmation.
- The backend reviews the original text, product lines, quantities and delivery. Review records bind to the current input, catalog, business data and quotation revision. Frontend checkboxes or deleted lines cannot bypass them.
- When quantities, products or delivery are changed manually, the page lists the differences. Enter a confirmation reason and review again. Confirmation applies only to the specific values confirmed; further changes require another confirmation.

See “1.5_修复与测试对照.md” for the mapping between fixes and regression cases.

## Updated pages

- Staff home: create a quotation, continue an unfinished quotation, pending approval, follow-up and recent records.
- Guided quotation: customer requirements → product review → quotation confirmation; approved quotations show customer replies and files.
- Owner approval: review products, original prices and suggestions first, then approve directly by default. Price edits, returns and historical evidence expand as needed.
- Owner settings: business data, the product catalog, shop details and optional connections are managed together. Staff do not see the settings entry.
- “Follow-up” means an approved quotation whose customer outcome is still open. “Closed” filters won or lost outcomes. Owner approval does not mean a sale was won.

When upgrading from 1.4 or earlier, retain data and .venv. Complete business data already imported does not need to be imported again. Update the backend and extension together to 1.6.1. For old unapproved business quotations, select “Review this quotation again,” save a new revision and submit it again. Approved PDFs and amounts are retained.

## Which guide to read

- Existing installation: read “更新到1.5_先看这里.md” and retain data.
- First-time teammate experience: read “队友使用指南_1.6.docx” or “先看这里.txt”.
- Editing business data: read “经营数据模板说明.md”.
- Comparing the team's requirements: read “功能覆盖说明_1.5.md”; the original is in docs/需求流程原文.docx.
- Technical interfaces and verification scope: API.md and VERIFICATION.md.

## Startup and import

1. Extract the complete package into a permanent folder. An existing Python installation can be used; Python 3.10+ is required and 3.12 is recommended.
2. Open the folder containing run.py, enter cmd in the file manager address bar, then run python run.py. Keep the window open.
3. Open http://127.0.0.1:8765/. On first use, set the shop name and different owner and staff passwords, each at least 8 characters long. The fixed account names are boss and staff.
4. As the owner, open Settings → Business data, select samples/business_demo.xlsx, choose “Check import contents,” then “Confirm complete business-data import.”
5. The complete workbook contains Products, Inventory, History, Delivery and Rules. Importing it creates both the product catalog and a business-data version, so there is no need to import the old products.xlsx separately.
6. For this demonstration, keep real AI and automatic WhatsApp mobile notifications disabled under Settings → Optional connections.

An internet connection is needed for the first dependency installation and for WhatsApp Web. Ordinary users do not need Node, keys or a mobile tunnel.

Importing only the old samples/products.xlsx retains the conservative legacy catalog mode and RM370.00 demonstration. After importing complete business data, all new quotations and revisions must pass stock and pricing-rule checks. Unchecking a frontend option cannot bypass those rules.

## Load the extension in WhatsApp Web

In Chrome, open chrome://extensions, enable Developer mode, load this project's extension folder, confirm version 1.6.1, then refresh https://web.whatsapp.com/.

The extension reads only the inquiry selected by the user for the current operation; it does not upload chats in bulk in the background. Select “Generate quotation” beside a message and sign in as staff in the side panel. Sign in as boss in a separate full-workspace tab. You can also capture selected text or paste it manually into the local workspace.

The mobile WhatsApp app and native Windows WhatsApp client do not gain an extension button. Disable an extension loaded from an old path or reload it from the correct path first.

## Complete demonstration

On the staff home page, select “New quotation,” expand “Try a sample inquiry,” and choose “Complete workflow sample.” Alternatively, enter:

    Hi boss, I need 20 bags cement for plastering. Prefer fast setting. Deliver to Shah Alam. How much?

The following inquiries are also supported:

    我要20袋水泥用于抹灰，偏好速凝，送到莎阿南，多少钱？
    Saya mahu 20 beg simen untuk melepa, mahu cepat kering. Hantar ke Shah Alam. Berapa harga?

1. Select “Organize requirements and review products.” The product page recommends CEM-A-FAST-50, Brand A Fast Cement, 50kg, with stock of 85 bags and a unit price of RM23. Alternatives, product switching and recognition details are collapsed by default.
2. Check the specification, quantity and delivery area, then select “Confirm products and view quotation.” If manual values differ from the original text, first enter a reason in the prompt and select “Confirm correction and review again.” The server checks specification selections; a reason cannot bypass insufficient stock. You can return to edit while retaining quantities and delivery information.
3. Compare original and suggested totals on the quotation page: original goods RM460, base delivery RM35 and original total RM495. The initial sample suggests a 3% discount (RM13.80) and RM25 delivery, for a total of RM471.20.
4. Staff check the customer and source, confirm the checkbox and select “Submit for owner approval.” Saving a draft is the secondary action.
5. The owner opens the quotation from the home page's pending-approval list or quotation records and selects “Confirm and approve.” To change the price, expand “Adjust discount and delivery.” Historical evidence and the return reason expand as needed.
6. For example, changing the discount to 4% and delivery to RM30 gives a final amount of RM471.60. The backend checks the maximum discount and minimum estimated margin; prices that are too low are rejected.
7. After approval, staff download the PDF and Excel files and choose the customer-reply language. The customer message is inserted into the corresponding chat draft for a person to check and send. Attach the PDF separately.
8. Once the customer decides, expand “Has the customer replied? Record the outcome,” save won, lost or open, and optionally enter actual delivery cost.
9. Create another similar quotation to include the new outcome in the statistics. If only the single sale above is newly recorded, with actual delivery cost RM29, similar closed orders increase from 8 to 9 and the suggested discount changes from 3% to 3.17%. Later values vary with recorded outcomes.

The interface can switch between Chinese, English and Malay. Missing quantities, delivery areas or unclear specifications trigger clarification; collection can also be selected explicitly. Unknown delivery areas require adding delivery rules to the business workbook. An SKU with insufficient stock cannot be saved as a valid business quotation.

## How pricing suggestions are calculated

The algorithm runs locally without calling a model:

- Similar orders require the same SKU combination, with each SKU's quantity between 0.5 and 2 times the current quantity. Orders from the same area are preferred. If no same-area combination exists, the interface explicitly states that cross-area discount references are used.
- Conversion rate = won orders / (won + lost orders). Open outcomes are excluded from the denominator, and a multi-product order counts as one order.
- The discount reference is the equally weighted average discount from similar won orders. Insufficient samples default to 0% with low confidence.
- Stock is considered high when it reaches the store's high_stock threshold. Low stock retains the original price. When stock is high and the similar-order conversion rate is below 50%, the algorithm tries adding 1 percentage point to the historical discount, still subject to maximum-discount and minimum-estimated-margin limits.
- Delivery references actual delivery costs from won orders in the area. With enough similar orders and high stock, a subsidy up to the maximum delivery allowance is permitted. Delivery rules are used when no actual-cost samples exist.
- Product cost, historical delivery costs and final revenue are used to estimate gross margin. These are checks based on estimated costs, not a guarantee of actual profit.
- Suggestions, historical sample counts and rule versions are fixed to the quotation revision. Later business data or customer outcomes do not rewrite approved quotations.

Stock comes from the imported snapshot. There are no automatic stock movements or reservations. Marking a sale as won records only the customer outcome; update and reimport the business workbook when stock changes.

## Feedback and records

Owner approval is not a customer sale. An approved quotation remains open; only explicitly saved won or lost outcomes enter the conversion rate.

The system records the owner's suggested values, final edits, approver, approval time and customer outcome. Won orders without an actual delivery cost can contribute to sales, discount and conversion statistics, but estimated delivery costs are not recorded as actual delivery history.

Excel records retain Quotes, Items and Activity. Business quotations also include Pricing and Requirements, plus Outcomes when outcomes have been recorded. Quotation records are kept separately from the original product price list.

Editing a completed quotation creates a new revision and requires approval again. Multiple revisions of the same Quote ID do not become multiple historical orders. A revision's suggestion excludes the quotation's own older revisions.

## Saving and backup

Accounts, catalogs, quotations and logs are stored in data/quotes.sqlite3; original uploads in data/uploads; PDFs in data/pdf; and the ledger in data/exports/quotations.xlsx.

Select Save draft or Submit to persist a quotation. Running python run.py again in the same directory reuses the existing accounts. Before backing up, stop the service with Ctrl+C, then copy the entire project folder or the complete data directory. Send teammates a clean installation package so that each creates their own accounts and data. Different computers do not synchronize automatically.

This package contains no real accounts, keys or customer information. Optional keys are still stored in the local connection-settings file without hardware-keystore encryption. Do not share your own data directory.

## Optional APIs and mobile approval

The existing optional OpenAI connection, WhatsApp notification queue, signed mobile links and independent gateway are retained. Legacy catalog mode can use a real model; the new requirement matching and historical pricing default to local rules and statistics throughout.

When a mobile entry is configured, the mobile page also shows original prices, suggestions, discounts and delivery. The owner can accept or edit them, then enter the owner password to approve. The full workspace remains bound to 127.0.0.1:8765 and the separate mobile gateway to 8766. Temporary HTTPS tunnels and real incoming messages still require integration tests with the user's account.

See “接入AI与手机通知_1.2.md” for the historical connection guide. These connections are not prerequisites for the API-free demonstration. Provider acceptance does not mean mobile delivery; delivery/read webhooks are not implemented. Customer replies are still sent by a person.

## Development and reproduction

The backend uses FastAPI, SQLite, openpyxl and ReportLab, with Decimal amounts. The extension is plain HTML/CSS/JS and has no bundle/build step.

    python -m pip install -r requirements-dev.txt
    python -m pytest tests -q
    node tests/extension_checks.mjs

See VERIFICATION.md for browser scripts. Ordinary application use does not require Node. The development sample-generation script tools/build_business_sample.mjs uses artifact-tool provided by Codex, which is not an end-user dependency. Sample Excel files are already included in the installation package and can be edited directly.

The PDF font is Noto Sans SC, distributed under the SIL Open Font License. See assets/OFL.txt.
