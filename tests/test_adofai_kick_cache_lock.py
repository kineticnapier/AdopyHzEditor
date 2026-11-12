"""Regression tests for cross-process ADOFAI Kick cache locking."""
import multiprocessing
import tempfile
import time
import unittest
from pathlib import Path

from core.adofai_assets import _kick_cache_lock


def _hold_lock(directory, entered, release):
    with _kick_cache_lock(Path(directory), timeout=10):
        entered.set()
        release.wait(8)


def _wait_for_lock(directory, entered, finished):
    entered.set()
    with _kick_cache_lock(Path(directory), timeout=10):
        finished.set()


class KickCacheLockTests(unittest.TestCase):
    def test_lock_is_released_after_holder_is_terminated(self):
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as tmp:
            entered = context.Event()
            release = context.Event()
            waiting = context.Event()
            finished = context.Event()
            holder = context.Process(target=_hold_lock, args=(tmp, entered, release))
            waiter = context.Process(target=_wait_for_lock, args=(tmp, waiting, finished))
            try:
                holder.start()
                self.assertTrue(entered.wait(5), "holder failed to acquire lock")
                waiter.start()
                self.assertTrue(waiting.wait(5), "waiter failed to start")
                self.assertFalse(finished.wait(0.25), "waiter acquired a held lock")
                holder.terminate()
                holder.join(5)
                self.assertFalse(holder.is_alive(), "holder did not terminate")
                self.assertTrue(finished.wait(5), "lock was not released on process exit")
            finally:
                release.set()
                for process in (holder, waiter):
                    if process.pid is not None:
                        process.join(5)
                        if process.is_alive():
                            process.terminate()
                            process.join(5)
            self.assertEqual(waiter.exitcode, 0)

    def test_other_process_waits_until_lock_is_released(self):
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as tmp:
            entered = context.Event()
            release = context.Event()
            waiting = context.Event()
            finished = context.Event()
            holder = context.Process(target=_hold_lock, args=(tmp, entered, release))
            waiter = context.Process(target=_wait_for_lock, args=(tmp, waiting, finished))
            try:
                holder.start()
                self.assertTrue(entered.wait(5), "holder failed to acquire lock")
                waiter.start()
                self.assertTrue(waiting.wait(5), "waiter failed to start")
                self.assertFalse(finished.wait(0.25), "waiter entered critical section too early")
                release.set()
                self.assertTrue(finished.wait(5), "waiter did not acquire released lock")
            finally:
                release.set()
                for process in (holder, waiter):
                    if process.pid is not None:
                        process.join(5)
                        if process.is_alive():
                            process.terminate()
                            process.join(5)
            self.assertEqual(holder.exitcode, 0)
            self.assertEqual(waiter.exitcode, 0)


if __name__ == "__main__":
    unittest.main()
