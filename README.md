# Card offers skill

Files behind my credit card offers bot, from my Substack post. Two versions of
the same daily job: activate every available Chase and Amex card offer, then
send a short roundup.

## v1 — July 2026: wrapper script + login/logout script + Codex agent in a sandbox

- `v1/bin/cards-fire.sh` is the wrapper launchd ran at 3 a.m. It takes a lock,
  runs `cards-prefire.sh` to bring the dedicated cards Chrome (CDP on
  `127.0.0.1:19223`) to the front, then calls `cards-auth.py login`.
- `v1/bin/cards-auth.py` is the only code that touches credentials. It reads
  1Password secret references (`v1/config/onepassword.conf.example`) with a
  service-account token kept in the Login Keychain by `cards-keychain.swift`,
  fills the bank login forms over CDP, and later signs out (`logout`).
- After login, the wrapper runs a Codex agent under the macOS Seatbelt profile
  `v1/config/cards-agent.sb`, which blocks the agent from 1Password, the
  Keychain and the auth code. The agent follows `v1/SKILL.md`, clicking offers
  through `v1/bin/lib/cdp-eval.sh` and reporting through `telegram-send.sh`.

## v2 — November 2026: a Hermes agent runs the whole job (Chase and Amex)

- One Hermes cron job follows `v2/SKILL.md`. Every step with one right answer
  is tested Python the agent calls from `browser_exec`; the agent only decides
  what a helper hands back as `needs_judgment`, using
  `v2/references/issuer-notes.md`.
- `v2/bin/cards_browser.py` does the bank steps: picks the bank tab, prepares
  the login for Hermes's native password-vault fill (the password never passes
  through the model), submits once, clicks and verifies each offer, signs out
  and writes the roundup. Chase and Amex cover the card the bank shows as
  selected.
- `v2/bin/cards_journal.py` keeps the crash-safe run journal: it reserves each
  login and click before it happens, spaces logins, and budgets the agent's
  turns. `v2/bin/cards_preflight.py` runs before the agent: it checks the
  browser, closes orphaned journals and opens today's.
- `v2/hermes/` has the cron job's prompt, the pre-run wrapper and how to apply
  them. `v2/tests/` runs the helpers against a fake browser:
  `python3 -m unittest discover -s v2/tests`.

## Sanitized, not runnable as is

Personal paths, account and host names, vault names, IDs and launchd labels are
replaced with placeholders (`<agent vault>`, `<telegram chat id>`,
`op://<vault>/<item>/<field>`, `com.example.`). Some pieces are not included:
the launchd plists, the Chrome-daemon setup, the v1 session-keepalive job, the
1Password provisioning scripts and the v1 scripted fallback; the files note
where they plugged in. v1 needs Python `websocket-client`; v2 needs Hermes
(its tests need only Python 3).

## Files

```
v1/SKILL.md                                   408
v1/bin/cards-auth.py                          442
v1/bin/cards-fire.sh                          253
v1/bin/cards-keychain.swift                    87
v1/bin/cards-prefire.sh                       183
v1/bin/lib/cdp-eval.sh                        135
v1/bin/lib/cdp-screenshot.sh                   97
v1/bin/lib/dedup-append.sh                     56
v1/bin/lib/telegram-send.sh                   124
v1/config/cards-agent.sb                       58
v1/config/onepassword.conf.example              8
v2/SKILL.md                                   126
v2/bin/cards_browser.py                       754
v2/bin/cards_journal.py                       320
v2/bin/cards_preflight.py                      96
v2/hermes/README.md                            38
v2/hermes/prompt.txt                            1
v2/hermes/scripts/cards_preflight.py           10
v2/references/issuer-notes.md                  57
v2/tests/test_cards_browser.py                572
v2/tests/test_cards_journal.py                156
v2/tests/test_offer_metadata.py                44
```
