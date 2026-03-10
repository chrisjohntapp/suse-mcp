# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""Unified zypper pattern management tool."""

from typing import Literal, Optional
from .utils import run_command, create_error_response, IS_SUSE


async def manage_patterns(
    action: Literal["list_patterns", "pattern_info"],
    pattern_name: Optional[str] = None
) -> dict:
    """Manage zypper patterns."""
    if not IS_SUSE:
        return create_error_response("NotSupported", "This feature is only available on SUSE Linux")
    if action == "list_patterns":
        return await _list_patterns()
    elif action == "pattern_info":
        if not pattern_name:
            return create_error_response("InvalidParameter", "pattern_name required")
        return await _get_pattern_info(pattern_name)
    else:
        return create_error_response(
            "InvalidAction",
            f"Unknown action: {action}. Use 'list_patterns' or 'pattern_info'",
        )


async def _list_patterns() -> dict:
    """List available zypper patterns."""
    exit_code, stdout, stderr = await run_command(
        ["zypper", "--no-refresh", "--non-interactive", "patterns"],
        timeout=30,
        check=False,
    )
    if exit_code not in (0, 100):
        return create_error_response("CommandError", f"Failed to list patterns: {stderr}")

    patterns = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("S |") or line.startswith("--") or "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4:
            patterns.append({
                "installed": parts[0] == "i",
                "name": parts[1],
                "version": parts[2],
                "repository": parts[3],
                "description": parts[4] if len(parts) > 4 else "",
            })

    return {
        "action": "list_patterns",
        "total_patterns": len(patterns),
        "patterns": patterns,
    }


async def _get_pattern_info(pattern_name: str) -> dict:
    """Get info for a specific zypper pattern."""
    exit_code, stdout, stderr = await run_command(
        ["zypper", "--no-refresh", "--non-interactive", "pattern-info", pattern_name],
        timeout=15,
        check=False,
    )
    if exit_code not in (0, 100):
        return create_error_response("CommandError", f"Failed to get pattern info: {stderr}")

    info: dict = {"name": pattern_name}
    for line in stdout.splitlines():
        kv = line.split(":", 1)
        if len(kv) == 2:
            key = kv[0].strip().lower().replace(" ", "_")
            value = kv[1].strip()
            info[key] = value

    return {
        "action": "pattern_info",
        "pattern": info,
    }


__all__ = ["manage_patterns"]
