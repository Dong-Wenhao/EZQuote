# Deploy the web workspace on Replit

This guide prepares a public **web workspace** using the same quotation workflow. The Chrome extension remains unchanged and continues to use a local backend on port 8765. The optional Replit entry point is `run_replit.py`; normal local startup remains `python run.py`.

Configuration in GitHub is not proof that Replit has been used. A public URL and proof of use must come from a successful run in your own Replit account.

## 1. Sign in and import the repository

1. Register or sign in at [Replit](https://replit.com).
2. Use the option to import an existing GitHub project. Interface labels may vary, such as **Import** or **Import from GitHub**.
3. Paste `https://github.com/Dong-Wenhao/EZQuote` and import the `main` branch.
4. Open the project workspace and confirm that `.replit`, `run_replit.py`, `backend/`, `extension/`, `assets/` and `samples/` are present.

Replit uses the Python 3.12 module in `.replit`. Both the workspace run command and the publishing run command prepare a project `.venv`, install the pinned runtime packages from `requirements.txt` there, and start the web server. Node.js and the development test packages are not required to run the prototype.

## 2. Add the initial account secrets

Before the first run, open Replit's **Secrets** tool and add:

| Name | Value to enter |
| --- | --- |
| `EZQUOTE_BOSS_PASSWORD` | Your own owner-demo password, 8–128 characters; at least 12 is recommended. |
| `EZQUOTE_STAFF_PASSWORD` | A different staff-demo password, 8–128 characters. |
| `EZQUOTE_SHOP_NAME` | Optional non-secret shop name, such as `EZQuote Demo`. |

The server creates the `boss` and `staff` accounts before opening the public port. It refuses an uninitialized deployment with missing, short or identical passwords. There are no default passwords and no public first-visitor account-creation step.

These passwords initialize an empty cloud database only. Restarting with existing accounts does not replace them, reset sessions or copy local user data. Keep the secrets available for rebuilding a fresh demonstration instance. Share demonstration login details with reviewers through the appropriate submission channel, rather than committing passwords to GitHub.

## 3. Run the workspace preview

1. Select **Run** and wait for dependency installation and server startup.
2. Open the preview in a full browser tab.
3. The app attempts to use Replit's supplied `REPLIT_DEV_DOMAIN` / `REPLIT_DOMAINS` values as exact allowed web origins. Their availability depends on the environment. If startup reports that no public origin is available, add `EZQUOTE_PUBLIC_ORIGIN` with the actual HTTPS preview or published origin, such as `https://your-actual-domain.replit.app`.
4. Use the actual domain allocated to your project. Do not enter the example above, a path, a wildcard or the URL of the Replit editor. A custom origin must use HTTPS.
5. Sign in as `boss` using your owner password. Open **Settings → Business data**, check and import `samples/business_demo.xlsx`.
6. Open another browser session or sign out, then sign in as `staff`. Run the complete quotation example in the [user guide](USER_GUIDE.md).

The server listens on `0.0.0.0` and the `PORT` supplied by its environment, defaulting to 8000. If Replit asks you to select a listening port, select that port. The existing local launcher is separate and continues to bind only `127.0.0.1:8765`.

Only configured exact hosts and origins are allowed. Unknown hosts and unrelated website origins remain blocked. A successful HTTPS preview does not establish that the published app is available.

## 4. Publish a single-instance demonstration

1. Open Replit's publishing or deployment interface.
2. Use the repository's publishing run command. The repository does not force a deployment type or purchase a plan.
3. Select a **single-instance** service available to your account, such as a single Reserved VM. Avoid several autoscaling replicas: each would have a different local SQLite database. Check the actual plan and credit terms shown by Replit before confirming a paid option.
4. Ensure the deployment receives the two account secrets and the correct public origin configuration. If the allocated published domain is not supplied automatically, set `EZQUOTE_PUBLIC_ORIGIN` to its exact HTTPS origin and restart or republish.
5. Open the published URL in a private/incognito browser window. Verify login, the synthetic workbook, inquiry review, owner approval, PDF download and customer-outcome recording.

The cloud data directory defaults to `data/replit-demo/`; `WA_QUOTE_DATA` can select another directory. It is separate from the ordinary local application's data directory. This is a synthetic demonstration using local SQLite and files. Persistence across Replit restarts, replacements or republishes is not guaranteed by this repository. Be prepared to import the sample again. Durable production use needs a verified persistent data design; do not use the prototype to hold real customer records on an unverified ephemeral filesystem.

## 5. Capture real proof and update the submission

After the app actually runs on Replit, capture the project page, running workspace, published URL, a successful quotation and the relevant Usage / Credits / History view. Assemble those real screenshots into `submission/Replit_Proof_of_Use.pdf`.

Use the same verified public URL in the README, proposal, pitch deck and tools declaration. Only then change the Replit status from pending to used/deployed. Upload the existing [demo recording](../submission/EzQuote_Demo.mp4) to YouTube and use its real public or unlisted link; the local recording alone is not a YouTube publication or Replit proof.
