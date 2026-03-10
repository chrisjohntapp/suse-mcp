# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Utility functions for SUSE Linux MCP Server.
Provides platform detection, subprocess execution, and error handling.
"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any

# Configure logging to stderr (STDIO server requirement)
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

# All known SUSE Linux os-release IDs
SUSE_IDS = frozenset([
    "sles",
    "sled",
    "sle-micro",
    "opensuse-tumbleweed",
    "opensuse-leap",
    "opensuse-leap-micro",
    "opensuse-microos",
    "opensuse-slowroll",
])

# Immutable variants use transactional-update instead of direct zypper installs
IMMUTABLE_IDS = frozenset([
    "sle-micro",
    "opensuse-leap-micro",
    "opensuse-microos",
])

# Map os-release ID to a short variant name
_VARIANT_SHORT: Dict[str, str] = {
    "sles": "sles",
    "sled": "sled",
    "sle-micro": "sle-micro",
    "opensuse-tumbleweed": "tumbleweed",
    "opensuse-leap": "leap",
    "opensuse-leap-micro": "leap-micro",
    "opensuse-microos": "microos",
    "opensuse-slowroll": "slowroll",
}


def _parse_os_release() -> Dict[str, str]:
    """Parse /etc/os-release into a dict of key=value pairs."""
    result: Dict[str, str] = {}
    try:
        with open("/etc/os-release") as f:
            for line in f.read().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                result[key] = value.strip('"')
    except FileNotFoundError:
        pass
    return result


def is_suse_linux() -> bool:
    """
    Detect if the current system is a SUSE Linux variant.

    Checks /etc/os-release for:
    1. ID matching a known SUSE variant
    2. ID_LIKE containing "suse" as a fallback

    Returns:
        bool: True if running on any SUSE Linux variant, False otherwise
    """
    fields = _parse_os_release()
    if fields.get("ID") in SUSE_IDS:
        logger.info("Detected SUSE Linux via ID=%s", fields["ID"])
        return True
    if "suse" in fields.get("ID_LIKE", "").lower():
        logger.info("Detected SUSE Linux via ID_LIKE")
        return True
    logger.info("Not running on SUSE Linux")
    return False


def get_suse_variant() -> Optional[str]:
    """
    Return the specific SUSE variant name for the current system.

    Returns:
        str: Short variant name (e.g. "tumbleweed", "leap", "sles", "microos"),
             or None if not running on SUSE Linux.
    """
    fields = _parse_os_release()
    os_id = fields.get("ID", "")
    if os_id in SUSE_IDS:
        return _VARIANT_SHORT[os_id]
    if "suse" in fields.get("ID_LIKE", "").lower():
        return os_id or None
    return None


def is_immutable() -> bool:
    """
    Return True if the current SUSE variant uses an immutable root filesystem.

    Immutable variants (MicroOS, Leap Micro, SLE Micro) require
    transactional-update for mutating package operations.

    Returns:
        bool: True for immutable variants, False otherwise.
    """
    fields = _parse_os_release()
    return fields.get("ID") in IMMUTABLE_IDS


# Module-level constants — computed once at import time
IS_SUSE: bool = is_suse_linux()
SUSE_VARIANT: Optional[str] = get_suse_variant()
IS_IMMUTABLE: bool = is_immutable()


async def run_command(
    cmd: list[str],
    timeout: int = 10,
    check: bool = True,
    skip_sudo_check: bool = False
) -> tuple[int, str, str]:
    """
    Execute a command asynchronously with timeout protection.

    Args:
        cmd: Command and arguments as list
        timeout: Timeout in seconds (default: 10)
        check: If True, raise exception on non-zero exit code
        skip_sudo_check: If True, skip the early sudo password check (for testing)

    Returns:
        Tuple of (exit_code, stdout, stderr)

    Raises:
        asyncio.TimeoutError: If command exceeds timeout
        RuntimeError: If check=True and command fails
    """
    logger.debug("Executing command: %s", ' '.join(cmd))

    is_sudo_command = cmd and cmd[0] == "sudo"
    if is_sudo_command and not skip_sudo_check:
        test_process = await asyncio.create_subprocess_exec(
            "sudo", "-n", "true",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await test_process.communicate()
        if test_process.returncode != 0:
            logger.warning("Sudo password is required but not cached.")
            return (
                1,
                "",
                "Sudo password required. Please configure passwordless sudo for zypper, "
                "or run the installation command manually in your terminal."
            )

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE if is_sudo_command else None
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )

        exit_code = process.returncode
        stdout_str = stdout.decode('utf-8', errors='replace') if stdout else ""
        stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ""

        logger.debug("Command exit code: %d", exit_code)

        if check and exit_code != 0:
            raise RuntimeError(
                f"Command failed with exit code {exit_code}: {stderr_str}"
            )

        return exit_code, stdout_str, stderr_str

    except asyncio.TimeoutError:
        logger.error("Command timed out after %ds: %s", timeout, ' '.join(cmd))
        raise
    except Exception as e:
        logger.error("Command execution failed: %s", e)
        raise


def create_error_response(
    error_type: str,
    message: str,
    details: Optional[str] = None,
    suggest_wiki_search: bool = True
) -> Dict[str, Any]:
    """
    Create a structured error response with openSUSE Wiki suggestions.

    Args:
        error_type: Type of error (e.g., "NetworkError", "NotFound")
        message: Human-readable error message
        details: Optional additional details
        suggest_wiki_search: Whether to suggest related Wiki searches (default: True)

    Returns:
        Structured error dict with Wiki suggestions
    """
    response: Dict[str, Any] = {
        "error": True,
        "type": error_type,
        "message": message
    }

    if details:
        response["details"] = details

    if suggest_wiki_search:
        wiki_suggestions = _get_wiki_suggestions_for_error(error_type, message)
        if wiki_suggestions:
            response["wiki_suggestions"] = wiki_suggestions
            response["help_text"] = (
                "Search the openSUSE Wiki for these topics to find solutions. "
                "Use the search_opensuse_wiki tool with these keywords."
            )

    logger.error("%s: %s", error_type, message)

    return response


def _get_wiki_suggestions_for_error(error_type: str, message: str) -> list[str]:
    """
    Generate relevant openSUSE Wiki search suggestions based on error type.

    Args:
        error_type: Type of error
        message: Error message

    Returns:
        List of suggested Wiki search terms
    """
    suggestions = []
    message_lower = message.lower()

    error_wiki_map = {
        "NotFound": ["Package management", "OBS"],
        "TimeoutError": ["Network configuration", "Repository management"],
        "HTTPError": ["Network configuration", "Proxy"],
        "CommandNotFound": ["Zypper", "System maintenance"],
        "NotSupported": ["Installation guide", "System requirements"],
        "RateLimitError": ["OBS", "Repository management"],
    }

    if error_type in error_wiki_map:
        suggestions.extend(error_wiki_map[error_type])

    keyword_map = {
        "zypper": ["Zypper", "Zypper usage"],
        "package": ["Package management", "Repositories"],
        "dependency": ["Dependency", "Package management"],
        "repository": ["Repository management", "Zypper"],
        "mirror": ["Repository management", "Mirrors"],
        "network": ["Network configuration", "Systemd-networkd"],
        "update": ["System maintenance", "Zypper#Updating packages"],
        "gpg": ["Package signing", "GnuPG"],
        "disk": ["File systems", "Partitioning"],
        "boot": ["Boot process", "systemd-boot"],
        "kernel": ["Kernel", "Kernel modules"],
        "driver": ["Kernel modules", "Hardware"],
        "graphics": ["Hardware", "NVIDIA", "AMD"],
        "obs": ["OBS", "Open Build Service"],
        "pattern": ["Patterns", "Zypper"],
        "transactional": ["Transactional updates", "MicroOS"],
    }

    for keyword, topics in keyword_map.items():
        if keyword in message_lower:
            suggestions.extend(topics)

    seen: set[str] = set()
    unique_suggestions = []
    for suggestion in suggestions:
        if suggestion not in seen:
            seen.add(suggestion)
            unique_suggestions.append(suggestion)

    return unique_suggestions[:5]


def check_command_exists(command: str) -> bool:
    """
    Check if a command exists in the system PATH.

    Args:
        command: Command name to check

    Returns:
        bool: True if command exists, False otherwise
    """
    try:
        result = os.system(f"which {command} > /dev/null 2>&1")
        return result == 0
    except Exception:
        return False
