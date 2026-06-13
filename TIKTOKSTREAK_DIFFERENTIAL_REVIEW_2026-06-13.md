# TikTok Streak Recipient Safety Review

## Executive Summary

| Severity | Count |
|----------|-------|
| Critical | 1 |
| High | 3 |
| Medium | 1 |
| Low | 0 |

**Overall risk before fix:** Critical
**Recommendation:** Deploy the fixed workflow; do not run older revisions.

Key metrics:
- Reviewed the complete send, contact resolution, contact loading, and workflow paths.
- Nine recipient-safety regression tests pass.
- Four locally configured contacts are explicitly enabled with no duplicate usernames or ambiguous labels.
- Unsafe legacy functions remain unreachable and raise immediately if called.

## What Changed

**Baseline:** `25c5589`
**Working tree:** recipient safety fix on 2026-06-13

| File | Risk | Change |
|------|------|--------|
| `utils.py` | Critical | Exact username verification, fail-closed contact loading, safe resolver matching |
| `.github/workflows/streak.yml` | High | Tests before sending, no scheduled resolver, no resolver-and-send run |
| `tests/test_recipient_safety.py` | High | Regression coverage for wrong-recipient scenarios |

## Critical Findings

### Critical: Page-wide IDs could authorize a send to the wrong open chat

**Historical location:** `utils.py` in baseline `25c5589`, old slow-match path
**Test coverage before fix:** None

The old slow-match flow read the first `user_id` or `sec_uid` found in scripts and
elements across the whole TikTok page. It accepted a match on any one of username,
conversation ID, user ID, or sec UID, then sent into whichever chat was currently
open. A stale/global ID could therefore match an allowed contact while the visible
chat belonged to someone else.

Attack/failure sequence:
1. The bot clicks an unrelated sidebar chat.
2. The page-wide scraper returns an ID belonging to an enabled contact.
3. The ID-only comparison selects that enabled contact.
4. The bot sends into the unrelated open chat.

Fix:
- The active chat must expose the exact configured username.
- A known conversation ID conflict rejects the send.
- Matching is checked twice before Enter is pressed.
- Page-wide IDs are not used by the send or resolver paths.

## High Findings

### High: Sending mutated contact identity

The old flow called `update_contact_in_list` after an ID-only match. Data scraped
from the wrong chat could overwrite the enabled contact's username and identifiers.
The new send flow never updates identity fields.

### High: Resolver amplified corrupt identity data

The resolver previously matched by display name and page-wide IDs, then ran
automatically every Monday before sending. It is now manual-only, never sends in
the same workflow run, and only updates an existing contact when username matches
exactly. Newly discovered usernames are disabled.

### High: Remote contact API failure used stale local recipients

When the configured API failed, the bot used cached local contacts. A person
disabled or removed remotely could still receive a message. The configured remote
source now fails closed and returns no recipients.

## Medium Findings

### Medium: Ambiguous labels and permissive enabled defaults

Missing or string-valued `enabled` fields could be treated as enabled, and duplicate
display names could select the wrong sidebar entry. Sending now requires explicit
`true` or integer `1`, unique enabled usernames, and a sidebar label owned by only
one enabled contact.

## Test Coverage

`python -m unittest discover -s tests -v`

Result: 9 tests passed.

Covered cases:
- Wrong active username never sends even when a stale ID matches.
- Exact username sends once.
- Conversation ID conflicts reject the send.
- Duplicate usernames and shared display names are rejected.
- Resolver does not mutate a contact matched only by display name.
- Remote API failure returns no recipients.
- Active profile extraction does not scan global profile links.

`python -m py_compile utils.py streak_bot.py tests/test_recipient_safety.py`

Result: passed.

## Blast Radius

`send_messages_flow` is the only scheduled send entry point and is called by
`streak_bot.py` and the compatibility wrapper. The workflow now runs the safety
tests before this entry point. Contact resolution and remote loading were also
changed because both can alter the recipient set used by later scheduled runs.

## Historical Context

- Commit `3e12e06` attempted to scope profile extraction to the chat header.
- Commit `25c5589` added username verification to the fast path, but retained the
  older ID-only slow path and page-wide ID extraction.
- The current fix makes username verification mandatory across all send paths.

## Recommendations

Immediate:
- Deploy this revision to the GitHub repository used by Actions.
- Do not manually rerun an older workflow revision.

Operational:
- Use the resolver as a separate manual run.
- Review newly discovered disabled contacts before enabling them.
- Treat skipped recipients as a safe failure requiring contact metadata review.

## Analysis Methodology

**Strategy:** Deep review for a small codebase.

Techniques:
- Full send-path and resolver tracing.
- Git history and blame review for recipient logic.
- Failure modeling for stale DOM and page-wide identifiers.
- Contact-data uniqueness checks.
- Regression tests and Python compilation.

Limitations:
- No live TikTok message was sent during verification.
- TikTok can change its DOM; strict mode will skip recipients if header selectors
  stop working rather than falling back to unsafe matching.

**Confidence:** High for preventing the identified wrong-recipient paths.
