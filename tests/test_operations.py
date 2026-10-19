from pathlib import Path
import tempfile
import unittest

from ops.health import transition
from ops.release_state import ReleaseStore


class HealthTests(unittest.TestCase):
    def test_failures_are_debounced_and_recovery_requires_two_successes(self):
        state = {"healthy": True, "failures": 0, "successes": 2}
        for _ in range(2):
            state = transition(state, False)
            self.assertTrue(state["healthy"])
        state = transition(state, False)
        self.assertFalse(state["healthy"])
        state = transition(state, True)
        self.assertFalse(state["healthy"])
        self.assertTrue(transition(state, True)["healthy"])

    def test_failure_streak_is_reset_by_success(self):
        state = transition(transition(None, False), False)
        state = transition(state, True)
        self.assertEqual(state["failures"], 0)
        self.assertIsNone(transition(state, False)["healthy"])


class ReleaseTests(unittest.TestCase):
    def test_concurrent_release_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with ReleaseStore(folder):
                with self.assertRaises(RuntimeError):
                    with ReleaseStore(folder):
                        pass

    def test_interrupted_release_restores_last_known_good(self):
        with tempfile.TemporaryDirectory() as folder:
            with ReleaseStore(folder) as store:
                store.commit(store.begin("good"))
                store.begin("bad")
            calls = []
            with ReleaseStore(folder) as store:
                self.assertTrue(store.recover(calls.append))
                self.assertFalse(store.journal.exists())
            self.assertEqual(calls, ["good"])

    def test_failed_recovery_retains_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            with ReleaseStore(folder) as store:
                store.commit(store.begin("good"))
                store.begin("bad")
                def fail(tag):
                    raise RuntimeError("offline")
                with self.assertRaises(RuntimeError):
                    store.recover(fail)
                self.assertTrue(store.journal.exists())

    def test_first_release_requires_manual_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            with ReleaseStore(folder) as store:
                store.begin("first")
                with self.assertRaises(RuntimeError):
                    store.recover(lambda tag: None)
                self.assertTrue(store.journal.exists())

    def test_commit_written_before_crash_is_not_rolled_back(self):
        with tempfile.TemporaryDirectory() as folder:
            with ReleaseStore(folder) as store:
                pending = store.begin("good")
                store.commit(pending)
                store.atomic(store.journal, pending)
                self.assertFalse(store.recover(lambda tag: self.fail("must not rollback")))
