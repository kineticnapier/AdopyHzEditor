"""Regression tests for cross-process ADOFAI Kick cache locking."""
import multiprocessing
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from core import adofai_assets

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

    def test_lock_timeout_does_not_enter_critical_section(self):
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as tmp:
            entered = context.Event()
            release = context.Event()
            holder = context.Process(target=_hold_lock, args=(tmp, entered, release))
            try:
                holder.start()
                self.assertTrue(entered.wait(5), "holder failed to acquire lock")
                with self.assertRaises(TimeoutError):
                    with _kick_cache_lock(Path(tmp), timeout=0.2):
                        self.fail("entered a critical section while lock was held")
            finally:
                release.set()
                if holder.pid is not None:
                    holder.join(5)
                    if holder.is_alive():
                        holder.terminate()
                        holder.join(5)
            self.assertEqual(holder.exitcode, 0)

    def test_lock_is_released_when_context_body_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with self.assertRaisesRegex(ValueError, "deliberate"):
                with _kick_cache_lock(directory, timeout=1):
                    raise ValueError("deliberate")
            with _kick_cache_lock(directory, timeout=1):
                pass

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


    def test_reader_callback_holds_lock_and_preserves_path_api(self):
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "sndKick.wav"
            with patch.object(adofai_assets, "find_adofai_installation", return_value=Path(tmp)), \
                 patch.object(adofai_assets, "adofai_kick_cache_path", return_value=cache_path), \
                 patch.object(adofai_assets, "_cached_signature_matches", return_value=True):
                self.assertEqual(adofai_assets.ensure_adofai_kick(), cache_path)
                waiting = context.Event()
                finished = context.Event()
                waiter = context.Process(target=_wait_for_lock, args=(tmp, waiting, finished))
                try:
                    def read_locked(path):
                        self.assertEqual(path, cache_path)
                        waiter.start()
                        self.assertTrue(waiting.wait(5))
                        self.assertFalse(finished.wait(0.25), "writer acquired lock during decode")
                        return "decoded"
                    self.assertEqual(
                        adofai_assets.ensure_adofai_kick(_read_locked=read_locked),
                        "decoded",
                    )
                    self.assertTrue(finished.wait(5), "lock was not released after decode")
                finally:
                    if waiter.pid is not None:
                        waiter.join(5)
                        if waiter.is_alive():
                            waiter.terminate()
                            waiter.join(5)
                self.assertEqual(waiter.exitcode, 0)

    def test_reader_callback_exception_releases_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "sndKick.wav"
            with patch.object(adofai_assets, "find_adofai_installation", return_value=Path(tmp)), \
                 patch.object(adofai_assets, "adofai_kick_cache_path", return_value=cache_path), \
                 patch.object(adofai_assets, "_cached_signature_matches", return_value=True):
                def fail(_path):
                    raise ValueError("decode failed")
                with self.assertRaisesRegex(ValueError, "decode failed"):
                    adofai_assets.ensure_adofai_kick(_read_locked=fail)
                with _kick_cache_lock(Path(tmp), timeout=1):
                    pass


    def test_reader_callback_after_refresh_holds_lock(self):
        """A forced refresh must publish both files before protected decoding."""
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            cache_path = directory / "sndKick.wav"
            manifest_path = directory / "sndKick.source.json"
            waiting = context.Event()
            finished = context.Event()
            waiter = context.Process(target=_wait_for_lock, args=(tmp, waiting, finished))

            def fake_extract(_game_root, output):
                Path(output).write_bytes(b"new wav")

            try:
                with patch.object(adofai_assets, "find_adofai_installation", return_value=directory), \
                     patch.object(adofai_assets, "adofai_kick_cache_path", return_value=cache_path), \
                     patch.object(adofai_assets, "_cache_manifest_path", return_value=manifest_path), \
                     patch.object(adofai_assets, "_run_extractor", side_effect=fake_extract), \
                     patch.object(adofai_assets, "_valid_kick_wav", return_value=True), \
                     patch.object(adofai_assets, "_source_signature", return_value={"source": "new"}):
                    def read_locked(path):
                        self.assertEqual(path, cache_path)
                        self.assertEqual(path.read_bytes(), b"new wav")
                        self.assertIn('"source": "new"', manifest_path.read_text(encoding="utf-8"))
                        waiter.start()
                        self.assertTrue(waiting.wait(5), "writer failed to start")
                        self.assertFalse(finished.wait(0.25), "writer acquired lock during refreshed decode")
                        return "refreshed decoded"

                    self.assertEqual(
                        adofai_assets.ensure_adofai_kick(force=True, _read_locked=read_locked),
                        "refreshed decoded",
                    )
                    self.assertTrue(finished.wait(5), "writer did not acquire released lock")
            finally:
                if waiter.pid is not None:
                    waiter.join(5)
                    if waiter.is_alive():
                        waiter.terminate()
                        waiter.join(5)
            self.assertEqual(waiter.exitcode, 0)

if __name__ == "__main__":
    unittest.main()
