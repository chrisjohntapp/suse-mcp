# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
System health check module.
Provides a comprehensive system health check by integrating multiple system diagnostics.
"""

import logging
from typing import Dict, Any

from .utils import IS_IMMUTABLE, SUSE_VARIANT

logger = logging.getLogger(__name__)


async def run_system_health_check() -> Dict[str, Any]:
    """
    Run a comprehensive system health check.

    Integrates multiple system diagnostics to provide a complete overview of
    the system health status in a single call.

    Returns:
        Dict with comprehensive health check results
    """
    from .system import (
        get_system_info,
        check_disk_space,
        check_failed_services,
        get_package_cache_stats,
    )
    from .zypper import (
        check_updates_dry_run,
        list_orphan_packages,
        check_database_freshness,
    )
    from .news import check_critical_news
    from .mirrors import check_repos_health

    logger.info("Starting comprehensive system health check")

    health_report: Dict[str, Any] = {
        "status": "success",
        "system_info": {},
        "disk_space": {},
        "services": {},
        "package_cache": {},
        "updates": {},
        "news": {},
        "orphans": {},
        "database": {},
        "repos": {},
        "issues": [],
        "suggestions": [],
    }

    try:
        # System information
        health_report["system_info"] = await get_system_info()

        # Disk space
        disk_space = await check_disk_space()
        health_report["disk_space"] = disk_space

        # Failed services
        health_report["services"] = await check_failed_services()

        # Package cache stats
        health_report["package_cache"] = await get_package_cache_stats()

        # Updates
        updates = await check_updates_dry_run()
        health_report["updates"] = updates
        if not updates.get("error") and updates.get("updates_available"):
            count = updates.get("count", 0)
            if IS_IMMUTABLE:
                health_report["suggestions"].append({
                    "message": f"{count} updates available",
                    "action": "Run 'sudo transactional-update dup' to update (reboot to apply)",
                })
            else:
                health_report["suggestions"].append({
                    "message": f"{count} updates available",
                    "action": "Run 'sudo zypper update' to update the system",
                })

        # Critical news
        health_report["news"] = await check_critical_news()

        # Orphan packages
        orphans = await list_orphan_packages()
        health_report["orphans"] = orphans
        if not orphans.get("error") and orphans.get("has_orphans"):
            health_report["suggestions"].append({
                "message": f"{orphans.get('orphan_count', 0)} orphan packages detected",
                "action": "Run 'zypper packages --orphaned' to review orphans",
            })

        # Database freshness
        health_report["database"] = await check_database_freshness()

        # Repo health
        health_report["repos"] = await check_repos_health()

        # Variant-specific suggestions
        if SUSE_VARIANT in ("sles", "sled", "sle-micro"):
            health_report["suggestions"].append({
                "message": "SLE system detected",
                "action": "Use 'SUSEConnect' for repository and subscription management",
            })

        issue_count = len(health_report["issues"])
        suggestion_count = len(health_report["suggestions"])
        health_report["summary"] = {
            "total_issues": issue_count,
            "critical_issues": len([i for i in health_report["issues"] if i.get("type") == "critical"]),
            "warnings": len([i for i in health_report["issues"] if i.get("type") == "warning"]),
            "suggestions": suggestion_count,
        }

        logger.info("Health check completed: %d issues, %d suggestions", issue_count, suggestion_count)
        return health_report

    except Exception as e:
        logger.error("Health check failed: %s", e)
        return {
            "status": "error",
            "error": str(e),
            "issues": [],
            "suggestions": [],
            "summary": {
                "total_issues": 1,
                "critical_issues": 1,
                "warnings": 0,
                "suggestions": 0,
            },
        }
