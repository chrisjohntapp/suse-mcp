# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Tests for suse_ops_server.utils module.
"""

import asyncio
from unittest.mock import MagicMock, mock_open, patch

import pytest

from suse_ops_server.utils import (
    IS_SUSE,
    SUSE_VARIANT,
    IS_IMMUTABLE,
    check_command_exists,
    create_error_response,
    get_suse_variant,
    is_immutable,
    is_suse_linux,
    run_command,
)


def _make_open(content: str):
    """Return a mock for builtins.open that returns the given string content."""
    return mock_open(read_data=content)


class TestPlatformDetection:
    """Test platform detection for all SUSE variants."""

    @pytest.mark.parametrize("os_id,expected_variant,expected_immutable", [
        ("opensuse-tumbleweed", "tumbleweed", False),
        ("opensuse-leap",       "leap",       False),
        ("opensuse-slowroll",   "slowroll",   False),
        ("sles",                "sles",       False),
        ("sled",                "sled",       False),
        ("opensuse-microos",    "microos",    True),
        ("opensuse-leap-micro", "leap-micro", True),
        ("sle-micro",           "sle-micro",  True),
    ])
    def test_all_suse_variants(self, os_id, expected_variant, expected_immutable):
        """is_suse_linux, get_suse_variant and is_immutable handle every variant."""
        content = f'ID={os_id}\nNAME="Test"\n'
        with patch("builtins.open", _make_open(content)):
            assert is_suse_linux() is True
            assert get_suse_variant() == expected_variant
            assert is_immutable() is expected_immutable

    def test_id_like_suse_fallback(self):
        """id_like=suse triggers detection even for an unknown ID."""
        content = 'ID=custom-suse-distro\nID_LIKE="suse"\n'
        with patch("builtins.open", _make_open(content)):
            assert is_suse_linux() is True

    def test_not_suse_ubuntu(self):
        """Non-SUSE os-release returns False."""
        content = 'ID=ubuntu\nID_LIKE=debian\n'
        with patch("builtins.open", _make_open(content)):
            assert is_suse_linux() is False
            assert get_suse_variant() is None
            assert is_immutable() is False

    def test_no_os_release_file(self):
        """Missing /etc/os-release returns False without raising."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            assert is_suse_linux() is False
            assert get_suse_variant() is None
            assert is_immutable() is False

    def test_module_constants_are_bool(self):
        """Module-level constants have the correct types."""
        assert isinstance(IS_SUSE, bool)
        assert isinstance(IS_IMMUTABLE, bool)
        assert SUSE_VARIANT is None or isinstance(SUSE_VARIANT, str)


class TestCommandExecution:
    """Test async command execution."""

    @pytest.mark.asyncio
    async def test_run_command_success(self, mock_subprocess_success):
        """Successful command returns exit 0 and captured stdout."""
        with patch("asyncio.create_subprocess_exec", new=mock_subprocess_success):
            exit_code, stdout, stderr = await run_command(
                ["echo", "hello"], skip_sudo_check=True
            )
        assert exit_code == 0
        assert stdout == "success output"
        assert stderr == ""

    @pytest.mark.asyncio
    async def test_run_command_failure_with_check(self, mock_subprocess_failure):
        """check=True raises RuntimeError on non-zero exit."""
        with patch("asyncio.create_subprocess_exec", new=mock_subprocess_failure):
            with pytest.raises(RuntimeError, match="Command failed with exit code 1"):
                await run_command(["false"], check=True, skip_sudo_check=True)

    @pytest.mark.asyncio
    async def test_run_command_failure_without_check(self, mock_subprocess_failure):
        """check=False returns the error without raising."""
        with patch("asyncio.create_subprocess_exec", new=mock_subprocess_failure):
            exit_code, stdout, stderr = await run_command(
                ["false"], check=False, skip_sudo_check=True
            )
        assert exit_code == 1
        assert stdout == ""
        assert stderr == "error output"

    @pytest.mark.asyncio
    async def test_run_command_timeout(self):
        """Slow command raises asyncio.TimeoutError."""
        async def _slow_communicate():
            await asyncio.sleep(10)
            return (b"", b"")

        mock_process = MagicMock()
        mock_process.communicate = _slow_communicate

        async def _create_slow_subprocess(*args, **kwargs):
            return mock_process

        with patch("asyncio.create_subprocess_exec", new=_create_slow_subprocess):
            with pytest.raises(asyncio.TimeoutError):
                await run_command(["sleep", "10"], timeout=0.1, skip_sudo_check=True)

    @pytest.mark.asyncio
    async def test_run_command_sudo_password_not_cached(self):
        """Uncached sudo password returns error without running the real command."""
        async def _mock_communicate():
            return (b"", b"sudo: a password is required")

        mock_test_process = MagicMock()
        mock_test_process.returncode = 1
        mock_test_process.communicate = _mock_communicate

        call_count = 0

        async def _create_subprocess(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_test_process

        with patch("asyncio.create_subprocess_exec", new=_create_subprocess):
            exit_code, stdout, stderr = await run_command(["sudo", "zypper", "install", "vim"])

        assert exit_code == 1
        assert "Sudo password required" in stderr
        assert call_count == 1  # only the sudo -n true check, not the real command


class TestErrorHandling:
    """Test error response creation and formatting."""

    def test_create_error_response_basic(self):
        """Basic error response has required fields and no wiki suggestions."""
        response = create_error_response(
            "TestError", "Something went wrong", suggest_wiki_search=False
        )
        assert response["error"] is True
        assert response["type"] == "TestError"
        assert response["message"] == "Something went wrong"
        assert "wiki_suggestions" not in response

    def test_create_error_response_with_details(self):
        """details field is included when provided."""
        response = create_error_response(
            "TestError",
            "Something went wrong",
            details="More information here",
            suggest_wiki_search=False,
        )
        assert response["details"] == "More information here"

    def test_create_error_response_with_wiki_suggestions(self):
        """Known error type populates wiki_suggestions and help_text."""
        response = create_error_response(
            "NotFound", "Package not found", suggest_wiki_search=True
        )
        assert "wiki_suggestions" in response
        assert isinstance(response["wiki_suggestions"], list)
        assert len(response["wiki_suggestions"]) > 0
        assert "help_text" in response
        assert "search_opensuse_wiki" in response["help_text"]

    def test_wiki_suggestions_for_network_error(self):
        """Network-related error message surfaces network/mirror topics."""
        response = create_error_response(
            "NetworkError",
            "Failed to connect to repository mirror",
            suggest_wiki_search=True,
        )
        suggestions = response.get("wiki_suggestions", [])
        assert any("network" in s.lower() or "mirror" in s.lower() or "repositor" in s.lower()
                   for s in suggestions)

    def test_wiki_suggestions_for_zypper_error(self):
        """zypper keyword in message surfaces zypper-related topics."""
        response = create_error_response(
            "CommandError",
            "zypper failed to refresh repositories",
            suggest_wiki_search=True,
        )
        suggestions = response.get("wiki_suggestions", [])
        assert any("zypper" in s.lower() for s in suggestions)

    def test_wiki_suggestions_max_five(self):
        """At most 5 wiki suggestions are returned."""
        response = create_error_response(
            "NotFound",
            "zypper package dependency mirror network repository obs",
            suggest_wiki_search=True,
        )
        assert len(response.get("wiki_suggestions", [])) <= 5


class TestCommandExistence:
    """Test command existence checking."""

    def test_check_command_exists_found(self):
        with patch("os.system", return_value=0):
            assert check_command_exists("zypper") is True

    def test_check_command_exists_not_found(self):
        with patch("os.system", return_value=1):
            assert check_command_exists("nonexistent_command_xyz") is False

    def test_check_command_exists_exception(self):
        with patch("shutil.which", side_effect=Exception("Test error")):
            assert check_command_exists("test") is False
