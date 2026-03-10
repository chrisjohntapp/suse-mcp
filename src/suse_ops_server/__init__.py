# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
SUSE Linux MCP Server

A Model Context Protocol server that bridges AI assistants with the SUSE Linux
ecosystem, providing access to the openSUSE Wiki, OBS, and official repositories.
"""

__version__ = "3.4.0"

from .wiki import search_wiki, get_wiki_page, get_wiki_page_as_text
from .obs import (
    search_obs,
    get_obs_info,
    get_spec_file,
    analyze_spec_security,
    audit_obs_package,
    install_obs_package,
)
from .zypper import (
    get_official_package_info,
    check_updates_dry_run,
    remove_package,
    remove_packages_batch,
    remove_packages,
    list_orphan_packages,
    remove_orphans,
    manage_orphans,
    find_package_owner,
    list_package_files,
    search_package_files,
    query_file_ownership,
    verify_package_integrity,
    list_explicit_packages,
    mark_as_explicit,
    mark_as_dependency,
    manage_install_reason,
    check_database_freshness,
)
from .system import (
    get_system_info,
    check_disk_space,
    get_package_cache_stats,
    analyze_storage,
    check_failed_services,
    get_boot_logs,
    diagnose_system,
)
from .system_health_check import run_system_health_check
from .news import get_latest_news, check_critical_news, get_news_since_last_update, fetch_news
from .logs import (
    get_transaction_history,
    find_when_installed,
    find_failed_transactions,
    get_database_sync_history,
    query_package_history,
)

from .mirrors import (
    list_repos,
    test_repo_speed,
    check_repos_health,
    optimize_mirrors,
)
from .config import (
    analyze_zypper_conf,
    analyze_rpm_macros,
    check_package_locks,
)
from .patterns import manage_patterns
from .utils import IS_SUSE, run_command

# Import server from the server module
from .server import server


# Main function will be defined here
async def main():
    """
    Main entry point for the MCP server.
    Runs the server using STDIO transport (default for Docker MCP Catalog).
    """
    import mcp.server.stdio

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


def main_sync():
    """Synchronous wrapper for the main function (STDIO transport)."""
    import asyncio

    asyncio.run(main())



__all__ = [
    # Wiki
    "search_wiki",
    "get_wiki_page",
    "get_wiki_page_as_text",
    # OBS
    "search_obs",
    "get_obs_info",
    "get_spec_file",
    "analyze_spec_security",
    "audit_obs_package",
    "install_obs_package",
    # Zypper
    "get_official_package_info",
    "check_updates_dry_run",
    "remove_package",
    "remove_packages_batch",
    "remove_packages",
    "list_orphan_packages",
    "remove_orphans",
    "manage_orphans",
    "find_package_owner",
    "list_package_files",
    "search_package_files",
    "query_file_ownership",
    "verify_package_integrity",
    "list_explicit_packages",
    "mark_as_explicit",
    "mark_as_dependency",
    "manage_install_reason",
    "check_database_freshness",
    # System
    "get_system_info",
    "check_disk_space",
    "get_package_cache_stats",
    "analyze_storage",
    "check_failed_services",
    "get_boot_logs",
    "run_system_health_check",
    # News
    "get_latest_news",
    "check_critical_news",
    "get_news_since_last_update",
    "fetch_news",
    # Logs
    "get_transaction_history",
    "find_when_installed",
    "find_failed_transactions",
    "get_database_sync_history",
    "query_package_history",
    # Mirrors/Repos
    "list_repos",
    "test_repo_speed",
    "check_repos_health",
    "optimize_mirrors",
    # Config
    "analyze_zypper_conf",
    "analyze_rpm_macros",
    "check_package_locks",
    # Patterns
    "manage_patterns",
    # Utils
    "IS_SUSE",
    "run_command",
    # Main functions
    "main",
    "main_sync",
]
