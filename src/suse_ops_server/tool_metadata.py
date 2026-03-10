# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Tool metadata and relationship definitions.

Provides structured information about tool categories, relationships, and workflows
to improve tool discovery and organization.
"""

from typing import List, Literal
from dataclasses import dataclass, field

# Type aliases for clarity
Category = Literal[
    "discovery",
    "lifecycle",
    "maintenance",
    "organization",
    "security",
    "monitoring",
    "history",
    "mirrors",
    "config"
]

Platform = Literal["any", "suse", "systemd"]
Permission = Literal["read", "write"]


@dataclass
class ToolMetadata:
    """Metadata for a single tool."""
    name: str
    category: Category
    platform: Platform
    permission: Permission
    workflow: str
    related_tools: List[str] = field(default_factory=list)
    prerequisite_tools: List[str] = field(default_factory=list)


TOOL_METADATA = {
     # Discovery & Information
     "search_opensuse_wiki": ToolMetadata(
         name="search_opensuse_wiki",
         category="discovery",
         platform="any",
         permission="read",
         workflow="research",
         related_tools=["search_obs", "get_official_package_info"],
         prerequisite_tools=[]
     ),
      "search_obs": ToolMetadata(
          name="search_obs",
          category="discovery",
          platform="any",
          permission="read",
          workflow="research",
          related_tools=[
              "get_official_package_info",
              "audit_obs_security",
              "install_obs_package"
          ],
          prerequisite_tools=[]
      ),
     "get_official_package_info": ToolMetadata(
         name="get_official_package_info",
         category="discovery",
         platform="any",
         permission="read",
         workflow="research",
         related_tools=["search_obs", "install_obs_package"],
         prerequisite_tools=[]
     ),
     "fetch_news": ToolMetadata(
         name="fetch_news",
         category="discovery",
         platform="any",
         permission="read",
         workflow="safety",
         related_tools=["check_updates_dry_run"],
         prerequisite_tools=[]
     ),

    # Package Lifecycle
    "check_updates_dry_run": ToolMetadata(
        name="check_updates_dry_run",
        category="lifecycle",
        platform="suse",
        permission="read",
        workflow="update",
        related_tools=["check_critical_news", "check_disk_space"],
        prerequisite_tools=[]
    ),
     "install_obs_package": ToolMetadata(
         name="install_obs_package",
         category="lifecycle",
         platform="suse",
         permission="write",
         workflow="installation",
         related_tools=[
             "check_updates_dry_run",
             "verify_package_integrity",
             "query_package_history"
         ],
         prerequisite_tools=[
             "get_official_package_info",
             "audit_obs_security"
         ]
     ),

    # Package Maintenance
    "verify_package_integrity": ToolMetadata(
        name="verify_package_integrity",
        category="maintenance",
        platform="suse",
        permission="read",
        workflow="verify",
        related_tools=["query_package_history", "query_file_ownership"],
        prerequisite_tools=[]
    ),
    "check_database_freshness": ToolMetadata(
        name="check_database_freshness",
        category="maintenance",
        platform="suse",
        permission="read",
        workflow="verify",
        related_tools=["query_package_history"],
        prerequisite_tools=[]
    ),

    # File Organization
    "query_file_ownership": ToolMetadata(
        name="query_file_ownership",
        category="organization",
        platform="suse",
        permission="read",
        workflow="debug",
        related_tools=["verify_package_integrity", "manage_patterns"],
        prerequisite_tools=[]
    ),
    "manage_patterns": ToolMetadata(
        name="manage_patterns",
        category="organization",
        platform="suse",
        permission="read",
        workflow="explore",
        related_tools=["query_file_ownership"],
        prerequisite_tools=[]
    ),

     # Security Analysis
     "audit_obs_security": ToolMetadata(
         name="audit_obs_security",
         category="security",
         platform="any",
         permission="read",
         workflow="audit",
         related_tools=["search_obs", "install_obs_package"],
         prerequisite_tools=[]
     ),

    # System Monitoring
    "get_system_info": ToolMetadata(
        name="get_system_info",
        category="monitoring",
        platform="any",
        permission="read",
        workflow="diagnose",
        related_tools=["analyze_storage", "check_failed_services"],
        prerequisite_tools=[]
    ),
    "analyze_storage": ToolMetadata(
        name="analyze_storage",
        category="monitoring",
        platform="any",
        permission="read",
        workflow="diagnose",
        related_tools=["check_failed_services"],
        prerequisite_tools=[]
    ),
    "diagnose_system": ToolMetadata(
        name="diagnose_system",
        category="monitoring",
        platform="systemd",
        permission="read",
        workflow="diagnose",
        related_tools=["analyze_storage"],
        prerequisite_tools=[]
    ),
    "run_system_health_check": ToolMetadata(
        name="run_system_health_check",
        category="monitoring",
        platform="suse",
        permission="read",
        workflow="diagnose",
        related_tools=[
            "get_system_info",
            "analyze_storage",
            "check_failed_services",
            "check_updates_dry_run",
            "check_critical_news",
            "manage_orphans",
            "check_database_freshness",
            "optimize_mirrors"
        ],
        prerequisite_tools=[]
    ),

    # Package Removal & Maintenance
    "remove_packages": ToolMetadata(
        name="remove_packages",
        category="lifecycle",
        platform="suse",
        permission="write",
        workflow="removal",
        related_tools=["manage_orphans", "verify_package_integrity"],
        prerequisite_tools=[]
    ),
    "manage_orphans": ToolMetadata(
        name="manage_orphans",
        category="maintenance",
        platform="suse",
        permission="write",
        workflow="cleanup",
        related_tools=["remove_packages", "manage_install_reason"],
        prerequisite_tools=[]
    ),
    "query_package_history": ToolMetadata(
        name="query_package_history",
        category="history",
        platform="suse",
        permission="read",
        workflow="audit",
        related_tools=["verify_package_integrity", "check_database_freshness"],
        prerequisite_tools=[]
    ),
    "manage_install_reason": ToolMetadata(
        name="manage_install_reason",
        category="maintenance",
        platform="suse",
        permission="write",
        workflow="organize",
        related_tools=["manage_orphans", "query_package_history"],
        prerequisite_tools=[]
    ),

    # Mirror Management
    "optimize_mirrors": ToolMetadata(
        name="optimize_mirrors",
        category="mirrors",
        platform="suse",
        permission="read",
        workflow="optimize",
        related_tools=["analyze_zypper_conf", "check_disk_space"],
        prerequisite_tools=[]
    ),

    # Configuration Management
    "analyze_zypper_conf": ToolMetadata(
        name="analyze_zypper_conf",
        category="config",
        platform="suse",
        permission="read",
        workflow="explore",
        related_tools=["analyze_rpm_macros", "optimize_mirrors"],
        prerequisite_tools=[]
    ),
    "analyze_rpm_macros": ToolMetadata(
        name="analyze_rpm_macros",
        category="config",
        platform="suse",
        permission="read",
        workflow="explore",
        related_tools=["analyze_zypper_conf"],
        prerequisite_tools=[]
    ),
}


CATEGORIES = {
    "discovery": {
        "name": "Discovery & Information",
        "description": "Search and retrieve package/documentation information",
    },
    "lifecycle": {
        "name": "Package Lifecycle",
        "description": "Install, update, and remove packages",
    },
    "maintenance": {
        "name": "Package Maintenance",
        "description": "Analyze, verify, and maintain package health",
    },
    "organization": {
        "name": "File Organization",
        "description": "Navigate package-file relationships",
    },
    "security": {
        "name": "Security Analysis",
        "description": "Evaluate package safety before installation",
    },
    "monitoring": {
        "name": "System Monitoring",
        "description": "Monitor system health and diagnostics",
    },
    "history": {
        "name": "Transaction History",
        "description": "Audit package operations",
    },
    "mirrors": {
        "name": "Mirror Management",
        "description": "Optimize repository mirrors",
    },
    "config": {
        "name": "Configuration",
        "description": "Analyze system configuration",
    }
}


def get_tools_by_category(category: Category) -> List[str]:
    return [
        name for name, meta in TOOL_METADATA.items()
        if meta.category == category
    ]


def get_tools_by_platform(platform: Platform) -> List[str]:
    return [
        name for name, meta in TOOL_METADATA.items()
        if meta.platform == platform or meta.platform == "any"
    ]


def get_tools_by_permission(permission: Permission) -> List[str]:
    return [
        name for name, meta in TOOL_METADATA.items()
        if meta.permission == permission
    ]


def get_related_tools(tool_name: str) -> List[str]:
    if tool_name not in TOOL_METADATA:
        return []
    return TOOL_METADATA[tool_name].related_tools


def get_prerequisite_tools(tool_name: str) -> List[str]:
    if tool_name not in TOOL_METADATA:
        return []
    return TOOL_METADATA[tool_name].prerequisite_tools


def get_workflow_tools(workflow: str) -> List[str]:
    return [
        name for name, meta in TOOL_METADATA.items()
        if meta.workflow == workflow
    ]


def get_category_info(category: Category) -> dict:
    return CATEGORIES.get(category, {})


def get_tool_statistics() -> dict:
    category_counts = {}
    platform_counts = {}
    permission_counts = {}

    for meta in TOOL_METADATA.values():
        category_counts[meta.category] = category_counts.get(meta.category, 0) + 1
        platform_counts[meta.platform] = platform_counts.get(meta.platform, 0) + 1
        permission_counts[meta.permission] = permission_counts.get(meta.permission, 0) + 1

    return {
        "total_tools": len(TOOL_METADATA),
        "by_category": category_counts,
        "by_platform": platform_counts,
        "by_permission": permission_counts
    }
