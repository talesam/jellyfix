"""Shared test fixtures for Jellyfix test suite."""

import sys
from pathlib import Path

import pytest

# Add the jellyfix package to sys.path so imports work without installation
_JELLYFIX_ROOT = Path(__file__).resolve().parent.parent / "usr" / "share" / "jellyfix"
if str(_JELLYFIX_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_JELLYFIX_ROOT.parent))


@pytest.fixture
def tmp_media(tmp_path: Path):
    """Create a temporary media directory with sample files."""
    return tmp_path
