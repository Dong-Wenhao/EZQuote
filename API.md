# EzQuote API 1.6.1

Base URL: http://127.0.0.1:8765/api

Workspace APIs require `Authorization: Bearer TOKEN`, except for health, setup and login. Sessions last 12 hours. The boss and staff accounts are created during initial setup, passwords are stored as hashes, and the API does not accept a role supplied by the client. Mobile APIs use a dedicated signed token; decisions also require the boss password, as described below.

| Method and path | Permission | Purpose |
| --- | --- | --- |
| GET /health | Public | Connectivity, version and setup status |
| POST /setup | Only before any accounts exist | shop_name, boss_password, staff_password |
| POST /login | Public | username is boss or staff; password |
| POST /logout | Signed in | Revoke the current session |
| GET /me | Signed in | Current account and role |
| GET /shop | Signed in | Shop profile |
| PUT /shop | Boss | name, address, phone, terms |
| GET /integrations/status | Signed in | Only AI and phone notification enablement and configuration status |
| GET /integrations | Boss | Non-secret settings and booleans indicating whether credentials are stored |
| PUT /integrations | Boss | Save ConnectionUpdate; empty credentials preserve existing values, while clear_ai_key / clear_wa_token explicitly remove them |
| GET /catalog | Signed in | Current catalog version and products |
| GET /catalog/template | Signed in | Download the synthetic Excel sample |
| POST /catalog/preview | Boss | Check an upload and return headers, mappings, worksheets, products and invalid rows |
| POST /catalog/import | Boss | Revalidate and save a new catalog version |
| POST /inquiries/parse | Signed in | text; return language, item details, candidates and clarification questions |
| POST /quotes | Signed in | Create a quotation draft; request_key prevents duplicate quotations from repeated requests |
| GET /quotes | Signed in | Boss sees the entire shop; staff see quotations they created |
| GET /quotes/ID | Access to the quotation | Quotation, current approval, approved revisions and activity log |
| PUT /quotes/ID | Access to the quotation | expected_revision and new draft content; create a new revision |
| POST /quotes/ID/submit | Access to the quotation | expected_revision; submit to the boss inbox |
| POST /quotes/ID/approve | Boss | expected_revision; freeze a snapshot and generate files |
| POST /quotes/ID/reject | Boss | expected_revision, reason |
| POST /quotes/ID/export | Access to the quotation | expected_revision; retry from the existing approved snapshot |
| GET /quotes/ID/pdf?revision=N | Access to the quotation | Read approved revisions only |
| POST /quotes/ID/activity | Access to the quotation | revision; action is REPLY_COPIED, PDF_PREPARED or REPLY_INSERTED |
| GET /exports/ledger | Signed in | Generate a shop-wide export workbook from approved snapshots and logs |
| GET /notifications | Signed in | Pending-approval notifications for the current role |
| POST /quotes/ID/mobile-link | Access to the quotation | expected_revision; prepare a time-limited mobile approval URL for one quotation |
| POST /quotes/ID/phone-notification | Access to the quotation | expected_revision; manually notify or retry; ACCEPTED / UNKNOWN requires confirm_resend=true |
| POST /mobile/review | Mobile approval token | View the single current revision associated with the token |
| POST /mobile/decision | Mobile token and boss password | expected_revision; decision is approve / return; boss_password, reason |
| POST /mobile/pdf | Mobile approval token | Download the PDF for this approved revision after export is complete |

Excel upload body:

    {
      "filename": "products.xlsx",
      "content_b64": "BASE64_OF_XLSX",
      "mapping": {"unit_price": "My Price"},
      "sheet_name": "Products"
    }

mapping and sheet_name are optional. The maximum size is 5 MB. Macros are not parsed, and cell formulas are not used to calculate prices. The service does not write back to the user's original Excel file.

Draft body:

    {
      "customer": "Demo 01",
      "inquiry": "A牌50kg水泥20袋",
      "language": "zh",
      "items": [{"sku":"CEM-A-50","quantity":"20"}],
      "notes": "",
      "source_confirmed": true,
      "request_key": "UNIQUE-CLIENT-UUID"
    }

Include expected_revision when editing. The server reads prices from the current catalog; extra unit_price, role or approved_by fields are rejected. Monetary values are returned as strings with two decimal places. Database timestamps are UTC; the interface displays them in the computer's local time.

Since 1.1, a draft may include source; it may also be omitted or null:

    {
      "kind": "whatsapp",
      "tab_id": 5,
      "page_session": "CONTENT-SCRIPT-SESSION-UUID",
      "chat_token": "CHAT-VIEW-UUID",
      "chat_title": "Synthetic Customer",
      "message_id": "WHATSAPP-DOM-MESSAGE-ID",
      "anchor": "CAPTURE-ANCHOR-UUID"
    }

source is chat association metadata checked by the user. It does not authorize sending messages or approving quotations. It is saved by quote_id and revision without overwriting older revisions; quotation details return the current source. Manually entered quotations and version 1.0 quotations return null. Passing null during a revision clears the association for the new revision while retaining the old revision's association.

REPLY_INSERTED only means that content was inserted into the chat input; it does not mean WhatsApp sent or delivered it. Before inserting an approved reply, the extension rereads the server's revision, approval status and reply text. It does not use amounts or free text supplied by the page. The event is recorded after insertion and must not be used as a sent-message statistic.

Status flow: DRAFT → PENDING_APPROVAL → EXPORT_PENDING → COMPLETED. A boss return sets REJECTED; editing any status creates a new revision and returns to DRAFT. Revisions do not overwrite approved snapshots.

HTTP 401 requires login, 403 means access is forbidden, 409 means a status or revision conflict, and 422 means input validation failed. If approval succeeds but export fails, the business status is EXPORT_PENDING. HTTP 200 alone must not be displayed as complete success.

The main service remains bound exclusively to 127.0.0.1:8765 and accepts origins from the local workspace and Chrome extension. The mobile gateway binds to 127.0.0.1:8766 and exposes only /mobile, its scripts and styles, /health, and /api/mobile/review, decision and pdf. A public tunnel should connect to 8766; the gateway exposes no account, catalog, configuration or full workspace endpoints.

Mobile API `Authorization: Bearer TOKEN` uses a signed approval token; a normal login session cannot replace it. The token is placed in the notification URL fragment and then submitted by the page in a request header, keeping it out of service access logs. Approval and return also verify the existing boss password, with a limit on incorrect attempts. The link and business revision are checked and consumed in the same transaction.

Connection settings and deployment steps are documented in `接入AI与手机通知_1.2.md`. AI parse responses include ai_state (disabled / used / fallback). On success, method is openai_catalog; on fallback, method is catalog_rules with warning_code. Callers must not present fallback as a successful model call.

Quotation details include mobile_notification with status, error, attempts and updated_at. Status is PENDING, WAITING_GATEWAY, SENDING, ACCEPTED, FAILED, UNKNOWN, PAUSED or CANCELLED. ACCEPTED means only that the WhatsApp API accepted the request; it does not prove delivery. Notification network failures or interruptions do not trigger automatic resending.

WhatsApp notifications currently go only to the explicitly configured boss phone number; customer replies are not sent automatically. The scope remains one shop with fixed boss / staff accounts.


## 1.3 Business data and requirements workflow

| Method and path | Permission | Purpose |
| --- | --- | --- |
| GET /business | Signed in | Business version, inventory, delivery, rules and history overview; no raw history rows |
| GET /business/template | Signed in | Download business_demo.xlsx |
| POST /business/preview | Boss | Upload format; validate Products, Inventory, History, Delivery and Rules |
| POST /business/import | Boss | Same format; atomically import the catalog and business version; repeated imports of the same file are idempotent |
| POST /requirements/review | Signed in with quotation access | Check the original inquiry against final products and delivery; return issues or review_id |
| POST /pricing/preview | Signed in | items, inquiry, area, fulfilment, review_id; optional quote_id excludes this quotation's history during a review |
| POST /quotes/ID/outcome | Access to the quotation | Record open/won/lost only after approval; include expected_revision, expected_outcome_version, note and optional actual_delivery_cost |

/api/inquiries/parse adds mode=requirements, area and fulfilment (auto/delivery/pickup), returning requirement JSON, best_match, alternatives, inventory and reasons in three languages. Omitting mode continues to use the legacy catalog parsing endpoint.

Creating and revising quotations may include pricing_enabled=true, delivery_area and fulfilment (delivery/pickup). After business data has been imported, this mode is mandatory; the client cannot set it to false to bypass inventory or pricing policies. Older approved snapshots remain readable; older pending quotations must be edited and reviewed again.

In addition to expected_revision, /api/quotes/ID/approve accepts discount_pct, freight and pricing_note. Omitting both numeric values means the boss accepts the saved recommendation. Extra fields such as total and unit_price remain rejected. The backend checks maximum discount and minimum estimated gross margin, then saves the decision and approved snapshot in the same transaction.

A quotation's pricing object contains requirement, recommendation and decision. recommendation stores original prices, recommended discount and freight, recommended total, reference sample count, conversion rate, business version, inventory snapshot, cost estimates and reasons in three languages. decision is null before approval; after approval it stores accepted/edited, discount amount, freight, final total, approver, time and note.

A quotation's total while pending approval is the recommended total, not an approved price. Official customer replies come only from approved snapshots. Customer outcome is separate from quotation status; approval does not automatically mark an order as won.

Customer outcomes use expected_outcome_version to prevent overwriting another person's newer record. Saving an identical outcome again does not create a new version. Statistics use only the latest evaluated revision for a given Quote ID, and a quotation being revised excludes its own older history. Unknown actual delivery costs are excluded from average freight costs.

Mobile decision may also include discount_pct, freight and pricing_note, while still requiring the boss password and signed link. review adds pricing; the public gateway remains restricted to single-quotation approval routes.

## 1.4 Step-by-step workspace

Version 1.4 introduced step-by-step pages. The backend and extension in this release are both 1.6.1. Full business quotations add the mandatory review contract below; older clients must be updated together.

Each item returned by GET /api/quotes adds outcome (open/won/lost), taken from the customer outcome for the current quotation revision; it defaults to open if no outcome has been recorded. Staff can list only their own quotations, while the boss can view the shop's list. The latest 200 quotations are returned. The frontend counts PENDING_APPROVAL as awaiting approval, COMPLETED/EXPORT_PENDING with outcome=open as awaiting follow-up, and filters won/lost as closed.

step and needsReparse in the page's saved draft only restore the interface within the same session. They cannot replace official backend quotations or approval records. Changing the original inquiry requires parsing the products again.


## 1.5 Requirements review contract

`POST /requirements/review` request:

```json
{
  "inquiry": "Need 20 bags cement for plastering. Prefer fast setting. Deliver to Shah Alam.",
  "items": [{"sku":"CEM-A-FAST-50","quantity":"20","source_id":null}],
  "area":"Shah Alam",
  "fulfilment":"delivery",
  "corrections":[],
  "quote_id":null,
  "expected_revision":0
}
```

The server reparses the original text; client-supplied fulfilment does not override facts in that text. source_id comes from the parse result. When the product row count is unchanged, source_id may be omitted and rows mapped in order, but quantities are still checked independently. When adding or removing rows, retain their source_id values; unknown or duplicate sources are rejected.

When `can_quote=false` is returned, no review_id usable for official pricing is issued. `issue_details` contains id, code, field, source_id, source_text, the original span, severity, target, and expected_value or choices. Quantity tokens also retain raw, value, unit and the original offset; an unrecognized trailing fragment does not replace the complete number.

Manual corrections must send `corrections:[{"issue_id":"RETURNED_ID","value":"SPECIFIC_CONFIRMED_VALUE","reason":"REASON_VERIFIED_WITH_CUSTOMER"}]`. quantity is a normalized numeric string; sku is a specific SKU; area and fulfilment are the actual final values; ambiguous conditions use the returned choices. Cancel an original product with `{"action":"remove","source_id":"ORIGINAL_SOURCE"}` and add a product with `{"sku":"SPECIFIC_SKU","quantity":"QUANTITY"}`. A reason must contain at least 3 characters. resolved=true, unknown issue IDs, stale issues, incorrect values and extra fields are not accepted.

The server may automatically verify a specific SKU selection that satisfies the original specification. Unknown products, changed quantities and changes to use/preferences/brand still require their corresponding issues to be resolved; insufficient stock always triggers aggregate validation. Multiple products that cannot be split or conditions with unclear ownership require editing the original text and cannot be bypassed with a generic confirmation.

A successful review returns a random review_id and persists the original facts, final selections, issue resolutions, operator, time, parser version, catalog version and business version. Its digest binds the original text, final SKUs/quantities, delivery, corrections, sources and quotation context. review_id belongs only to that user and input and cannot be used for another quotation/revision; changing input or business data after review returns 409 review_stale.

In full business mode, `/pricing/preview`, `POST /quotes` and `PUT /quotes/ID` require review_id. Reviewing a revision requires quote_id and the current expected_revision; PUT must then use the same expected_revision. preview may include quote_id to exclude this quotation's history. Direct creation, revision, submission and initial boss approval all enforce server validation; mobile approval reuses the same checks. Repeated creation remains idempotent through request_key and the digest of the reviewed content.

Quotation details add `review` and `review_required`. An older unapproved business quotation without a current review must receive a new reviewed revision; approved snapshots and PDFs are retained. The backend migration adds only requirement_reviews and quote_reviews. Manual resolution is recorded in the REQUIREMENTS_REVIEWED log; approved snapshots include requirement_review, while pricing.requirement contains the reviewed requirements, selections and record associations.

Structured error detail may contain codes such as review_stale, review_required, invalid_correction, invalid_source_segment and duplicate_source_segment. HTTP 409 means the current input must be reviewed again; 422 means a request value is invalid. HTTP 200 with can_quote=false only means the review completed and listed unresolved issues, not that a quotation can be created.


## 1.5.1 Review additions

Version 1.5.1 uses requirements_rules_v3. Numeric parsing first scans the complete token. Ranges and alternative quantities return multiple_quantities; these issues require verification and editing the original text and cannot be bypassed by confirming a correction value. Invalid selected quantities are checked before normalization and return 422. Added-item issues return the correct item_index and match the specific SKU and quantity. Legacy price-list parsing shares the complete number scanner, but that mode still requires manual price-list checks and provides no business inventory or delivery policies.

The quote in mobile review adds review_required. The mobile page displays manual corrections from pricing.requirement.resolutions. A stale review blocks approval but still permits return. A URL fragment change reloads the scoped quotation; old requests cannot overwrite another quotation, and the password and edited values are cleared when the link changes.

Browser-local drafts record parserVersion. If the version differs, the original text is retained, reparsing is required and old correction caches are cleared. The server still independently checks review_id and parser version; a local cache does not confer authorization.

## 1.5.2 Number integrity and unknown segments

Version 1.5.2 uses requirements_rules_v4. Scanning is anchored on units, first capturing the entire numeric expression and then validating its format. Unknown characters between digits and abnormal repeated separators cannot be skipped to retry parsing the trailing digits. NFKC is used only to determine whether the complete expression is a range; it does not directly transform quantities or the entire source text. raw and span always come from the original text, avoiding position shifts caused by global character normalization. 20／30 returns multiple_quantities; 1_020, unknown symbols and abnormal repeated separators return quantity_format without a default quantity.

When a product is recognized on one side of a conjunction, the other side can be attached back only if it is clearly classified as a preference, specification, logistics statement or polite expression. Other segments remain requirement items and cannot be discarded because the catalog lacks a matching product. Missing products/quantities return unknown_product/quantity. Directly deleting that item still produces missing_product; its explicit cancellation and reason must be recorded under the existing contract. Preference continuation lines and logistics tails containing unknown content are retained as well.

An unresolved review does not generate review_id. Direct pricing returns 422 review_required; creation without a review returns 409 review_stale. Pre-upgrade v3 reviews and caches cannot be used for new quotations, and older unapproved quotations must save a revision with a new review. Approved snapshots and PDFs are not rewritten. Support remains limited to common building-material expressions, not complete semantic understanding of arbitrary natural language.


## 1.5.3 Source coverage and page request ownership

The current parser is requirements_rules_v5. backend/number_words.py evaluates only complete Chinese, English and Malay numbers that follow supported grammar. It no longer adds arbitrary words together or ignores unsupported magnitudes to take trailing values. AI evidence number validation and local scanning share this function. Invalid written quantities retain raw and return quantity_format.

If the source text of a matched product contains content beyond its quantity, specification, product alias, explicit conditions, delivery and common request wording, the parser returns the new blocking issue uncovered_text. The uncovered_text field contains the unexplained segment; span and source_text retain the original text. A generic correction value or reason cannot resolve this issue: the user must supplement, split into lines or edit the original text and parse again. No review_id is issued. Explicit unknown standalone products retain the existing unknown_product, quantity and explicit cancellation contract. The rules conservatively ask for clarification for some normal expressions outside the supported scope and do not promise to understand arbitrary natural language.

English negation supports common straight and curly apostrophes in don't/doesn't. Unclassifiable negative suffixes are also blocked by coverage checks. CR and Unicode line separators are split while preserving original offsets.

The desktop page constrains asynchronous responses by workspace sequence and quotation ID/revision. Opening, polling, saving, submitting, approving, returning, recording outcomes and file operations update only the context in which they began. If the user switches to a new draft during saving, the already authorized save/submission for the original quotation still completes normally, and the new draft is not cleared. After asynchronous review completes before saving, source confirmation is checked again. PDF downloads and preparation records remain bound to the original quotation and revision; a failed response from an old session cannot clear a new session's login.

After upgrading, older unapproved v4 reviews must be regenerated and older drafts must be parsed again. Approved snapshots are not recalculated retroactively.


## 1.5.4 Controlled rejection of long inquiries

In full business mode, parse and requirements/review share understand → split_segments. Splitting uses an explicit stack, pushing right before left to preserve the source's left-to-right order and spans. Product mention positions in the source are cached to avoid repeatedly scanning long trailing text. The existing conjunction criteria and protection for complete numeric expressions are retained.

Budgets are: at most 40 product requirements, including unknown products requiring clarification; at most 160 original nonempty segments; at most 160 pending ranges; at most 320 stack-pop work steps; and at most 512,000 characters of cumulative scanned ranges. Delivery, greetings and standalone modifiers are first classified under the existing rules and do not directly consume the product allowance, but still consume the processing budget. Exceeding any budget fails the entire operation: the first 40 items are not truncated into a result, and no review ID or quotation is written. Valid quotation request bodies still allow at most 40 items.

Budget exceptions are consistently returned by CatalogError as HTTP 422 with this response:

    {"detail":"Inquiry is too large. Use at most 40 products and submit smaller batches."}

The Chinese, English and Malay workspaces map this stable message to their respective smaller-batch prompts. Pydantic continues to validate the 12,000-character request-body limit for text/inquiry, with oversized input still producing a 422 validation error. Neither error represents a quotable result.

This change adds no database tables, does not change requirements_rules_v5 or the review digest format, and does not recalculate existing approved quotations. Performance targets and results on the fixed test machine are documented in VERIFICATION.md. The 2-second target is not a performance guarantee for arbitrary computers, catalogs and inputs.


## 1.6.1 Interface assets

The fixed static asset theme.css adds the green theme and wide/narrow layouts. It is the only addition to the local workspace root's asset allowlist; /assets continues to serve extension assets. The manifest, backend health endpoint and mobile gateway all report version 1.6.1. Business contracts for creation, review, pricing, approval, PDF, Excel and logging retain their existing rules; no business APIs, roles or database tables are added.
