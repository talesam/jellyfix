"""Regression tests for the jellyfix-batch wrapper."""

import os
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent.parent / "usr" / "bin" / "jellyfix-batch"


def test_batch_preserves_shell_metacharacters_in_workdir(tmp_path):
    media_dir = tmp_path / "Law & Order's Unit"
    media_dir.mkdir()

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    args_file = tmp_path / "args.txt"

    fake_jellyfix = fake_bin / "jellyfix"
    fake_jellyfix.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$@\" > \"$JELLYFIX_ARGS_FILE\"\n",
        encoding="utf-8",
    )
    fake_jellyfix.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["JELLYFIX_ARGS_FILE"] = str(args_file)

    result = subprocess.run(
        [str(SCRIPT), "-n", str(media_dir)],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    args = args_file.read_text(encoding="utf-8").splitlines()
    workdir_index = args.index("--workdir")
    assert args[workdir_index + 1] == str(media_dir)


def test_batch_rejects_invalid_jobs(tmp_path):
    media_dir = tmp_path / "show"
    media_dir.mkdir()

    result = subprocess.run(
        [str(SCRIPT), "-j", "0", "-n", str(media_dir)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 1
    assert "--jobs" in result.stderr
