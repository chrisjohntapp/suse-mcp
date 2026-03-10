# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Tests for suse_ops_server.mirrors module (SUSE repo management).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from suse_ops_server.mirrors import (
    REPOS_DIR,
    list_repos,
    test_repo_speed as _test_repo_speed,
    check_repos_health,
    optimize_mirrors,
)


SAMPLE_REPO_FILE = """\
[openSUSE-Tumbleweed-Oss]
name=openSUSE-Tumbleweed-Oss
enabled=1
autorefresh=1
baseurl=https://download.opensuse.org/tumbleweed/repo/oss/
type=rpm-md
gpgcheck=1
"""

SAMPLE_REPO_DISABLED = """\
[openSUSE-Tumbleweed-Debug]
name=openSUSE-Tumbleweed-Debug
enabled=0
autorefresh=0
baseurl=https://download.opensuse.org/tumbleweed/repo/debug/
type=rpm-md
gpgcheck=1
"""


class TestListRepos:
    """Test repo listing from /etc/zypp/repos.d/."""

    def test_success(self, tmp_path):
        repo_file = tmp_path / "oss.repo"
        repo_file.write_text(SAMPLE_REPO_FILE)
        with patch("suse_ops_server.mirrors.REPOS_DIR", str(tmp_path)):
            result = list_repos()
            assert result["repo_count"] == 1
            repo = result["repos"][0]
            assert repo["name"] == "openSUSE-Tumbleweed-Oss"
            assert repo["enabled"] is True
            assert repo["autorefresh"] is True
            assert "download.opensuse.org" in repo["baseurl"]
            assert repo["gpgcheck"] is True

    def test_multiple_repos(self, tmp_path):
        (tmp_path / "oss.repo").write_text(SAMPLE_REPO_FILE)
        (tmp_path / "debug.repo").write_text(SAMPLE_REPO_DISABLED)
        with patch("suse_ops_server.mirrors.REPOS_DIR", str(tmp_path)):
            result = list_repos()
            assert result["repo_count"] == 2
            enabled = [r for r in result["repos"] if r["enabled"]]
            disabled = [r for r in result["repos"] if not r["enabled"]]
            assert len(enabled) == 1
            assert len(disabled) == 1

    def test_empty_dir(self, tmp_path):
        with patch("suse_ops_server.mirrors.REPOS_DIR", str(tmp_path)):
            result = list_repos()
            assert result["repo_count"] == 0

    def test_dir_not_found(self):
        with patch("suse_ops_server.mirrors.REPOS_DIR", "/nonexistent"):
            result = list_repos()
            assert result["error"] is True
            assert result["type"] == "NotFound"


class TestRepoSpeed:
    """Test repo speed testing."""

    @pytest.mark.asyncio
    async def test_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("httpx.AsyncClient") as mock_client, \
             patch("time.time", side_effect=[0.0, 0.05]):
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.head = AsyncMock(return_value=mock_response)
            result = await _test_repo_speed("https://download.opensuse.org/tumbleweed/repo/oss/")
            assert result["success"] is True
            assert result["latency_ms"] == 50.0
            assert "repodata/repomd.xml" in result["test_url"]

    @pytest.mark.asyncio
    async def test_timeout(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.head = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )
            result = await _test_repo_speed("https://slow.example.com/repo/")
            assert result["success"] is False
            assert result["error"] == "timeout"

    @pytest.mark.asyncio
    async def test_appends_trailing_slash(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("httpx.AsyncClient") as mock_client, \
             patch("time.time", side_effect=[0.0, 0.01]):
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.head = AsyncMock(return_value=mock_response)
            result = await _test_repo_speed("https://example.com/repo")
            assert result["baseurl"] == "https://example.com/repo/"


class TestCheckReposHealth:
    """Test repos health check."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.mirrors.IS_SUSE", True)
    async def test_healthy(self, tmp_path):
        (tmp_path / "oss.repo").write_text(SAMPLE_REPO_FILE)
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("suse_ops_server.mirrors.REPOS_DIR", str(tmp_path)), \
             patch("httpx.AsyncClient") as mock_client, \
             patch("time.time", side_effect=[0.0, 0.05]):
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.head = AsyncMock(return_value=mock_response)
            result = await check_repos_health()
            assert result["healthy"] is True
            assert result["repo_count"] == 1
            assert result["enabled_count"] == 1
            assert result["reachable_count"] == 1
            assert result["issues"] == []

    @pytest.mark.asyncio
    @patch("suse_ops_server.mirrors.IS_SUSE", True)
    async def test_no_enabled_repos(self, tmp_path):
        (tmp_path / "debug.repo").write_text(SAMPLE_REPO_DISABLED)
        with patch("suse_ops_server.mirrors.REPOS_DIR", str(tmp_path)):
            result = await check_repos_health()
            assert "No enabled repositories" in result["issues"][0]

    @pytest.mark.asyncio
    @patch("suse_ops_server.mirrors.IS_SUSE", False)
    async def test_not_suse(self):
        result = await check_repos_health()
        assert result["error"] is True
        assert result["type"] == "NotSupported"


class TestOptimizeMirrors:
    """Test optimize_mirrors entry point."""

    @pytest.mark.asyncio
    async def test_status_action(self, tmp_path):
        (tmp_path / "oss.repo").write_text(SAMPLE_REPO_FILE)
        with patch("suse_ops_server.mirrors.REPOS_DIR", str(tmp_path)):
            result = await optimize_mirrors(action="status")
            assert result["action"] == "status"
            assert result["configuration"]["repo_count"] == 1

    @pytest.mark.asyncio
    async def test_test_action(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("httpx.AsyncClient") as mock_client, \
             patch("time.time", side_effect=[0.0, 0.03]):
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.head = AsyncMock(return_value=mock_response)
            result = await optimize_mirrors(
                action="test",
                baseurl="https://download.opensuse.org/tumbleweed/repo/oss/",
            )
            assert result["action"] == "test"
            assert result["result"]["success"] is True

    @pytest.mark.asyncio
    async def test_test_action_missing_url(self):
        result = await optimize_mirrors(action="test")
        assert result["error"] is True
        assert result["type"] == "InvalidParameter"

    @pytest.mark.asyncio
    async def test_invalid_action(self):
        result = await optimize_mirrors(action="invalid")
        assert result["error"] is True
        assert result["type"] == "InvalidAction"
