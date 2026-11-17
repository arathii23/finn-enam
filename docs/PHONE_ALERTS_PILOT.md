# FINN phone alert pilot

The pilot uses ntfy on [iOS or Android](https://docs.ntfy.sh/subscribe/phone/). The default check sends leading NSE filings published after the pilot start time. Tapping a real alert opens the exchange attachment when available. The notification also links to the company’s saved results. It uses the exchange subject and time, and no model runs.

Do not publish a subscription link for the pilot. An unlisted ntfy.sh topic is not access controlled. Anyone who knows the name can read or post to it. Use it only for the test and public filings. [Topic guidance](https://docs.ntfy.sh/publish/#picking-a-topic)

## Confirm one alert on a phone

1. Install ntfy and allow notifications. Choose a long, random topic and subscribe on the phone. Set that topic as the repository’s Actions secret `NTFY_TOPIC`. Keep the name out of commits, screenshots, and shared messages.
2. After the workflow change is published and the owner approves a test, open **Actions → Check phone alerts → Run workflow**. Select **Send one labelled test**. The command-line equivalent is:

   ```bash
   gh workflow run phone-alerts.yml --repo arathii23/finn-enam -f test_notification=true
   ```

3. Lock the phone and confirm it displays **FINN · Test alert**. Tap it and check that it opens the public Portfolio Review. A successful runner log confirms ntfy accepted the message. Only the phone confirms it arrived.

For an operator testing from their own machine, `PYTHONPATH=backend .venv/bin/python -m finn alerts --test` also sends exactly one test when `NTFY_TOPIC` is supplied to that process. It does not read the portfolio or touch alert history.

## Allow the first real alert

After the phone test passes, use the repository’s Actions variables to set `FINN_ALERTS_START_AT` to the pilot start as an ISO 8601 timestamp with an offset, then set `FINN_ALERTS_ENABLED=1` with the owner’s approval. First run the workflow in its default dry-run mode and review the candidates. To deliver after approval, run it manually with `dry_run=false` and leave **Send one labelled test** off. The initial pilot excludes market flags. Keep any extra filing categories unset first.

Confirm that a real alert opens its NSE file and that rerunning the check does not send it again. Record the time on the phone separately from service acceptance. Decide on a schedule and any public subscription UI after the pilot. Remove `FINN_ALERTS_ENABLED` to stop real delivery and remove the subscription from the phone to stop receiving messages.
