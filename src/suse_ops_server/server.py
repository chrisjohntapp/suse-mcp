# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
MCP Server setup for SUSE Linux operations.

This module contains the MCP server configuration, resources, tools, and prompts
for the SUSE Linux MCP server.
"""

import logging
import json
from typing import Any
from urllib.parse import urlparse

from mcp.server import Server
from mcp.types import (
    Resource,
    Tool,
    ToolAnnotations,
    TextContent,
    ImageContent,
    EmbeddedResource,
    Prompt,
    PromptMessage,
    GetPromptResult,
)

from . import (
    # Wiki functions
    search_wiki,
    get_wiki_page_as_text,
    # OBS functions
    search_obs,
    get_obs_info,
    get_spec_file,
    analyze_spec_security,
    audit_obs_package,
    install_obs_package,
    # Zypper functions
    get_official_package_info,
    check_updates_dry_run,
    remove_packages,
    list_orphan_packages,
    list_explicit_packages,
    manage_orphans,
    query_file_ownership,
    verify_package_integrity,
    manage_install_reason,
    check_database_freshness,
    # System functions
    get_system_info,
    check_disk_space,
    get_package_cache_stats,
    analyze_storage,
    check_failed_services,
    get_boot_logs,
    diagnose_system,
    # News functions
    get_latest_news,
    check_critical_news,
    get_news_since_last_update,
    fetch_news,
    # Logs functions
    get_transaction_history,
    find_failed_transactions,
    query_package_history,
    # Mirrors/Repos functions
    list_repos,
    check_repos_health,
    optimize_mirrors,
    # Config functions
    analyze_zypper_conf,
    analyze_rpm_macros,
    check_package_locks,
    # Patterns
    manage_patterns,
    # System health check
    run_system_health_check,
    # Utils
    IS_SUSE,
    run_command,
)

# Configure logging
logger = logging.getLogger(__name__)

# Initialize MCP server
server = Server("suse-ops-server")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_platform_error_message(tool_name: str, current_platform: str = None) -> str:
    """
    Create an informative error message with recovery hints for platform-specific tools.
    
    Args:
        tool_name: Name of the tool that requires SUSE Linux
        current_platform: Current platform/OS (auto-detected if not provided)
    
    Returns:
        Formatted error message with recovery suggestions
    """
    import platform
    
    if current_platform is None:
        try:
            if IS_SUSE:
                current_platform = "SUSE Linux"
            else:
                import distro
                current_platform = f"{distro.name()} {distro.version()}" if distro.name() else platform.system()
        except:
            current_platform = platform.system()
    
    error_msg = f"""Error: '{tool_name}' requires SUSE Linux

Current system: {current_platform}

This tool requires a running SUSE Linux system to function. However, you can still:

Alternative actions:
1. Use platform-agnostic tools:
   - search_opensuse_wiki: Search openSUSE Wiki documentation (works anywhere)
   - search_obs: Search OBS packages (works anywhere)
   - get_official_package_info: Get package info (works anywhere)
   - get_latest_news: Check openSUSE news (works anywhere)
   - check_critical_news: Check for critical openSUSE news (works anywhere)

2. Browse documentation resources:
   - opensuse-wiki://<page_title> - Read any openSUSE Wiki page
   - obs://<package>/info - Get OBS package metadata
   - suse-repo://<package> - Get official package details

3. If you're planning to use SUSE Linux:
   - Visit the openSUSE Wiki Installation Guide: opensuse-wiki://Installation_guide
   - Check latest openSUSE news before installing: get_latest_news

Note: Tools marked with [DISCOVERY], [SECURITY], and news-related tools work on any system."""
    
    return error_msg


def create_standard_output_schema(data_schema: dict, description: str = "") -> dict:
    """
    Create a standard output schema with status, data, error fields.

    This helper function creates consistent output schemas for all tools,
    ensuring they all return a predictable structure with status indicators
    and error handling.

    Args:
        data_schema: JSON schema for the 'data' field
        description: Optional description of the output

    Returns:
        Complete output schema dict

    Example:
        >>> create_standard_output_schema(
        ...     data_schema={"type": "array", "items": {"type": "string"}},
        ...     description="List of package names"
        ... )
    """
    schema = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["success", "error"],
                "description": "Operation status"
            },
            "data": data_schema,
            "error": {
                "type": "string",
                "description": "Error message (only present if status is error)"
            },
            "wiki_suggestions": {
                "type": "array",
                "description": "Related Wiki articles for troubleshooting (only present on error)",
                "items": {"type": "string"}
            }
        },
        "required": ["status"]
    }

    if description:
        schema["description"] = description

    return schema


# ============================================================================
# RESOURCES
# ============================================================================

@server.list_resources()
async def list_resources() -> list[Resource]:
    """
    List available resource URI schemes.
    
    Returns:
        List of Resource objects describing available URI schemes
    """
    return [
        # Wiki resources
        Resource(
            uri="opensuse-wiki://Installation_guide",
            name="openSUSE Wiki - Installation Guide",
            mimeType="text/markdown",
            description="Example: Fetch openSUSE Wiki pages as Markdown"
        ),
        # OBS resources
        Resource(
            uri="obs://vim/spec",
            name="OBS - vim Spec File",
            mimeType="text/plain",
            description="Example: Fetch OBS package spec files"
        ),
        Resource(
            uri="obs://vim/info",
            name="OBS - vim Package Info",
            mimeType="application/json",
            description="Example: Fetch OBS package metadata"
        ),
        # Official repository resources
        Resource(
            uri="suse-repo://vim",
            name="Official Repository - Package Info",
            mimeType="application/json",
            description="Example: Fetch official repository package details"
        ),
        # Zypper resources
        Resource(
            uri="zypper://installed",
            name="System - Installed Packages",
            mimeType="application/json",
            description="List installed packages on SUSE Linux system"
        ),
        Resource(
            uri="zypper://orphans",
            name="System - Orphan Packages",
            mimeType="application/json",
            description="List orphaned packages (dependencies no longer required)"
        ),
        Resource(
            uri="zypper://explicit",
            name="System - Explicitly Installed Packages",
            mimeType="application/json",
            description="List packages explicitly installed by user"
        ),
        Resource(
            uri="zypper://patterns",
            name="System - Zypper Patterns",
            mimeType="application/json",
            description="List all available zypper patterns"
        ),
        # System resources
        Resource(
            uri="system://info",
            name="System - System Information",
            mimeType="application/json",
            description="Get system information (kernel, architecture, memory, uptime)"
        ),
        Resource(
            uri="system://disk",
            name="System - Disk Space",
            mimeType="application/json",
            description="Check disk space usage for critical paths"
        ),
        Resource(
            uri="system://services/failed",
            name="System - Failed Services",
            mimeType="application/json",
            description="List failed systemd services"
        ),
        Resource(
            uri="system://logs/boot",
            name="System - Boot Logs",
            mimeType="text/plain",
            description="Get recent boot logs from journalctl"
        ),
        # News resources
        Resource(
            uri="opensuse-news://latest",
            name="openSUSE News - Latest",
            mimeType="application/json",
            description="Get latest openSUSE news announcements"
        ),
        Resource(
            uri="opensuse-news://critical",
            name="openSUSE News - Critical",
            mimeType="application/json",
            description="Get critical openSUSE news requiring manual intervention"
        ),
        Resource(
            uri="opensuse-news://since-update",
            name="openSUSE News - Since Last Update",
            mimeType="application/json",
            description="Get news posted since last zypper update"
        ),
        # Transaction log resources
        Resource(
            uri="zypper://log/recent",
            name="Zypp Log - Recent Transactions",
            mimeType="application/json",
            description="Get recent package transactions from zypp history"
        ),
        Resource(
            uri="zypper://log/failed",
            name="Zypp Log - Failed Transactions",
            mimeType="application/json",
            description="Get failed package transactions"
        ),
        # Mirror resources
        Resource(
            uri="mirrors://active",
            name="Mirrors - Active Configuration",
            mimeType="application/json",
            description="Get currently configured mirrors"
        ),
        Resource(
            uri="mirrors://health",
            name="Mirrors - Health Status",
            mimeType="application/json",
            description="Get mirror configuration health assessment"
        ),
        # Config resources
        Resource(
            uri="config://zypper",
            name="Config - zypper.conf",
            mimeType="application/json",
            description="Get parsed zypper.conf configuration"
        ),
        Resource(
            uri="config://rpm-macros",
            name="Config - rpm macros",
            mimeType="application/json",
            description="Get parsed rpm macros configuration"
        ),
        # Database resources
        Resource(
            uri="zypper://database/freshness",
            name="Zypper - Database Freshness",
            mimeType="application/json",
            description="Check when package databases were last synchronized"
        ),
        # System health resources
        Resource(
            uri="system://health",
            name="System - Health Check",
            mimeType="application/json",
            description="Comprehensive system health check report"
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    """
    Read a resource by URI.

    Supported schemes:
    - opensuse-wiki://{page_title} - Returns Wiki page as Markdown
    - obs://{package}/spec - Returns raw spec file
    - obs://{package}/info - Returns OBS package metadata
    - suse-repo://{package} - Returns official repository package info
    - zypper://installed - Returns list of installed packages (SUSE only)
    - zypper://orphans - Returns list of orphaned packages (SUSE only)
    - zypper://explicit - Returns list of explicitly installed packages (SUSE only)
    - zypper://patterns - Returns list of all zypper patterns (SUSE only)
    - system://info - Returns system information
    - system://disk - Returns disk space information
    - system://services/failed - Returns failed systemd services
    - system://logs/boot - Returns recent boot logs

    Args:
        uri: Resource URI (can be string or AnyUrl object)

    Returns:
        Resource content as string

    Raises:
        ValueError: If URI scheme is unsupported or resource not found
    """
    # Convert to string if it's a Pydantic AnyUrl object
    uri_str = str(uri)
    logger.info(f"Reading resource: {uri_str}")
    
    parsed = urlparse(uri_str)
    scheme = parsed.scheme
    
    if scheme == "opensuse-wiki":
        # Extract page title from path (remove leading /)
        page_title = parsed.path.lstrip('/')

        if not page_title:
            # If only hostname provided, use it as title
            page_title = parsed.netloc

        if not page_title:
            raise ValueError("Wiki page title required in URI (e.g., opensuse-wiki://Installation_guide)")

        # Fetch Wiki page as Markdown
        content = await get_wiki_page_as_text(page_title)
        return content

    elif scheme == "obs":
        # Extract package name from netloc or path
        package_name = parsed.netloc or parsed.path.lstrip('/').split('/')[0]

        if not package_name:
            raise ValueError("OBS package name required in URI (e.g., obs://vim/spec or obs://vim/info)")

        # Determine what to fetch based on path
        path_parts = parsed.path.lstrip('/').split('/')

        if len(path_parts) > 1 and path_parts[1] == "spec":
            # Fetch spec file
            spec_result = await get_spec_file(package_name)
            return spec_result.get("spec_content", json.dumps(spec_result, indent=2))
        elif len(path_parts) > 1 and path_parts[1] == "info":
            # Fetch package info
            package_info = await get_obs_info(package_name)
            return json.dumps(package_info, indent=2)
        else:
            # Default to package info
            package_info = await get_obs_info(package_name)
            return json.dumps(package_info, indent=2)

    elif scheme == "suse-repo":
        # Extract package name from netloc or path
        package_name = parsed.netloc or parsed.path.lstrip('/')

        if not package_name:
            raise ValueError("Package name required in URI (e.g., suse-repo://vim)")

        # Fetch official package info
        package_info = await get_official_package_info(package_name)
        return json.dumps(package_info, indent=2)
    
    elif scheme == "zypper":
        if not IS_SUSE:
            raise ValueError(create_platform_error_message("zypper:// resources"))

        resource_path = parsed.netloc or parsed.path.lstrip('/')

        if resource_path == "installed":
            # Get installed packages via rpm
            exit_code, stdout, stderr = await run_command(["rpm", "-qa", "--qf", "%{NAME} %{VERSION}-%{RELEASE}\n"])
            if exit_code != 0:
                raise ValueError(f"Failed to get installed packages: {stderr}")

            packages = []
            for line in stdout.strip().split('\n'):
                if line.strip():
                    parts = line.strip().rsplit(' ', 1)
                    if len(parts) == 2:
                        packages.append({"name": parts[0], "version": parts[1]})

            return json.dumps(packages, indent=2)

        elif resource_path == "orphans":
            result = await list_orphan_packages()
            return json.dumps(result, indent=2)

        elif resource_path == "explicit":
            result = await list_explicit_packages()
            return json.dumps(result, indent=2)

        elif resource_path == "patterns":
            result = await manage_patterns(action="list_patterns")
            return json.dumps(result, indent=2)

        elif resource_path.startswith("log/"):
            log_type = resource_path.split('/', 1)[1] if '/' in resource_path else ""

            if log_type == "recent":
                result = await get_transaction_history()
                return json.dumps(result, indent=2)
            elif log_type == "failed":
                result = await find_failed_transactions()
                return json.dumps(result, indent=2)
            else:
                raise ValueError(f"Unsupported log resource: {log_type}")

        elif resource_path == "database/freshness":
            result = await check_database_freshness()
            return json.dumps(result, indent=2)

        else:
            raise ValueError(f"Unsupported zypper resource: {resource_path}")

    elif scheme == "system":
        resource_path = parsed.netloc or parsed.path.lstrip('/')

        if resource_path == "info":
            # Get system information
            result = await get_system_info()
            return json.dumps(result, indent=2)

        elif resource_path == "disk":
            # Get disk space information
            result = await check_disk_space()
            return json.dumps(result, indent=2)

        elif resource_path == "services/failed":
            # Get failed services
            result = await check_failed_services()
            return json.dumps(result, indent=2)

        elif resource_path == "logs/boot":
            # Get boot logs
            result = await get_boot_logs()
            # Return raw text for logs
            if result.get("success"):
                return result.get("logs", "")
            else:
                raise ValueError(result.get("error", "Failed to get boot logs"))

        elif resource_path == "health":
            # Get system health check
            result = await run_system_health_check()
            return json.dumps(result, indent=2)

        else:
            raise ValueError(f"Unsupported system resource: {resource_path}")

    elif scheme == "opensuse-news":
        resource_path = parsed.netloc or parsed.path.lstrip('/')

        if resource_path == "latest":
            result = await get_latest_news()
            return json.dumps(result, indent=2)

        elif resource_path == "critical":
            result = await check_critical_news()
            return json.dumps(result, indent=2)

        elif resource_path == "since-update":
            result = await get_news_since_last_update()
            return json.dumps(result, indent=2)

        else:
            raise ValueError(f"Unsupported opensuse-news resource: {resource_path}")

    elif scheme == "mirrors":
        if not IS_SUSE:
            raise ValueError(create_platform_error_message("mirrors:// resources"))

        resource_path = parsed.netloc or parsed.path.lstrip('/')

        if resource_path == "active":
            # Get active mirrors
            result = await list_repos()
            return json.dumps(result, indent=2)

        elif resource_path == "health":
            # Get mirror health
            result = await check_repos_health()
            return json.dumps(result, indent=2)

        else:
            raise ValueError(f"Unsupported mirrors resource: {resource_path}")

    elif scheme == "config":
        if not IS_SUSE:
            raise ValueError(create_platform_error_message("config:// resources"))

        resource_path = parsed.netloc or parsed.path.lstrip('/')

        if resource_path == "zypper":
            result = await analyze_zypper_conf()
            return json.dumps(result, indent=2)

        elif resource_path == "rpm-macros":
            result = await analyze_rpm_macros()
            return json.dumps(result, indent=2)

        else:
            raise ValueError(f"Unsupported config resource: {resource_path}")

    else:
        raise ValueError(f"Unsupported URI scheme: {scheme}")


# ============================================================================
# TOOLS
# ============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """
    List available tools for SUSE Linux operations.
    
    Returns:
        List of Tool objects describing available operations
    """
    return [
        # Wiki tools
        Tool(
            name="search_opensuse_wiki",
            description="[DISCOVERY] Search the openSUSE Wiki for documentation. Returns a list of matching pages with titles, snippets, and URLs. Prefer Wiki results over general web knowledge for SUSE-specific issues. Example: Search for 'zypper' to find documentation on package management.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (keywords or phrase)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),
        
        # OBS tools
        Tool(
            name="search_obs",
            description="[DISCOVERY] Search the Open Build Service (OBS) for packages. Returns package info including project, repository, and description. Always check official repos first using get_official_package_info. Use case: Search OBS for community-maintained packages not in official repositories.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Package search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 20)",
                        "default": 20
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort method: 'relevance' (default), 'votes', 'popularity', or 'modified'",
                        "enum": ["relevance", "votes", "popularity", "modified"],
                        "default": "relevance"
                    }
                },
                "required": ["query"]
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),
        
        Tool(
            name="get_official_package_info",
            description="[DISCOVERY] Get information about an official SUSE repository package. Uses local zypper if available, otherwise queries the OBS API. Always prefer official packages over OBS community packages. Example query: 'python3' returns version, dependencies, install size, and repository location.",
            inputSchema={
                "type": "object",
                "properties": {
                    "package_name": {
                        "type": "string",
                        "description": "Exact package name"
                    }
                },
                "required": ["package_name"]
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),
        
        Tool(
            name="check_updates_dry_run",
            description="[LIFECYCLE] Check for available system updates without applying them. Only works on SUSE Linux systems. Safe read-only operation that shows pending updates. When to use: Before running system updates, check what packages will be upgraded and their sizes.",
            inputSchema={
                "type": "object",
                "properties": {}
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),
        
        Tool(
            name="install_obs_package",
            description="[LIFECYCLE] Install a package from OBS with security checks. Workflow: 1. Fetch OBS metadata 2. Analyze spec file for security issues 3. Block installation if critical issues found 4. Add OBS repo and install via zypper. Only works on SUSE Linux. Requires sudo access.",
            inputSchema={
                "type": "object",
                "properties": {
                    "package_name": {
                        "type": "string",
                        "description": "Name of package to install from OBS"
                    }
                },
                "required": ["package_name"]
            },
            annotations=ToolAnnotations(destructiveHint=True)
        ),
        
         Tool(
             name="audit_obs_security",
             description="[SECURITY] Comprehensive security audit for OBS packages. Actions: spec_analysis (scan spec file for security red flags), full_audit (fetch and audit an OBS package by name). Examples: audit_obs_security(action='spec_analysis', spec_content='...'), audit_obs_security(action='full_audit', package_name='vim'). Always audit OBS packages before installing.",
             inputSchema={
                 "type": "object",
                 "properties": {
                     "action": {
                         "type": "string",
                         "enum": ["spec_analysis", "full_audit"],
                         "description": "Type of security audit"
                     },
                     "spec_content": {
                         "type": "string",
                         "description": "Spec file content for analysis (for spec_analysis action)"
                     },
                     "package_name": {
                         "type": "string",
                         "description": "Package name for full audit (for full_audit action)"
                     },
                     "project": {
                         "type": "string",
                         "description": "OBS project (default: openSUSE:Factory)"
                     }
                 },
                 "required": ["action"]
             },
             annotations=ToolAnnotations(readOnlyHint=True)
         ),

        # Package Removal
        Tool(
            name="remove_packages",
            description="[LIFECYCLE] Unified tool for removing packages (single or multiple). Accepts either a single package name or a list of packages. Supports removal with dependencies and forced removal. Only works on SUSE Linux. Requires sudo access. Examples: packages='firefox', remove_dependencies=true → removes Firefox with its dependencies; packages=['pkg1', 'pkg2', 'pkg3'] → batch removal of multiple packages; packages='lib', force=true → force removal ignoring dependencies (dangerous!).",
            inputSchema={
                "type": "object",
                "properties": {
                    "packages": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}}
                        ],
                        "description": "Package name (string) or list of package names (array) to remove"
                    },
                    "remove_dependencies": {
                        "type": "boolean",
                        "description": "Remove packages and their unneeded dependencies. Default: false",
                        "default": False
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force removal ignoring dependencies. Use with caution! Default: false",
                        "default": False
                    }
                },
                "required": ["packages"]
            },
            annotations=ToolAnnotations(destructiveHint=True)
        ),

        # Orphan Package Management
        Tool(
            name="manage_orphans",
            description="[MAINTENANCE] Unified tool for managing orphaned packages (dependencies no longer required). Supports two actions: 'list' (show orphaned packages) and 'remove' (remove orphaned packages). Only works on SUSE Linux. Requires sudo access for removal. Examples: action='list' → shows all orphaned packages with disk usage; action='remove', dry_run=true → preview what would be removed; action='remove', dry_run=false, exclude=['pkg1'] → remove all orphans except 'pkg1'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "remove"],
                        "description": "Action to perform: 'list' (list orphaned packages) or 'remove' (remove orphaned packages)"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview what would be removed without actually removing (only for remove action). Default: true",
                        "default": True
                    },
                    "exclude": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of package names to exclude from removal (only for remove action)"
                    }
                },
                "required": ["action"]
            },
            annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False)  # Mixed: list is read-only, remove is destructive
        ),

        # File Ownership Query (Consolidated)
        Tool(
            name="query_file_ownership",
            description="[ORGANIZATION] Unified tool for querying file-package ownership relationships. Supports three modes: 'file_to_package' (find which package owns a file), 'package_to_files' (list all files in a package with optional filtering), and 'filename_search' (search for files across all packages). Only works on SUSE Linux. Examples: mode='file_to_package', query='/usr/bin/python' → returns 'python' package; mode='package_to_files', query='systemd', filter_pattern='*.service' → lists all systemd service files; mode='filename_search', query='*.desktop' → finds all packages with desktop entries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query string: file path for file_to_package mode, package name for package_to_files mode, or filename pattern for filename_search mode"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["file_to_package", "package_to_files", "filename_search"],
                        "description": "Query mode: 'file_to_package' (find package owner), 'package_to_files' (list package files), or 'filename_search' (search across packages)"
                    },
                    "filter_pattern": {
                        "type": "string",
                        "description": "Optional regex pattern to filter files (only used in package_to_files mode, e.g., '*.conf' or '/etc/')"
                    }
                },
                "required": ["query", "mode"]
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),


        # Package Verification
        Tool(
            name="verify_package_integrity",
            description="[MAINTENANCE] Verify the integrity of installed package files. Detects modified, missing, or corrupted files. Only works on SUSE Linux. When to use: After system crash or disk errors, verify 'linux' package files match expected checksums.",
            inputSchema={
                "type": "object",
                "properties": {
                    "package_name": {
                        "type": "string",
                        "description": "Name of the package to verify"
                    }
                },
                "required": ["package_name"]
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),

        # Package Groups
        Tool(
            name="manage_patterns",
            description="[ORGANIZATION] Unified zypper pattern management. Actions: list_patterns (all patterns), pattern_info (details about a specific pattern). Examples: manage_patterns(action='list_patterns'), manage_patterns(action='pattern_info', pattern_name='base')",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list_patterns", "pattern_info"],
                        "description": "Operation to perform"
                    },
                    "pattern_name": {
                        "type": "string",
                        "description": "Pattern name (required for pattern_info)"
                    }
                },
                "required": ["action"]
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),

        # Install Reason Management
        Tool(
            name="manage_install_reason",
            description="[MAINTENANCE] Unified tool for managing package install reasons. Supports three actions: 'list' (list all explicitly installed packages), 'mark_explicit' (prevent package from being removed as orphan), and 'mark_dependency' (allow package to be auto-removed with orphans). Only works on SUSE Linux. Examples: action='list' → returns all user-installed packages; action='mark_explicit', package_name='python-pip' → keeps package even when dependencies change; action='mark_dependency', package_name='lib32-gcc-libs' → allows auto-removal with orphans.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "mark_explicit", "mark_dependency"],
                        "description": "Action to perform: 'list' (list explicit packages), 'mark_explicit' (mark as user-installed), or 'mark_dependency' (mark as auto-removable)"
                    },
                    "package_name": {
                        "type": "string",
                        "description": "Package name (required for mark_explicit and mark_dependency actions)"
                    }
                },
                "required": ["action"]
            },
            annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False)  # Mixed: list is read-only, marking is destructive
        ),

        # System Diagnostic Tools
        Tool(
            name="get_system_info",
            description="[MONITORING] Get comprehensive system information including kernel version, architecture, hostname, uptime, and memory statistics. Works on any system. Returns SUSE variant, kernel, architecture, and memory info.",
            inputSchema={
                "type": "object",
                "properties": {}
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),

        Tool(
            name="analyze_storage",
            description="[MONITORING] Unified storage analysis tool. Actions: disk_usage (check disk space for critical paths), cache_stats (analyze zypp package cache). Works on any system for disk_usage, SUSE only for cache_stats.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["disk_usage", "cache_stats"],
                        "description": "Analysis type to perform"
                    }
                },
                "required": ["action"]
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),

        Tool(
            name="diagnose_system",
            description="[MONITORING] Unified system diagnostics for systemd-based systems. Actions: failed_services (check for failed systemd services), boot_logs (retrieve recent boot logs). Works on systemd-based systems only.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["failed_services", "boot_logs"],
                        "description": "Diagnostic action to perform"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of log lines (for boot_logs). Default: 100",
                        "default": 100
                    }
                },
                "required": ["action"]
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),

        # News Tools
        Tool(
            name="fetch_news",
            description="[DISCOVERY] Unified news fetching from openSUSE. Actions: latest (get recent news), critical (find news requiring manual intervention), since_update (news since last system update). Works on any system for latest/critical, SUSE only for since_update.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["latest", "critical", "since_update"],
                        "description": "Type of news query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum news items (for latest/critical). Default: 10",
                        "default": 10
                    },
                    "since_date": {
                        "type": "string",
                        "description": "ISO date to filter from (for latest action)"
                    }
                },
                "required": ["action"]
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),

        # Transaction Log Tools
        # Consolidated Transaction History Tool
        Tool(
            name="query_package_history",
            description="[HISTORY] Unified tool for querying package history from zypp logs. Supports four query types: 'all' (recent transactions), 'package' (specific package install/upgrade history), 'failures' (failed transactions), and 'sync' (database sync history). Only works on SUSE Linux. Examples: query_type='all', limit=50 → recent transactions; query_type='package', package_name='docker' → when docker was installed; query_type='failures' → find errors; query_type='sync', limit=20 → sync history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": ["all", "package", "failures", "sync"],
                        "description": "Type of query: 'all' (recent transactions), 'package' (package history), 'failures' (failed transactions), or 'sync' (database sync history)"
                    },
                    "package_name": {
                        "type": "string",
                        "description": "Package name (required for query_type='package')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 50)",
                        "default": 50
                    }
                },
                "required": ["query_type"]
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),

        # Mirror Management Tools
        Tool(
            name="optimize_mirrors",
            description="[MIRRORS] Smart repository management. Actions: 'status' (list configured repos), 'test' (test repo speeds), 'health' (full health check). Examples: optimize_mirrors(action='status', auto_test=True) lists and tests all repos; optimize_mirrors(action='health') checks for issues and gives recommendations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["status", "test", "suggest", "health"],
                        "description": "Operation to perform: 'status' (list mirrors), 'test' (test speeds), 'suggest' (get recommendations), 'health' (full check)"
                    },
                    "country": {
                        "type": "string",
                        "description": "Optional country code for suggestions (e.g., 'US', 'DE') - action='suggest' only"
                    },
                    "mirror_url": {
                        "type": "string",
                        "description": "Specific mirror URL to test - action='test' only"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of mirrors for suggestions (default 10)",
                        "default": 10
                    },
                    "auto_test": {
                        "type": "boolean",
                        "description": "If true, test mirrors after listing - action='status' only",
                        "default": False
                    }
                },
                "required": ["action"]
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),

        # Configuration Tools
        Tool(
            name="analyze_zypper_conf",
            description="[CONFIG] Parse and analyze zypper.conf with optional focus. Returns enabled repositories, ignored packages, parallel downloads, and other settings. Only works on SUSE Linux. Examples: focus='full' (default) returns all settings; focus='ignored_packages' returns only ignored packages with warnings for critical ones; focus='parallel_downloads' returns only parallel downloads setting with optimization recommendations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "focus": {
                        "type": "string",
                        "enum": ["full", "ignored_packages", "parallel_downloads"],
                        "description": "What to analyze: 'full' (all settings), 'ignored_packages' (only ignored packages), 'parallel_downloads' (only parallel downloads setting)",
                        "default": "full"
                    }
                }
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),

        Tool(
            name="analyze_rpm_macros",
            description="[CONFIG] Parse and analyze rpm macros. Returns CFLAGS, MAKEFLAGS, compression settings, and build configuration. Only works on SUSE Linux. Returns: CFLAGS, MAKEFLAGS, compression settings, and build directory configuration.",
            inputSchema={
                "type": "object",
                "properties": {}
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),

        Tool(
            name="check_database_freshness",
            description="[MAINTENANCE] Check when package databases were last synchronized. Warns if databases are stale (> 24 hours). Only works on SUSE Linux. When to use: Check if zypper cache is stale and needs 'zypper refresh'.",
            inputSchema={
                "type": "object",
                "properties": {}
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),
        
        Tool(
            name="run_system_health_check",
            description="[MONITORING] Run a comprehensive system health check. Integrates multiple diagnostics to provide a complete overview of system status, including disk space, failed services, updates, orphan packages, and more. Only works on SUSE Linux. Comprehensive check: Updates available, disk space, failed services, database freshness, orphans, and critical news.",
            inputSchema={
                "type": "object",
                "properties": {}
            },
            annotations=ToolAnnotations(readOnlyHint=True)
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    Execute a tool by name with the provided arguments.
    
    Args:
        name: Tool name
        arguments: Tool arguments
    
    Returns:
        List of content objects with tool results
    
    Raises:
        ValueError: If tool name is unknown
    """
    logger.info(f"Calling tool: {name} with args: {arguments}")
    
    if name == "search_opensuse_wiki":
        query = arguments["query"]
        limit = arguments.get("limit", 10)
        results = await search_wiki(query, limit)
        return [TextContent(type="text", text=json.dumps(results, indent=2))]
    
    elif name == "search_obs":
        query = arguments["query"]
        limit = arguments.get("limit", 20)
        sort_by = arguments.get("sort_by", "relevance")
        results = await search_obs(query, limit)
        return [TextContent(type="text", text=json.dumps(results, indent=2))]
    
    elif name == "get_official_package_info":
        package_name = arguments["package_name"]
        result = await get_official_package_info(package_name)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "check_updates_dry_run":
        if not IS_SUSE:
            return [TextContent(type="text", text=create_platform_error_message("check_updates_dry_run"))]
        
        result = await check_updates_dry_run()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "install_obs_package":
        if not IS_SUSE:
            return [TextContent(type="text", text=create_platform_error_message("install_obs_package"))]
        
        package_name = arguments["package_name"]
        result = await install_obs_package(package_name)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "audit_obs_security":
        action = arguments["action"]
        if action == "spec_analysis":
            spec_content = arguments.get("spec_content", "")
            result = analyze_spec_security(spec_content)
        elif action == "full_audit":
            package_name = arguments.get("package_name", "")
            project = arguments.get("project", "openSUSE:Factory")
            result = await audit_obs_package(package_name, project)
        else:
            result = {"error": True, "type": "InvalidAction", "message": f"Unknown action: {action}"}
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Package Removal Tools
    elif name == "remove_packages":
        if not IS_SUSE:
            return [TextContent(type="text", text=create_platform_error_message("remove_packages"))]

        packages = arguments["packages"]
        remove_dependencies = arguments.get("remove_dependencies", False)
        force = arguments.get("force", False)
        result = await remove_packages(packages, remove_dependencies, force)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Orphan Package Management
    elif name == "manage_orphans":
        if not IS_SUSE:
            return [TextContent(type="text", text=create_platform_error_message("manage_orphans"))]

        action = arguments["action"]
        dry_run = arguments.get("dry_run", True)
        exclude = arguments.get("exclude", None)
        result = await manage_orphans(action, dry_run, exclude)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # File Ownership Query
    elif name == "query_file_ownership":
        if not IS_SUSE:
            return [TextContent(type="text", text=create_platform_error_message("query_file_ownership"))]

        query = arguments["query"]
        mode = arguments["mode"]
        filter_pattern = arguments.get("filter_pattern", None)
        result = await query_file_ownership(query, mode, filter_pattern)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Package Verification
    elif name == "verify_package_integrity":
        if not IS_SUSE:
            return [TextContent(type="text", text=create_platform_error_message("verify_package_integrity"))]

        package_name = arguments["package_name"]
        result = await verify_package_integrity(package_name)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Package Groups
    elif name == "manage_patterns":
        if not IS_SUSE:
            return [TextContent(type="text", text=create_platform_error_message("manage_patterns"))]
        
        action = arguments["action"]
        pattern_name = arguments.get("pattern_name", None)
        result = await manage_patterns(action, pattern_name=pattern_name)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Install Reason Management
    elif name == "manage_install_reason":
        if not IS_SUSE:
            return [TextContent(type="text", text=create_platform_error_message("manage_install_reason"))]

        action = arguments["action"]
        package_name = arguments.get("package_name", None)
        result = await manage_install_reason(action, package_name)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # System Diagnostic Tools
    elif name == "get_system_info":
        result = await get_system_info()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "analyze_storage":
        action = arguments["action"]
        result = await analyze_storage(action)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "diagnose_system":
        action = arguments["action"]
        lines = arguments.get("lines", 100)
        result = await diagnose_system(action, lines)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # News tools
    elif name == "fetch_news":
        action = arguments["action"]
        limit = arguments.get("limit", 10)
        since_date = arguments.get("since_date", None)
        result = await fetch_news(action, limit, since_date)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Consolidated transaction history tool
    elif name == "query_package_history":
        if not IS_SUSE:
            return [TextContent(type="text", text=create_platform_error_message("query_package_history"))]
        
        query_type = arguments.get("query_type")
        package_name = arguments.get("package_name")
        limit = arguments.get("limit", 50)
        result = await query_package_history(query_type=query_type, package_name=package_name, limit=limit)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Mirror management tool (consolidated)
    elif name == "optimize_mirrors":
        action = arguments.get("action")
        country = arguments.get("country")
        mirror_url = arguments.get("mirror_url")
        limit = arguments.get("limit", 10)
        auto_test = arguments.get("auto_test", False)
        
        result = await optimize_mirrors(
            action=action,
            country=country,
            mirror_url=mirror_url,
            limit=limit,
            auto_test=auto_test
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Configuration tools
    elif name == "analyze_zypper_conf":
        if not IS_SUSE:
            return [TextContent(type="text", text=create_platform_error_message("analyze_zypper_conf"))]
        
        focus = arguments.get("focus", "full")
        result = await analyze_zypper_conf(focus=focus)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "analyze_rpm_macros":
        if not IS_SUSE:
            return [TextContent(type="text", text=create_platform_error_message("analyze_rpm_macros"))]
        
        result = await analyze_rpm_macros()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "run_system_health_check":
        if not IS_SUSE:
            return [TextContent(type="text", text=create_platform_error_message("run_system_health_check"))]
        
        result = await run_system_health_check()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "check_database_freshness":
        if not IS_SUSE:
            return [TextContent(type="text", text=create_platform_error_message("check_database_freshness"))]
        
        result = await check_database_freshness()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        raise ValueError(f"Unknown tool: {name}")


# ============================================================================
# PROMPTS
# ============================================================================

@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    """
    List available prompts for guided workflows.
    
    Returns:
        List of Prompt objects describing available workflows
    """
    return [
        Prompt(
            name="troubleshoot_issue",
            description="Diagnose system errors and provide solutions using openSUSE Wiki knowledge",
            arguments=[
                {
                    "name": "error_message",
                    "description": "The error message or issue description",
                    "required": True
                },
                {
                    "name": "context",
                    "description": "Additional context about when/where the error occurred",
                    "required": False
                }
            ]
        ),
        Prompt(
            name="audit_obs_package",
            description="Perform comprehensive security audit of an OBS package before installation",
            arguments=[
                {
                    "name": "package_name",
                    "description": "Name of the OBS package to audit",
                    "required": True
                }
            ]
        ),
        Prompt(
            name="analyze_dependencies",
            description="Analyze package dependencies and suggest installation order",
            arguments=[
                {
                    "name": "package_name",
                    "description": "Name of the package to analyze dependencies for",
                    "required": True
                }
            ]
        ),
        Prompt(
            name="safe_system_update",
            description="Enhanced system update workflow that checks for critical news, disk space, and failed services before updating",
            arguments=[]
        ),
        Prompt(
            name="cleanup_system",
            description="Comprehensive system cleanup workflow: remove orphans, clean cache, verify integrity",
            arguments=[
                {
                    "name": "aggressive",
                    "description": "Perform aggressive cleanup (removes more packages). Default: false",
                    "required": False
                }
            ]
        ),
        Prompt(
            name="package_investigation",
            description="Deep package research before installation: check repos, analyze security, review dependencies",
            arguments=[
                {
                    "name": "package_name",
                    "description": "Package name to investigate",
                    "required": True
                }
            ]
        ),
        Prompt(
            name="mirror_optimization",
            description="Test and configure fastest mirrors based on location and latency",
            arguments=[
                {
                    "name": "country",
                    "description": "Country code for mirror suggestions (e.g., US, DE, JP)",
                    "required": False
                }
            ]
        ),
        Prompt(
            name="system_health_check",
            description="Comprehensive system diagnostic: check disk, services, logs, database, integrity",
            arguments=[]
        ),
    ]


@server.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str]) -> GetPromptResult:
    """
    Generate a prompt response for guided workflows.
    
    Args:
        name: Prompt name
        arguments: Prompt arguments
    
    Returns:
        GetPromptResult with generated messages
    
    Raises:
        ValueError: If prompt name is unknown
    """
    logger.info(f"Generating prompt: {name} with args: {arguments}")
    
    if name == "troubleshoot_issue":
        error_message = arguments["error_message"]
        context = arguments.get("context", "")
        
        # Extract keywords from error message for Wiki search
        keywords = error_message.lower().split()
        wiki_query = " ".join(keywords[:5])  # Use first 5 words as search query
        
        # Search Wiki for relevant pages
        try:
            wiki_results = await search_wiki(wiki_query, limit=3)
        except Exception as e:
            wiki_results = []
        
        messages = [
            PromptMessage(
                role="user",
                content=PromptMessage.TextContent(
                    type="text",
                    text=f"I'm experiencing this error: {error_message}\n\nContext: {context}\n\nPlease help me troubleshoot this issue using SUSE Linux knowledge."
                )
            )
        ]
        
        if wiki_results:
            wiki_content = "Here are some relevant openSUSE Wiki pages that might help:\n\n"
            for result in wiki_results:
                wiki_content += f"- **{result['title']}**: {result.get('snippet', 'No description available')}\n"
                wiki_content += f"  URL: {result['url']}\n\n"
            
            messages.append(
                PromptMessage(
                    role="assistant",
                    content=PromptMessage.TextContent(
                        type="text",
                        text=wiki_content
                    )
                )
            )
        
        return GetPromptResult(
            description=f"Troubleshooting guidance for: {error_message}",
            messages=messages
        )
    
    elif name == "audit_obs_package":
        package_name = arguments["package_name"]
        
        # Get package info and spec file
        try:
            audit_result = await audit_obs_package(package_name)

            audit_summary = f"""
# Security Audit Report for {package_name}

## Spec File Security Analysis
- **Risk Score**: {audit_result.get('risk_score', 'N/A')}/100
- **Security Issues Found**: {len(audit_result.get('findings', []))}
- **Critical Issues**: {len([f for f in audit_result.get('findings', []) if f.get('severity') == 'critical'])}

## Recommendations
"""

            risk_score = audit_result.get('risk_score', 0)
            if risk_score > 70:
                audit_summary += "HIGH RISK - Consider finding an alternative package or reviewing the source code manually.\n"
            elif risk_score > 50:
                audit_summary += "MEDIUM RISK - Proceed with caution and review the findings below.\n"
            else:
                audit_summary += "LOW RISK - Package appears safe to install.\n"
            
            messages = [
                PromptMessage(
                    role="user",
                    content=PromptMessage.TextContent(
                        type="text",
                        text=f"Please audit the OBS package '{package_name}' for security issues before installation."
                    )
                ),
                PromptMessage(
                    role="assistant",
                    content=PromptMessage.TextContent(
                        type="text",
                        text=audit_summary
                    )
                )
            ]
            
            return GetPromptResult(
                description=f"Security audit for OBS package: {package_name}",
                messages=messages
            )
            
        except Exception as e:
            return GetPromptResult(
                description=f"Security audit for OBS package: {package_name}",
                messages=[
                    PromptMessage(
                        role="assistant",
                        content=PromptMessage.TextContent(
                            type="text",
                            text=f"Error auditing package '{package_name}': {str(e)}"
                        )
                    )
                ]
            )
    
    elif name == "analyze_dependencies":
        package_name = arguments["package_name"]
        
        # Check if it's an official package first
        try:
            official_info = await get_official_package_info(package_name)
            if official_info.get("found"):
                deps = official_info.get("dependencies", [])
                opt_deps = official_info.get("optional_dependencies", [])
                
                analysis = f"""
# Dependency Analysis for {package_name} (Official Package)

## Required Dependencies
{chr(10).join([f"- {dep}" for dep in deps]) if deps else "None"}

## Optional Dependencies
{chr(10).join([f"- {dep}" for dep in opt_deps]) if opt_deps else "None"}

## Installation Order
1. Install required dependencies first
2. Install optional dependencies as needed
3. Install {package_name} last

## Installation Commands
```bash
# Install required dependencies
sudo zypper install {' '.join(deps) if deps else '# No required dependencies'}

# Install optional dependencies (if needed)
sudo zypper install {' '.join(opt_deps) if opt_deps else '# No optional dependencies'}

# Install the package
sudo zypper install {package_name}
```
"""
            else:
                # Check OBS
                obs_info = await get_obs_info(package_name)
                if obs_info.get("found"):
                    analysis = f"""
# Dependency Analysis for {package_name} (OBS Package)

## OBS Package Information
- **Project**: {obs_info.get('project', 'Unknown')}
- **Description**: {obs_info.get('description', 'Unknown')}

## Installation Considerations
1. **Security Check**: Run a security audit before installation
2. **Dependencies**: OBS packages may have additional dependency requirements
3. **Repository**: Package needs to be added from OBS repository

## Recommended Installation Process
```bash
# 1. Add OBS repository (if not already added)
sudo zypper addrepo <obs-repo-url> {package_name}-repo

# 2. Refresh repositories
sudo zypper refresh

# 3. Install the package
sudo zypper install {package_name}
```

Important: Always audit OBS packages for security before installation!
"""
                else:
                    analysis = f"Package '{package_name}' not found in official repositories or OBS."
        
        except Exception as e:
            analysis = f"Error analyzing dependencies for '{package_name}': {str(e)}"
        
        return GetPromptResult(
            description=f"Dependency analysis for: {package_name}",
            messages=[
                PromptMessage(
                    role="user",
                    content=PromptMessage.TextContent(
                        type="text",
                        text=f"Please analyze the dependencies for the package '{package_name}' and suggest the best installation approach."
                    )
                ),
                PromptMessage(
                    role="assistant",
                    content=PromptMessage.TextContent(
                        type="text",
                        text=analysis
                    )
                )
            ]
        )
    
    elif name == "safe_system_update":
        if not IS_SUSE:
            return GetPromptResult(
                description="Safe system update workflow",
                messages=[
                    PromptMessage(
                        role="assistant",
                        content=PromptMessage.TextContent(
                            type="text",
                            text=create_platform_error_message("safe_system_update prompt")
                        )
                    )
                ]
            )
        
        analysis = "# Safe System Update Workflow\n\n"
        warnings = []
        recommendations = []
        
        # Step 1: Check for critical news
        try:
            critical_news = await check_critical_news(limit=10)
            
            if critical_news.get("has_critical"):
                analysis += "## ⚠️ Critical SUSE Linux News\n\n"
                for news_item in critical_news.get("critical_news", [])[:3]:
                    analysis += f"**{news_item['title']}**\n"
                    analysis += f"Published: {news_item['published']}\n"
                    analysis += f"{news_item['summary'][:200]}...\n"
                    analysis += f"[Read more]({news_item['link']})\n\n"
                
                warnings.append("Critical news requiring manual intervention found!")
                recommendations.append("Read all critical news articles before updating")
            else:
                analysis += "## ✓ No Critical News\n\nNo manual intervention required for recent updates.\n\n"
        except Exception as e:
            analysis += f"## ⚠️ News Check Failed\n\n{str(e)}\n\n"
        
        # Step 2: Check disk space
        try:
            disk_space = await check_disk_space()
            disk_usage = disk_space.get("disk_usage", {})
            
            analysis += "## Disk Space Status\n\n"
            for path, info in disk_usage.items():
                if "warning" in info:
                    analysis += f"- ⚠️ {path}: {info['available']} available ({info['use_percent']} used) - {info['warning']}\n"
                    warnings.append(f"Low disk space on {path}")
                else:
                    analysis += f"- ✓ {path}: {info['available']} available ({info['use_percent']} used)\n"
            analysis += "\n"
        except Exception as e:
            analysis += f"## ⚠️ Disk Space Check Failed\n\n{str(e)}\n\n"
        
        # Step 3: Check pending updates
        try:
            updates = await check_updates_dry_run()
            
            if updates.get("updates_available"):
                count = updates.get("count", 0)
                analysis += f"## Pending Updates ({count} packages)\n\n"
                
                # Show first 10 updates
                for update in updates.get("packages", [])[:10]:
                    analysis += f"- {update['package']}: {update['current_version']} → {update['new_version']}\n"
                
                if count > 10:
                    analysis += f"\n...and {count - 10} more packages\n"
                analysis += "\n"
            else:
                analysis += "## ✓ System Up to Date\n\nNo updates available.\n\n"
                return GetPromptResult(
                    description="System is already up to date",
                    messages=[
                        PromptMessage(
                            role="assistant",
                            content=PromptMessage.TextContent(
                                type="text",
                                text=analysis
                            )
                        )
                    ]
                )
        except Exception as e:
            analysis += f"## ⚠️ Update Check Failed\n\n{str(e)}\n\n"
        
        # Step 4: Check failed services
        try:
            failed_services = await check_failed_services()
            
            if not failed_services.get("all_ok"):
                analysis += "## ⚠️ Failed Services Detected\n\n"
                for service in failed_services.get("failed_services", [])[:5]:
                    analysis += f"- {service['unit']}\n"
                warnings.append("System has failed services")
                recommendations.append("Investigate failed services before updating")
                analysis += "\n"
            else:
                analysis += "## ✓ All Services Running\n\nNo failed systemd services.\n\n"
        except Exception as e:
            analysis += f"## ⚠️ Service Check Failed\n\n{str(e)}\n\n"
        
        # Step 5: Check database freshness
        try:
            db_freshness = await check_database_freshness()
            
            if db_freshness.get("needs_sync"):
                analysis += "## Database Synchronization\n\n"
                analysis += f"Databases are {db_freshness.get('oldest_age_hours', 0):.1f} hours old.\n"
                recommendations.append("Database will be synchronized during update")
                analysis += "\n"
        except Exception as e:
            logger.warning(f"Database freshness check failed: {e}")
        
        # Step 6: Summary and recommendations
        analysis += "## Recommendations\n\n"
        
        if warnings:
            analysis += "### Warnings:\n"
            for warning in warnings:
                analysis += f"- ⚠️ {warning}\n"
            analysis += "\n"
        
        if recommendations:
            analysis += "### Before Updating:\n"
            for rec in recommendations:
                analysis += f"- {rec}\n"
            analysis += "\n"
        
        if not warnings:
            analysis += "✓ System is ready for update\n\n"
            analysis += "Run: `sudo zypper update`\n"
        else:
            analysis += "⚠️ **Address warnings before updating**\n"
        
        return GetPromptResult(
            description="Safe system update analysis",
            messages=[
                PromptMessage(
                    role="user",
                    content=PromptMessage.TextContent(
                        type="text",
                        text="Check if my system is ready for a safe update"
                    )
                ),
                PromptMessage(
                    role="assistant",
                    content=PromptMessage.TextContent(
                        type="text",
                        text=analysis
                    )
                )
            ]
        )

    elif name == "cleanup_system":
        if not IS_SUSE:
            return GetPromptResult(
                description="System cleanup workflow",
                messages=[
                    PromptMessage(
                        role="assistant",
                        content=PromptMessage.TextContent(
                            type="text",
                            text=create_platform_error_message("cleanup_system prompt")
                        )
                    )
                ]
            )

        aggressive = arguments.get("aggressive", "false").lower() == "true"

        return GetPromptResult(
            description="System cleanup workflow",
            messages=[
                PromptMessage(
                    role="user",
                    content=PromptMessage.TextContent(
                        type="text",
                        text=f"""Please perform a comprehensive system cleanup:

1. **Check Orphaned Packages**:
   - Run manage_orphans with action='list'
   - Review the list for packages that can be safely removed
   {'   - Be aggressive: remove all orphans unless critical' if aggressive else '   - Be conservative: keep packages that might be useful'}

2. **Clean Package Cache**:
   - Run get_package_cache_stats
   - If cache is > 1GB or has > 100 packages, suggest cleanup
   - Provide command: sudo zypper clean (remove cached packages)

3. **Verify Package Integrity**:
   - For critical packages (kernel, systemd, zypper), run verify_package_integrity
   - Report any modified or missing files

4. **Check Database Freshness**:
   - Run check_database_freshness
   - If database is stale (> 7 days), suggest: sudo zypper refresh

5. **Summary**:
   - Space freed (estimate)
   - Packages removed
   - Integrity issues found
   - Recommended next steps

Be thorough and explain each step."""
                    )
                )
            ]
        )

    elif name == "package_investigation":
        package_name = arguments.get("package_name", "")

        if not package_name:
            return GetPromptResult(
                description="Package investigation workflow",
                messages=[
                    PromptMessage(
                        role="assistant",
                        content=PromptMessage.TextContent(
                            type="text",
                            text="Error: package_name argument is required"
                        )
                    )
                ]
            )

        return GetPromptResult(
            description=f"Deep investigation of package: {package_name}",
            messages=[
                PromptMessage(
                    role="user",
                    content=PromptMessage.TextContent(
                        type="text",
                        text=f"""Please investigate the package '{package_name}' thoroughly before installation:

1. **Check Official Repositories First**:
   - Run get_official_package_info("{package_name}")
   - If found in official repos: SAFE - recommend using zypper install
   - If not found: Continue to OBS investigation

2. **Search OBS** (if not in official repos):
   - Run search_obs("{package_name}")
   - Review: project, description, build status
   - Check for similar packages in better-maintained projects

3. **Security Analysis**:
   - Run audit_obs_security(action='full_audit', package_name='{package_name}')
   - Risk score interpretation:
     - 0-29: Low risk
     - 30-59: Medium risk - review findings
     - 60-100: High risk - DO NOT INSTALL

4. **Spec File Audit** (if proceeding with OBS):
   - Fetch spec file content
   - Run analyze_spec_security
   - Review scriptlet sections for dangerous commands

5. **Check Dependencies**:
   - Review BuildRequires and Requires from spec file
   - Check if dependencies are in official repos
   - Note any additional OBS repo requirements

6. **Final Recommendation**:
   - ✅ Safe to install (with command)
   - ⚠️ Proceed with caution (explain risks)
   - ⛔ Do not install (explain why)

7. **Alternative Suggestions**:
   - Suggest official repo alternatives if available
   - Suggest better-maintained OBS projects if found

Be comprehensive and explain security implications."""
                    )
                )
            ]
        )

    elif name == "mirror_optimization":
        country = arguments.get("country", "")

        return GetPromptResult(
            description="Mirror optimization workflow",
            messages=[
                PromptMessage(
                    role="user",
                    content=PromptMessage.TextContent(
                        type="text",
                        text=f"""Please optimize repository mirrors:

1. **List and Test Current Mirrors**:
   - Run optimize_mirrors(action='status', auto_test=True)
   - Show currently configured mirrors with their speeds
   - Identify slow mirrors (> 500ms)

2. **Suggest Optimal Mirrors**:
   - Run optimize_mirrors(action='suggest'{f', country="{country}"' if country else ''}, limit=10)
   - Based on geographic location and current status
   - Show top 10 recommended mirrors

3. **Health Check**:
   - Run optimize_mirrors(action='health')
   - Identify any configuration issues
   - Check for outdated or unreachable mirrors

4. **Recommendations**:
   - Suggest repository configuration changes
   - Provide commands to manage /etc/zypp/repos.d/ configuration
   - Recommend optimal repository setup

5. **Expected Benefits**:
   - Estimate download speed improvements
   - Reduced update times
   - Better reliability

Be detailed and provide specific mirror URLs and configuration commands."""
                    )
                )
            ]
        )

    elif name == "system_health_check":
        if not IS_SUSE:
            return GetPromptResult(
                description="System health check",
                messages=[
                    PromptMessage(
                        role="assistant",
                        content=PromptMessage.TextContent(
                            type="text",
                            text=create_platform_error_message("system_health_check prompt")
                        )
                    )
                ]
            )

        return GetPromptResult(
            description="Comprehensive system health check",
            messages=[
                PromptMessage(
                    role="user",
                    content=PromptMessage.TextContent(
                        type="text",
                        text="""Please perform a comprehensive system health diagnostic:

1. **System Information**:
   - Run get_system_info
   - Review kernel version, uptime, memory usage
   - Check for abnormalities

2. **Disk Space Analysis**:
   - Run check_disk_space
   - Identify partitions with low space
   - Run get_package_cache_stats
   - Calculate total reclaimable space

3. **Service Health**:
   - Run check_failed_services
   - List all failed systemd services
   - If failures found, run get_boot_logs to investigate

4. **Package Database Health**:
   - Run check_database_freshness
   - Check when last synchronized
   - Check for failed transactions in zypp history
   - Identify any package operation failures

5. **Package Integrity**:
   - Run manage_orphans with action='list'
   - Count orphaned packages and space used
   - Suggest running verify_package_integrity on critical packages

6. **Configuration Health**:
   - Run analyze_zypper_conf (focus='full') for full config
   - Run analyze_zypper_conf (focus='ignored_packages') to check for ignored critical packages
   - Warn about critical packages being ignored

7. **Mirror Health**:
   - Run optimize_mirrors(action='health')
   - Identify mirror issues

8. **Summary Report**:
   - Overall health status (Healthy/Warnings/Critical)
   - List of issues found with severity levels
   - Prioritized recommendations for fixes
   - Estimate of system optimization potential

Be thorough and provide actionable recommendations with specific commands."""
                    )
                )
            ]
        )

    else:
        raise ValueError(f"Unknown prompt: {name}")
