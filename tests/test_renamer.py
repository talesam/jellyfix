"""Tests for core/renamer.py safety behavior."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from jellyfix.core.renamer import RenameOperation, Renamer


def _renamer(tmp_path: Path) -> Renamer:
    config = MagicMock()
    config.fetch_metadata = False

    with patch("jellyfix.core.renamer.get_config", return_value=config):
        renamer = Renamer()

    renamer.work_dir = tmp_path
    return renamer


def test_execute_aborts_before_delete_when_reversible_operation_fails(tmp_path):
    delete_target = tmp_path / "foreign.spa.srt"
    delete_target.write_text("subtitle", encoding="utf-8")

    renamer = _renamer(tmp_path)
    renamer.operations = [
        RenameOperation(
            source=delete_target,
            destination=delete_target,
            operation_type="delete",
            reason="delete foreign subtitle",
        ),
        RenameOperation(
            source=tmp_path / "missing.mkv",
            destination=tmp_path / "renamed.mkv",
            operation_type="rename",
            reason="missing source",
        ),
    ]

    stats = renamer.execute_operations(dry_run=False)

    assert stats["failed"] == 1
    assert stats["deleted"] == 0
    assert delete_target.exists()
