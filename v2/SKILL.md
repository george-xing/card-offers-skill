---
name: credit-card-offers
description: Activate Chase and Amex card offers through the existing cards browser and the agent's 1Password vault. Use for the scheduled daily activation run and for offer checks.
metadata:
  hermes:
    category: finance
    tags: [chase, amex, offers, 1password, browser]
---

# Credit Card Offers — Hermes

The user authorized this daily workflow for Chase and Amex. Every step with one
right answer lives in tested Python (`bin/cards_browser.py` in this skill's
folder); you decide only what it hands back as `needs_judgment`. The 03:00
America/New_York cron job delivers your final answer to Telegram; do not send
messages yourself.

## Hard rules

- Only the existing **cards Chrome** on `http://127.0.0.1:19223`, through one
  named `browser_exec` session. Never another port, profile or fresh browser.
  Do not close Chrome.
- Passwords: only native `browser_vault_list` / `browser_vault_fill` with the
  `<agent vault>` Login items. Never `op`, shell, typing, screenshots or logs.
  Never put input values or full card numbers in output; card labels stay masked.
- One login submission per issuer per run, made by `submit_login` only.
  Never resubmit, even after a timeout; probe read-only instead.
- MFA, CAPTCHA, device check or password reset stops that issuer. Never choose
  a method, request a code or call `browser_vault_enter_code`.
- One click per offer, made by `activate`. A key in `attempted_offers` without
  an activation is uncertain: never click it again.
- Issuers strictly one at a time, Chase → Amex: login, offers, sign-out and
  outcome before the next login. The journal enforces 60 s between logins.
- No purchases, account settings, preference changes or unrelated terms.
- Cron has nobody to approve flagged commands: never `python3 -c`, `-e`,
  piped interpreters or `ps` pipelines in `terminal`. Use `browser_exec` and `read_file`.
- Dry-run (when asked): `attach()` and read-only probes only. No navigation,
  fill, submit, click, sign-out, message or journal outcome.

## Setup

The job's pre-run script prints JSON (`cards_preflight.py`): CDP status, closed
orphan journals, this run's `journal` path and the open tabs. If there is no
Script Output, call it first (`CARDS_BIN` is this skill's `bin/` folder):

```python
import sys; from pathlib import Path
CARDS_BIN = Path.home() / "card-offers-skill/v2/bin"  # wherever this folder lives
sys.path.insert(0, str(CARDS_BIN))
import cards_preflight, json; print(json.dumps(cards_preflight.run()))
```

If `cdp.ok` is false, stop and return the roundup. Use the printed journal
path for the whole run.

## Calling the helper

Every `browser_exec` call rebuilds the bank object; nothing persists between
calls except the journal. Count your turns (one model response = one turn) and
pass the current number as `turn`:

```python
import sys; from pathlib import Path
sys.path.insert(0, str(Path.home() / "card-offers-skill/v2/bin"))
from cards_browser import Bank
bank = Bank("chase", JOURNAL, harness=globals(), turn=TURN)
print(bank.attach())
print(bank.prepare_login(IDENTIFIER))   # same call is fine
```

`IDENTIFIER` is the username `browser_vault_list` returns for the issuer's
Login item (Chase item must allow `https://secure.chase.com`, Amex
`https://www.americanexpress.com`).

## Per issuer

1. `attach()` then `prepare_login(IDENTIFIER)`.
2. `browser_vault_fill` with the handle, `target_id` and `frame_selector`
   (omit it when empty) from `prepare_login`. Require `success: true`, one
   password field and the same `target_id`.
3. `submit_login(IDENTIFIER, vault_target_id)`.
4. `activate()` until the status is not `deadline`.
5. `sign_out()`.

| Status | Do |
| --- | --- |
| `attached`, `ready_for_vault_fill` | Next step. |
| `already_authenticated` | Skip fill and submit; go to offers. |
| `offers_ready` | Offers. |
| `mfa`, `rejected`, `captcha`, `blocked_fields_hidden` | Issuer done; it is recorded. Next issuer. |
| `skipped_budget` | Issuer and every later one are skipped. Go to roundup. |
| `refused` | A rule held; read `reason`. Fix the cause or move on; never work around it. |
| `deadline` | Call `activate()` again in a new `browser_exec` (`timeout_s=420`). |
| `exhausted` | Offers done. Sign out. |
| `cap`, `unverified`, `click_not_confirmed`, `card_not_found`, `card_mismatch`, `no_counter`, `unparsed_tile`, `hub_not_loaded` | Stop activating this issuer; sign out. It is recorded as partial. |
| `needs_judgment` | Read `reason` and `page`; see [issuer-notes.md](references/issuer-notes.md). |
| `verified` (sign-out) | Issuer finished. |
| `unverified` (sign-out) | It already polled 40 s and recorded a partial outcome. Report it; do not click again. |

For `needs_judgment` you may retry the same method with
`Bank(..., overrides={"username": "#observedId"})` when a selector moved; the
override is recorded and flagged in the roundup. Never override to bypass a
refusal, and never write your own login or activation click code.

Chase and Amex both cover the card the bank shows as selected after login;
`activate()` never switches cards.

## Budget and stopping

`prepare_login` refuses an issuer when fewer than 15 of the 80 turns remain.
By turn 74, stop bank work: sign out of any authenticated issuer, then go to
the roundup. If a tool call times out, read the journal with `read_file` once
before doing anything else; activation loops stop themselves at 330 s.

## Roundup

```python
from cards_browser import roundup
print(roundup(JOURNAL))
```

It finalizes the journal (closing unfinished issuers) and prints the summary,
starting with `[CRON_FAILURE]` on its own line when the run is not completed.
Return that text as your final answer, unchanged. You may append one line for
something the journal cannot know. Never claim Telegram delivery; Hermes does
it. Do not emit `[SILENT]`.
