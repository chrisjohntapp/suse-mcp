# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Tests for suse_ops_server.patterns module (zypper pattern management).
"""

from unittest.mock import patch

import pytest

from suse_ops_server.patterns import manage_patterns


SAMPLE_PATTERNS_OUTPUT = """\
S | Name                     | Version    | Repository                | Description
--+--------------------------+------------+---------------------------+----------------------------
i | base                     | 20240101-1 | openSUSE-Tumbleweed-Oss   | Base System
  | devel_basis               | 20240101-1 | openSUSE-Tumbleweed-Oss   | Base Development
i | enhanced_base            | 20240101-1 | openSUSE-Tumbleweed-Oss   | Enhanced Base System
"""

SAMPLE_PATTERN_INFO_OUTPUT = """\
Information for pattern base:
Name: base
Version: 20240101-1
Summary: Base System
Description: Minimal base system
Category: Base Technologies
Installed: Yes
Visible: Yes
"""


class TestManagePatterns:
    """Test manage_patterns entry point."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.patterns.IS_SUSE", True)
    async def test_list_patterns(self):
        with patch("suse_ops_server.patterns.run_command") as mock_run:
            mock_run.return_value = (0, SAMPLE_PATTERNS_OUTPUT, "")
            result = await manage_patterns("list_patterns")
            assert result["action"] == "list_patterns"
            assert result["total_patterns"] == 3
            installed = [p for p in result["patterns"] if p["installed"]]
            assert len(installed) == 2
            assert result["patterns"][0]["name"] == "base"

    @pytest.mark.asyncio
    @patch("suse_ops_server.patterns.IS_SUSE", True)
    async def test_pattern_info(self):
        with patch("suse_ops_server.patterns.run_command") as mock_run:
            mock_run.return_value = (0, SAMPLE_PATTERN_INFO_OUTPUT, "")
            result = await manage_patterns("pattern_info", pattern_name="base")
            assert result["action"] == "pattern_info"
            assert result["pattern"]["name"] == "base"
            assert result["pattern"]["version"] == "20240101-1"

    @pytest.mark.asyncio
    @patch("suse_ops_server.patterns.IS_SUSE", True)
    async def test_pattern_info_missing_name(self):
        result = await manage_patterns("pattern_info")
        assert result["error"] is True
        assert result["type"] == "InvalidParameter"

    @pytest.mark.asyncio
    @patch("suse_ops_server.patterns.IS_SUSE", True)
    async def test_invalid_action(self):
        result = await manage_patterns("invalid")
        assert result["error"] is True
        assert result["type"] == "InvalidAction"

    @pytest.mark.asyncio
    @patch("suse_ops_server.patterns.IS_SUSE", False)
    async def test_not_suse(self):
        result = await manage_patterns("list_patterns")
        assert result["error"] is True
        assert result["type"] == "NotSupported"

    @pytest.mark.asyncio
    @patch("suse_ops_server.patterns.IS_SUSE", True)
    async def test_list_patterns_command_error(self):
        with patch("suse_ops_server.patterns.run_command") as mock_run:
            mock_run.return_value = (1, "", "zypper: error")
            result = await manage_patterns("list_patterns")
            assert result["error"] is True
            assert result["type"] == "CommandError"

    @pytest.mark.asyncio
    @patch("suse_ops_server.patterns.IS_SUSE", True)
    async def test_list_patterns_empty(self):
        empty = "S | Name | Version | Repository | Description\n--+------+---------+------------+-------------\n"
        with patch("suse_ops_server.patterns.run_command") as mock_run:
            mock_run.return_value = (0, empty, "")
            result = await manage_patterns("list_patterns")
            assert result["total_patterns"] == 0
