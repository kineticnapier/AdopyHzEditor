"""Compatibility entry point for :mod:`exporters.rabbit_zip_formula`."""

if __name__ == "__main__":
    import runpy as _runpy
    _runpy.run_module("exporters.rabbit_zip_formula", run_name="__main__")
else:
    import sys as _sys
    from exporters import rabbit_zip_formula as _impl
    _sys.modules[__name__] = _impl
