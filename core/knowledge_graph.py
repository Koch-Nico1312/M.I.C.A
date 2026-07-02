"""Small knowledge graph projection for local Jarvis sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GraphNode:
    id: str
    label: str
    source: str
    tags: list[str] = field(default_factory=list)
    uri: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    relation: str = "related"
    evidence: str = ""


def _node_id(source: str, label: str) -> str:
    return f"{source}:{label}".lower().replace(" ", "-")


def build_knowledge_graph(
    *,
    memory: dict[str, Any] | None = None,
    documents: list[dict[str, Any]] | None = None,
    note_edges: list[dict[str, Any]] | None = None,
    source_filter: list[str] | None = None,
    tag_filter: list[str] | None = None,
    limit: int = 120,
) -> dict[str, Any]:
    wanted_sources = {item.lower() for item in source_filter or []}
    wanted_tags = {item.lower() for item in tag_filter or []}
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    def include(source: str, tags: list[str]) -> bool:
        if wanted_sources and source.lower() not in wanted_sources:
            return False
        if wanted_tags and not wanted_tags.intersection({tag.lower() for tag in tags}):
            return False
        return True

    for category, items in (memory or {}).items():
        if not isinstance(items, dict):
            continue
        category_id = _node_id("memory", category)
        if include("memory", [category]):
            nodes[category_id] = GraphNode(category_id, category, "memory", tags=[category])
        for key, entry in list(items.items())[:limit]:
            tags = entry.get("tags", []) if isinstance(entry, dict) else []
            tags = [str(tag) for tag in tags] + [str(category)]
            if not include("memory", tags):
                continue
            node_id = _node_id("memory", f"{category}/{key}")
            value = entry.get("value") if isinstance(entry, dict) else entry
            nodes[node_id] = GraphNode(
                id=node_id,
                label=str(key),
                source="memory",
                tags=tags,
                metadata={"category": category, "preview": str(value or "")[:160]},
            )
            edges.append(GraphEdge(category_id, node_id, "contains", str(value or "")[:120]))

    for record in documents or []:
        tags = [str(record.get("type") or "document")]
        if record.get("indexed"):
            tags.append("indexed")
        if not include("documents", tags):
            continue
        label = str(record.get("name") or "document")
        node_id = _node_id("documents", label)
        nodes[node_id] = GraphNode(
            id=node_id,
            label=label,
            source="documents",
            tags=tags,
            uri=str(record.get("path") or ""),
            metadata={
                "status": record.get("status"),
                "analysis": record.get("analysis"),
                "chunks": record.get("chunks", 0),
            },
        )
        if record.get("indexed"):
            index_id = _node_id("documents", "semantic-index")
            nodes[index_id] = GraphNode(index_id, "Semantic Index", "documents", tags=["indexed"])
            edges.append(GraphEdge(index_id, node_id, "indexes", str(record.get("analysis") or "")))

    for raw_edge in note_edges or []:
        source = str(raw_edge.get("source") or "")
        target = str(raw_edge.get("target") or "")
        if not source or not target:
            continue
        source_id = _node_id("notes", source)
        target_id = _node_id("notes", target)
        if include("obsidian", ["note"]):
            nodes.setdefault(source_id, GraphNode(source_id, Path(source).stem, "obsidian", tags=["note"], uri=source))
            nodes.setdefault(target_id, GraphNode(target_id, Path(target).stem, "obsidian", tags=["note"], uri=target))
            edges.append(
                GraphEdge(
                    source_id,
                    target_id,
                    str(raw_edge.get("relation") or "links"),
                    str(raw_edge.get("evidence") or ""),
                )
            )

    graph_nodes = list(nodes.values())[:limit]
    node_ids = {node.id for node in graph_nodes}
    graph_edges = [edge for edge in edges if edge.source in node_ids and edge.target in node_ids][: limit * 2]
    return {
        "nodes": [node.__dict__.copy() for node in graph_nodes],
        "edges": [edge.__dict__.copy() for edge in graph_edges],
        "filters": {
            "sources": sorted({node.source for node in graph_nodes}),
            "tags": sorted({tag for node in graph_nodes for tag in node.tags}),
        },
        "counts": {"nodes": len(graph_nodes), "edges": len(graph_edges)},
    }
