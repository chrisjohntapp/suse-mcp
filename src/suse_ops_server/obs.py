# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
OBS (Open Build Service) interface module.
Provides search, package info, and .spec file retrieval via OBS API.
"""

import logging
import os
import re
from typing import Dict, Any, Optional
import httpx

from .utils import IS_IMMUTABLE, run_command, create_error_response

logger = logging.getLogger(__name__)

OBS_API_URL = os.environ.get("OBS_API_URL", "https://api.opensuse.org")
DEFAULT_TIMEOUT = 10.0


async def search_obs(query: str, limit: int = 20) -> Dict[str, Any]:
    """
    Search OBS packages.

    Args:
        query: Search term
        limit: Maximum results (default 20)

    Returns:
        Dict with matching packages
    """
    logger.info("Searching OBS for: %s", query)

    try:
        url = f"{OBS_API_URL}/search/package"
        params = {"match": f"@name+contains+'{query}'", "limit": limit}
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            xml_text = response.text

        packages = _parse_search_xml(xml_text)
        return {
            "query": query,
            "count": len(packages),
            "packages": packages,
        }

    except httpx.TimeoutException:
        return create_error_response("TimeoutError", f"OBS search timed out for: {query}")
    except httpx.HTTPStatusError as e:
        return create_error_response("HTTPError", f"OBS search failed with HTTP {e.response.status_code}")
    except Exception as e:
        logger.error("OBS search failed: %s", e)
        return create_error_response("SearchError", f"Failed to search OBS: {str(e)}")


def _parse_search_xml(xml_text: str) -> list:
    """Parse OBS search XML response."""
    from xml.etree import ElementTree as ET
    packages = []
    try:
        root = ET.fromstring(xml_text)
        for pkg in root.findall("package"):
            packages.append({
                "name": pkg.get("name", ""),
                "project": pkg.get("project", ""),
            })
    except ET.ParseError as e:
        logger.warning("Failed to parse OBS search XML: %s", e)
    return packages


async def get_obs_info(package_name: str, project: str = "openSUSE:Factory") -> Dict[str, Any]:
    """
    Get OBS package metadata.

    Args:
        package_name: Package name
        project: OBS project (default openSUSE:Factory)

    Returns:
        Dict with package metadata
    """
    logger.info("Fetching OBS info for: %s/%s", project, package_name)

    try:
        url = f"{OBS_API_URL}/package/metadata/{project}/{package_name}"
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            xml_text = response.text

        return {
            "package": package_name,
            "project": project,
            "metadata": xml_text,
        }

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return create_error_response("NotFound", f"Package '{package_name}' not found in {project}")
        return create_error_response("HTTPError", f"OBS metadata fetch failed with HTTP {e.response.status_code}")
    except httpx.TimeoutException:
        return create_error_response("TimeoutError", f"OBS metadata request timed out for: {package_name}")
    except Exception as e:
        logger.error("OBS info fetch failed: %s", e)
        return create_error_response("FetchError", f"Failed to get OBS package info: {str(e)}")


async def get_spec_file(package_name: str, project: str = "openSUSE:Factory") -> Dict[str, Any]:
    """
    Retrieve .spec file content from OBS.

    Args:
        package_name: Package name
        project: OBS project (default openSUSE:Factory)

    Returns:
        Dict with spec file content
    """
    logger.info("Fetching .spec file for: %s/%s", project, package_name)

    try:
        url = f"{OBS_API_URL}/source/{project}/{package_name}/{package_name}.spec"
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            spec_content = response.text

        return {
            "package": package_name,
            "project": project,
            "spec_content": spec_content,
        }

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return create_error_response("NotFound", f"Spec file not found for '{package_name}' in {project}")
        return create_error_response("HTTPError", f"Spec file fetch failed with HTTP {e.response.status_code}")
    except httpx.TimeoutException:
        return create_error_response("TimeoutError", f"Spec file request timed out for: {package_name}")
    except Exception as e:
        logger.error("Spec file fetch failed: %s", e)
        return create_error_response("FetchError", f"Failed to get spec file: {str(e)}")


def analyze_spec_security(spec_content: str) -> Dict[str, Any]:
    """
    Analyze a .spec file for risky %pre/%post scriptlets.

    Args:
        spec_content: Content of the .spec file

    Returns:
        Dict with security analysis results
    """
    risks = []
    risk_patterns = [
        (r'curl\s+\S+\s*\|\s*(?:ba)?sh', "Downloads and pipes to shell (curl|sh)"),
        (r'wget\s+-[^\s]*\s+\S+\s*\|\s*(?:ba)?sh', "Downloads and pipes to shell (wget|sh)"),
        (r'wget\s+.*-O\s*-.*\|\s*(?:ba)?sh', "Downloads and pipes to shell (wget -O -|sh)"),
        (r'eval\s+.*base64', "Evaluates base64-encoded payload"),
        (r'rm\s+-[rf]{1,2}\s+/', "Deletes from root filesystem"),
        (r':\(\)\s*\{.*:\|:&\s*\}', "Fork bomb detected"),
        (r'chmod\s+[0-7]*7[0-7]*\s+/', "Makes root paths world-writable"),
    ]

    in_scriptlet = False
    scriptlet_name = ""
    scriptlet_lines = []

    for line in spec_content.splitlines():
        stripped = line.strip()
        if re.match(r'^%(pre|post|preun|postun|pretrans|posttrans)\b', stripped):
            in_scriptlet = True
            scriptlet_name = stripped.split()[0]
            scriptlet_lines = []
        elif re.match(r'^%\w', stripped) and in_scriptlet:
            in_scriptlet = False
            scriptlet_lines = []
        elif in_scriptlet:
            scriptlet_lines.append(line)
            for pattern, description in risk_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    risks.append({
                        "scriptlet": scriptlet_name,
                        "line": line.strip(),
                        "description": description,
                    })

    return {
        "has_risks": len(risks) > 0,
        "risk_count": len(risks),
        "risks": risks,
    }


async def audit_obs_package(package_name: str, project: str = "openSUSE:Factory") -> Dict[str, Any]:
    """
    Fetch spec file and analyze for security risks.

    Args:
        package_name: Package name
        project: OBS project (default openSUSE:Factory)

    Returns:
        Dict with security audit results
    """
    spec_result = await get_spec_file(package_name, project)

    if "error" in spec_result:
        return spec_result

    spec_content = spec_result.get("spec_content", "")
    security = analyze_spec_security(spec_content)

    return {
        "package": package_name,
        "project": project,
        "security": security,
        "recommendation": "CAUTION: Review risky scriptlets before installing" if security["has_risks"] else "No obvious security risks found in scriptlets",
    }


async def install_obs_package(package_name: str) -> Dict[str, Any]:
    """
    Install a package using zypper (or transactional-update on immutable variants).

    Args:
        package_name: Package name to install

    Returns:
        Dict with installation result
    """
    if IS_IMMUTABLE:
        cmd = ["sudo", "transactional-update", "pkg", "install", package_name]
    else:
        cmd = ["sudo", "zypper", "--non-interactive", "install", package_name]

    logger.info("Installing OBS package: %s", package_name)

    try:
        exit_code, stdout, stderr = await run_command(cmd, timeout=120)
        if exit_code != 0:
            return create_error_response("InstallError", f"Failed to install {package_name}: {stderr}")
        return {
            "package": package_name,
            "installed": True,
            "output": stdout,
            "note": "Reboot required to activate changes" if IS_IMMUTABLE else "",
        }
    except Exception as e:
        logger.error("Package install failed: %s", e)
        return create_error_response("InstallError", f"Failed to install package: {str(e)}")
