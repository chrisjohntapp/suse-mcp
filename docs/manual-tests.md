# Manual Tests

Tools marked (any system) work without a SUSE Linux host. All others require a running SUSE Linux system.

---

## Tools

### search_opensuse_wiki (any system)

Search the openSUSE Wiki for documentation pages.

- [ ] Ask: "Search the openSUSE Wiki for 'zypper'" - verify at least one result is returned with a title and URL.

---

### search_obs (any system)

Search the Open Build Service for packages.

- [ ] Ask: "Search OBS for 'neovim'" - verify results include package names, projects, and descriptions.

---

### get_official_package_info (any system)

Get information about a package from official SUSE repositories.

- [ ] Ask: "Get official package info for 'bash'" - verify version, description, and repository are returned.

---

### fetch_news - latest (any system)

Fetch recent openSUSE news from the RSS feed.

- [ ] Ask: "Fetch the latest 5 openSUSE news items" - verify 5 items are returned with titles and dates.

---

### fetch_news - critical (any system)

Find openSUSE news items requiring manual intervention.

- [ ] Ask: "Check for critical openSUSE news" - verify the response indicates checked_items count (result may have zero critical items, which is valid).

---

### fetch_news - since_update (SUSE only)

Get news posted since the last zypper system update.

- [ ] Ask: "Fetch openSUSE news since last system update" - verify the response includes a last_update timestamp and a list of news items.

---

### audit_obs_security - full_audit (any system)

Run a security audit on an OBS package by fetching and analyzing its spec file.

- [ ] Ask: "Audit OBS package 'vim' for security issues" - verify a risk level and findings list are returned.

---

### audit_obs_security - spec_analysis (any system)

Analyze a provided spec file content for security red flags.

- [ ] Ask: "Analyze this spec file for security issues: `Name: test\nVersion: 1.0\n%post\nrm -rf /`" - verify the response flags the destructive command.

---

### get_system_info (any system)

Get kernel version, architecture, hostname, uptime, and memory statistics.

- [ ] Ask: "Get system information" - verify kernel version, architecture, and memory fields are present in the response.

---

### analyze_storage - disk_usage (any system)

Check disk space usage for critical paths.

- [ ] Ask: "Check disk usage" - verify filesystem mount points and usage percentages are returned.

---

### analyze_storage - cache_stats (SUSE only)

Analyze the zypp package cache size and contents.

- [ ] Ask: "Check zypper cache stats" - verify cache size and package count are returned.

---

### diagnose_system - failed_services

Check for failed systemd services.

- [ ] Ask: "Check for failed systemd services" - verify the response lists failed services or confirms none are failed.

---

### diagnose_system - boot_logs

Retrieve recent boot log entries from journalctl.

- [ ] Ask: "Show the last 50 boot log lines" - verify log lines are returned.

---

### check_updates_dry_run (SUSE only)

Preview available system updates without applying them.

- [ ] Ask: "Check for available system updates without installing" - verify pending update packages or a message that the system is up to date is returned.

---

### install_obs_package (SUSE only)

Install a package from OBS after security checks.

- [ ] Ask: "Install OBS package 'hello'" - verify the tool performs a security audit step before attempting installation.

---

### remove_packages (SUSE only)

Remove one or more installed packages.

- [ ] Ask: "Remove package 'hello'" - verify the tool reports the package was removed or was not installed.

---

### manage_orphans - list (SUSE only)

List packages installed as dependencies that are no longer required.

- [ ] Ask: "List orphaned packages" - verify a list of orphaned packages or a message that none exist is returned.

---

### manage_orphans - remove (SUSE only)

Remove orphaned packages (dry run by default).

- [ ] Ask: "Show what orphan packages would be removed (dry run)" - verify a dry-run preview is returned without any packages being removed.

---

### query_file_ownership - file_to_package (SUSE only)

Find which package owns a given file.

- [ ] Ask: "Which package owns /usr/bin/bash?" - verify the response names the owning package (e.g., `bash`).

---

### query_file_ownership - package_to_files (SUSE only)

List all files belonging to a package.

- [ ] Ask: "List files in the 'bash' package" - verify a list of file paths is returned.

---

### query_file_ownership - filename_search (SUSE only)

Search for a filename pattern across all installed packages.

- [ ] Ask: "Search for files matching '*.desktop' across all packages" - verify matching file paths and their owning packages are returned.

---

### verify_package_integrity (SUSE only)

Verify installed package files against expected checksums.

- [ ] Ask: "Verify integrity of the 'bash' package" - verify the response shows files checked and any discrepancies (or confirms all files are intact).

---

### manage_patterns - list_patterns (SUSE only)

List all available zypper patterns.

- [ ] Ask: "List all zypper patterns" - verify a list of pattern names is returned.

---

### manage_patterns - pattern_info (SUSE only)

Show details about a specific zypper pattern.

- [ ] Ask: "Show info for the 'base' zypper pattern" - verify pattern description and included packages are returned.

---

### manage_install_reason - list (SUSE only)

List all packages explicitly installed by the user.

- [ ] Ask: "List all explicitly installed packages" - verify a list of package names is returned.

---

### manage_install_reason - mark_explicit (SUSE only)

Mark a package as explicitly installed to prevent auto-removal.

- [ ] Ask: "Mark 'vim' as explicitly installed" - verify the response confirms the install reason was updated.

---

### manage_install_reason - mark_dependency (SUSE only)

Mark a package as a dependency so it can be auto-removed with orphans.

- [ ] Ask: "Mark 'vim' as a dependency install" - verify the response confirms the install reason was updated.

---

### query_package_history - all (SUSE only)

Show recent package transactions from zypp history.

- [ ] Ask: "Show last 10 package transactions" - verify a list of timestamped install/update/remove events is returned.

---

### query_package_history - package (SUSE only)

Show install and upgrade history for a specific package.

- [ ] Ask: "Show history for package 'bash'" - verify timestamps and actions for the package are returned.

---

### query_package_history - failures (SUSE only)

Find failed package transactions in the zypp log.

- [ ] Ask: "Show failed package transactions" - verify the response lists failures or confirms none exist.

---

### query_package_history - sync (SUSE only)

Show database synchronization history.

- [ ] Ask: "Show zypper database sync history" - verify a list of sync timestamps is returned.

---

### optimize_mirrors - status (SUSE only)

List currently configured repositories.

- [ ] Ask: "Show configured zypper repositories" - verify repository names, URLs, and enabled status are returned.

---

### optimize_mirrors - health (SUSE only)

Run a full health check on configured repositories.

- [ ] Ask: "Check repository health" - verify the response includes a health assessment and any recommendations.

---

### analyze_zypper_conf (SUSE only)

Parse and analyze zypper.conf settings.

- [ ] Ask: "Analyze zypper configuration" - verify the response includes settings such as parallel downloads and any ignored packages.

---

### analyze_rpm_macros (SUSE only)

Parse and analyze rpm macro settings including CFLAGS and build configuration.

- [ ] Ask: "Analyze rpm macros" - verify CFLAGS, MAKEFLAGS, and compression settings are returned.

---

### check_database_freshness (SUSE only)

Check when package databases were last synchronized.

- [ ] Ask: "Check zypper database freshness" - verify timestamps for last sync and a staleness warning if applicable are returned.

---

### run_system_health_check (SUSE only)

Run a comprehensive system health check covering disk, services, updates, and news.

- [ ] Ask: "Run a full system health check" - verify the response includes sections for disk space, failed services, pending updates, orphans, and critical news.

---

## Resources

Resources are URI-addressable read-only data exposed by the server.

### opensuse-wiki://{page_title} (any system)

- [ ] Read `opensuse-wiki://Installation_guide` - verify markdown content of the openSUSE installation guide is returned.

---

### obs://{package}/info (any system)

- [ ] Read `obs://vim/info` - verify JSON metadata for the vim OBS package is returned.

---

### obs://{package}/spec (any system)

- [ ] Read `obs://vim/spec` - verify the raw RPM spec file for vim is returned.

---

### suse-repo://{package} (any system)

- [ ] Read `suse-repo://bash` - verify official repository metadata for bash is returned.

---

### zypper://installed (SUSE only)

- [ ] Read `zypper://installed` - verify a JSON list of installed packages is returned.

---

### zypper://orphans (SUSE only)

- [ ] Read `zypper://orphans` - verify a JSON list of orphaned packages (or empty list) is returned.

---

### zypper://explicit (SUSE only)

- [ ] Read `zypper://explicit` - verify a JSON list of explicitly installed packages is returned.

---

### zypper://patterns (SUSE only)

- [ ] Read `zypper://patterns` - verify a JSON list of zypper patterns is returned.

---

### system://info (any system)

- [ ] Read `system://info` - verify JSON with kernel version, architecture, hostname, and memory is returned.

---

### system://disk (any system)

- [ ] Read `system://disk` - verify JSON with filesystem usage for critical paths is returned.

---

### system://services/failed

- [ ] Read `system://services/failed` - verify JSON listing failed systemd services (or empty list) is returned.

---

### system://logs/boot

- [ ] Read `system://logs/boot` - verify recent journalctl boot log lines are returned.

---

### opensuse-news://latest (any system)

- [ ] Read `opensuse-news://latest` - verify JSON with recent openSUSE news items is returned.

---

### opensuse-news://critical (any system)

- [ ] Read `opensuse-news://critical` - verify JSON with critical news items (or empty list) is returned.

---

### opensuse-news://since-update (SUSE only)

- [ ] Read `opensuse-news://since-update` - verify JSON with news since last zypper update is returned.

---

### zypper://log/recent (SUSE only)

- [ ] Read `zypper://log/recent` - verify JSON with recent zypper transaction history is returned.

---

### zypper://log/failed (SUSE only)

- [ ] Read `zypper://log/failed` - verify JSON with failed zypper transactions (or empty list) is returned.

---

### mirrors://active (SUSE only)

- [ ] Read `mirrors://active` - verify JSON with active mirror/repository configuration is returned.

---

### mirrors://health (SUSE only)

- [ ] Read `mirrors://health` - verify JSON with mirror health assessment and recommendations is returned.

---

### config://zypper (SUSE only)

- [ ] Read `config://zypper` - verify JSON with parsed zypper.conf settings is returned.

---

### config://rpm-macros (SUSE only)

- [ ] Read `config://rpm-macros` - verify JSON with parsed rpm macro values is returned.

---

### zypper://database/freshness (SUSE only)

- [ ] Read `zypper://database/freshness` - verify JSON with database sync timestamps and staleness status is returned.

---

### system://health (SUSE only)

- [ ] Read `system://health` - verify JSON with comprehensive system health report is returned.
