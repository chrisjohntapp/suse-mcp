# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Pytest configuration and shared fixtures for suse-ops-server tests.
"""

import asyncio
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.fixture
def mock_os_release_tumbleweed(tmp_path: Path) -> Path:
    """Create a temporary /etc/os-release file for openSUSE Tumbleweed."""
    os_release = tmp_path / "os-release"
    os_release.write_text(
        'NAME="openSUSE Tumbleweed"\n'
        'ID=opensuse-tumbleweed\n'
        'ID_LIKE="opensuse suse"\n'
        'PRETTY_NAME="openSUSE Tumbleweed"\n'
    )
    return os_release


@pytest.fixture
def mock_os_release_leap(tmp_path: Path) -> Path:
    """Create a temporary /etc/os-release file for openSUSE Leap."""
    os_release = tmp_path / "os-release"
    os_release.write_text(
        'NAME="openSUSE Leap"\n'
        'VERSION="15.6"\n'
        'ID=opensuse-leap\n'
        'ID_LIKE="opensuse suse"\n'
        'PRETTY_NAME="openSUSE Leap 15.6"\n'
    )
    return os_release


@pytest.fixture
def mock_os_release_microos(tmp_path: Path) -> Path:
    """Create a temporary /etc/os-release file for openSUSE MicroOS (immutable)."""
    os_release = tmp_path / "os-release"
    os_release.write_text(
        'NAME="openSUSE MicroOS"\n'
        'ID=opensuse-microos\n'
        'ID_LIKE="opensuse suse"\n'
        'PRETTY_NAME="openSUSE MicroOS"\n'
    )
    return os_release


@pytest.fixture
def mock_os_release_sles(tmp_path: Path) -> Path:
    """Create a temporary /etc/os-release file for SUSE Linux Enterprise Server."""
    os_release = tmp_path / "os-release"
    os_release.write_text(
        'NAME="SLES"\n'
        'VERSION="15-SP6"\n'
        'ID=sles\n'
        'ID_LIKE=suse\n'
        'PRETTY_NAME="SUSE Linux Enterprise Server 15 SP6"\n'
    )
    return os_release


@pytest.fixture
def mock_os_release_ubuntu(tmp_path: Path) -> Path:
    """Create a temporary /etc/os-release file for Ubuntu (non-SUSE)."""
    os_release = tmp_path / "os-release"
    os_release.write_text(
        'NAME="Ubuntu"\n'
        'VERSION="22.04 LTS (Jammy Jellyfish)"\n'
        'ID=ubuntu\n'
        'ID_LIKE=debian\n'
    )
    return os_release


@pytest.fixture
def mock_subprocess_success():
    """Mock successful subprocess execution."""
    async def _mock_communicate():
        return (b"success output", b"")

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate = _mock_communicate

    async def _create_subprocess(*args, **kwargs):
        return mock_process

    return _create_subprocess


@pytest.fixture
def mock_subprocess_failure():
    """Mock failed subprocess execution."""
    async def _mock_communicate():
        return (b"", b"error output")

    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.communicate = _mock_communicate

    async def _create_subprocess(*args, **kwargs):
        return mock_process

    return _create_subprocess


@pytest.fixture
async def mock_httpx_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide a mock httpx AsyncClient for testing HTTP requests."""
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def mock_httpx_response():
    """Create a mock HTTP response factory."""
    def _create_response(
        status_code: int = 200,
        json_data: dict = None,
        text_data: str = None,
        headers: dict = None
    ) -> MagicMock:
        """Create a mock HTTP response with specified attributes."""
        response = MagicMock()
        response.status_code = status_code
        response.headers = headers or {}

        if json_data is not None:
            response.json = MagicMock(return_value=json_data)

        if text_data is not None:
            response.text = text_data

        response.raise_for_status = MagicMock()
        if status_code >= 400:
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=MagicMock(),
                response=response
            )

        return response

    return _create_response


@pytest.fixture
def sample_zypper_info():
    """Sample zypper info output for testing."""
    return """\
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
