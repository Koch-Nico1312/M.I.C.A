def test_crawl_url_requires_full_url():
    from actions.web_crawl import crawl_url

    result = crawl_url({"url": "example.com"})

    assert "http:// or https://" in result


def test_crawl_url_returns_markdown_and_saves_metadata(monkeypatch):
    from actions import web_crawl

    async def fake_crawl(url, **kwargs):
        return {
            "url": url,
            "markdown": "# Example\n\nUseful content",
            "success": True,
            "status_code": 200,
            "error": None,
        }

    saved = {}

    def fake_save(url, markdown, metadata):
        saved["url"] = url
        saved["markdown"] = markdown
        saved["metadata"] = metadata
        return {"markdown_path": "data/web_crawls/example.md", "chunks_path": "chunks.json"}

    monkeypatch.setattr(web_crawl, "_crawl_with_crawl4ai", fake_crawl)
    monkeypatch.setattr(web_crawl, "_save_crawl_artifact", fake_save)
    monkeypatch.setattr(web_crawl, "_index_crawl", lambda *_args, **_kwargs: True)

    result = web_crawl.crawl_url(
        {"url": "https://example.com", "query": "Useful", "index": True, "max_chars": 100}
    )

    assert "Crawled: https://example.com" in result
    assert "Indexed: yes" in result
    assert "# Example" in result
    assert saved["metadata"]["crawler"] == "crawl4ai"


def test_crawl_url_reports_missing_dependency(monkeypatch):
    from actions import web_crawl

    async def fake_crawl(_url, **_kwargs):
        raise RuntimeError("Crawl4AI is not installed.")

    monkeypatch.setattr(web_crawl, "_crawl_with_crawl4ai", fake_crawl)

    result = web_crawl.crawl_url({"url": "https://example.com"})

    assert result.startswith("Crawl failed:")
    assert "not installed" in result
