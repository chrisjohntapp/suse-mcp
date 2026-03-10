# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Tests for suse_ops_server.system module.
"""

from unittest.mock import AsyncMock, patch, mock_open

import pytest

from suse_ops_server.system import (
    get_system_info,
    check_disk_space,
    get_package_cache_stats,
    check_failed_services,
    get_boot_logs,
    analyze_storage,
    diagnose_system,
)


class TestSystemInfo:
    """Test system information retrieval."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.system.IS_SUSE", True)
    @patch("suse_ops_server.system.SUSE_VARIANT", "opensuse-tumbleweed")
    @patch("suse_ops_server.system.IS_IMMUTABLE", False)
    async def test_get_system_info_success(self):
        async def mock_run_command(cmd, **kwargs):
            if "uname" in cmd and "-r" in cmd:
                return (0, "6.7.1-1-default\n", "")
            elif "uname" in cmd and "-m" in cmd:
                return (0, "x86_64\n", "")
            elif "hostname" in cmd:
                return (0, "susebox\n", "")
            elif "uptime" in cmd:
                return (0, "up 2 days, 3 hours\n", "")
            return (0, "", "")

        meminfo_content = """MemTotal:       16384000 kB
MemFree:         8192000 kB
MemAvailable:   12288000 kB
"""

        with patch("suse_ops_server.system.run_command", mock_run_command), \
             patch("builtins.open", mock_open(read_data=meminfo_content)):
            result = await get_system_info()

            assert result["kernel"] == "6.7.1-1-default"
            assert result["architecture"] == "x86_64"
            assert result["hostname"] == "susebox"
            assert "uptime" in result
            assert result["memory_total_mb"] > 0
            assert result["is_suse_linux"] is True
            assert result["suse_variant"] == "opensuse-tumbleweed"
            assert result["is_immutable"] is False

    @pytest.mark.asyncio
    @patch("suse_ops_server.system.IS_SUSE", True)
    @patch("suse_ops_server.system.SUSE_VARIANT", "opensuse-microos")
    @patch("suse_ops_server.system.IS_IMMUTABLE", True)
    async def test_get_system_info_immutable(self):
        async def mock_run_command(cmd, **kwargs):
            if "uname" in cmd and "-r" in cmd:
                return (0, "6.7.1-1-default\n", "")
            return (1, "", "error")

        with patch("suse_ops_server.system.run_command", mock_run_command):
            result = await get_system_info()

            assert result["kernel"] == "6.7.1-1-default"
            assert result["is_suse_linux"] is True
            assert result["suse_variant"] == "opensuse-microos"
            assert result["is_immutable"] is True

    @pytest.mark.asyncio
    async def test_get_system_info_partial_failure(self):
        async def mock_run_command(cmd, **kwargs):
            if "uname" in cmd and "-r" in cmd:
                return (0, "6.7.1-1-default\n", "")
            return (1, "", "error")

        with patch("suse_ops_server.system.run_command", mock_run_command):
            result = await get_system_info()

            assert "kernel" in result
            assert result["kernel"] == "6.7.1-1-default"


class TestDiskSpace:
    """Test disk space checking."""

    @pytest.mark.asyncio
    async def test_check_disk_space_success(self):
        df_output = """Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1       100G   60G   40G  60% /
"""
        async def mock_run_command(cmd, **kwargs):
            return (0, df_output, "")

        with patch("suse_ops_server.system.run_command", mock_run_command):
            result = await check_disk_space()

            assert "disk_usage" in result
            assert "/" in result["disk_usage"]
            assert result["disk_usage"]["/"]["size"] == "100G"
            assert result["disk_usage"]["/"]["use_percent"] == "60%"

    @pytest.mark.asyncio
    async def test_check_disk_space_critical(self):
        df_output = """Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1       100G   95G    5G  95% /
"""
        async def mock_run_command(cmd, **kwargs):
            return (0, df_output, "")

        with patch("suse_ops_server.system.run_command", mock_run_command):
            result = await check_disk_space()

            assert "/" in result["disk_usage"]
            assert "warning" in result["disk_usage"]["/"]
            assert "Critical" in result["disk_usage"]["/"]["warning"]

    @pytest.mark.asyncio
    async def test_check_disk_space_low(self):
        df_output = """Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1       100G   85G   15G  85% /
"""
        async def mock_run_command(cmd, **kwargs):
            return (0, df_output, "")

        with patch("suse_ops_server.system.run_command", mock_run_command):
            result = await check_disk_space()

            assert "/" in result["disk_usage"]
            assert "warning" in result["disk_usage"]["/"]
            assert "Low" in result["disk_usage"]["/"]["warning"]


class TestPackageCache:
    """Test zypp package cache statistics."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.system.IS_SUSE", True)
    async def test_get_package_cache_stats_success(self, tmp_path):
        cache_dir = tmp_path / "packages"
        cache_dir.mkdir()

        (cache_dir / "vim-9.1.0330-1.1.x86_64.rpm").write_bytes(b"0" * 1024 * 1024)
        (cache_dir / "kernel-default-6.7.1-1.1.x86_64.rpm").write_bytes(b"0" * 2 * 1024 * 1024)

        with patch("suse_ops_server.system.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.glob.return_value = list(cache_dir.glob("**/*.rpm"))

            result = await get_package_cache_stats()

            assert result["package_count"] == 2
            assert result["total_size_mb"] > 0

    @pytest.mark.asyncio
    @patch("suse_ops_server.system.IS_SUSE", False)
    async def test_get_package_cache_stats_not_suse(self):
        result = await get_package_cache_stats()
        assert result["error"] is True
        assert result["type"] == "NotSupported"

    @pytest.mark.asyncio
    @patch("suse_ops_server.system.IS_SUSE", True)
    async def test_get_package_cache_stats_not_found(self):
        with patch("suse_ops_server.system.Path") as mock_path:
            mock_path.return_value.exists.return_value = False

            result = await get_package_cache_stats()
            assert result["error"] is True
            assert result["type"] == "NotFound"


class TestFailedServices:
    """Test failed services detection."""

    @pytest.mark.asyncio
    async def test_check_failed_services_success(self):
        output = """  UNIT                    LOAD   ACTIVE SUB    DESCRIPTION
foo.service             loaded failed failed Foo Service

1 loaded units listed.
"""
        async def mock_run_command(cmd, **kwargs):
            return (0, output, "")

        with patch("suse_ops_server.system.check_command_exists", return_value=True), \
             patch("suse_ops_server.system.run_command", mock_run_command):
            result = await check_failed_services()

            assert result["failed_count"] == 1
            assert result["all_ok"] is False

    @pytest.mark.asyncio
    async def test_check_failed_services_none(self):
        output = """0 loaded units listed.\n"""
        async def mock_run_command(cmd, **kwargs):
            return (0, output, "")

        with patch("suse_ops_server.system.check_command_exists", return_value=True), \
             patch("suse_ops_server.system.run_command", mock_run_command):
            result = await check_failed_services()

            assert result["failed_count"] == 0
            assert result["all_ok"] is True

    @pytest.mark.asyncio
    async def test_check_failed_services_no_systemctl(self):
        with patch("suse_ops_server.system.check_command_exists", return_value=False):
            result = await check_failed_services()
            assert result["error"] is True
            assert result["type"] == "NotSupported"


class TestBootLogs:
    """Test boot log retrieval."""

    @pytest.mark.asyncio
    async def test_get_boot_logs_success(self):
        log_output = """Nov 10 10:00:00 susebox kernel: Linux version 6.7.1
Nov 10 10:00:01 susebox systemd[1]: Starting system...
Nov 10 10:00:02 susebox systemd[1]: System started successfully
"""
        async def mock_run_command(cmd, **kwargs):
            return (0, log_output, "")

        with patch("suse_ops_server.system.check_command_exists", return_value=True), \
             patch("suse_ops_server.system.run_command", mock_run_command):
            result = await get_boot_logs(lines=100)

            assert result["line_count"] == 3
            assert len(result["logs"]) == 3
            assert "kernel" in result["logs"][0]

    @pytest.mark.asyncio
    async def test_get_boot_logs_custom_lines(self):
        log_output = "\n".join([f"Line {i}" for i in range(50)])

        async def mock_run_command(cmd, **kwargs):
            assert "-n" in cmd
            assert "50" in cmd
            return (0, log_output, "")

        with patch("suse_ops_server.system.check_command_exists", return_value=True), \
             patch("suse_ops_server.system.run_command", mock_run_command):
            result = await get_boot_logs(lines=50)

            assert result["line_count"] == 50

    @pytest.mark.asyncio
    async def test_get_boot_logs_failure(self):
        async def mock_run_command(cmd, **kwargs):
            return (1, "", "journalctl error")

        with patch("suse_ops_server.system.check_command_exists", return_value=True), \
             patch("suse_ops_server.system.run_command", mock_run_command):
            result = await get_boot_logs()

            assert "error" in result
            assert result["type"] == "CommandError"

    @pytest.mark.asyncio
    async def test_get_boot_logs_no_journalctl(self):
        with patch("suse_ops_server.system.check_command_exists", return_value=False):
            result = await get_boot_logs()
            assert result["error"] is True
            assert result["type"] == "NotSupported"


class TestAnalyzeStorage:
    """Test unified storage analysis."""

    @pytest.mark.asyncio
    async def test_analyze_storage_disk_usage(self):
        df_output = """Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1       100G   60G   40G  60% /
"""
        async def mock_run_command(cmd, **kwargs):
            return (0, df_output, "")

        with patch("suse_ops_server.system.run_command", mock_run_command):
            result = await analyze_storage("disk_usage")
            assert "disk_usage" in result

    @pytest.mark.asyncio
    @patch("suse_ops_server.system.IS_SUSE", True)
    async def test_analyze_storage_cache_stats(self, tmp_path):
        cache_dir = tmp_path / "packages"
        cache_dir.mkdir()
        (cache_dir / "test-1.0-1.x86_64.rpm").write_bytes(b"0" * 1024)

        with patch("suse_ops_server.system.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.glob.return_value = list(cache_dir.glob("**/*.rpm"))

            result = await analyze_storage("cache_stats")
            assert "package_count" in result

    @pytest.mark.asyncio
    async def test_analyze_storage_invalid(self):
        result = await analyze_storage("invalid")
        assert result["error"] is True
        assert result["type"] == "InvalidAction"


class TestDiagnoseSystem:
    """Test unified system diagnostics."""

    @pytest.mark.asyncio
    async def test_diagnose_system_failed_services(self):
        output = "0 loaded units listed.\n"
        async def mock_run_command(cmd, **kwargs):
            return (0, output, "")

        with patch("suse_ops_server.system.check_command_exists", return_value=True), \
             patch("suse_ops_server.system.run_command", mock_run_command):
            result = await diagnose_system(action="failed_services")
            assert "failed_count" in result

    @pytest.mark.asyncio
    async def test_diagnose_system_boot_logs(self):
        log_output = "Line 1\nLine 2\n"
        async def mock_run_command(cmd, **kwargs):
            return (0, log_output, "")

        with patch("suse_ops_server.system.check_command_exists", return_value=True), \
             patch("suse_ops_server.system.run_command", mock_run_command):
            result = await diagnose_system(action="boot_logs", lines=50)
            assert "logs" in result

    @pytest.mark.asyncio
    async def test_diagnose_system_invalid_action(self):
        result = await diagnose_system(action="invalid_action")
        assert result["error"] is True
        assert result["type"] == "InvalidAction"
