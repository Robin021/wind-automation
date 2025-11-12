from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .config import PathsConfig


def ensure_directories(paths: PathsConfig) -> Iterable[Path]:
    """Ensure all required directories exist and return the ones created."""
    created = []
    to_create = [
        paths.data_root,
        paths.stocks_dir,
        paths.trades_dir,
        paths.pending_orders_dir,
        paths.reports_dir,
        paths.log_file.parent,
    ]
    for directory in to_create:
        directory.mkdir(parents=True, exist_ok=True)
        created.append(directory)
    return created
