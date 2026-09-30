# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""Tests for command detection helpers in suse_ops_server.utils.

Detection must not depend on the external `which` binary: minimal container images
(and proot terminals) frequently ship no `which`, which made every tool that
guards on command availability report "not installed" even when the command is
present at an absolute path.
"""

import os
import stat
from unittest.mock import patch

from suse_ops_server.utils import check_command_exists


def _fake_bin(tmp_path, name):
    d = tmp_path / "bin"
    d.mkdir(exist_ok=True)
    target = d / name
    target.write_text("#!/bin/sh\n")
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return d


class TestCheckCommandExists:
    def test_finds_command_on_path(self, tmp_path):
        _fake_bin(tmp_path, "zypper")
        with patch.dict(os.environ, {"PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin"}):
            assert check_command_exists("zypper") is True

    def test_returns_false_for_missing_command(self, tmp_path):
        with patch.dict(os.environ, {"PATH": f"{tmp_path / 'bin'}"}):
            assert check_command_exists("definitely-not-a-real-command") is False

    def test_does_not_require_the_which_binary(self, tmp_path):
        """PATH contains the tool but not `which` - detection must still work."""
        bin_dir = _fake_bin(tmp_path, "zypper")
        empty = tmp_path / "empty"
        empty.mkdir()
        with patch.dict(os.environ, {"PATH": f"{bin_dir}:{empty}"}):
            assert check_command_exists("zypper") is True
