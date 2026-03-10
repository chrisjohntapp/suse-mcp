# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Zypper/RPM package management interface module.
Provides package info and update checks with hybrid local/remote approach.
"""

import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

from .utils import (
    IS_SUSE,
    IS_IMMUTABLE,
    run_command,
    create_error_response,
    check_command_exists,
)

logger = logging.getLogger(__name__)

# openSUSE software search API
OPENSUSE_SOFTWARE_URL = "https://software.opensuse.org/search.json"

# Zypper repo metadata cache
ZYPP_CACHE_DIR = "/var/cache/zypp/raw"

# HTTP client settings
DEFAULT_TIMEOUT = 10.0

# Critical packages to warn about
CRITICAL_PACKAGES = ["kernel-default", "systemd", "zypper", "glibc"]


async def get_official_package_info(package_name: str) -> Dict[str, Any]:
    """
    Get information about an official repository package.

    Uses hybrid approach:
    - If on SUSE Linux: run `zypper --no-refresh info <pkg>` locally
    - Otherwise (or on failure): query software.opensuse.org API

    Args:
        package_name: Package name

    Returns:
        Dict with package information
    """
    logger.info("Fetching info for official package: %s", package_name)

    if IS_SUSE and check_command_exists("zypper"):
        info = await _get_package_info_local(package_name)
        if info is not None:
            return info
        logger.warning("Local zypper query failed for %s, trying remote API", package_name)

    return await _get_package_info_remote(package_name)


async def _get_package_info_local(package_name: str) -> Optional[Dict[str, Any]]:
    """Query package info using local zypper command."""
    try:
        exit_code, stdout, stderr = await run_command(
            ["zypper", "--no-refresh", "--non-interactive", "info", package_name],
            timeout=15,
            check=False,
        )

        if exit_code != 0 or not stdout.strip():
            return None

        parsed = _parse_zypper_info_output(stdout)
        if parsed is None:
            return None

        parsed["source"] = "local"
        return parsed

    except Exception as e:
        logger.warning("Local zypper info failed: %s", e)
        return None


async def _get_package_info_remote(package_name: str) -> Dict[str, Any]:
    """Query package info from software.opensuse.org API."""
    try:
        params = {"q": package_name, "base_project": "openSUSE:Factory"}
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(OPENSUSE_SOFTWARE_URL, params=params)
            response.raise_for_status()
            data = response.json()

        packages = data.get("packages", [])
        if not packages:
            return create_error_response(
                "NotFound",
                f"Package '{package_name}' not found in openSUSE repositories",
            )

        pkg = packages[0]
        return {
            "source": "remote",
            "name": pkg.get("name", package_name),
            "version": pkg.get("version", ""),
            "description": pkg.get("description", ""),
            "project": pkg.get("project", ""),
            "repository": pkg.get("repository", ""),
            "arch": pkg.get("arch", ""),
            "url": pkg.get("url", ""),
        }

    except httpx.TimeoutException:
        logger.error("Timeout fetching remote package info for %s", package_name)
        return create_error_response(
            "TimeoutError",
            f"Request to openSUSE software search timed out for: {package_name}",
        )
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error fetching remote package info: %s", e)
        return create_error_response(
            "HTTPError",
            f"openSUSE software search failed with HTTP {e.response.status_code}",
        )
    except Exception as e:
        logger.error("Remote package info failed: %s", e)
        return create_error_response(
            "RemoteError",
            f"Failed to fetch remote package info: {str(e)}",
        )


def _parse_zypper_info_output(output: str) -> Optional[Dict[str, Any]]:
    """
    Parse `zypper info` output into a structured dict.

    Expected format:
        Information for package vim:
        ----------------------------
        Repository     : openSUSE-Tumbleweed-Oss
        Name           : vim
        Version        : 9.1.0330-1.1
        Arch           : x86_64
        ...
    """
    if not output or not output.strip():
        return None

    result: Dict[str, Any] = {}
    current_key: Optional[str] = None
    current_value: List[str] = []

    field_map = {
        "Name": "name",
        "Version": "version",
        "Arch": "arch",
        "Vendor": "vendor",
        "Installed Size": "installed_size",
        "Installed": "installed",
        "Status": "status",
        "Source package": "source_package",
        "Upstream URL": "url",
        "Summary": "summary",
        "Description": "description",
        "Repository": "repository",
    }

    for line in output.splitlines():
        # Skip separator/header lines
        if re.match(r'^-+$', line.strip()):
            continue
        if re.match(r'^Information for package', line):
            continue
        if not line.strip():
            if current_key == "description" and current_value:
                current_value.append("")
            continue

        # Key : Value line
        kv_match = re.match(r'^([A-Za-z ]+?)\s*:\s*(.*)', line)
        if kv_match:
            # Flush previous multi-line value
            if current_key and current_value is not None:
                key_name = field_map.get(current_key, current_key.lower().replace(" ", "_"))
                result[key_name] = "\n".join(current_value).strip()

            raw_key = kv_match.group(1).strip()
            value = kv_match.group(2).strip()
            current_key = raw_key
            current_value = [value] if value else []
        elif current_key and line.startswith(" "):
            current_value.append(line.strip())

    # Flush last key
    if current_key and current_value is not None:
        key_name = field_map.get(current_key, current_key.lower().replace(" ", "_"))
        result[key_name] = "\n".join(current_value).strip()

    if not result or "name" not in result:
        return None

    return result


def _parse_list_updates_output(output: str) -> List[Dict[str, Any]]:
    """
    Parse `zypper list-updates` pipe-delimited table output.

    Expected format:
        S | Repository | Name | Current Version | Available Version | Arch
        --+------------+------+-----------------+-------------------+-----
        v | repo       | vim  | 9.0.1000-1.1    | 9.1.0330-1.1      | x86_64
    """
    packages = []

    for line in output.splitlines():
        line = line.strip()
        # Skip header, separator, and loading lines
        if not line or line.startswith("S |") or line.startswith("--") or line.startswith("Loading") or line.startswith("Reading"):
            continue
        if "|" not in line:
            continue

        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 6:
            continue

        # parts: [S, Repository, Name, Current Version, Available Version, Arch]
        status = parts[0]
        # Only include actual update lines (status is 'v' for update available)
        if status not in ("v", "i"):
            continue

        packages.append({
            "repository": parts[1],
            "package": parts[2],
            "current_version": parts[3],
            "new_version": parts[4],
            "arch": parts[5] if len(parts) > 5 else "",
        })

    return packages


async def check_updates_dry_run() -> Dict[str, Any]:
    """
    Check for available package updates without installing.

    Uses `zypper list-updates --no-refresh`.
    On immutable variants, uses `transactional-update dup --dry-run`.

    Returns:
        Dict with updates_available, count, and packages list
    """
    if not IS_SUSE:
        return create_error_response(
            "NotSupported",
            "This feature is only available on SUSE Linux",
        )

    if IS_IMMUTABLE:
        raise NotImplementedError(
            "check_updates_dry_run on immutable variants not yet implemented"
        )

    if not check_command_exists("zypper"):
        return create_error_response(
            "CommandNotFound",
            "zypper is not installed or not in PATH",
        )

    logger.info("Checking for available updates via zypper")

    try:
        exit_code, stdout, stderr = await run_command(
            ["zypper", "--no-refresh", "--non-interactive", "list-updates"],
            timeout=30,
            check=False,
            skip_sudo_check=True,
        )

        if exit_code == 4:
            # Exit 4 means zypper itself had a problem (e.g. locked)
            return create_error_response(
                "CommandError",
                f"zypper list-updates failed: {stderr}",
            )

        packages = _parse_list_updates_output(stdout)
        return {
            "updates_available": len(packages) > 0,
            "count": len(packages),
            "packages": packages,
        }

    except Exception as e:
        logger.error("Update check failed: %s", e)
        return create_error_response(
            "UpdateCheckError",
            f"Failed to check for updates: {str(e)}",
        )


async def verify_package_integrity(package_name: str) -> Dict[str, Any]:
    """
    Verify the integrity of installed package files using `rpm -V`.

    Args:
        package_name: Package name to verify

    Returns:
        Dict with verification results
    """
    if not IS_SUSE:
        return create_error_response(
            "NotSupported",
            "This feature is only available on SUSE Linux",
        )

    if not check_command_exists("rpm"):
        return create_error_response(
            "CommandNotFound",
            "rpm is not installed or not in PATH",
        )

    logger.info("Verifying package integrity: %s", package_name)

    try:
        exit_code, stdout, stderr = await run_command(
            ["rpm", "-V", package_name],
            timeout=15,
            check=False,
            skip_sudo_check=True,
        )

        if exit_code == 1 and "not installed" in stderr.lower():
            return create_error_response(
                "NotFound",
                f"Package '{package_name}' is not installed",
            )

        # rpm -V prints nothing if all is OK; lines indicate modified files
        changed_files = []
        for line in stdout.splitlines():
            if line.strip():
                changed_files.append(line.strip())

        return {
            "package": package_name,
            "integrity_ok": len(changed_files) == 0,
            "changed_files": changed_files,
            "changed_count": len(changed_files),
        }

    except Exception as e:
        logger.error("Package integrity check failed: %s", e)
        return create_error_response(
            "IntegrityCheckError",
            f"Failed to verify package integrity: {str(e)}",
        )


async def find_package_owner(file_path: str) -> Dict[str, Any]:
    """
    Find which package owns a file using `rpm -qf`.

    Args:
        file_path: Absolute path to the file

    Returns:
        Dict with owning package name
    """
    if not IS_SUSE:
        return create_error_response(
            "NotSupported",
            "This feature is only available on SUSE Linux",
        )

    logger.info("Finding package owner for: %s", file_path)

    try:
        exit_code, stdout, stderr = await run_command(
            ["rpm", "-qf", file_path],
            timeout=10,
            check=False,
            skip_sudo_check=True,
        )

        if exit_code != 0:
            return create_error_response(
                "NotFound",
                f"File '{file_path}' is not owned by any installed package",
            )

        return {
            "file": file_path,
            "package": stdout.strip(),
        }

    except Exception as e:
        logger.error("File ownership query failed: %s", e)
        return create_error_response(
            "QueryError",
            f"Failed to find package owner: {str(e)}",
        )


async def query_file_ownership(file_path: str) -> Dict[str, Any]:
    """Alias for find_package_owner for API compatibility."""
    return await find_package_owner(file_path)


async def list_package_files(package_name: str) -> Dict[str, Any]:
    """
    List files installed by a package using `rpm -ql`.

    Args:
        package_name: Package name

    Returns:
        Dict with list of installed files
    """
    if not IS_SUSE:
        return create_error_response(
            "NotSupported",
            "This feature is only available on SUSE Linux",
        )

    logger.info("Listing files for package: %s", package_name)

    try:
        exit_code, stdout, stderr = await run_command(
            ["rpm", "-ql", package_name],
            timeout=10,
            check=False,
            skip_sudo_check=True,
        )

        if exit_code != 0:
            return create_error_response(
                "NotFound",
                f"Package '{package_name}' is not installed",
            )

        files = [line.strip() for line in stdout.splitlines() if line.strip()]
        return {
            "package": package_name,
            "file_count": len(files),
            "files": files,
        }

    except Exception as e:
        logger.error("File list query failed: %s", e)
        return create_error_response(
            "QueryError",
            f"Failed to list package files: {str(e)}",
        )


async def search_package_files(pattern: str) -> Dict[str, Any]:
    """
    Find which package provides files matching a path pattern.

    Uses `rpm -qf` for exact paths. For glob patterns,
    falls back to `rpm -qf` on each match.

    Args:
        pattern: File path or glob pattern

    Returns:
        Dict with matching package-file mappings
    """
    if not IS_SUSE:
        return create_error_response(
            "NotSupported",
            "This feature is only available on SUSE Linux",
        )

    logger.info("Searching for package providing: %s", pattern)

    try:
        exit_code, stdout, stderr = await run_command(
            ["rpm", "-qf", pattern],
            timeout=10,
            check=False,
            skip_sudo_check=True,
        )

        if exit_code == 0 and stdout.strip():
            return {
                "pattern": pattern,
                "matches": [{"file": pattern, "package": stdout.strip()}],
            }

        return create_error_response(
            "NotFound",
            f"No package found providing: {pattern}",
        )

    except Exception as e:
        logger.error("Package file search failed: %s", e)
        return create_error_response(
            "QueryError",
            f"Failed to search package files: {str(e)}",
        )


def _parse_zypper_packages_output(output: str) -> List[str]:
    """Parse pipe-delimited `zypper packages` output, returning package names."""
    names = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("S |") or line.startswith("--") or line.startswith("Loading") or line.startswith("Reading"):
            continue
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        # parts: [S, Name, Type, Version, Arch, Repository]
        if len(parts) >= 2 and parts[1]:
            names.append(parts[1])
    return names


async def list_orphan_packages() -> Dict[str, Any]:
    """
    List packages not required by any other installed package.

    Uses `zypper packages --orphaned`.

    Returns:
        Dict with orphaned package list
    """
    if not IS_SUSE:
        return create_error_response(
            "NotSupported",
            "This feature is only available on SUSE Linux",
        )

    if not check_command_exists("zypper"):
        return create_error_response(
            "CommandNotFound",
            "zypper is not installed or not in PATH",
        )

    logger.info("Listing orphan packages")

    try:
        exit_code, stdout, stderr = await run_command(
            ["zypper", "--no-refresh", "--non-interactive", "packages", "--orphaned"],
            timeout=30,
            check=False,
            skip_sudo_check=True,
        )

        if exit_code not in (0, 100):
            return create_error_response(
                "CommandError",
                f"zypper packages --orphaned failed: {stderr}",
            )

        orphans = _parse_zypper_packages_output(stdout)
        return {
            "orphan_count": len(orphans),
            "has_orphans": len(orphans) > 0,
            "orphans": orphans,
        }

    except Exception as e:
        logger.error("Orphan list failed: %s", e)
        return create_error_response(
            "QueryError",
            f"Failed to list orphan packages: {str(e)}",
        )


async def remove_orphans(dry_run: bool = True) -> Dict[str, Any]:
    """
    Remove orphaned packages.

    Args:
        dry_run: If True, list what would be removed without removing

    Returns:
        Dict with removal results
    """
    if not IS_SUSE:
        return create_error_response(
            "NotSupported",
            "This feature is only available on SUSE Linux",
        )

    orphan_result = await list_orphan_packages()
    if "error" in orphan_result:
        return orphan_result

    orphans = orphan_result.get("orphans", [])
    if not orphans:
        return {"removed": [], "count": 0, "dry_run": dry_run, "message": "No orphans found"}

    if dry_run:
        return {"would_remove": orphans, "count": len(orphans), "dry_run": True}

    return await remove_packages(orphans)


async def manage_orphans(
    action: str,
    packages: Optional[List[str]] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Unified orphan management tool.

    Args:
        action: "list" or "remove"
        packages: Specific packages to remove (action="remove" only)
        dry_run: If True, preview only (action="remove")

    Returns:
        Dict with results
    """
    if action == "list":
        return await list_orphan_packages()
    elif action == "remove":
        if packages:
            if dry_run:
                return {"would_remove": packages, "count": len(packages), "dry_run": True}
            return await remove_packages(packages)
        return await remove_orphans(dry_run=dry_run)
    else:
        return create_error_response(
            "InvalidAction",
            f"Unknown action: {action}. Use 'list' or 'remove'",
        )


async def remove_package(
    package_name: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Remove a single package.

    Args:
        package_name: Package to remove
        reason: Optional removal reason for logging

    Returns:
        Dict with removal result
    """
    return await remove_packages([package_name])


async def remove_packages_batch(
    packages: List[str],
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Remove multiple packages in a single zypper call."""
    return await remove_packages(packages)


async def remove_packages(
    packages: List[str],
    orphan_check: bool = True,
    cascade: bool = False,
) -> Dict[str, Any]:
    """
    Remove packages using zypper (or transactional-update on immutable variants).

    Args:
        packages: Package names to remove
        orphan_check: Unused (kept for API compatibility)
        cascade: If True, also remove packages that depend on the removed packages

    Returns:
        Dict with removal result
    """
    if not IS_SUSE:
        return create_error_response(
            "NotSupported",
            "This feature is only available on SUSE Linux",
        )

    if not packages:
        return create_error_response("InvalidParameter", "No packages specified")

    if IS_IMMUTABLE:
        raise NotImplementedError(
            "remove_packages on immutable variants (transactional-update) not yet implemented"
        )

    cmd = ["sudo", "zypper", "--non-interactive", "remove"]
    if cascade:
        cmd.append("--clean-deps")
    cmd.extend(packages)

    logger.info("Removing packages: %s", packages)

    try:
        exit_code, stdout, stderr = await run_command(cmd, timeout=60)

        if exit_code != 0:
            return create_error_response(
                "RemovalError",
                f"Failed to remove packages: {stderr}",
            )

        return {
            "removed": packages,
            "count": len(packages),
            "output": stdout,
        }

    except Exception as e:
        logger.error("Package removal failed: %s", e)
        return create_error_response(
            "RemovalError",
            f"Failed to remove packages: {str(e)}",
        )


async def list_explicit_packages() -> Dict[str, Any]:
    """
    List installed packages.

    Note: zypper does not distinguish between explicitly installed and
    dependency-installed packages. All installed packages are returned.

    Returns:
        Dict with installed packages list
    """
    if not IS_SUSE:
        return create_error_response(
            "NotSupported",
            "This feature is only available on SUSE Linux",
        )

    logger.info("Listing installed packages")

    try:
        exit_code, stdout, stderr = await run_command(
            ["zypper", "--no-refresh", "--non-interactive", "packages", "--installed-only"],
            timeout=30,
            check=False,
            skip_sudo_check=True,
        )

        if exit_code not in (0, 100):
            return create_error_response(
                "CommandError",
                f"zypper packages --installed-only failed: {stderr}",
            )

        packages = _parse_zypper_packages_output(stdout)
        return {
            "package_count": len(packages),
            "packages": packages,
            "note": "zypper does not track explicit vs dependency-installed; all installed packages shown",
        }

    except Exception as e:
        logger.error("Package list failed: %s", e)
        return create_error_response(
            "QueryError",
            f"Failed to list installed packages: {str(e)}",
        )


async def mark_as_explicit(package_name: str) -> Dict[str, Any]:
    """Not supported by zypper/RPM."""
    return create_error_response(
        "NotSupported",
        "zypper/RPM does not support marking packages as explicitly installed. "
        "Use package locks (`zypper addlock`) to pin packages instead.",
    )


async def mark_as_dependency(package_name: str) -> Dict[str, Any]:
    """Not supported by zypper/RPM."""
    return create_error_response(
        "NotSupported",
        "zypper/RPM does not support marking packages as dependency-installed.",
    )


async def manage_install_reason(
    package_name: str,
    reason: str,
) -> Dict[str, Any]:
    """Not supported by zypper/RPM."""
    return create_error_response(
        "NotSupported",
        "zypper/RPM does not support install reason tracking. "
        "Use package locks (`zypper addlock`) to pin packages instead.",
    )


async def check_database_freshness() -> Dict[str, Any]:
    """
    Check how recently the zypper repository metadata was refreshed.

    Inspects modification timestamps of files in /var/cache/zypp/raw/.

    Returns:
        Dict with database age and freshness assessment
    """
    if not IS_SUSE:
        return create_error_response(
            "NotSupported",
            "This feature is only available on SUSE Linux",
        )

    logger.info("Checking zypper database freshness")

    try:
        cache_path = Path(ZYPP_CACHE_DIR)

        if not cache_path.exists():
            return create_error_response(
                "NotFound",
                f"Zypper cache directory not found at {ZYPP_CACHE_DIR}",
            )

        # Each repo has a subdirectory; find the newest repomd.xml files
        repo_files = list(cache_path.glob("*/repomd.xml"))
        if not repo_files:
            # Fall back to any file in the cache
            repo_files = list(cache_path.glob("*/*"))

        if not repo_files:
            return create_error_response(
                "NotFound",
                "No repository metadata found in zypper cache",
            )

        import time
        now = time.time()
        ages_hours = []
        repo_info = []

        for repo_file in repo_files:
            try:
                mtime = repo_file.stat().st_mtime
                age_hours = (now - mtime) / 3600
                ages_hours.append(age_hours)
                repo_info.append({
                    "repo": repo_file.parent.name,
                    "age_hours": round(age_hours, 1),
                })
            except OSError:
                continue

        if not ages_hours:
            return create_error_response(
                "NotFound",
                "Could not read repository metadata timestamps",
            )

        oldest_age_hours = max(ages_hours)
        database_count = len(ages_hours)
        needs_sync = oldest_age_hours > 24

        recommendations = []
        if oldest_age_hours > 168:  # 1 week
            recommendations.append(
                "Repository metadata is over a week old. Run `zypper refresh` "
                "followed by `zypper update` for a full system update."
            )
        elif needs_sync:
            recommendations.append(
                "Repository metadata is over 24 hours old. "
                "Run `zypper refresh` to update repository data."
            )

        logger.info(
            "Database freshness: %d repos, oldest %.1f hours old",
            database_count,
            oldest_age_hours,
        )

        return {
            "database_count": database_count,
            "oldest_age_hours": round(oldest_age_hours, 1),
            "needs_sync": needs_sync,
            "recommendations": recommendations,
            "repos": repo_info,
        }

    except Exception as e:
        logger.error("Database freshness check failed: %s", e)
        return create_error_response(
            "DatabaseCheckError",
            f"Failed to check database freshness: {str(e)}",
        )
