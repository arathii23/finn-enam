# FINN followed-company phone alerts

Users open **Alerts**, choose companies and filing types, and select **Set up my phone**. FINN creates one random ntfy topic for that setup. The user subscribes to it in the free ntfy iPhone or Android app, sends a test, and confirms receipt to enable filing alerts. Changing the chosen companies reuses the same topic. Every user manages their own setup through an anonymous access code saved in their browser.

## What the feature covers

- The 15 companies in FINN's configured portfolio. The page lists the available company names and symbols and supports search.
- Results, major business changes, dividends/share changes, and earnings calls. These are selections over the existing NSE metadata classification. Each notification quotes the original subject and provides its date and source link.
- One source refresh shared across subscribers. Every subscriber is filtered by company, filing type, subscription start time and successful source checks. Identical attachments on NSE mirrors share a delivery identity.
- New follows, new filing types and resumed subscriptions start at the time of the change. Previously accepted filings are recorded separately for each subscriber.
- Matching filings are bundled into up to three notifications per device per UTC day. Each notification contains up to five filings. There is a shared 200-notification daily safety cap across tests and deliveries. Overflow remains pending within the seven-day source window.
- Pause and delete are available in the app. Save the access code to restore the setup in another browser. Each device's ntfy feed can be subscribed to from multiple phones using the same topic.

The ntfy topic is unlisted and randomly generated, with 192 bits of entropy. Anyone who obtains its name can read or post to it. Topics and access codes must be kept private. The user sees this explanation during setup. FINN sends public filings, and the original source remains the verification destination. [ntfy topic documentation](https://docs.ntfy.sh/publish/#picking-a-topic)

## One-time setup by the service owner

1. Create a Redis database on Upstash's **Free** plan. Its published allowance is 500,000 commands/month with 250 MB storage. Keep the Free plan selected. Obtain the REST URL and standard REST token. Add `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` to the ignored local `.env` file for verification, then to the Render service's environment. Never add these values to code, frontend build variables, public data, screenshots or chat. [Upstash free plan](https://upstash.com/pricing/redis)
2. Generate a strong random `FINN_PHONE_ALERTS_JOB_TOKEN`. Store it in Render's environment and as a repository Actions secret of that same name. It authorizes the dispatch endpoint and carries no subscriber data. FINN's original `NTFY_TOPIC` secret continues to belong to the earlier owner-only smoke test.
3. Deploy the backend and publish the frontend containing the Alerts tab. The static Pages app makes its alert requests to the existing HTTPS Render backend. CORS allows the Pages origin and the backend. A missing storage or scheduler configuration is shown as awaiting activation, and saving is disabled.
4. Run **Check followed-company phone alerts** manually with the default dry-run option. It should complete with a source check and aggregate counts. Subscriptions, topics and access codes stay in Redis. Public snapshots, GitHub artifacts and runner logs receive aggregate counts only.
5. Complete a real user's setup on an iPhone. Check the lock-screen test, source link, selected-company delivery, changing choices, pausing, restoring from an access code, and deleting. Record actual phone receipt separately from ntfy acceptance.
6. After verification, set the repository Actions variable `FINN_PHONE_ALERTS_ENABLED=1`. The workflow is scheduled at minutes 17 and 47 of each hour. GitHub's scheduler and free Render hosting can delay a check. The last completed source check and coverage are visible in the app. Removing this variable stops scheduled dispatch.

## Verification boundaries

The Redis store is independent of Render's filesystem and its seed corpus. Subscriber access uses a random 256-bit bearer code, hashed for record lookup. API responses containing settings are marked `Cache-Control: no-store`. Browser URLs contain neither access codes nor topics. User-supplied destinations are rejected. Test sending is explicit, limited to once per minute per setup, and requires an existing subscription.

Subscription changes, deletion and dispatch share a per-record Redis lock. The dispatcher also has a global lock and a bounded run time. Accepted sends persist deduplication state per subscriber. A provider failure retains pending filings for a later check. An external service accepting a message and the subsequent Redis write cannot form one transaction. A crash or storage outage in that interval can cause a repeat on retry. This feature makes no exactly-once delivery guarantee.

The free ntfy service currently allows 250 messages per day per visitor. FINN reserves a lower allowance and bundles messages. These limits support an initial public pilot and can defer alerts when many users subscribe. Actual phone delivery, free-service capacity and scheduler timeliness require live observation. [ntfy limits](https://docs.ntfy.sh/publish/#limitations)

## Local verification on 18 November 2026

The backend suite passed 255 tests. Both the live and Pages frontend builds passed. Browser checks passed at 360, 390, 430 and 1280 pixels for both builds, covering selection, test confirmation, activation, changing choices, persistence across reloads, separate browser isolation, access-code restoration, pause, resume, deletion and horizontal overflow. Browser checks used an isolated storage double and a simulated notification sender.

The new flow still needs verification against the owner's Upstash database, published scheduler execution, and physical phone receipt. Those checks require the free database credentials and live activation. The earlier owner-only ntfy smoke test is separate from this per-user flow.

The owner-provided Upstash database passed isolated integration checks on 18 November 2026 for writes, fresh-instance reads, separate subscriptions, locking, preference updates, dry-run behavior, routing, deduplication, pausing and deletion. The verification namespace was cleaned up. Provider delivery in those isolated storage checks was simulated.
