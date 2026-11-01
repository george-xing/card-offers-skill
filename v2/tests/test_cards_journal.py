import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("cards_journal", Path(__file__).parents[1] / "bin/cards_journal.py")
journal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "hermes-runs/run.json"
        self.j = journal.Journal(self.path)
        self.j.prepare()
        self.j.issuer("chase", tab_id="test")

    def test_login_reservation_survives_restart(self):
        self.j.reserve_login("chase")
        with self.assertRaises(ValueError):
            journal.Journal(self.path).reserve_login("chase")

    def test_declaring_zero_submissions_is_a_noop_but_counts_are_protected(self):
        # 2026-10-31: issuer(..., login_submissions=0) raised after prepare() and orphaned a running journal.
        self.j.issuer("chase", login_submissions=0, tab_id="test")
        self.assertEqual(json.loads(self.path.read_text())["issuers"]["chase"]["login_submissions"], 0)
        with self.assertRaises(ValueError):
            self.j.issuer("chase", login_submissions=1)
        self.j.reserve_login("chase")
        with self.assertRaises(ValueError):
            self.j.issuer("chase", login_submissions=0)

    def test_logins_are_serialized_and_spaced(self):
        self.j.issuer("amex", tab_id="amex-tab")
        self.j.reserve_login("chase")
        with self.assertRaisesRegex(ValueError, "Record the chase outcome"):
            self.j.reserve_login("amex")
        self.j.issuer("chase", status="completed", sign_out="verified")
        self.assertGreater(self.j.login_wait_seconds("amex"), 50)
        with self.assertRaisesRegex(ValueError, "Wait"):
            self.j.reserve_login("amex")
        self.assertEqual(json.loads(self.path.read_text())["issuers"]["amex"]["login_submissions"], 0)
        with self.j.transaction() as data:
            data["issuers"]["chase"]["submission_recorded_at"] = "2000-01-01T00:00:00+00:00"
        self.assertEqual(self.j.login_wait_seconds("amex"), 0)
        self.j.reserve_login("amex")

    def test_abandon_only_closes_journals_without_bank_actions(self):
        self.j.abandon("journal setup error")
        data = json.loads(self.path.read_text())
        self.assertEqual((data["status"], data["abandoned_reason"]), ("abandoned", "journal setup error"))
        other = journal.Journal(Path(self.tmp.name) / "hermes-runs/other.json")
        other.prepare()
        other.issuer("chase")
        other.reserve_login("chase")
        with self.assertRaises(ValueError):
            other.abandon("too late")

    def test_uncertain_click_cannot_be_repeated(self):
        self.j.reserve_offer("chase", "chase::example")
        with self.assertRaises(ValueError):
            journal.Journal(self.path).reserve_offer("chase", "chase::example")
        self.assertEqual(self.j.finish(), "partial")

    def test_record_is_idempotent_and_omits_unknown_fields(self):
        for _ in range(2):
            self.j.record("chase", "chase::example", merchant="Example", password="not-a-real-secret")
        data = json.loads(self.path.read_text())
        self.assertEqual(len(data["activations"]), 1)
        self.assertNotIn("password", data["activations"][0])
        self.assertEqual(len(json.loads((Path(self.tmp.name) / "chase-activated.json").read_text())), 1)

    def test_persistence_failure_retains_canonical_verified_record(self):
        (Path(self.tmp.name) / "chase-activated.json").write_text("broken")
        with self.assertRaises(ValueError):
            self.j.record("chase", "chase::example", merchant="Example")
        self.assertEqual(len(json.loads(self.path.read_text())["activations"]), 1)

    def test_completion_requires_both_issuers_and_signout(self):
        self.j.issuer("chase", status="completed", sign_out="verified")
        self.assertEqual(self.j.finish(), "partial")
        self.j.issuer("amex", status="completed", sign_out="verified")
        self.assertEqual(self.j.finish(), "completed")

    def test_failed_transaction_keeps_previous_document(self):
        before = self.path.read_bytes()
        with self.assertRaises(RuntimeError), self.j.transaction() as data:
            data["status"] = "completed"
            raise RuntimeError("interrupted")
        self.assertEqual(self.path.read_bytes(), before)

    def test_only_chase_and_amex_are_issuers(self):
        with self.assertRaises(ValueError):
            self.j.prepare(required_issuers=("chase", "other"))
        with self.assertRaises(ValueError):
            self.j.issuer("other")

    def test_later_verified_signout_resolves_only_its_transient_failure(self):
        with self.j.transaction() as data:
            data["failures"].append({"issuer": "chase", "reason": "sign-out not verified"})
        for name in ("chase", "amex"):
            self.j.issuer(name, status="completed", sign_out="verified")
        self.assertEqual(self.j.finish(), "completed")
        self.assertTrue(json.loads(self.path.read_text())["failures"][0]["resolved"])
        with self.j.transaction() as data:
            data["failures"].append({"issuer": "amex", "reason": "persistence gap"})
        self.assertEqual(self.j.finish(), "partial")

    def test_budget_gate_skips_an_issuer_it_cannot_finish(self):
        self.j.prepare(required_issuers=("chase", "amex"))
        self.assertTrue(self.j.budget_allows("chase", journal.MAX_TURNS - journal.ISSUER_TURN_RESERVE))
        self.assertFalse(self.j.budget_allows("amex", journal.MAX_TURNS - journal.ISSUER_TURN_RESERVE + 1))
        data = json.loads(self.path.read_text())
        self.assertEqual(data["issuers"]["amex"]["status"], "skipped_budget")
        self.assertEqual(data["failures"][-1]["reason"], "skipped_budget")
        self.j.reserve_login("chase")
        with self.assertRaisesRegex(ValueError, "already submitted"):
            self.j.skip("chase", "too late")

    def test_close_finalizes_an_interrupted_run(self):
        # 2026-11-01: the turn limit hit after the last issuer's vault fill and left the journal running.
        self.j.prepare(required_issuers=("chase", "amex"))
        self.j.reserve_login("chase")
        self.j.issuer("amex", fields_ready=True)
        self.assertEqual(self.j.close("turn budget exhausted before Amex login"), "partial")
        data = json.loads(self.path.read_text())
        self.assertEqual({n: i["status"] for n, i in data["issuers"].items()},
                         {"chase": "partial", "amex": "skipped_budget"})
        self.assertEqual(len(data["failures"]), 2)
        with self.assertRaisesRegex(ValueError, "already partial"):
            self.j.close("again")

    def test_close_keeps_recorded_outcomes(self):
        self.j.prepare(required_issuers=("chase", "amex"))
        self.j.issuer("chase", status="completed", sign_out="verified")
        self.assertEqual(self.j.close("turn budget"), "partial")
        data = json.loads(self.path.read_text())
        self.assertEqual([f["issuer"] for f in data["failures"]], ["amex"])
        self.assertEqual(data["issuers"]["chase"]["status"], "completed")


class ChaseCardTests(unittest.TestCase):
    def test_selected_card_comes_from_the_switcher(self):
        probe = {"selected": " Sapphire Reserve (...1111)\n", "url": "https://secure.chase.com/x"}
        self.assertTrue(journal.chase_card_selected(probe, "Sapphire Reserve (...1111)"))
        self.assertFalse(journal.chase_card_selected(probe, "Freedom (...2222)"))
        self.assertFalse(journal.chase_card_selected({"selected": None}, "Sapphire Reserve (...1111)"))

    def test_hub_url_must_be_card_scoped(self):
        hub = "https://secure.chase.com/web/auth/dashboard#/dashboard/merchantOffers/offer-hub?accountId=1"
        self.assertEqual(journal.chase_card_hub(hub), hub)
        with self.assertRaises(ValueError):
            journal.chase_card_hub("https://secure.chase.com/web/auth/dashboard?navKey=reviewMerchantOffers")
