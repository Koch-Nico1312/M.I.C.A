import json

from actions.advanced_knowledge import advanced_knowledge
from core.document_ingestion import build_ingestion_record
from core.knowledge_manager import KnowledgeManager, KnowledgeSource, LlamaIndexKnowledgeAdapter


def test_document_ingestion_records_markitdown_converter_for_pdf(tmp_path, monkeypatch):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF placeholder")

    class FakeAdapter:
        def convert_file(self, path, *, max_chars):
            class Result:
                ok = True
                result = "# Converted\nText from PDF"
                error = ""

            return Result()

    monkeypatch.setattr(
        "core.advanced_knowledge_integrations.get_markitdown_adapter",
        lambda: FakeAdapter(),
    )

    record, chunks = build_ingestion_record(pdf)

    assert record["status"] == "chunked"
    assert record["metadata"]["advanced_converter"] == "markitdown"
    assert "Converted" in record["metadata"]["text_preview"]
    assert chunks


def test_llama_index_adapter_reports_missing_sdk_without_breaking_search():
    adapter = LlamaIndexKnowledgeAdapter()

    results = adapter.search("anything", limit=3)
    outcome = adapter.index(KnowledgeSource(kind="advanced_index", uri="missing"))

    assert results == []
    assert outcome["indexed"] is False
    assert outcome["source"] == "advanced_index"


def test_knowledge_manager_can_include_advanced_index_adapter():
    manager = KnowledgeManager(adapters=[LlamaIndexKnowledgeAdapter()])

    outcome = manager.index({"kind": "advanced_index", "uri": "missing"})

    assert outcome["indexed"] is False
    assert outcome["outcomes"][0]["source"] == "advanced_index"


def test_advanced_knowledge_status_action_returns_optional_backend_status():
    payload = json.loads(advanced_knowledge({"action": "status"}))

    assert "markitdown" in payload
    assert "llama_index" in payload
    assert "available" in payload["markitdown"]

