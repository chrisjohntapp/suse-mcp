# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""Tests for the consolidated tool wiring in suse_ops_server.server.

The unified tools advertise richer input schemas than the functions they dispatch
to actually accept. These tests pin the argument mapping so a mismatch fails here
instead of raising TypeError in a live MCP session.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from suse_ops_server.server import call_tool


def _text(result):
    return json.loads(result[0].text)


class TestQueryFileOwnershipModes:
    """query_file_ownership advertises three modes but used to pass all three
    arguments to a single-parameter function, so every call raised TypeError."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.server.IS_SUSE", True)
    async def test_file_to_package(self):
        with patch("suse_ops_server.server.find_package_owner", new=AsyncMock(return_value={"package": "zypper"})) as owner:
            result = _text(await call_tool("query_file_ownership", {"query": "/usr/bin/zypper", "mode": "file_to_package"}))
        assert result["package"] == "zypper"
        owner.assert_awaited_once_with("/usr/bin/zypper")

    @pytest.mark.asyncio
    @patch("suse_ops_server.server.IS_SUSE", True)
    async def test_package_to_files_applies_filter(self):
        files = {"files": ["/usr/lib/systemd/system/journald.service", "/usr/bin/journalctl"]}
        with patch("suse_ops_server.server.list_package_files", new=AsyncMock(return_value=files)):
            result = _text(await call_tool("query_file_ownership", {"query": "systemd", "mode": "package_to_files", "filter_pattern": "*.service"}))
        assert result["files"] == ["/usr/lib/systemd/system/journald.service"]

    @pytest.mark.asyncio
    @patch("suse_ops_server.server.IS_SUSE", True)
    async def test_filename_search(self):
        with patch("suse_ops_server.server.search_package_files", new=AsyncMock(return_value={"matches": []})) as search:
            await call_tool("query_file_ownership", {"query": "*.desktop", "mode": "filename_search"})
        search.assert_awaited_once_with("*.desktop")

    @pytest.mark.asyncio
    @patch("suse_ops_server.server.IS_SUSE", True)
    async def test_unknown_mode_reports_error(self):
        result = _text(await call_tool("query_file_ownership", {"query": "x", "mode": "nonsense"}))
        assert result["error"] is True
        assert result["type"] == "InvalidMode"


class TestOptimizeMirrorsArguments:
    """optimize_mirrors(action, baseurl) does not accept country/limit/auto_test."""

    @pytest.mark.asyncio
    async def test_mirror_url_maps_to_baseurl(self):
        with patch("suse_ops_server.server.optimize_mirrors", new=AsyncMock(return_value={"ok": True})) as opt:
            result = _text(await call_tool("optimize_mirrors", {"action": "test", "mirror_url": "https://example.org"}))
        assert result["ok"] is True
        opt.assert_awaited_once_with("test", baseurl="https://example.org")

    @pytest.mark.asyncio
    async def test_unsupported_argument_reports_not_supported(self):
        with patch("suse_ops_server.server.optimize_mirrors", new=AsyncMock(return_value={"ok": True})) as opt:
            result = _text(await call_tool("optimize_mirrors", {"action": "suggest", "country": "DE"}))
        assert result["error"] is True
        assert result["type"] == "NotSupported"
        opt.assert_not_awaited()


class TestManageOrphansArguments:
    """exclude must reach `packages` and dry_run must stay a bool."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.server.IS_SUSE", True)
    async def test_exclude_maps_to_packages(self):
        with patch("suse_ops_server.server.manage_orphans", new=AsyncMock(return_value={"ok": True})) as orphans:
            await call_tool("manage_orphans", {"action": "remove", "dry_run": True, "exclude": ["vim"]})
        orphans.assert_awaited_once_with("remove", packages=["vim"], dry_run=True)

    @pytest.mark.asyncio
    @patch("suse_ops_server.server.IS_SUSE", True)
    async def test_remove_passes_dry_run_through(self):
        with patch("suse_ops_server.server.manage_orphans", new=AsyncMock(return_value={"ok": True})) as orphans:
            await call_tool("manage_orphans", {"action": "remove", "dry_run": False, "exclude": ["vim"]})
        orphans.assert_awaited_once_with("remove", packages=["vim"], dry_run=False)


class TestRemovePackagesArguments:
    """remove_packages(packages, orphan_check, cascade) - the tool schema names them
    remove_dependencies and force."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.server.IS_SUSE", True)
    async def test_dependency_and_force_mapping(self):
        with patch("suse_ops_server.server.remove_packages", new=AsyncMock(return_value={"ok": True})) as remove:
            await call_tool("remove_packages", {"packages": ["vim"], "remove_dependencies": True, "force": True})
        remove.assert_awaited_once_with(["vim"], orphan_check=True, cascade=True)

    @pytest.mark.asyncio
    @patch("suse_ops_server.server.IS_SUSE", True)
    async def test_defaults(self):
        with patch("suse_ops_server.server.remove_packages", new=AsyncMock(return_value={"ok": True})) as remove:
            await call_tool("remove_packages", {"packages": "vim"})
        remove.assert_awaited_once_with("vim", orphan_check=False, cascade=False)


class TestManageInstallReasonArguments:
    @pytest.mark.asyncio
    @patch("suse_ops_server.server.IS_SUSE", True)
    async def test_list_uses_list_explicit_packages(self):
        with patch("suse_ops_server.server.list_explicit_packages", new=AsyncMock(return_value={"packages": []})) as explicit:
            await call_tool("manage_install_reason", {"action": "list"})
        explicit.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("suse_ops_server.server.IS_SUSE", True)
    async def test_mark_explicit_passes_reason(self):
        with patch("suse_ops_server.server.manage_install_reason", new=AsyncMock(return_value={"ok": True})) as reason:
            await call_tool("manage_install_reason", {"action": "mark_explicit", "package_name": "git"})
        reason.assert_awaited_once_with("git", "mark_explicit")

    @pytest.mark.asyncio
    @patch("suse_ops_server.server.IS_SUSE", True)
    async def test_mark_action_without_package_reports_missing_parameter(self):
        result = _text(await call_tool("manage_install_reason", {"action": "mark_dependency"}))
        assert result["type"] == "MissingParameter"


class TestQueryPackageHistoryArguments:
    """query_package_history(package_name, limit) has no query_type parameter."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.server.IS_SUSE", True)
    async def test_all_uses_limit(self):
        with patch("suse_ops_server.server.query_package_history", new=AsyncMock(return_value={"transactions": []})) as history:
            await call_tool("query_package_history", {"query_type": "all", "limit": 5})
        history.assert_awaited_once_with(package_name=None, limit=5)

    @pytest.mark.asyncio
    @patch("suse_ops_server.server.IS_SUSE", True)
    async def test_package_requires_name(self):
        result = _text(await call_tool("query_package_history", {"query_type": "package"}))
        assert result["type"] == "MissingParameter"

    @pytest.mark.asyncio
    @patch("suse_ops_server.server.IS_SUSE", True)
    async def test_unimplemented_query_type(self):
        with patch("suse_ops_server.server.query_package_history", new=AsyncMock(return_value={})) as history:
            result = _text(await call_tool("query_package_history", {"query_type": "failures"}))
        assert result["type"] == "NotSupported"
        history.assert_not_awaited()
