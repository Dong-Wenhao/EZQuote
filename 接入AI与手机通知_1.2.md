# AI and owner mobile notifications: local integration guide

First replace the original project with the 1.2 code while keeping data, then sign in with the existing boss account and open “Connection settings” in the full workspace.

This guide covers account configuration and final integration testing together. The code is prepared, but access to real services still depends on your API permissions, quota, Meta test numbers, and network.

## 1. AI service

1. Create your own API key on the [OpenAI API platform](https://platform.openai.com/api-keys) and confirm that this project has permission to call the model.
2. Enter the key locally under “Connection settings → AI inquiry understanding.” The default model is gpt-5.4-mini. You can instead enter a model available to your account that supports structured output through the Responses API.
3. Select “Enable real AI integration” and save the connection settings.
4. After saving, the key field is cleared and only the saved status is shown. Leaving the field empty later preserves the key. To remove a saved key, select the clear option and disable AI.

AI receives the selected inquiry text plus the names, brands, specifications, units, and codes of up to 300 relevant products. The application does not additionally include chat contact details or price-list price fields. If the selected text itself contains personal information, that information is submitted as part of the text.

The model separates products and interprets quantities. The backend checks evidence in the original text, brands, specifications, quantities, and catalog matches. Amounts are calculated on the server using the price list. Saving and approving quotations still require human confirmation.

The interface displays:

| Display | Meaning |
| --- | --- |
| AI understanding + price-list verification | The model returned structured output and the application validated it |
| Using product catalog rules for this request | AI is not currently enabled |
| AI is temporarily unavailable; using catalog rules for this request | A timeout, credential issue, model permission, refusal, or output-validation problem occurred; an error code follows |

API calls count toward your account's API usage. The application does not automatically repeat model requests. A visible rule-based fallback is retained when the model fails.

## 2. Opening the approval page on the owner's phone

The computer's 127.0.0.1 address refers only to that computer. The owner must open the HTTPS link in the notification on their phone.

### Install cloudflared once

Run this in a new Windows command window:

    winget install --id Cloudflare.cloudflared --exact

After installation, close the old command window, open a new one, and check:

    cloudflared --version

If winget is unavailable, use the Windows download on the [official Cloudflare download page](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/). Alternatively, rename the official executable for your computer to cloudflared.exe and place it in this project's tools directory.

### Start mobile mode

1. Press Ctrl+C to stop the normal quotation service first.
2. Double-click Start Mobile Windows.bat in the original project, or run the following from cmd in the original directory:

       python run.py --mobile

3. The application starts the local quotation service, a separate mobile gateway, and a temporary tunnel. When the temporary HTTPS address appears, keep the command window running.
4. Sign in as boss, open “Connection settings,” and select “Reload settings.” The “Mobile approval HTTPS URL” is normally filled in automatically.
5. Save the connection settings.

The local workspace continues to use port 8765, and the mobile gateway uses a separate port, 8766. The launcher exposes only 8766 through the tunnel. The mobile gateway provides viewing, decisions, and PDFs for a single quotation; it does not expose account, price-list, or full-workspace APIs.

The temporary gateway is intended for development demonstrations and has no availability guarantee. Its domain changes after a restart, so links in old notifications may no longer work. After restarting, reload the gateway address, then explicitly resend notifications for quotations that are still pending. Long-term deployment requires a fixed HTTPS endpoint pointing to the separate mobile gateway service.

### Prepare an approval link before configuring Meta

Even without Meta credentials, once the mobile gateway is running and saved, staff can select “Copy mobile approval link” after submitting a quotation and manually forward it to the owner to check the mobile approval page. This does not send a message automatically.

The owner opens the link, checks the line items, enters the owner password created during initial store setup, and approves or rejects the quotation. Links are valid for 60 minutes by default. Editing a quotation invalidates old links, and repeated clicks cannot approve it twice. Mobile approval uses the same backend approval and archiving logic.

## 3. Connecting WhatsApp mobile notifications

The extension uses the WhatsApp Cloud API to send notifications; it does not reuse the WhatsApp login session in Chrome. A Meta-assigned test business number can be the notification sender, while staff continue to use their existing WhatsApp accounts with the extension.

Open [Meta WhatsApp developer getting started](https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started) and prepare an application with WhatsApp business messaging enabled in your own developer account. Use that account's API Setup / getting-started page to obtain a test sender and access token, then add and verify the actual owner as a test recipient. Interface names depend on the account's current pages.

Return to the local “Connection settings” and fill in:

| Local field | What to enter |
| --- | --- |
| WhatsApp Phone Number ID | The ID associated with the business sender number; copy the value shown on the Meta API page |
| WhatsApp access token | A valid access token for the corresponding application and business number |
| Owner WhatsApp number | The actual recipient number, including country code; Malaysian numbers start with 60; enter digits |
| Number confirmation | Select this after confirming that it is the owner's receiving number |
| Graph API version | Defaults to v26.0; a supported version from the account's example may also be used |
| Mobile approval HTTPS URL | Filled in automatically by mobile mode, or your configured fixed gateway |

Access tokens may have expiration dates and permission limits; replace them when expired. Add test recipients according to Meta's test-number requirements. Do not send service credentials in customer chats or team groups.

### Development test: plain text

For an initial test, select “Development test: plain text” under notification mode.

First send a message from the owner's actual receiving number to the Meta test business sender number to establish an available service window. Plain text must be sent within this 24-hour service window. Requests outside it are rejected by the API and should use an approved template instead.

Select the plain-text notification language, enable “Automatically notify the owner's phone when a quotation is submitted,” confirm the recipient number, and save. The backend then automatically queues a notification when staff submit a quotation.

### Template notifications

Template mode requires a Meta-approved template with four positional body parameters in this fixed order:

1. Quotation number;
2. Customer;
3. Amount;
4. Mobile approval link.

The following synthetic body can be a starting point when creating a template; Meta determines whether it is approved:

    New quotation {{1}} requires approval.
    Customer: {{2}}
    Amount: {{3}}
    Review: {{4}}

You can apply for the name quote_approval. The language code must match the approved version, for example en_US. The application fills only the four body parameters; it does not currently send template button or media-header parameters. Choose a template with this structure.

Meta's built-in hello_world template does not follow this four-body-variable contract. Do not use it as the extension's four-parameter quotation template.

## 4. Perform one complete integration test

Keep mobile mode running. The owner and staff each use their existing accounts.

1. Using the supplied synthetic price list, staff enter this inquiry:

       A牌50kg水泥二十袋，还有 Brand A PVC pipe 20mm five pieces

2. Check that the “AI understanding + price-list verification” label appears. The model should identify 20 bags of Brand A 50kg cement and 5 pieces of Brand A 20mm PVC pipe. The synthetic price-list total should be RM413.75.
3. Staff check the source and line items, then select “Confirm details and submit to owner.”
4. The pending quotation shows its mobile notification status. The owner checks the actual WhatsApp message on their phone and opens the approval link.
5. The owner checks the items, enters this store's boss password, and approves.
6. The staff status should change to completed, with PDF and Excel archives generated. The owner can also download that quotation's PDF on their phone.
7. Finally, staff verify reply insertion and attachment sending in real WhatsApp Web.

For the first real test, prefer a synthetic demonstration inquiry that both participants know is a test.

## 5. Interpreting statuses

| Status | Action |
| --- | --- |
| Waiting for mobile mode to start | The notification has not been submitted to WhatsApp; run mobile mode and keep the terminal open |
| Notification queued / submitting | Wait for backend processing; the interface updates automatically |
| Accepted by the WhatsApp API | This proves only that the API accepted the request; check actual receipt on the owner's phone |
| API request failed | Check the error code, token, numbers, template, and service window; correct the issue before retrying |
| Sending outcome uncertain | First check whether the owner received it, then explicitly decide whether to resend to avoid duplicate notifications |
| Link expired or quotation changed | Generate an approval link for the latest revision |
| Mobile service temporarily disconnected | Keep the computer, mobile gateway, and tunnel running, then check the latest HTTPS address |

Delivery / read webhooks are not currently integrated, so API acceptance is not shown as delivery. If the process is interrupted, notifications being sent are marked as uncertain rather than automatically resent.

## 6. Data and code

Credentials are stored in the connection settings file under local data, without hardware-backed key-store encryption. Do not share data with teammates or upload it to GitHub; share the source archive instead. Stop the service before backing up the entire data directory to retain accounts, records, and mobile-link signing information.

The new code is mainly in backend/ai.py, connections.py, mobile.py, mobile_gateway.py, and the mobile directory. End users do not need to read these files.

Development verification commands and completed coverage are in VERIFICATION.md. The included test provider exists only in tests/mobile_fixture_server.py and is explicitly started by test scripts. It does not participate in real run.py execution and does not use real credentials.

## Official API references

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [GPT-5.4 Mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
- [WhatsApp service messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/send-messages)
- [WhatsApp template fundamentals](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/overview)
- [WhatsApp template components](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/components/)
- [Meta Graph API changelog](https://developers.facebook.com/docs/graph-api/changelog/)
- [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

Documentation checked: October 20, 2026. Some Meta pages could not be fully opened in the reference-reading environment. The template request structure was also checked against documentation from Meta's official historical SDK. Actual account permissions, template validation, and message delivery still require real integration testing.
