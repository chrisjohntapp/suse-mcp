# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Tests for suse_ops_server.config module (zypper.conf, RPM macros, package locks).
"""

from unittest.mock import patch

import pytest

from suse_ops_server.config import (
    ZYPPER_CONF,
    RPM_MACROS,
    analyze_zypper_conf,
    analyze_rpm_macros,
    check_package_locks,
    _parse_zypper_locks,
)


SAMPLE_ZYPPER_CONF = """\
[main]
gpgcheck = 1

[solver]
onlyRequires = 0

[download]
max_concurrent_connections = 5
"""

SAMPLE_RPM_MACROS = """\
# RPM macros
%_build_arch    x86_64
%_topdir        %{getenv:HOME}/rpmbuild
%vendor         openSUSE
"""

SAMPLE_ZYPPER_LOCKS = """\
# | Name           | Type    | Repository
--+----------------+---------+------------
1 | kernel-default | package | (any)
2 | glibc          | package | (any)
"""


class TestAnalyzeZypperConf:
    """Test zypper.conf parsing."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.config.IS_SUSE", True)
    async def test_success(self, tmp_path):
        conf_file = tmp_path / "zypper.conf"
        conf_file.write_text(SAMPLE_ZYPPER_CONF)
        with patch("suse_ops_server.config.ZYPPER_CONF", str(conf_file)):
            result = await analyze_zypper_conf()
            assert result["config_path"] == str(conf_file)
            assert "main.gpgcheck" in result["options"]
            assert result["options"]["main.gpgcheck"] == "1"
            assert result["parallel_downloads"] == 5
            assert result["sig_level"] == "1"
            assert "raw_config" in result

    @pytest.mark.asyncio
    @patch("suse_ops_server.config.IS_SUSE", True)
    async def test_focus_options(self, tmp_path):
        conf_file = tmp_path / "zypper.conf"
        conf_file.write_text(SAMPLE_ZYPPER_CONF)
        with patch("suse_ops_server.config.ZYPPER_CONF", str(conf_file)):
            result = await analyze_zypper_conf(focus="options")
            assert "options" in result
            assert "raw_config" not in result

    @pytest.mark.asyncio
    @patch("suse_ops_server.config.IS_SUSE", True)
    async def test_no_parallel_downloads(self, tmp_path):
        conf_file = tmp_path / "zypper.conf"
        conf_file.write_text("[main]\ngpgcheck = 1\n")
        with patch("suse_ops_server.config.ZYPPER_CONF", str(conf_file)):
            result = await analyze_zypper_conf()
            assert result["parallel_downloads"] is None

    @pytest.mark.asyncio
    @patch("suse_ops_server.config.IS_SUSE", True)
    async def test_file_not_found(self):
        with patch("suse_ops_server.config.ZYPPER_CONF", "/nonexistent/zypper.conf"):
            result = await analyze_zypper_conf()
            assert result["error"] is True
            assert result["type"] == "NotFound"

    @pytest.mark.asyncio
    @patch("suse_ops_server.config.IS_SUSE", False)
    async def test_not_suse(self):
        result = await analyze_zypper_conf()
        assert result["error"] is True
        assert result["type"] == "NotSupported"


class TestAnalyzeRpmMacros:
    """Test RPM macros parsing."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.config.IS_SUSE", True)
    async def test_success(self, tmp_path):
        macros_file = tmp_path / "macros"
        macros_file.write_text(SAMPLE_RPM_MACROS)
        with patch("suse_ops_server.config.RPM_MACROS", str(macros_file)):
            result = await analyze_rpm_macros()
            assert result["config_path"] == str(macros_file)
            assert result["macros"]["%_build_arch"] == "x86_64"
            assert result["macros"]["%_topdir"] == "%{getenv:HOME}/rpmbuild"
            assert result["macros"]["%vendor"] == "openSUSE"
            assert result["build_arch"] == "x86_64"

    @pytest.mark.asyncio
    @patch("suse_ops_server.config.IS_SUSE", True)
    async def test_no_build_arch(self, tmp_path):
        macros_file = tmp_path / "macros"
        macros_file.write_text("%vendor openSUSE\n")
        with patch("suse_ops_server.config.RPM_MACROS", str(macros_file)):
            result = await analyze_rpm_macros()
            assert result["build_arch"] is None

    @pytest.mark.asyncio
    @patch("suse_ops_server.config.IS_SUSE", True)
    async def test_empty_file(self, tmp_path):
        macros_file = tmp_path / "macros"
        macros_file.write_text("# only comments\n")
        with patch("suse_ops_server.config.RPM_MACROS", str(macros_file)):
            result = await analyze_rpm_macros()
            assert result["macros"] == {}

    @pytest.mark.asyncio
    @patch("suse_ops_server.config.IS_SUSE", True)
    async def test_file_not_found(self):
        with patch("suse_ops_server.config.RPM_MACROS", "/nonexistent/macros"):
            result = await analyze_rpm_macros()
            assert result["error"] is True
            assert result["type"] == "NotFound"

    @pytest.mark.asyncio
    @patch("suse_ops_server.config.IS_SUSE", False)
    async def test_not_suse(self):
        result = await analyze_rpm_macros()
        assert result["error"] is True
        assert result["type"] == "NotSupported"


class TestCheckPackageLocks:
    """Test zypper package lock detection."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.config.IS_SUSE", True)
    async def test_has_locks(self):
        with patch("suse_ops_server.config.run_command") as mock_run:
            mock_run.return_value = (0, SAMPLE_ZYPPER_LOCKS, "")
            result = await check_package_locks()
            assert result["has_locks"] is True
            assert result["count"] == 2
            assert result["locks"][0]["name"] == "kernel-default"
            assert result["locks"][1]["name"] == "glibc"

    @pytest.mark.asyncio
    @patch("suse_ops_server.config.IS_SUSE", True)
    async def test_no_locks(self):
        empty_output = "# | Name | Type | Repository\n--+------+------+------------\n"
        with patch("suse_ops_server.config.run_command") as mock_run:
            mock_run.return_value = (0, empty_output, "")
            result = await check_package_locks()
            assert result["has_locks"] is False
            assert result["count"] == 0

    @pytest.mark.asyncio
    @patch("suse_ops_server.config.IS_SUSE", True)
    async def test_command_error(self):
        with patch("suse_ops_server.config.run_command") as mock_run:
            mock_run.return_value = (2, "", "zypper: command failed")
            result = await check_package_locks()
            assert result["error"] is True
            assert result["type"] == "CommandError"

    @pytest.mark.asyncio
    @patch("suse_ops_server.config.IS_SUSE", False)
    async def test_not_suse(self):
        result = await check_package_locks()
        assert result["error"] is True
        assert result["type"] == "NotSupported"


class TestParseZypperLocks:
    """Test _parse_zypper_locks helper."""

    def test_parse_locks(self):
        locks = _parse_zypper_locks(SAMPLE_ZYPPER_LOCKS)
        assert len(locks) == 2
        assert locks[0]["name"] == "kernel-default"
        assert locks[0]["type"] == "package"
        assert locks[1]["name"] == "glibc"

    def test_parse_empty(self):
        locks = _parse_zypper_locks("")
        assert locks == []

    def test_parse_header_only(self):
        output = "# | Name | Type | Repository\n--+------+------+------------\n"
        locks = _parse_zypper_locks(output)
        assert locks == []
