# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Tests for suse_ops_server.system_health_check module.
"""

from unittest.mock import AsyncMock, patch

import pytest

from suse_ops_server.system_health_check import run_system_health_check


def _mock_async(return_value):
    return AsyncMock(return_value=return_value)


# Patches target the source modules since system_health_check uses lazy imports
_SYSTEM = "suse_ops_server.system"
_ZYPPER = "suse_ops_server.zypper"
_NEWS = "suse_ops_server.news"
_MIRRORS = "suse_ops_server.mirrors"
_HC = "suse_ops_server.system_health_check"


def _base_patches(updates=None, orphans=None):
    """Return a list of patches for all health check dependencies."""
    if updates is None:
        updates = {"updates_available": False}
    if orphans is None:
        orphans = {"has_orphans": False}
    return [
        patch(f"{_SYSTEM}.get_system_info", _mock_async({"kernel": "6.7.1"})),
        patch(f"{_SYSTEM}.check_disk_space", _mock_async({"disk_usage": {}})),
        patch(f"{_SYSTEM}.check_failed_services", _mock_async({"failed_count": 0})),
        patch(f"{_SYSTEM}.get_package_cache_stats", _mock_async({"package_count": 10})),
        patch(f"{_ZYPPER}.check_updates_dry_run", _mock_async(updates)),
        patch(f"{_NEWS}.check_critical_news", _mock_async({"has_critical": False})),
        patch(f"{_ZYPPER}.list_orphan_packages", _mock_async(orphans)),
        patch(f"{_ZYPPER}.check_database_freshness", _mock_async({"fresh": True})),
        patch(f"{_MIRRORS}.check_repos_health", _mock_async({"healthy": True})),
    ]


class TestSystemHealthCheck:
    """Test comprehensive system health check."""

    @pytest.mark.asyncio
    @patch(f"{_HC}.IS_IMMUTABLE", False)
    @patch(f"{_HC}.SUSE_VARIANT", "opensuse-tumbleweed")
    async def test_health_check_standard_variant(self):
        patches = _base_patches(updates={"updates_available": True, "count": 5})
        for p in patches:
            p.start()
        try:
            result = await run_system_health_check()

            assert result["status"] == "success"
            assert result["system_info"]["kernel"] == "6.7.1"
            update_suggestions = [s for s in result["suggestions"] if "updates available" in s["message"]]
            assert len(update_suggestions) == 1
            assert "zypper update" in update_suggestions[0]["action"]
        finally:
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    @patch(f"{_HC}.IS_IMMUTABLE", True)
    @patch(f"{_HC}.SUSE_VARIANT", "opensuse-microos")
    async def test_health_check_immutable_variant(self):
        patches = _base_patches(updates={"updates_available": True, "count": 3})
        for p in patches:
            p.start()
        try:
            result = await run_system_health_check()

            assert result["status"] == "success"
            update_suggestions = [s for s in result["suggestions"] if "updates available" in s["message"]]
            assert len(update_suggestions) == 1
            assert "transactional-update" in update_suggestions[0]["action"]
            assert "reboot" in update_suggestions[0]["action"]
        finally:
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    @patch(f"{_HC}.IS_IMMUTABLE", False)
    @patch(f"{_HC}.SUSE_VARIANT", "sles")
    async def test_health_check_sle_variant(self):
        patches = _base_patches()
        for p in patches:
            p.start()
        try:
            result = await run_system_health_check()

            assert result["status"] == "success"
            sle_suggestions = [s for s in result["suggestions"] if "SLE" in s["message"]]
            assert len(sle_suggestions) == 1
            assert "SUSEConnect" in sle_suggestions[0]["action"]
        finally:
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    @patch(f"{_HC}.IS_IMMUTABLE", False)
    @patch(f"{_HC}.SUSE_VARIANT", "opensuse-tumbleweed")
    async def test_health_check_with_orphans(self):
        patches = _base_patches(orphans={"has_orphans": True, "orphan_count": 7})
        for p in patches:
            p.start()
        try:
            result = await run_system_health_check()

            orphan_suggestions = [s for s in result["suggestions"] if "orphan" in s["message"]]
            assert len(orphan_suggestions) == 1
            assert "7 orphan" in orphan_suggestions[0]["message"]
        finally:
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    @patch(f"{_HC}.IS_IMMUTABLE", False)
    @patch(f"{_HC}.SUSE_VARIANT", "opensuse-tumbleweed")
    async def test_health_check_exception(self):
        with patch(f"{_SYSTEM}.get_system_info", side_effect=RuntimeError("boom")):
            result = await run_system_health_check()

            assert result["status"] == "error"
            assert "boom" in result["error"]
            assert result["summary"]["critical_issues"] == 1
