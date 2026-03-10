# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
Tests for suse_ops_server.news module (openSUSE news feed).
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from suse_ops_server.news import (
    OPENSUSE_NEWS_URL,
    CRITICAL_KEYWORDS,
    get_latest_news,
    check_critical_news,
    get_news_since_last_update,
)


SAMPLE_RSS_FEED = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
    <channel>
        <title>openSUSE News</title>
        <item>
            <title>Manual intervention required for foo package</title>
            <link>https://news.opensuse.org/manual-intervention-foo/</link>
            <pubDate>Mon, 10 Nov 2025 10:00:00 +0000</pubDate>
            <description><![CDATA[<p>Action required before upgrading foo package.</p>]]></description>
        </item>
        <item>
            <title>New kernel release 6.7</title>
            <link>https://news.opensuse.org/kernel-6-7/</link>
            <pubDate>Sun, 09 Nov 2025 14:00:00 +0000</pubDate>
            <description><![CDATA[<p>The Linux kernel has been updated to version 6.7.</p>]]></description>
        </item>
        <item>
            <title>Breaking change in systemd</title>
            <link>https://news.opensuse.org/systemd-breaking/</link>
            <pubDate>Sat, 08 Nov 2025 09:00:00 +0000</pubDate>
            <description><![CDATA[<p>Important changes in systemd configuration.</p>]]></description>
        </item>
    </channel>
</rss>
"""


def _mock_rss_response(feed_content):
    mock = MagicMock()
    mock.content = feed_content.encode("utf-8")
    mock.raise_for_status = MagicMock()
    return mock


class TestNewsRetrieval:
    """Test openSUSE news feed retrieval."""

    @pytest.mark.asyncio
    async def test_get_latest_news_success(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=_mock_rss_response(SAMPLE_RSS_FEED)
            )
            result = await get_latest_news(limit=10)
            assert result["count"] == 3
            assert len(result["news"]) == 3
            assert result["news"][0]["title"] == "Manual intervention required for foo package"

    @pytest.mark.asyncio
    async def test_get_latest_news_with_limit(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=_mock_rss_response(SAMPLE_RSS_FEED)
            )
            result = await get_latest_news(limit=2)
            assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_get_latest_news_http_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "HTTP 500", request=MagicMock(), response=mock_response
        )
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await get_latest_news()
        assert result["error"] is True
        assert result["type"] == "HTTPError"

    @pytest.mark.asyncio
    async def test_get_latest_news_timeout(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )
            result = await get_latest_news()
        assert result["error"] is True
        assert result["type"] == "Timeout"


class TestCriticalNews:
    """Test critical news detection."""

    @pytest.mark.asyncio
    async def test_check_critical_news_found(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=_mock_rss_response(SAMPLE_RSS_FEED)
            )
            result = await check_critical_news()
            assert result["has_critical"] is True
            assert result["critical_count"] >= 1
            assert "matched_keywords" in result["critical_news"][0]

    @pytest.mark.asyncio
    async def test_check_critical_news_none_found(self):
        safe_feed = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
    <channel>
        <item>
            <title>Regular update</title>
            <link>https://news.opensuse.org/regular/</link>
            <pubDate>Mon, 10 Nov 2025 10:00:00 +0000</pubDate>
            <description><![CDATA[<p>Normal update.</p>]]></description>
        </item>
    </channel>
</rss>
"""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=_mock_rss_response(safe_feed)
            )
            result = await check_critical_news()
            assert result["has_critical"] is False
            assert result["critical_count"] == 0


class TestNewsSinceUpdate:
    """Test news since last zypp update."""

    @pytest.mark.asyncio
    @patch("suse_ops_server.news.IS_SUSE", True)
    async def test_get_news_since_last_update_success(self, tmp_path):
        # Create a zypp history file with a recent update
        zypp_log = tmp_path / "history"
        zypp_log.write_text(
            "2025-11-08 10:00:00|install|vim|9.1.0330-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|a1\n"
            "2025-11-09 15:30:00|update|python3|3.11.5-1.1|x86_64|root@localhost|openSUSE-Tumbleweed-Oss|b2\n"
        )
        # RSS feed with one item after the update, one before
        rss_feed = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
    <channel>
        <item>
            <title>Recent news after update</title>
            <link>https://news.opensuse.org/recent/</link>
            <pubDate>Mon, 10 Nov 2025 10:00:00 +0000</pubDate>
            <description><![CDATA[<p>New announcement.</p>]]></description>
        </item>
        <item>
            <title>Old news before update</title>
            <link>https://news.opensuse.org/old/</link>
            <pubDate>Wed, 06 Nov 2025 10:00:00 +0000</pubDate>
            <description><![CDATA[<p>Old announcement.</p>]]></description>
        </item>
    </channel>
</rss>
"""
        with patch("suse_ops_server.news.ZYPP_HISTORY_PATH", str(zypp_log)), \
             patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=_mock_rss_response(rss_feed)
            )
            result = await get_news_since_last_update()
            assert result["has_news"] is True
            assert result["news_count"] == 1
            assert "last_update" in result
            assert result["news"][0]["title"] == "Recent news after update"

    @pytest.mark.asyncio
    @patch("suse_ops_server.news.IS_SUSE", False)
    async def test_get_news_since_last_update_not_suse(self):
        result = await get_news_since_last_update()
        assert result["error"] is True
        assert result["type"] == "NotSupported"

    @pytest.mark.asyncio
    @patch("suse_ops_server.news.IS_SUSE", True)
    async def test_get_news_since_last_update_no_log(self):
        with patch("suse_ops_server.news.ZYPP_HISTORY_PATH", "/nonexistent/history"):
            result = await get_news_since_last_update()
            assert result["error"] is True
            assert result["type"] == "NotFound"
