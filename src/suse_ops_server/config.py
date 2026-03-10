# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Configuration file parsing module.
Parses zypper.conf and RPM macros for SUSE Linux.
"""

import logging
import re
from configparser import ConfigParser
from pathlib import Path
from typing import Dict, Any

from .utils import IS_SUSE, create_error_response, run_command

logger = logging.getLogger(__name__)

ZYPPER_CONF = "/etc/zypper/zypper.conf"
RPM_MACROS = "/etc/rpm/macros"


async def analyze_zypper_conf(focus: str = "full") -> Dict[str, Any]:
    """
    Parse and analyze /etc/zypper/zypper.conf.

    Args:
        focus: "full" returns all settings; "options" returns just the options dict

    Returns:
        Dict with parsed zypper configuration
    """
    if not IS_SUSE:
        return create_error_response("NotSupported", "This feature is only available on SUSE Linux")

    logger.info("Analyzing zypper.conf")

    conf_path = Path(ZYPPER_CONF)
    if not conf_path.exists():
        return create_error_response("NotFound", f"zypper.conf not found at {ZYPPER_CONF}")

    try:
        parser = ConfigParser()
        parser.read(conf_path)

        options: Dict[str, str] = {}
        for section in parser.sections():
            for key, value in parser.items(section):
                options[f"{section}.{key}"] = value

        # Extract specific useful settings
        parallel_downloads = None
        raw = options.get("download.max_concurrent_connections")
        if raw is not None:
            try:
                parallel_downloads = int(raw)
            except ValueError:
                parallel_downloads = None

        sig_level = options.get("main.gpgcheck") or options.get("repo.gpgcheck")

        raw_config = conf_path.read_text()

        if focus == "options":
            return {"options": options}

        return {
            "config_path": str(conf_path),
            "options": options,
            "parallel_downloads": parallel_downloads,
            "sig_level": sig_level,
            "raw_config": raw_config,
        }

    except Exception as e:
        logger.error("Failed to analyze zypper.conf: %s", e)
        return create_error_response("ConfigParseError", f"Failed to analyze zypper.conf: {str(e)}")


async def analyze_rpm_macros() -> Dict[str, Any]:
    """
    Parse /etc/rpm/macros (shell-style %MACRO value lines).

    Returns:
        Dict with macros dict and build_arch
    """
    if not IS_SUSE:
        return create_error_response("NotSupported", "This feature is only available on SUSE Linux")

    logger.info("Analyzing RPM macros")

    macros_path = Path(RPM_MACROS)
    if not macros_path.exists():
        return create_error_response("NotFound", f"RPM macros not found at {RPM_MACROS}")

    try:
        macros: Dict[str, str] = {}
        for line in macros_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'^(%\w+)\s+(.+)$', line)
            if m:
                macros[m.group(1)] = m.group(2).strip()

        build_arch = macros.get("%_build_arch") or macros.get("%_arch")

        return {
            "config_path": str(macros_path),
            "macros": macros,
            "build_arch": build_arch,
        }

    except Exception as e:
        logger.error("Failed to analyze RPM macros: %s", e)
        return create_error_response("ConfigParseError", f"Failed to analyze RPM macros: {str(e)}")


async def check_package_locks() -> Dict[str, Any]:
    """
    List locked packages using `zypper locks`.

    Returns:
        Dict with locks list, count, has_locks
    """
    if not IS_SUSE:
        return create_error_response("NotSupported", "This feature is only available on SUSE Linux")

    logger.info("Checking package locks")

    try:
        exit_code, stdout, stderr = await run_command(
            ["zypper", "locks"],
            timeout=10,
            check=False,
            skip_sudo_check=True,
        )

        if exit_code not in (0, 1):
            return create_error_response("CommandError", f"zypper locks failed: {stderr}")

        locks = _parse_zypper_locks(stdout)
        return {
            "locks": locks,
            "count": len(locks),
            "has_locks": len(locks) > 0,
        }

    except Exception as e:
        logger.error("Failed to check package locks: %s", e)
        return create_error_response("CommandError", f"Failed to check package locks: {str(e)}")


def _parse_zypper_locks(output: str) -> list:
    """Parse `zypper locks` table output."""
    locks = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("--"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3 and parts[0].isdigit():
            locks.append({
                "name": parts[1],
                "type": parts[2] if len(parts) > 2 else "",
            })
    return locks
