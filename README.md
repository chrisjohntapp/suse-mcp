# SUSE Linux MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that bridges AI assistants with the SUSE Linux ecosystem. Enables safe, reliable access to the openSUSE Wiki, OBS (Open Build Service), and SUSE repositories for AI-assisted system management.

Supports all SUSE variants: openSUSE Tumbleweed, Leap, MicroOS, Slowroll, SLES, SLED, and SLE Micro. Immutable variants use `transactional-update` automatically.

## Resources (URI-based Access)

### Documentation and Search

| URI Scheme | Example | Returns |
|---|---|---|
| `opensuse-wiki://` | `opensuse-wiki://Installation_guide` | Markdown-formatted Wiki page |

### Package Information

| URI Scheme | Example | Returns |
|---|---|---|
| `suse-repo://` | `suse-repo://vim` | Official repository package details |
| `obs://*/spec` | `obs://vim/spec` | OBS spec file with safety analysis |
| `obs://*/info` | `obs://vim/info` | OBS package metadata |

### System Packages (SUSE only)

| URI Scheme | Example | Returns |
|---|---|---|
| `zypper://installed` | `zypper://installed` | Installed packages list |
| `zypper://orphans` | `zypper://orphans` | Orphaned packages |
| `zypper://explicit` | `zypper://explicit` | Explicitly installed packages |
| `zypper://patterns` | `zypper://patterns` | Zypper patterns |
| `zypper://database/freshness` | `zypper://database/freshness` | Package database sync status |

### System Monitoring and Logs

| URI Scheme | Example | Returns |
|---|---|---|
| `system://info` | `system://info` | System information (kernel, memory, uptime) |
| `system://disk` | `system://disk` | Disk space usage statistics |
| `system://services/failed` | `system://services/failed` | Failed systemd services |
| `system://logs/boot` | `system://logs/boot` | Recent boot logs |
| `system://health` | `system://health` | System health check |
| `zypper://log/recent` | `zypper://log/recent` | Recent package transactions |
| `zypper://log/failed` | `zypper://log/failed` | Failed package transactions |

### News and Updates

| URI Scheme | Example | Returns |
|---|---|---|
| `opensuse-news://latest` | `opensuse-news://latest` | Latest openSUSE news |
| `opensuse-news://critical` | `opensuse-news://critical` | Critical news requiring manual intervention |
| `opensuse-news://since-update` | `opensuse-news://since-update` | News since last system update |

### Configuration

| URI Scheme | Example | Returns |
|---|---|---|
| `config://zypper` | `config://zypper` | Parsed zypper.conf configuration |
| `config://rpm-macros` | `config://rpm-macros` | Parsed RPM macros configuration |
| `mirrors://active` | `mirrors://active` | Currently configured repositories |
| `mirrors://health` | `mirrors://health` | Repository health status |

## Tools

| Tool | Description |
|---|---|
| `search_opensuse_wiki` | Query openSUSE Wiki with ranked results |
| `search_obs` | Search OBS packages |
| `get_official_package_info` | Get official package details |
| `check_updates_dry_run` | Check for available updates |
| `install_obs_package` | Install OBS package with security checks |
| `audit_obs_security` | Security audit for OBS packages (spec analysis, full audit) |
| `remove_packages` | Remove packages (single or batch) |
| `manage_orphans` | List or remove orphaned packages |
| `query_file_ownership` | File-package ownership queries |
| `verify_package_integrity` | Check file integrity |
| `manage_patterns` | List and inspect zypper patterns |
| `manage_install_reason` | Manage install reasons (explicit/dependency) |
| `get_system_info` | System info (kernel, memory, uptime) |
| `analyze_storage` | Disk usage and cache statistics |
| `diagnose_system` | System diagnostics |
| `fetch_news` | Fetch openSUSE news |
| `query_package_history` | Query zypp transaction history |
| `optimize_mirrors` | Repository management (status, test, suggest, health) |
| `analyze_zypper_conf` | Parse zypper.conf settings |
| `analyze_rpm_macros` | Parse RPM macros configuration |
| `check_database_freshness` | Check package database sync status |
| `run_system_health_check` | Comprehensive system health check |

## Prompts

| Prompt | Purpose |
|---|---|
| `troubleshoot_issue` | Diagnose system errors using openSUSE Wiki |
| `audit_obs_package` | Pre-installation security audit of OBS packages |
| `analyze_dependencies` | Dependency analysis and install order |
| `safe_system_update` | Safe update workflow with pre-flight checks |
| `cleanup_system` | System cleanup (orphans, cache, integrity) |
| `package_investigation` | Deep package research before installation |
| `mirror_optimization` | Test and configure fastest mirrors |
| `system_health_check` | Comprehensive system diagnostic |

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Quick Start

```bash
uv run suse-ops-server
```

## Configuration

Add to your MCP client configuration (Claude, Cursor, or any STDIO-compatible client):

```json
{
  "mcpServers": {
    "suse-linux": {
      "command": "uv",
      "args": ["run", "suse-ops-server"]
    }
  }
}
```

## Container

```bash
podman build -f Containerfile .
podman run -i suse-mcp-server
```

## License

This project is dual-licensed under your choice of:

- **[GPL-3.0-only](https://www.gnu.org/licenses/gpl-3.0.en.html)** - See [LICENSE-GPL](LICENSE-GPL)
- **[MIT License](https://opensource.org/licenses/MIT)** - See [LICENSE-MIT](LICENSE-MIT)
