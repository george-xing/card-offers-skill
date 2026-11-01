# Hermes cron job (example)

The daily run is one Hermes cron job, "Credit card offers — Hermes", at 03:00
America/New_York with the `credit-card-offers` skill, the terminal, file,
skills and browser toolsets, and Telegram delivery. `prompt.txt` is its prompt
and `scripts/cards_preflight.py` its pre-run script.

## Pre-run hook (Hermes 0.21.3)

A cron job's `script` runs before the agent; its stdout is added to the prompt
under "Script Output" (`cron/scheduler_prompt.py`). A last stdout line of JSON
`{"wakeAgent": false}` would skip the agent; the preflight never prints that.
Scripts must resolve inside `~/.hermes/scripts/` after following symlinks
(`cron/scheduler_script.py::_resolve_script_path`), so a symlink into the
skill checkout is refused; `.py` runs with Hermes's own Python. The
`cron.script_timeout_seconds` in `~/.hermes/config.yaml` is 30, enough for the
preflight.

## Apply

With this repo cloned at `~/card-offers-skill` (adjust the wrapper's path
otherwise) and `<job id>` from `hermes cron list`:

```bash
cp ~/card-offers-skill/v2/hermes/scripts/cards_preflight.py ~/.hermes/scripts/cards_preflight.py
hermes cron edit <job id> --script cards_preflight.py --prompt "$(cat ~/card-offers-skill/v2/hermes/prompt.txt)"
```

The first preflight closes every `running` journal older than 45 minutes as
`partial`.

## Roll back

Save the job's previous prompt before applying, then:

```bash
hermes cron edit <job id> --script "" --prompt "$(cat previous-prompt.txt)"
```
