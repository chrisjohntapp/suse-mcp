# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Tests for suse_ops_server.zypper module.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

import httpx
import pytest

from suse_ops_server.zypper import (
    OPENSUSE_SOFTWARE_URL,
    _parse_zypper_info_output,
    _parse_list_updates_output,
    _parse_zypper_packages_output,
    check_updates_dry_run,
    get_official_package_info,
    check_database_freshness,
    verify_package_integrity,
    find_package_owner,
    list_package_files,
    search_package_files,
    list_orphan_packages,
    remove_orphans,
    manage_orphans,
    remove_packages,
    list_explicit_packages,
    mark_as_explicit,
    mark_as_dependency,
    manage_install_reason,
)


SAMPLE_ZYPPER_INFO = """\
Information for package vim:
----------------------------
Repository     : openSUSE-Tumbleweed-Oss
Name           : vim
Version        : 9.1.0330-1.1
Arch           : x86_64
Vendor         : openSUSE
Installed Size : 3.5 MiB
Installed      : Yes
Status         : up-to-date
Source package : vim-9.1.0330-1.1.src
Upstream URL   : https://www.vim.org
Summary        : Vi IMproved
Description    :
  Vim (Vi IMproved) is an almost compatible version of the UNIX editor vi.
"""

SAMPLE_LIST_UPDATES = """\
S | Repository                   | Name           | Current Version | Available Version | Arch
--+------------------------------+----------------+-----------------+-------------------+-------
v | openSUSE-Tumbleweed-Oss      | vim            | 9.0.1000-1.1    | 9.1.0330-1.1      | x86_64
v | openSUSE-Tumbleweed-Oss      | python3        | 3.11.0-1.1      | 3.11.5-1.1        | x86_64
"""

SAMPLE_ZYPPER_PACKAGES = """\
S | Name           | Type         | Version      | Arch   | Repository
--+----------------+--------------+--------------+--------+----------------
i | vim            | package      | 9.1.0330-1.1 | x86_64 | openSUSE-Tumbleweed-Oss
i | python3        | package      | 3.11.5-1.1   | x86_64 | openSUSE-Tumbleweed-Oss
"""


class TestParseZypperInfoOutput:
    """Test _parse_zypper_info_output."""

    def test_parse_valid_output(self):
        result = _parse_zypper_info_output(SAMPLE_ZYPPER_INFO)
        assert result is not None
        assert result["name"] == "vim"
        assert result["version"] == "9.1.0330-1.1"
        assert result["arch"] == "x86_64"
        assert result["vendor"] == "openSUSE"
        assert result["repository"] == "openSUSE-Tumbleweed-Oss"
        assert result["url"] == "https://www.vim.org"

    def test_parse_empty_output(self):
        result = _parse_zypper_info_output("")
        assert result is None

    def test_parse_output_missing_name(self):
        result = _parse_zypper_info_output("Version : 1.0\nArch : x86_64\n")
        assert result is None


class TestParseListUpdatesOutput:
    """Test _parse_list_updates_output."""

    def test_parse_updates(self):
        packages = _parse_list_updates_output(SAMPLE_LIST_UPDATES)
        assert len(packages) == 2
        assert packages[0]["package"] == "vim"
        assert packages[0]["current_version"] == "9.0.1000-1.1"
        assert packages[0]["new_version"] == "9.1.0330-1.1"
        assert packages[0]["arch"] == "x86_64"
        assert packages[1]["package"] == "python3"

    def test_parse_empty_output(self):
        packages = _parse_list_updates_output("")
        assert packages == []

    def test_parse_header_only(self):
        header = "S | Repository | Name | Current Version | Available Version | Arch\n"
        packages = _parse_list_updates_output(header)
        assert packages == []


class TestParseZypperPackagesOutput:
    """Test _parse_zypper_packages_output."""

    def test_parse_packages(self):
        names = _parse_zypper_packages_output(SAMPLE_ZYPPER_PACKAGES)
        assert "vim" in names
        assert "python3" in names

    def test_parse_empty_output(self):
        names = _parse_zypper_packages_output("")
        assert names == []


class TestGetOfficialPackageInfo:
    """Test get_official_package_info."""

    @pytest.mark.asyncio
    async def test_local_on_suse(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.check_command_exists", return_value=True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (0, SAMPLE_ZYPPER_INFO, "")
            result = await get_official_package_info("vim")
            assert result["source"] == "local"
            assert result["name"] == "vim"
            assert result["version"] == "9.1.0330-1.1"

    @pytest.mark.asyncio
    async def test_remote_when_not_on_suse(self, mock_httpx_response):
        mock_response = mock_httpx_response(
            status_code=200,
            json_data={
                "packages": [
                    {
                        "name": "vim",
                        "version": "9.1.0330-1.1",
                        "description": "Vi IMproved",
                        "project": "openSUSE:Factory",
                        "repository": "standard",
                        "arch": "x86_64",
                        "url": "https://www.vim.org",
                    }
                ]
            },
        )

        with (
            patch("suse_ops_server.zypper.IS_SUSE", False),
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await get_official_package_info("vim")
            assert result["source"] == "remote"
            assert result["name"] == "vim"

    @pytest.mark.asyncio
    async def test_remote_package_not_found(self, mock_httpx_response):
        mock_response = mock_httpx_response(
            status_code=200,
            json_data={"packages": []},
        )

        with (
            patch("suse_ops_server.zypper.IS_SUSE", False),
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await get_official_package_info("nonexistent")
            assert result["error"] is True
            assert result["type"] == "NotFound"

    @pytest.mark.asyncio
    async def test_remote_timeout(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", False),
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )
            result = await get_official_package_info("vim")
            assert result["error"] is True
            assert result["type"] == "TimeoutError"


class TestCheckUpdatesDryRun:
    """Test check_updates_dry_run."""

    @pytest.mark.asyncio
    async def test_check_updates_not_suse(self):
        with patch("suse_ops_server.zypper.IS_SUSE", False):
            result = await check_updates_dry_run()
            assert result["error"] is True
            assert result["type"] == "NotSupported"

    @pytest.mark.asyncio
    async def test_check_updates_success(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.IS_IMMUTABLE", False),
            patch("suse_ops_server.zypper.check_command_exists", return_value=True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (0, SAMPLE_LIST_UPDATES, "")
            result = await check_updates_dry_run()
            assert result["updates_available"] is True
            assert result["count"] == 2
            assert len(result["packages"]) == 2

    @pytest.mark.asyncio
    async def test_check_updates_none_available(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.IS_IMMUTABLE", False),
            patch("suse_ops_server.zypper.check_command_exists", return_value=True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (0, "S | Repository | Name | Current Version | Available Version | Arch\n", "")
            result = await check_updates_dry_run()
            assert result["updates_available"] is False
            assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_check_updates_immutable_raises(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.IS_IMMUTABLE", True),
        ):
            with pytest.raises(NotImplementedError):
                await check_updates_dry_run()


class TestVerifyPackageIntegrity:
    """Test verify_package_integrity."""

    @pytest.mark.asyncio
    async def test_not_suse(self):
        with patch("suse_ops_server.zypper.IS_SUSE", False):
            result = await verify_package_integrity("vim")
            assert result["error"] is True

    @pytest.mark.asyncio
    async def test_integrity_ok(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.check_command_exists", return_value=True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (0, "", "")
            result = await verify_package_integrity("vim")
            assert result["integrity_ok"] is True
            assert result["changed_count"] == 0

    @pytest.mark.asyncio
    async def test_integrity_modified_files(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.check_command_exists", return_value=True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (1, "S.5....T.  /usr/bin/vim\n", "")
            result = await verify_package_integrity("vim")
            assert result["integrity_ok"] is False
            assert result["changed_count"] == 1


class TestFindPackageOwner:
    """Test find_package_owner."""

    @pytest.mark.asyncio
    async def test_not_suse(self):
        with patch("suse_ops_server.zypper.IS_SUSE", False):
            result = await find_package_owner("/usr/bin/vim")
            assert result["error"] is True

    @pytest.mark.asyncio
    async def test_found(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (0, "vim-9.1.0330-1.1.x86_64\n", "")
            result = await find_package_owner("/usr/bin/vim")
            assert result["file"] == "/usr/bin/vim"
            assert "vim" in result["package"]

    @pytest.mark.asyncio
    async def test_not_found(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (1, "", "file is not owned by any package")
            result = await find_package_owner("/tmp/random")
            assert result["error"] is True


class TestListPackageFiles:
    """Test list_package_files."""

    @pytest.mark.asyncio
    async def test_not_suse(self):
        with patch("suse_ops_server.zypper.IS_SUSE", False):
            result = await list_package_files("vim")
            assert result["error"] is True

    @pytest.mark.asyncio
    async def test_success(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (0, "/usr/bin/vim\n/usr/share/vim/\n", "")
            result = await list_package_files("vim")
            assert result["package"] == "vim"
            assert result["file_count"] == 2
            assert "/usr/bin/vim" in result["files"]

    @pytest.mark.asyncio
    async def test_package_not_installed(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (1, "", "package not installed")
            result = await list_package_files("nonexistent")
            assert result["error"] is True


class TestSearchPackageFiles:
    """Test search_package_files."""

    @pytest.mark.asyncio
    async def test_not_suse(self):
        with patch("suse_ops_server.zypper.IS_SUSE", False):
            result = await search_package_files("/usr/bin/vim")
            assert result["error"] is True

    @pytest.mark.asyncio
    async def test_found(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (0, "vim-9.1.0330-1.1.x86_64\n", "")
            result = await search_package_files("/usr/bin/vim")
            assert len(result["matches"]) == 1
            assert result["matches"][0]["file"] == "/usr/bin/vim"

    @pytest.mark.asyncio
    async def test_not_found(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (1, "", "not owned")
            result = await search_package_files("/tmp/random")
            assert result["error"] is True


class TestListOrphanPackages:
    """Test list_orphan_packages."""

    @pytest.mark.asyncio
    async def test_not_suse(self):
        with patch("suse_ops_server.zypper.IS_SUSE", False):
            result = await list_orphan_packages()
            assert result["error"] is True

    @pytest.mark.asyncio
    async def test_has_orphans(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.check_command_exists", return_value=True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (0, SAMPLE_ZYPPER_PACKAGES, "")
            result = await list_orphan_packages()
            assert result["has_orphans"] is True
            assert result["orphan_count"] == 2

    @pytest.mark.asyncio
    async def test_no_orphans(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.check_command_exists", return_value=True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (0, "S | Name | Type | Version | Arch | Repository\n", "")
            result = await list_orphan_packages()
            assert result["has_orphans"] is False
            assert result["orphan_count"] == 0


class TestRemoveOrphans:
    """Test remove_orphans."""

    @pytest.mark.asyncio
    async def test_dry_run_no_orphans(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.check_command_exists", return_value=True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (0, "S | Name | Type | Version | Arch | Repository\n", "")
            result = await remove_orphans(dry_run=True)
            assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_dry_run_with_orphans(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.check_command_exists", return_value=True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (0, SAMPLE_ZYPPER_PACKAGES, "")
            result = await remove_orphans(dry_run=True)
            assert result["dry_run"] is True
            assert result["count"] == 2


class TestManageOrphans:
    """Test manage_orphans."""

    @pytest.mark.asyncio
    async def test_list_action(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.check_command_exists", return_value=True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (0, SAMPLE_ZYPPER_PACKAGES, "")
            result = await manage_orphans("list")
            assert "orphans" in result

    @pytest.mark.asyncio
    async def test_invalid_action(self):
        result = await manage_orphans("invalid")
        assert result["error"] is True

    @pytest.mark.asyncio
    async def test_remove_with_packages_dry_run(self):
        result = await manage_orphans("remove", packages=["vim"], dry_run=True)
        assert result["dry_run"] is True
        assert "vim" in result["would_remove"]


class TestRemovePackages:
    """Test remove_packages."""

    @pytest.mark.asyncio
    async def test_not_suse(self):
        with patch("suse_ops_server.zypper.IS_SUSE", False):
            result = await remove_packages(["vim"])
            assert result["error"] is True

    @pytest.mark.asyncio
    async def test_no_packages(self):
        with patch("suse_ops_server.zypper.IS_SUSE", True):
            result = await remove_packages([])
            assert result["error"] is True

    @pytest.mark.asyncio
    async def test_immutable_raises(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.IS_IMMUTABLE", True),
        ):
            with pytest.raises(NotImplementedError):
                await remove_packages(["vim"])

    @pytest.mark.asyncio
    async def test_success(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.IS_IMMUTABLE", False),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (0, "vim removed\n", "")
            result = await remove_packages(["vim"])
            assert result["count"] == 1
            assert "vim" in result["removed"]


class TestListExplicitPackages:
    """Test list_explicit_packages."""

    @pytest.mark.asyncio
    async def test_not_suse(self):
        with patch("suse_ops_server.zypper.IS_SUSE", False):
            result = await list_explicit_packages()
            assert result["error"] is True

    @pytest.mark.asyncio
    async def test_success(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.run_command") as mock_run,
        ):
            mock_run.return_value = (0, SAMPLE_ZYPPER_PACKAGES, "")
            result = await list_explicit_packages()
            assert result["package_count"] == 2
            assert "vim" in result["packages"]


class TestMarkFunctions:
    """Test mark_as_explicit and mark_as_dependency."""

    @pytest.mark.asyncio
    async def test_mark_as_explicit_not_supported(self):
        result = await mark_as_explicit("vim")
        assert result["error"] is True
        assert result["type"] == "NotSupported"

    @pytest.mark.asyncio
    async def test_mark_as_dependency_not_supported(self):
        result = await mark_as_dependency("vim")
        assert result["error"] is True
        assert result["type"] == "NotSupported"

    @pytest.mark.asyncio
    async def test_manage_install_reason_not_supported(self):
        result = await manage_install_reason("vim", "explicit")
        assert result["error"] is True
        assert result["type"] == "NotSupported"


class TestCheckDatabaseFreshness:
    """Test check_database_freshness."""

    @pytest.mark.asyncio
    async def test_not_suse(self):
        with patch("suse_ops_server.zypper.IS_SUSE", False):
            result = await check_database_freshness()
            assert result["error"] is True

    @pytest.mark.asyncio
    async def test_cache_dir_not_found(self):
        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("pathlib.Path.exists", return_value=False),
        ):
            result = await check_database_freshness()
            assert result["error"] is True
            assert result["type"] == "NotFound"

    @pytest.mark.asyncio
    async def test_fresh_database(self, tmp_path):
        import time
        # Create a fake cache structure
        repo_dir = tmp_path / "openSUSE-Tumbleweed-Oss"
        repo_dir.mkdir()
        repomd = repo_dir / "repomd.xml"
        repomd.write_text("<repomd/>")
        # Set mtime to now (fresh)
        now = time.time()
        import os
        os.utime(repomd, (now, now))

        with (
            patch("suse_ops_server.zypper.IS_SUSE", True),
            patch("suse_ops_server.zypper.ZYPP_CACHE_DIR", str(tmp_path)),
        ):
            result = await check_database_freshness()
            assert result["needs_sync"] is False
            assert result["database_count"] == 1
