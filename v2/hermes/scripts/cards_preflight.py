"""Hermes cron pre-run wrapper: copy (not symlink) to ~/.hermes/scripts/cards_preflight.py.

Hermes 0.21.3 only runs job scripts that resolve inside ~/.hermes/scripts/, so a
symlink into the skill checkout is refused. This file stays put and runs the
maintained preflight from the checkout.
"""
from pathlib import Path
import runpy

runpy.run_path(str(Path.home() / "card-offers-skill/v2/bin/cards_preflight.py"), run_name="__main__")
