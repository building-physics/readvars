from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import shutil
import uuid

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "regression: compares package output byte-for-byte with stored gold output",
    )


@pytest.fixture
def tmp_path() -> Iterator[Path]:
    """Provide a writable temp path on hosts with locked global temp ACLs."""
    root = Path(__file__).parent / ".runtime"
    root.mkdir(exist_ok=True)
    path = root / uuid.uuid4().hex
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
