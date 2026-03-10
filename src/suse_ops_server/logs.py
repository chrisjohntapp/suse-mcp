# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Zypp history log parsing module.
Parses /var/log/zypp/history for troubleshooting and auditing.
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from .utils import IS_SUSE, create_error_response

logger = logging.getLogger(__name__)

ZYPP_HISTORY = "/var/log/zypp/history"


def parse_log_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single pipe-delimited zypp history line.

    Format: timestamp|action|name|version|arch|reqby|repo|checksum

    Args:
        line: Log line to parse

    Returns:
        Dict with parsed data or None if not a transaction line
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    parts = line.split("|")
    if len(parts) < 2:
        return None

    timestamp = parts[0].strip()
    action = parts[1].strip() if len(parts) > 1 else ""
    name = parts[2].strip() if len(parts) > 2 else ""
    version = parts[3].strip() if len(parts) > 3 else ""
    arch = parts[4].strip() if len(parts) > 4 else ""
    reqby = parts[5].strip() if len(parts) > 5 else ""
    repo = parts[6].strip() if len(parts) > 6 else ""

    if not timestamp or not action:
        return None

    return {
        "timestamp": timestamp,
        "action": action,
        "package": name,
        "version": version,
        "arch": arch,
        "reqby": reqby,
        "repo": repo,
        "raw_line": line,
    }


async def get_transaction_history(limit: int = 50, action_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Read zypp history and return recent transactions.

    Args:
        limit: Maximum number of transactions to return
        action_filter: Filter by action (install, remove, update, etc.)

    Returns:
        Dict with transaction history
    """
    if not IS_SUSE:
        return create_error_response("NotSupported", "This feature is only available on SUSE Linux")

    log_path = Path(ZYPP_HISTORY)
    if not log_path.exists():
        return create_error_response("NotFound", f"Zypp history not found at {ZYPP_HISTORY}")

    try:
        transactions = []
        with open(log_path, "r") as f:
            lines = f.readlines()

        for line in reversed(lines):
            if len(transactions) >= limit:
                break
            parsed = parse_log_line(line)
            if parsed is None:
                continue
            if action_filter and parsed["action"].lower() != action_filter.lower():
                continue
            transactions.append(parsed)

        return {
            "count": len(transactions),
            "transactions": transactions,
        }

    except Exception as e:
        logger.error("Failed to read zypp history: %s", e)
        return create_error_response("LogParseError", f"Failed to read transaction history: {str(e)}")


async def find_when_installed(package_name: str) -> Dict[str, Any]:
    """
    Find first install entry for a package.

    Args:
        package_name: Package name to search for

    Returns:
        Dict with installation date and history
    """
    if not IS_SUSE:
        return create_error_response("NotSupported", "This feature is only available on SUSE Linux")

    log_path = Path(ZYPP_HISTORY)
    if not log_path.exists():
        return create_error_response("NotFound", f"Zypp history not found at {ZYPP_HISTORY}")

    try:
        first_install = None
        updates = []
        removals = []

        with open(log_path, "r") as f:
            for line in f:
                parsed = parse_log_line(line)
                if parsed is None or parsed["package"] != package_name:
                    continue
                action = parsed["action"].lower()
                if action == "install":
                    if first_install is None:
                        first_install = parsed
                elif action in ("update", "downgrade"):
                    updates.append(parsed)
                elif action == "remove":
                    removals.append(parsed)

        if first_install is None:
            return create_error_response("NotFound", f"No install record found for: {package_name}")

        return {
            "package": package_name,
            "first_installed": first_install,
            "update_count": len(updates),
            "updates": updates,
            "removal_count": len(removals),
            "removals": removals,
        }

    except Exception as e:
        logger.error("Failed to find install history: %s", e)
        return create_error_response("LogParseError", f"Failed to find installation history: {str(e)}")


async def find_failed_transactions() -> Dict[str, Any]:
    """
    Look for failed transactions in zypp history.

    Returns:
        Dict with failed transaction info
    """
    if not IS_SUSE:
        return create_error_response("NotSupported", "This feature is only available on SUSE Linux")

    log_path = Path(ZYPP_HISTORY)
    if not log_path.exists():
        return create_error_response("NotFound", f"Zypp history not found at {ZYPP_HISTORY}")

    try:
        failures = []
        with open(log_path, "r") as f:
            for line in f:
                parsed = parse_log_line(line)
                if parsed is None:
                    continue
                if "fail" in parsed["action"].lower():
                    failures.append(parsed)

        return {
            "count": len(failures),
            "has_failures": len(failures) > 0,
            "failures": failures,
        }

    except Exception as e:
        logger.error("Failed to search for failures: %s", e)
        return create_error_response("LogParseError", f"Failed to search for failed transactions: {str(e)}")


async def get_database_sync_history(limit: int = 10) -> Dict[str, Any]:
    """
    Look for refresh/sync entries in zypp history.

    Args:
        limit: Maximum number of sync events to return

    Returns:
        Dict with database sync history
    """
    if not IS_SUSE:
        return create_error_response("NotSupported", "This feature is only available on SUSE Linux")

    log_path = Path(ZYPP_HISTORY)
    if not log_path.exists():
        return create_error_response("NotFound", f"Zypp history not found at {ZYPP_HISTORY}")

    try:
        sync_events = []
        with open(log_path, "r") as f:
            lines = f.readlines()

        for line in reversed(lines):
            if len(sync_events) >= limit:
                break
            parsed = parse_log_line(line)
            if parsed is None:
                continue
            if "refresh" in parsed["action"].lower() or "zypper-refresh" in parsed["action"].lower():
                sync_events.append(parsed)

        return {
            "count": len(sync_events),
            "sync_events": sync_events,
        }

    except Exception as e:
        logger.error("Failed to get sync history: %s", e)
        return create_error_response("LogParseError", f"Failed to get database sync history: {str(e)}")


async def query_package_history(package_name: str, limit: int = 20) -> Dict[str, Any]:
    """
    Get all history entries for a specific package.

    Args:
        package_name: Package name to query
        limit: Maximum entries to return

    Returns:
        Dict with package history
    """
    if not IS_SUSE:
        return create_error_response("NotSupported", "This feature is only available on SUSE Linux")

    log_path = Path(ZYPP_HISTORY)
    if not log_path.exists():
        return create_error_response("NotFound", f"Zypp history not found at {ZYPP_HISTORY}")

    try:
        entries = []
        with open(log_path, "r") as f:
            for line in f:
                if len(entries) >= limit:
                    break
                parsed = parse_log_line(line)
                if parsed and parsed["package"] == package_name:
                    entries.append(parsed)

        return {
            "package": package_name,
            "count": len(entries),
            "history": entries,
        }

    except Exception as e:
        logger.error("Failed to query package history: %s", e)
        return create_error_response("LogParseError", f"Failed to query package history: {str(e)}")
