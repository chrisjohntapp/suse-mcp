# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Configuration file parsing module.
Parses zypper.conf and RPM macros for SUSE Linux.
"""

import logging
import re
from configparser import ConfigParser
from pathlib import Path
from typing import Any, Dict, List

from .utils import IS_SUSE, create_error_response, run_command

logger = logging.getLogger(__name__)

# Path constants stay overridable (tests and callers patch these names).
#
# SUSE/openSUSE ships zypper.conf at /etc/zypp/zypper.conf, owned by the zypper package.
# /etc/zypper/zypper.conf is the Fedora location; it is kept as a fallback so the tool
# still works on Fedora-derived images, but the SUSE path is what we look for first.
ZYPPER_CONF = "/etc/zypp/zypper.conf"
ZYPPER_CONF_ALTERNATIVES = ["/etc/zypper/zypper.conf"]

# RPM macro sources on openSUSE/SUSE, in the order rpm itself applies them:
# local overrides (/etc/rpm/macros, /etc/rpm/macros.d), the distribution macros
# (/usr/lib/rpm/macros legacy file and /usr/lib/rpm/macros.d/), and finally the
# host's platform macros. /etc/rpm/macros is an empty directory on openSUSE, so the
# alternatives are what make this tool return anything useful there.
#
# Overriding RPM_MACROS keeps the original single-path behaviour, so existing callers
# and tests that point it at one file keep working exactly as before.
RPM_MACROS = "/etc/rpm/macros"
RPM_MACROS_DEFAULT = "/etc/rpm/macros"
RPM_MACRO_ALTERNATIVES = [
    "/etc/rpm/macros.d",
    "/usr/lib/rpm/macros",
    "/usr/lib/rpm/macros.d",
]
RPM_MACRO_PLATFORM_ROOT = "/usr/lib/rpm/platform"


def _first_existing(paths):
    for p in paths:
        if Path(p).exists():
            return Path(p)
    return None


async def _macro_sources():
    """Resolve the RPM macro files to merge, honouring an overridden RPM_MACROS."""
    if RPM_MACROS != RPM_MACROS_DEFAULT:
        # Explicit override: use exactly that file or directory, nothing else.
        override = Path(RPM_MACROS)
        return [override] if override.exists() else []

    sources = [Path(p) for p in [RPM_MACROS] + RPM_MACRO_ALTERNATIVES if Path(p).exists()]
    # Only this machine's platform macros; scanning every architecture would report
    # another host's %_arch as the build arch. rpm's %_arch is the short name (aarch64)
    # while the platform dirs use the canonical triplet (aarch64-linux).
    exit_code, stdout, _ = await run_command(["rpm", "--eval", "%{_arch}"], timeout=5, check=False)
    host_arch = (stdout or "").strip() if exit_code == 0 else ""
    platform_root = Path(RPM_MACRO_PLATFORM_ROOT)
    if host_arch and platform_root.is_dir():
        for platform_dir in sorted(p for p in platform_root.glob("*") if p.is_dir()):
            if platform_dir.name == host_arch or platform_dir.name.startswith(host_arch + "-"):
                platform_macros = platform_dir / "macros"
                if platform_macros.exists():
                    sources.append(platform_macros)
    return sources


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

    candidates = [ZYPPER_CONF] + [p for p in ZYPPER_CONF_ALTERNATIVES if p != ZYPPER_CONF]
    conf_path = _first_existing(candidates)
    if conf_path is None:
        return create_error_response(
            "NotFound", f"zypper.conf not found at any of {candidates}"
        )

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

    sources = await _macro_sources()
    if not sources:
        return create_error_response("NotFound", f"RPM macros not found at {RPM_MACROS}")

    try:
        macros: Dict[str, str] = {}
        files: List[str] = []
        for source in sources:
            # a source is either a single macro file or a directory of them
            candidates = sorted(p for p in source.iterdir() if p.is_file()) if source.is_dir() else [source]
            for macro_file in candidates:
                files.append(str(macro_file))
                for line in macro_file.read_text(errors="replace").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    m = re.match(r'^(%\w+)\s+(.+)$', line)
                    if m:
                        macros[m.group(1)] = m.group(2).strip()

        build_arch = macros.get("%_build_arch") or macros.get("%_arch")

        return {
            "config_path": str(sources[0]),
            "sources": [str(s) for s in sources],
            "files_parsed": len(files),
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
