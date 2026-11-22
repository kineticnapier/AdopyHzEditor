"""Closing the window must end the process even if a thread is stuck."""

from __future__ import annotations

import threading
import time
import unittest

try:
    import web_ui
except SystemExit:  # pywebview missing
    web_ui = None


@unittest.skipIf(web_ui is None, "pywebview is not installed")
class ExitWatchdogTests(unittest.TestCase):
    def setUp(self):
        web_ui._exit_watchdog_started.clear()

    def tearDown(self):
        web_ui._exit_watchdog_started.clear()

    def test_exits_after_grace_period(self):
        calls = []
        thread = web_ui._start_exit_watchdog(0.1, exit_fn=calls.append)
        thread.join(2.0)
        self.assertEqual(calls, [0])
        self.assertTrue(thread.daemon)

    def test_starts_only_once(self):
        calls = []
        first = web_ui._start_exit_watchdog(0.1, exit_fn=calls.append)
        self.assertIsNone(web_ui._start_exit_watchdog(0.1, exit_fn=calls.append))
        first.join(2.0)
        self.assertEqual(calls, [0])

    def test_does_not_fire_before_the_grace_period(self):
        calls = []
        stop = threading.Event()
        thread = web_ui._start_exit_watchdog(5.0, exit_fn=calls.append, stop=stop)
        time.sleep(0.2)
        self.assertEqual(calls, [])
        stop.set()
        thread.join(2.0)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
