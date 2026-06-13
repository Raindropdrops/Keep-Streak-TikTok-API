# TikTok Streak Reliability and Recipient Safety Review

## Executive Summary

| Severity | Count | Status |
|----------|-------|--------|
| Critical | 2 | Fixed |
| High | 4 | Fixed |
| Medium | 2 | Fixed |

The scheduled workflow was not reliably delivering every day. GitHub Actions
reported success even when the bot delivered to only part of the enabled contact
list, including several runs with zero confirmed sends. The bot now fails the job
when delivery is incomplete and uses two idempotent morning catch-up runs.

Recipient safety remains fail-closed: every send requires the exact configured
username, and retries repeat that verification before typing or pressing Enter.

## Evidence

Recent scheduled runs before this fix:

| Vietnam date | Confirmed delivery |
|--------------|--------------------|
| 2026-06-12 | 11/38 |
| 2026-06-11 | 22/37 |
| 2026-06-10 | 6/30 |
| 2026-06-09 | 8/30 |
| 2026-06-08 | 30/30 |
| 2026-06-07 | 28/28 |
| 2026-06-06 | 0/28 |
| 2026-06-05 | 0/28 |
| 2026-06-04 | 0/27 |

The dominant Selenium error was a TikTok modal intercepting clicks. The old CLI
caught the exception and still exited with code zero.

## Critical Findings

### Workflow success did not mean complete delivery

`send_messages_flow` always returned `success`, and `streak_bot.py` swallowed fatal
errors. GitHub therefore had no reliable failure signal.

Fix:
- `success` now requires every enabled contact to be delivered for the Vietnam day.
- Partial or failed delivery exits the CLI with code 2.
- Failure artifacts are uploaded by the existing workflow step.

### Unsafe historical recipient matching

Older revisions could authorize a send using page-wide identifiers that did not
belong to the active chat. This was fixed earlier in the same review series and
remains covered by regression tests:
- Exact username is mandatory.
- A conflicting conversation ID rejects the send.
- Duplicate usernames and ambiguous sidebar labels are rejected.
- The resolver cannot enable newly discovered contacts automatically.

## High Findings

### One delayed cron had no recovery path

The workflow previously ran once at 04:00 Vietnam time. It now runs at 04:00,
06:00, and 08:00. A persisted daily delivery ledger ensures later runs only
attempt contacts still missing that day.

### Modal interception had no retry

Blocking overlays are dismissed with Escape and scoped close selectors. Each
retry re-verifies the exact recipient twice before sending. Retry backoff is
bounded and uncertain delivery verification is not blindly retried.

### Virtualized sidebar contacts were missed

The strict flow only searched the currently visible sidebar. It now scans several
positions in the conversation list while preserving unique-label and exact-header
verification.

### Cookies and API key were tracked in source

The current TikTok cookie is now stored in the `TIKTOK_COOKIES` GitHub Secret and
materialized only during the workflow. `cookies.json` is removed from Git tracking.
The Worker now reads `env.API_KEY` instead of a source constant.

Historical revisions still contain the old values. Rotate the TikTok session and
Worker API key after deployment; history rewriting was intentionally not performed.

## Medium Findings

### Telegram reports could fail on Markdown or message length

Notifications are now plain text and split into bounded chunks. Reports emphasize
the contacts still missing and distinguish newly sent from already delivered.

### Browser settings were fragile on GitHub runners

Chrome now uses a fixed window size, `/dev/shm` mitigation, no-sandbox mode, and a
page-load timeout suitable for hosted Linux runners.

## Verification

Commands:

```text
python -m unittest discover -s tests -v
python -m py_compile utils.py streak_bot.py tests/test_recipient_safety.py
git diff --check
```

Result: 16 tests passed; compilation and diff validation passed.

Coverage includes:
- Wrong active username never sends.
- Exact username sends once.
- Retry re-verifies the recipient.
- Daily catch-up history prevents duplicates.
- Partial delivery returns a non-success status.
- Remote contact failure fails closed.
- Duplicate usernames and ambiguous labels are rejected.

## Remaining Operational Actions

- Deploy `worker.js` with an `API_KEY` Worker secret configured.
- Rotate the TikTok login session because the old cookie exists in Git history.
- Rotate the API key after the Worker/backend deployment can be updated atomically.

## Limitations

No live TikTok message was sent during verification. TikTok can change its DOM;
the strict behavior is to skip and fail the workflow rather than send without
recipient verification.
