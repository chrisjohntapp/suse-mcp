# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Tests for suse_ops_server.logs module (zypp history parsing).
"""

from unittest.mock import patch

import pytest

from suse_ops_server.logs import (
    parse_log_line,
    get_transaction_history,
    find_when_installed,
    find_failed_transactions,
    get_database_sync_history,
    query_package_history,
)


# Zypp history format: timestamp|action|name|version|arch|reqby|repo|checksum
SAMPLE_ZYPP_HISTORY = """\
# 2025-11-10 zypp history file
2025-11-10 15:30:00|install|vim|9.1.0330-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|abc123
2025-11-10 15:31:00|update|python3|3.11.5-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|def456
2025-11-10 15:32:00|remove|firefox|120.0-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|
2025-11-10 15:33:00|install|python-pytest|7.4.3-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|ghi789
2025-11-10 15:34:00|downgrade|systemd|255.1-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|jkl012
"""

SAMPLE_HISTORY_VIM = """\
2025-11-05 10:00:00|install|vim|9.0.900-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|a1
2025-11-06 11:00:00|update|vim|9.0.950-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|a2
2025-11-07 12:00:00|remove|vim|9.0.950-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|
2025-11-08 13:00:00|install|vim|9.1.0330-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|a3
2025-11-09 14:00:00|update|vim|9.1.0400-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|a4
"""

SAMPLE_HISTORY_FAILURES = """\
2025-11-10 10:00:00|install|vim|9.1.0330-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|a1
2025-11-10 10:01:00|fail|python3|3.11.5-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|
2025-11-10 10:02:00|install|gcc|13.2-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|b2
"""

SAMPLE_HISTORY_REFRESH = """\
2025-11-08 10:00:00|install|vim|9.1.0330-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|a1
2025-11-09 11:00:00|refresh|openSUSE-Tumbleweed-Oss||||
2025-11-10 12:00:00|refresh|openSUSE-Tumbleweed-Non-Oss||||
2025-11-10 12:30:00|install|gcc|13.2-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|b2
"""


@pytest.fixture
def history_file(tmp_path):
    """Create a temporary zypp history file and patch ZYPP_HISTORY to point to it."""
    def _make(content):
        f = tmp_path / "history"
        f.write_text(content)
        return str(f)
    return _make


class TestLogParsing:
    """Test zypp history log line parsing."""

    def test_parse_log_line_install(self):
        line = "2025-11-10 15:30:00|install|vim|9.1.0330-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|abc123"
        result = parse_log_line(line)
        assert result is not None
        assert result["timestamp"] == "2025-11-10 15:30:00"
        assert result["action"] == "install"
        assert result["package"] == "vim"
        assert result["version"] == "9.1.0330-1.1"
        assert result["arch"] == "x86_64"
        assert result["repo"] == "openSUSE-Tumbleweed-Oss"

    def test_parse_log_line_update(self):
        line = "2025-11-10 15:31:00|update|python3|3.11.5-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|def456"
        result = parse_log_line(line)
        assert result is not None
        assert result["action"] == "update"
        assert result["package"] == "python3"

    def test_parse_log_line_comment(self):
        assert parse_log_line("# this is a comment") is None

    def test_parse_log_line_empty(self):
        assert parse_log_line("") is None

    def test_parse_log_line_invalid(self):
        assert parse_log_line("not a valid line") is None

    def test_parse_log_line_minimal_fields(self):
        result = parse_log_line("2025-11-10 15:30:00|install")
        assert result is not None
        assert result["action"] == "install"
        assert result["package"] == ""


class TestTransactionHistory:
    """Test transaction history retrieval."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", True)
    async def test_get_transaction_history_all(self, history_file):
        with patch("suse_ops_server.logs.ZYPP_HISTORY", history_file(SAMPLE_ZYPP_HISTORY)):
            result = await get_transaction_history(limit=10)
            assert result["count"] == 5
            assert len(result["transactions"]) == 5

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", True)
    async def test_get_transaction_history_install_only(self, history_file):
        with patch("suse_ops_server.logs.ZYPP_HISTORY", history_file(SAMPLE_ZYPP_HISTORY)):
            result = await get_transaction_history(limit=10, action_filter="install")
            assert result["count"] == 2
            for t in result["transactions"]:
                assert t["action"] == "install"

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", True)
    async def test_get_transaction_history_with_limit(self, history_file):
        with patch("suse_ops_server.logs.ZYPP_HISTORY", history_file(SAMPLE_ZYPP_HISTORY)):
            result = await get_transaction_history(limit=2)
            assert result["count"] == 2

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", False)
    async def test_not_suse(self):
        result = await get_transaction_history()
        assert result["error"] is True
        assert result["type"] == "NotSupported"


class TestPackageInstallationHistory:
    """Test package installation history."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", True)
    async def test_find_when_installed_success(self, history_file):
        with patch("suse_ops_server.logs.ZYPP_HISTORY", history_file(SAMPLE_HISTORY_VIM)):
            result = await find_when_installed("vim")
            assert result["package"] == "vim"
            assert result["first_installed"]["version"] == "9.0.900-1.1"
            assert result["update_count"] == 2
            assert len(result["updates"]) == 2

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", True)
    async def test_find_when_installed_with_removals(self, history_file):
        with patch("suse_ops_server.logs.ZYPP_HISTORY", history_file(SAMPLE_HISTORY_VIM)):
            result = await find_when_installed("vim")
            assert result["removal_count"] == 1
            assert len(result["removals"]) == 1

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", True)
    async def test_find_when_installed_not_found(self, history_file):
        with patch("suse_ops_server.logs.ZYPP_HISTORY", history_file(SAMPLE_HISTORY_VIM)):
            result = await find_when_installed("nonexistent")
            assert result["error"] is True
            assert result["type"] == "NotFound"


class TestFailedTransactions:
    """Test failed transaction detection."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", True)
    async def test_find_failed_transactions_success(self, history_file):
        with patch("suse_ops_server.logs.ZYPP_HISTORY", history_file(SAMPLE_HISTORY_FAILURES)):
            result = await find_failed_transactions()
            assert result["has_failures"] is True
            assert result["count"] == 1
            assert result["failures"][0]["package"] == "python3"

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", True)
    async def test_find_failed_transactions_none(self, history_file):
        clean = "2025-11-10 10:00:00|install|vim|9.1.0330-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|a1\n"
        with patch("suse_ops_server.logs.ZYPP_HISTORY", history_file(clean)):
            result = await find_failed_transactions()
            assert result["has_failures"] is False
            assert result["count"] == 0

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", False)
    async def test_not_suse(self):
        result = await find_failed_transactions()
        assert result["error"] is True
        assert result["type"] == "NotSupported"


class TestDatabaseSyncHistory:
    """Test database sync history."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", True)
    async def test_get_database_sync_history_success(self, history_file):
        with patch("suse_ops_server.logs.ZYPP_HISTORY", history_file(SAMPLE_HISTORY_REFRESH)):
            result = await get_database_sync_history(limit=10)
            assert result["count"] == 2
            for event in result["sync_events"]:
                assert "refresh" in event["action"].lower()

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", True)
    async def test_get_database_sync_history_with_limit(self, history_file):
        with patch("suse_ops_server.logs.ZYPP_HISTORY", history_file(SAMPLE_HISTORY_REFRESH)):
            result = await get_database_sync_history(limit=1)
            assert result["count"] == 1

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", False)
    async def test_not_suse(self):
        result = await get_database_sync_history()
        assert result["error"] is True
        assert result["type"] == "NotSupported"


class TestQueryPackageHistory:
    """Test package history queries."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", True)
    async def test_query_success(self, history_file):
        with patch("suse_ops_server.logs.ZYPP_HISTORY", history_file(SAMPLE_HISTORY_VIM)):
            result = await query_package_history("vim")
            assert result["package"] == "vim"
            assert result["count"] == 5
            assert len(result["history"]) == 5

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", True)
    async def test_query_with_limit(self, history_file):
        with patch("suse_ops_server.logs.ZYPP_HISTORY", history_file(SAMPLE_HISTORY_VIM)):
            result = await query_package_history("vim", limit=2)
            assert result["count"] == 2

    @pytest.mark.asyncio
    @patch("suse_ops_server.logs.IS_SUSE", True)
    async def test_query_not_found(self, history_file):
        with patch("suse_ops_server.logs.ZYPP_HISTORY", history_file(SAMPLE_HISTORY_VIM)):
            result = await query_package_history("nonexistent")
            assert result["count"] == 0
