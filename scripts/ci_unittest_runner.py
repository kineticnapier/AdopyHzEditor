"""CI unittest runner with periodic stack traces for stalled tests.

Run from repository root as a real file so multiprocessing spawn can re-import
the __main__ module (unlike a runner supplied through standard input).
"""
import faulthandler
import sys
import unittest


def main() -> int:
    faulthandler.enable()
    faulthandler.dump_traceback_later(120, repeat=True, file=sys.stderr)
    try:
        suite = unittest.defaultTestLoader.discover("tests", pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    finally:
        faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    sys.exit(main())
