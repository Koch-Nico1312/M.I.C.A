# M.I.C.A Solo Workspace

This guide is for running the platform features as a local, single-user M.I.C.A workspace.

## What Solo Mode Does

Solo mode turns the platform-style feature set into a personal workspace:

- agents are private and owned by the local user
- the personal group contains only the local owner
- SSO, LDAP, SCIM, remote connectors, and marketplace items are optional
- local knowledge, sandbox, workflows, artifacts, publishing, and companion access are prepared
- the Studio audit checks all 20 platform areas with evidence

## Use It In Studio

Open M.I.C.A Studio and use the buttons in the Solo banner:

1. **Solo vorbereiten** sets local defaults, private agents, personal ACLs, local knowledge sources, and publishing drafts.
2. **Quickstart ausfuehren** runs the useful local path end to end: agent, knowledge sync/search, document ingestion, sandbox, workflow, artifact, and publishing links.
3. **Audit pruefen** verifies the original 20 areas and shows concrete evidence for each item.

The Quickstart result gives local links for:

- `/apps/research-copilot`
- `/embed/research-copilot`
- `/api/agents/research-copilot/invoke`
- `/mcp/research-copilot`

## Solo Readiness Matrix

| # | Area | Solo behavior |
|---|---|---|
| 1 | Agent/Persona Builder | Private local agents with prompt, tools, knowledge, and parameters |
| 2 | Multi-user/RBAC | Single local owner, personal group, ACLs kept for safety |
| 3 | Marketplace | Optional local-review install path |
| 4 | OpenAPI Tool Import | Local import creates tools from specs |
| 5 | MCP Deferred Tools | Deferred discovery/load/unload remains available |
| 6 | Tool Editor | Function/filter/pipe/action editor and tests |
| 7 | Workflow Builder | Canvas nodes, edges, branches, loops, human checkpoints |
| 8 | Workflow Debugger | Run timeline, step data, retry and human-decision records |
| 9 | Evaluations/Arena | Local datasets, scoring, ELO and regression gate |
| 10 | Token/Cost/Latency | Local metric rows and aggregate action |
| 11 | Knowledge Sync | Local folder/watch sources first, remote sources optional |
| 12 | Hybrid RAG | BM25 + vector + rerank scoring path |
| 13 | Document Extraction | Local batch ingestion artifacts for text, tables, OCR/layout metadata |
| 14 | Notes/Artifacts | Persistent notes/reports/rendering |
| 15 | Code Interpreter | Local Python/JavaScript sandbox with guarded policy |
| 16 | Publishing | Local web app, embed, REST and MCP descriptors |
| 17 | Deployment | Docker/Compose/Helm readiness metadata remains available |
| 18 | SSO/OIDC/LDAP/SCIM | Optional in solo mode |
| 19 | Agent Chains | Local subagent chain runs |
| 20 | Companion | Browser/mobile companion endpoints and pairing |

## Programmatic Check

The platform hub exposes the same flow through actions:

```python
from core.platform_hub import get_platform_hub

hub = get_platform_hub()
hub.action("prepare_solo_workspace", {"workspace_name": "Personal M.I.C.A"})
hub.action("run_solo_quickstart", {})
audit = hub.action("run_solo_audit", {})["result"]
assert audit["status"] == "ready"
assert audit["blocking_count"] == 0
assert audit["total_count"] == 20
```

## Expected Good State

A healthy local workspace should report:

- `solo_status.status == "ready"`
- `solo_status.total_count == 20`
- `solo_status.blocking_count == 0`
- `run_solo_audit` verifies all 20 items
- the Quickstart history contains a recent report artifact and local publishing links
