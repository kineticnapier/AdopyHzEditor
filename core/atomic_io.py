from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(
    path: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
) -> None:
    """Durably stage text beside *path* and atomically replace the target."""
    target = Path(path)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(text)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, target)
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
