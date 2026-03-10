# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Repository management module.
Manages and checks SUSE repository configuration from /etc/zypp/repos.d/.
"""

import logging
import time
from configparser import ConfigParser
from pathlib import Path
from typing import Dict, Any, List, Optional

import httpx

from .utils import IS_SUSE, create_error_response

logger = logging.getLogger(__name__)

REPOS_DIR = "/etc/zypp/repos.d"


def list_repos() -> Dict[str, Any]:
    """
    Parse all .repo files in /etc/zypp/repos.d/ and return repo list.

    Returns:
        Dict with repos list
    """
    repos_path = Path(REPOS_DIR)
    if not repos_path.exists():
        return create_error_response("NotFound", f"Repos directory not found at {REPOS_DIR}")

    repos = []
    for repo_file in sorted(repos_path.glob("*.repo")):
        try:
            parser = ConfigParser()
            parser.read(repo_file)
            for section in parser.sections():
                repo = {
                    "name": section,
                    "file": str(repo_file),
                    "enabled": parser.getboolean(section, "enabled", fallback=True),
                    "autorefresh": parser.getboolean(section, "autorefresh", fallback=False),
                    "baseurl": parser.get(section, "baseurl", fallback=""),
                    "type": parser.get(section, "type", fallback="rpm-md"),
                    "gpgcheck": parser.getboolean(section, "gpgcheck", fallback=False),
                }
                repos.append(repo)
        except Exception as e:
            logger.warning("Failed to parse repo file %s: %s", repo_file, e)

    return {
        "repo_count": len(repos),
        "repos": repos,
    }


async def test_repo_speed(baseurl: str) -> Dict[str, Any]:
    """
    Test repo response time by HEAD-requesting repodata/repomd.xml.

    Args:
        baseurl: Base URL of the repository

    Returns:
        Dict with latency_ms and success
    """
    if not baseurl.endswith("/"):
        baseurl = baseurl + "/"
    test_url = baseurl + "repodata/repomd.xml"

    try:
        start = time.time()
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.head(test_url)
        latency_ms = (time.time() - start) * 1000

        return {
            "baseurl": baseurl,
            "test_url": test_url,
            "latency_ms": round(latency_ms, 2),
            "status_code": response.status_code,
            "success": response.status_code in (200, 301, 302),
        }

    except httpx.TimeoutException:
        return {
            "baseurl": baseurl,
            "test_url": test_url,
            "latency_ms": -1,
            "status_code": 0,
            "success": False,
            "error": "timeout",
        }
    except Exception as e:
        return {
            "baseurl": baseurl,
            "test_url": test_url,
            "latency_ms": -1,
            "status_code": 0,
            "success": False,
            "error": str(e),
        }


async def check_repos_health() -> Dict[str, Any]:
    """
    List repos and test speed of enabled ones.

    Returns:
        Dict with health summary
    """
    if not IS_SUSE:
        return create_error_response("NotSupported", "This feature is only available on SUSE Linux")

    repo_result = list_repos()
    if "error" in repo_result:
        return repo_result

    repos = repo_result.get("repos", [])
    enabled_repos = [r for r in repos if r.get("enabled")]

    speed_results = []
    for repo in enabled_repos:
        baseurl = repo.get("baseurl", "")
        if not baseurl:
            continue
        speed = await test_repo_speed(baseurl)
        speed["repo_name"] = repo["name"]
        speed_results.append(speed)

    successful = [r for r in speed_results if r.get("success")]
    issues = []
    if not enabled_repos:
        issues.append("No enabled repositories configured")
    elif not successful and speed_results:
        issues.append("All repositories are unreachable")

    return {
        "repo_count": len(repos),
        "enabled_count": len(enabled_repos),
        "speed_results": speed_results,
        "reachable_count": len(successful),
        "issues": issues,
        "healthy": len(issues) == 0,
    }


async def optimize_mirrors(
    action: str = "status",
    baseurl: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Repository management entry point.

    Args:
        action: "status" (list repos), "test" (test a specific repo), or "health" (health check)
        baseurl: Base URL for testing (action="test" only)

    Returns:
        Dict with results
    """
    if action == "status":
        return {"action": "status", "configuration": list_repos()}
    elif action == "test":
        if not baseurl:
            return create_error_response("InvalidParameter", "baseurl required for action='test'")
        return {"action": "test", "result": await test_repo_speed(baseurl)}
    elif action == "health":
        return {"action": "health", "assessment": await check_repos_health()}
    else:
        return create_error_response(
            "InvalidAction",
            f"Invalid action '{action}'. Use: status, test, health",
        )
