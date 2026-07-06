import sqlite3

from core.knowledge_manager import (
    KiwixWikipediaAdapter,
    KnowledgeContext,
    KnowledgeManager,
    KnowledgeResult,
    KnowledgeSource,
)


class FakeAdapter:
    def __init__(self, name, results=None, indexable_kinds=None):
        self.name = name
        self.results = results or []
        self.indexable_kinds = set(indexable_kinds or [])
        self.search_calls = []
        self.index_calls = []

    def search(self, query, limit):
        self.search_calls.append((query, limit))
        return self.results[:limit]

    def index(self, source):
        self.index_calls.append(source)
        return {
            "indexed": source.kind in self.indexable_kinds,
            "source": self.name,
            "uri": source.uri,
        }


class FakeSemanticSearch:
    def __init__(self, search_results=None):
        self.indexed_texts = []
        self.search_results = search_results or []

    def index_text(self, document_id, title, content, metadata=None):
        self.indexed_texts.append(
            {
                "document_id": document_id,
                "title": title,
                "content": content,
                "metadata": metadata or {},
            }
        )
        return True

    def search(self, query, n_results=5):
        return self.search_results[:n_results]


class FakeObsidianBridge:
    def __init__(self):
        self.notes = {}

    def create_note(self, relative_path, content):
        self.notes[relative_path] = content
        return relative_path


def test_search_queries_all_adapters_and_normalizes_limit():
    personal = FakeAdapter(
        "obsidian",
        [KnowledgeResult("Note", "Personal Docker note", "obsidian", score=None)],
    )
    docs = FakeAdapter(
        "documents",
        [KnowledgeResult("Docker.md", "Docker uses namespaces", "documents", score=0.2)],
    )
    manager = KnowledgeManager(adapters=[personal, docs])

    results = manager.search("docker", limit=5)

    assert [result.source for result in results] == ["documents", "obsidian"]
    assert personal.search_calls == [("docker", 5)]
    assert docs.search_calls == [("docker", 5)]


def test_search_can_filter_sources():
    personal = FakeAdapter("obsidian", [KnowledgeResult("Note", "Personal note", "obsidian")])
    docs = FakeAdapter("documents", [KnowledgeResult("Doc", "Indexed doc", "documents")])
    manager = KnowledgeManager(adapters=[personal, docs])

    results = manager.search("python", sources=["obsidian"])

    assert [result.source for result in results] == ["obsidian"]
    assert personal.search_calls
    assert docs.search_calls == []


def test_index_accepts_source_objects_and_reports_adapter_outcomes():
    docs = FakeAdapter("documents", indexable_kinds={"directory"})
    obsidian = FakeAdapter("obsidian", indexable_kinds={"obsidian"})
    manager = KnowledgeManager(adapters=[docs, obsidian])

    outcome = manager.index(KnowledgeSource(kind="directory", uri="docs"))

    assert outcome["indexed"] is True
    assert outcome["source"]["kind"] == "directory"
    assert outcome["outcomes"] == [
        {"indexed": True, "source": "documents", "uri": "docs"},
        {"indexed": False, "source": "obsidian", "uri": "docs"},
    ]


def test_index_accepts_dict_sources():
    docs = FakeAdapter("documents", indexable_kinds={"directory"})
    manager = KnowledgeManager(adapters=[docs])

    outcome = manager.index({"kind": "directory", "uri": "Documents", "metadata": {"tag": "local"}})

    assert outcome["indexed"] is True
    assert docs.index_calls[0].metadata == {"tag": "local"}


def test_get_context_returns_compact_context_bundle():
    adapter = FakeAdapter(
        "memory",
        [
            KnowledgeResult(
                title="knowledge/docker",
                content="Docker isolates processes with namespaces and cgroups.",
                source="memory",
                uri="memory://knowledge/docker",
                score=0.9,
            )
        ],
    )
    manager = KnowledgeManager(adapters=[adapter])

    context = manager.get_context("container isolation", limit=1, max_chars=120)

    assert context.query == "container isolation"
    assert len(context.results) == 1
    assert "memory: knowledge/docker" in context.text
    assert "namespaces and cgroups" in context.text


def test_suggest_notes_creates_note_plan_and_graph_edges():
    adapter = FakeAdapter(
        "documents",
        [
            KnowledgeResult("Docker.md", "Docker uses namespaces and cgroups.", "documents", score=0.2),
            KnowledgeResult("Linux namespaces.md", "Namespaces isolate resources.", "documents", score=0.3),
        ],
    )
    manager = KnowledgeManager(adapters=[adapter])

    plan = manager.suggest_notes("containers", limit=2)

    assert [suggestion.title for suggestion in plan.suggestions] == [
        "Docker",
        "Linux namespaces",
    ]
    assert plan.suggestions[0].links == ["Linux namespaces"]
    assert "[[Linux namespaces]]" in plan.suggestions[0].content
    assert plan.graph_edges[0].source == "Docker"
    assert plan.graph_edges[0].target == "Linux namespaces"


def test_write_suggested_notes_creates_obsidian_notes_and_graph():
    adapter = FakeAdapter(
        "documents",
        [
            KnowledgeResult("Docker.md", "Docker uses namespaces and cgroups.", "documents", "docs/Docker.md", score=0.2),
            KnowledgeResult("Podman.md", "Podman runs containers.", "documents", "docs/Podman.md", score=0.3),
        ],
    )
    bridge = FakeObsidianBridge()
    manager = KnowledgeManager(adapters=[adapter], obsidian_bridge_factory=lambda: bridge)

    outcome = manager.write_suggested_notes("containers", limit=2)

    assert outcome["suggested"] == 2
    assert outcome["written"] == ["Knowledge/Auto/Docker.md", "Knowledge/Auto/Podman.md"]
    assert "Knowledge/Graph.md" in bridge.notes
    assert "# Docker" in bridge.notes["Knowledge/Auto/Docker.md"]
    assert "[[Podman]]" in bridge.notes["Knowledge/Auto/Docker.md"]
    assert "[[Docker]] -> [[Podman]]" in bridge.notes["Knowledge/Graph.md"]


def test_mica_knowledge_search_handler_uses_obsidian_and_documents_by_default():
    from core.mica_live import MicaLive

    class FakeKnowledgeManager:
        adapters = []

        def __init__(self):
            self.search_calls = []

        def search(self, query, *, limit, sources):
            self.search_calls.append((query, limit, sources))
            return [
                KnowledgeResult("Docker Note", "Personal Docker note", "obsidian", "Topics/Docker.md"),
                KnowledgeResult("containers.md", "Namespaces and cgroups", "documents", "docs/containers.md"),
            ]

    fake_manager = FakeKnowledgeManager()
    mica = MicaLive.__new__(MicaLive)
    mica.knowledge_manager = fake_manager

    output = mica._handle_knowledge_search({"action": "search", "query": "docker"})

    assert fake_manager.search_calls == [("docker", 5, ["obsidian", "documents"])]
    assert "[obsidian] Docker Note" in output
    assert "[documents] containers.md" in output


def test_mica_knowledge_context_handler_uses_unified_context():
    from core.mica_live import MicaLive

    class FakeKnowledgeManager:
        adapters = []

        def get_context(self, query, *, limit, sources, max_chars):
            return KnowledgeContext(
                query=query,
                results=[KnowledgeResult("Python", "Context text", "documents")],
                text="[1] documents: Python\nContext text",
            )

    mica = MicaLive.__new__(MicaLive)
    mica.knowledge_manager = FakeKnowledgeManager()

    output = mica._handle_knowledge_search(
        {"action": "context", "query": "python", "sources": ["documents"], "max_chars": 200}
    )

    assert output == "[1] documents: Python\nContext text"


def test_mica_knowledge_suggest_notes_handler_returns_suggestions():
    from core.mica_live import MicaLive

    class FakeKnowledgeManager:
        def suggest_notes(self, query, *, limit, sources):
            return KnowledgeManager(
                adapters=[
                    FakeAdapter(
                        "documents",
                        [KnowledgeResult("Docker.md", "Docker note", "documents", score=0.2)],
                    )
                ]
            ).suggest_notes(query, limit=limit, sources=sources)

    mica = MicaLive.__new__(MicaLive)
    mica.knowledge_manager = FakeKnowledgeManager()

    output = mica._handle_knowledge_search(
        {"action": "suggest_notes", "query": "docker", "sources": ["documents"]}
    )

    assert '"suggestions"' in output
    assert '"title": "Docker"' in output


def test_mica_knowledge_write_notes_handler_writes_notes():
    from core.mica_live import MicaLive

    class FakeKnowledgeManager:
        def write_suggested_notes(self, query, *, limit, sources):
            return {"query": query, "suggested": 1, "written": ["Knowledge/Auto/Docker.md"]}

    mica = MicaLive.__new__(MicaLive)
    mica.knowledge_manager = FakeKnowledgeManager()

    output = mica._handle_knowledge_search({"action": "write_notes", "query": "docker"})

    assert '"written": [' in output
    assert "Knowledge/Auto/Docker.md" in output


def test_mica_knowledge_graph_handler_returns_edges():
    from core.mica_live import MicaLive

    manager = KnowledgeManager(
        adapters=[
            FakeAdapter(
                "documents",
                [
                    KnowledgeResult("Docker.md", "Docker note", "documents", score=0.2),
                    KnowledgeResult("Linux.md", "Linux note", "documents", score=0.3),
                ],
            )
        ]
    )
    mica = MicaLive.__new__(MicaLive)
    mica.knowledge_manager = manager

    output = mica._handle_knowledge_search({"action": "graph", "query": "containers"})

    assert "[[Docker]] -> [[Linux]]" in output


def test_knowledge_search_tool_is_declared():
    from tools.tool_declarations import FEATURE_TOOL_DECLARATIONS

    declaration = next(
        tool for tool in FEATURE_TOOL_DECLARATIONS if tool["name"] == "knowledge_search"
    )

    assert "Obsidian" in declaration["description"]
    assert "documents" in declaration["description"]
    assert "write_notes" in declaration["parameters"]["properties"]["action"]["description"]


def test_kiwix_adapter_reports_missing_zim_file(tmp_path):
    adapter = KiwixWikipediaAdapter(metadata_db_path=tmp_path / "wikipedia.sqlite")

    outcome = adapter.index(KnowledgeSource(kind="zim", uri=str(tmp_path / "missing.zim")))

    assert outcome["indexed"] is False
    assert outcome["reason"] == "missing_zim_file"


def test_kiwix_adapter_reports_missing_reader_dependency(tmp_path):
    zim_path = tmp_path / "wikipedia.zim"
    zim_path.write_text("placeholder", encoding="utf-8")

    def missing_reader(path):
        raise RuntimeError("pyzim is required to index .zim files")

    adapter = KiwixWikipediaAdapter(
        article_reader_factory=missing_reader,
        metadata_db_path=tmp_path / "wikipedia.sqlite",
    )

    outcome = adapter.index(KnowledgeSource(kind="zim", uri=str(zim_path)))

    assert outcome["indexed"] is False
    assert outcome["reason"] == "missing_dependency"
    assert "pyzim" in outcome["detail"]


def test_kiwix_adapter_indexes_fake_articles_to_sqlite_and_semantic_search(tmp_path):
    zim_path = tmp_path / "wikipedia.zim"
    zim_path.write_text("placeholder", encoding="utf-8")
    semantic_search = FakeSemanticSearch()

    def article_reader(path):
        assert path == zim_path
        return [
            {
                "title": "Docker",
                "path": "A/Docker",
                "description": "Docker overview",
                "categories": ["Software", "Containers"],
                "links": ["Linux namespaces"],
                "content": "<p>Docker uses namespaces and cgroups for isolation.</p>",
            },
            {
                "title": "Linux namespaces",
                "path": "A/Linux_namespaces",
                "categories": ["Linux"],
                "links": ["Docker"],
                "content": "Namespaces isolate process resources in Linux.",
            },
        ]

    adapter = KiwixWikipediaAdapter(
        semantic_search_factory=lambda: semantic_search,
        article_reader_factory=article_reader,
        metadata_db_path=tmp_path / "wikipedia.sqlite",
    )

    outcome = adapter.index(KnowledgeSource(kind="zim", uri=str(zim_path)))

    assert outcome["indexed"] is True
    assert outcome["articles_indexed"] == 2
    assert outcome["metadata_rows"] == 2
    assert len(semantic_search.indexed_texts) == 2
    assert semantic_search.indexed_texts[0]["metadata"]["source"] == "wikipedia"
    assert semantic_search.indexed_texts[0]["content"] == (
        "Docker uses namespaces and cgroups for isolation."
    )

    with sqlite3.connect(tmp_path / "wikipedia.sqlite") as conn:
        rows = conn.execute(
            "SELECT title, description, categories_json FROM wikipedia_articles ORDER BY title"
        ).fetchall()

    assert rows[0][0] == "Docker"
    assert rows[0][1] == "Docker overview"
    assert "Containers" in rows[0][2]


def test_kiwix_adapter_search_combines_semantic_and_sqlite_metadata(tmp_path):
    semantic_search = FakeSemanticSearch(
        [
            {
                "id": "wikipedia:test:A/Docker_0",
                "document": "Docker semantic chunk",
                "metadata": {
                    "source": "wikipedia",
                    "title": "Docker",
                    "zim_path": "test.zim",
                    "zim_entry_path": "A/Docker",
                },
                "distance": 0.1,
            },
            {
                "id": "local-doc_0",
                "document": "Unrelated local document",
                "metadata": {"source": "documents", "title": "Local"},
                "distance": 0.01,
            },
        ]
    )
    adapter = KiwixWikipediaAdapter(
        semantic_search_factory=lambda: semantic_search,
        metadata_db_path=tmp_path / "wikipedia.sqlite",
    )
    adapter._ensure_schema()
    adapter._store_article_metadata(
        {
            "zim_path": "test.zim",
            "path": "A/Podman",
            "title": "Podman",
            "description": "Podman is a container engine.",
            "categories": ["Containers"],
            "links": ["Docker"],
        }
    )

    results = adapter.search("container", limit=5)

    assert [result.title for result in results] == ["Docker", "Podman"]
    assert results[0].metadata["match_type"] == "semantic"
    assert results[1].metadata["match_type"] == "metadata"
