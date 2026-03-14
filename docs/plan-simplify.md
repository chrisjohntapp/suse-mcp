# Wiki Code Simplification Plan

## wiki.py

### 1. Remove `get_wiki_page_as_text` wrapper
`get_wiki_page_as_text` is a one-liner that calls `get_wiki_page(title, as_markdown=True)`, which is already the default. All callers can call `get_wiki_page(title)` directly. Remove the wrapper and update imports in `server.py` and `__init__.py`.

### 2. Move `import re` and `strip_html` out of `search_wiki`
The `re` import and `strip_html` function are defined inside the function body on every call. Move `import re` to the top of the file and define `strip_html` at module level (or inline it since it is a single `re.sub` call).

### 3. Remove unnecessary try/catch in `get_wiki_page` markdown conversion
Lines 128-131 catch a markdown conversion exception and silently return HTML. This hides bugs. The `markdownify` library does not raise on normal input. Remove the try/catch and let unexpected errors propagate.

### 4. Simplify error handling in `search_wiki`
Three separate except blocks produce slightly different error dicts via `create_error_response`. The `HTTPStatusError` and `TimeoutException` cases could be collapsed into the general `Exception` handler since the error message already contains enough context. Alternatively, just catch `httpx.HTTPError` (parent of both) plus the general case.

### 5. Remove the `as_markdown` parameter from `get_wiki_page`
Every caller passes `True` (or uses the default). The HTML path is unused. Remove the parameter and always convert to markdown, simplifying the function signature.

### 6. Remove redundant URL construction in `_fetch_via_scraping`
The URL uses `/title/{title}` but the standard MediaWiki path is `/wiki/{title}`. Verify which is correct; if `/title/` is wrong, this fallback may never work. If it does work via redirect (`follow_redirects=True`), switch to `/wiki/` to avoid the redirect.

## server.py

### 7. Simplify wiki resource URI parsing
Lines 394-406 handle the `opensuse-wiki://` scheme with a fallback from `parsed.path` to `parsed.netloc`. This dual extraction is confusing. Since URIs like `opensuse-wiki://Installation_guide` put the title in `netloc`, just use `parsed.netloc` and drop the path logic.

### 8. Remove `wiki_suggestions` from health check response schema
The `wiki_suggestions` field (line 179) in the health check response schema is never populated by the health check tool. Remove it.

### 9. Simplify troubleshoot prompt wiki integration
Lines 1394-1427: the wiki search results are iterated assuming dict keys (`result['title']`, `result['url']`), but `search_wiki` returns a dict with a `results` key, not a list. The code references `wiki_results` as if it is a list of results, but the return value is `{"query": ..., "count": ..., "results": [...]}`. This is likely a bug -- it should be `wiki_results.get("results", [])`. Fix this and simplify the iteration.

## tool_metadata.py

### 10. No changes needed
The wiki entry (`search_opensuse_wiki`) in `TOOL_METADATA` is minimal and correct.

## Summary

Priority order:
1. Fix the bug in troubleshoot prompt wiki iteration (item 9)
2. Remove `get_wiki_page_as_text` wrapper (item 1)
3. Remove `as_markdown` parameter (item 5)
4. Hoist `re` import and inline `strip_html` (item 2)
5. Fix scraping URL path (item 6)
6. Simplify URI parsing (item 7)
7. Remove dead `wiki_suggestions` schema field (item 8)
8. Remove markdown try/catch (item 3)
9. Simplify error handling (item 4)
