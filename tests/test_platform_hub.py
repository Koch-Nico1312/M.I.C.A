from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from core.platform_hub import PlatformHub


def _b64url_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_uint(value: int) -> str:
    return _b64url_bytes(value.to_bytes((value.bit_length() + 7) // 8, "big"))


def _signed_hs256_jwt(header: dict, payload: dict, secret: str) -> str:
    def encode(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
        return _b64url_bytes(raw)

    signing_input = f"{encode(header)}.{encode(payload)}"
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    encoded_signature = _b64url_bytes(signature)
    return f"{signing_input}.{encoded_signature}"


def _signed_rs256_jwt(header: dict, payload: dict, private_key: rsa.RSAPrivateKey) -> str:
    def encode(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
        return _b64url_bytes(raw)

    signing_input = f"{encode(header)}.{encode(payload)}"
    signature = private_key.sign(signing_input.encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input}.{_b64url_bytes(signature)}"


def _rsa_public_jwk(private_key: rsa.RSAPrivateKey, kid: str) -> dict:
    numbers = private_key.public_key().public_numbers()
    return {"kid": kid, "kty": "RSA", "alg": "RS256", "use": "sig", "n": _b64url_uint(numbers.n), "e": _b64url_uint(numbers.e)}


def test_platform_hub_seeds_core_feature_areas(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    snapshot = hub.snapshot()

    assert snapshot["counts"]["agents"] >= 1
    assert snapshot["counts"]["users"] >= 1
    assert snapshot["deployment"]["docker_compose"] == "docker-compose.yml"
    assert snapshot["deployment"]["dockerfile"] == "Dockerfile"
    assert snapshot["deployment"]["postgres"] == "compose+helm-ready"
    assert snapshot["deployment"]["redis"] == "compose+helm-ready"
    assert snapshot["sso"]["oidc"] == "configured"
    assert snapshot["companion"]["mobile_ui"] == "responsive"
    assert (tmp_path / "companion" / "manifest.json").exists()
    assert (tmp_path / "companion" / "popup.html").exists()
    assert (tmp_path / "companion" / "popup.js").exists()


def test_agent_builder_persists_agent(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    result = hub.action(
        "save_agent",
        {
            "name": "Finance Analyst",
            "model": "accurate",
            "prompt": "Analyze finance documents.",
            "tools": ["spreadsheet_reader"],
            "knowledge": ["finance-vault"],
            "parameters": {"temperature": 0.2},
        },
    )

    assert result["status"] == "ok"
    assert any(agent["name"] == "Finance Analyst" for agent in result["platform"]["agents"])


def test_prepare_solo_workspace_sets_personal_defaults(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    result = hub.action("prepare_solo_workspace", {"workspace_name": "My M.I.C.A"})
    snapshot = result["platform"]
    agent = next(item for item in snapshot["agents"] if item["id"] == "research-copilot")
    personal_group = next(item for item in snapshot["groups"] if item["id"] == "personal")
    local_memory = next(item for item in snapshot["knowledge"] if item["id"] == "mica-memory")

    assert result["status"] == "ok"
    assert snapshot["solo_status"]["workspace_name"] == "My M.I.C.A"
    assert snapshot["solo_status"]["status"] == "ready"
    assert snapshot["solo_status"]["total_count"] == 20
    assert snapshot["solo_status"]["blocking_count"] == 0
    assert snapshot["solo_status"]["ready_count"] >= 18
    assert agent["visibility"] == "private"
    assert agent["owner"] == "u-admin"
    assert "local-documents" in agent["knowledge"]
    assert personal_group["members"] == ["u-admin"]
    assert local_memory["status"] == "watching"
    assert snapshot["sso"]["solo_mode"] is True
    assert snapshot["sso"]["oidc"] == "optional"
    assert snapshot["marketplace_policy"]["solo_install_mode"] == "local-review"
    assert all(pub["policy"]["allowed_groups"] == ["personal"] for pub in snapshot["publishing"])
    assert {"web-app", "embeddable-chat", "rest-api", "mcp-server"} <= {pub["kind"] for pub in snapshot["publishing"]}
    assert any(artifact["id"] == "artifact-solo-start" for artifact in snapshot["artifacts"])


def test_solo_quickstart_runs_local_workspace_paths(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
        ingestion_dir=tmp_path / "ingestion",
        sandbox_artifact_dir=tmp_path / "sandbox",
    )

    result = hub.action(
        "run_solo_quickstart",
        {
            "workspace_name": "My M.I.C.A",
            "query": "local tools knowledge",
            "files": ["note.md", "scan.pdf"],
        },
    )
    quickstart = result["result"]
    snapshot = result["platform"]

    assert result["status"] == "ok"
    assert quickstart["status"] == "ready"
    assert quickstart["solo_status"]["blocking_count"] == 0
    assert quickstart["summary"]["title"] == "My M.I.C.A ist lokal bereit"
    assert quickstart["summary"]["knowledge_results"] == len(quickstart["knowledge_search"]["results"])
    assert quickstart["summary"]["ingested_documents"] == len(quickstart["ingestion_run"]["documents"])
    assert quickstart["next_actions"]
    assert quickstart["agent"]["status"] == "completed"
    assert quickstart["knowledge_run"]["status"] == "completed"
    assert quickstart["knowledge_search"]["results"]
    assert quickstart["ingestion_run"]["status"] == "completed"
    assert quickstart["sandbox_run"]["status"] == "completed"
    assert quickstart["artifact"]["id"] == "artifact-solo-quickstart"
    assert quickstart["rendered_artifact"]["status"] == "ready"
    assert quickstart["links"]["agent_app"] == "/apps/research-copilot"
    assert {"web-app", "embeddable-chat", "rest-api", "mcp-server"} <= {pub["kind"] for pub in snapshot["publishing"] if pub["status"] == "published"}
    assert snapshot["solo_quickstarts"][0]["artifact_id"] == "artifact-solo-quickstart"
    assert snapshot["solo_quickstarts"][0]["summary"]["ingested_documents"] == 2
    assert snapshot["solo_quickstarts"][0]["next_actions"][0]["href"] == "/apps/research-copilot"


def test_solo_audit_reports_evidence_for_all_twenty_items(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
        ingestion_dir=tmp_path / "ingestion",
        sandbox_artifact_dir=tmp_path / "sandbox",
    )

    hub.action("run_solo_quickstart", {"workspace_name": "My M.I.C.A"})
    audit_result = hub.action("run_solo_audit", {})
    audit = audit_result["result"]
    snapshot = audit_result["platform"]

    assert audit_result["status"] == "ok"
    assert audit["status"] == "ready"
    assert audit["total_count"] == 20
    assert audit["blocking_count"] == 0
    assert len(audit["items"]) == 20
    assert {item["id"] for item in audit["items"]} == {
        "agent_builder",
        "solo_access",
        "marketplace",
        "openapi_import",
        "mcp_deferred",
        "tool_editor",
        "workflow_builder",
        "workflow_debugger",
        "evaluations",
        "metrics",
        "knowledge_sync",
        "hybrid_rag",
        "document_extraction",
        "artifacts",
        "sandbox",
        "publishing",
        "deployment",
        "identity",
        "agent_chains",
        "companion",
    }
    assert all(item["evidence"] for item in audit["items"])
    assert all(item["verified"] for item in audit["items"])
    assert snapshot["solo_audits"][0]["id"] == audit["id"]
    assert snapshot["counts"]["solo_audits"] == 1


def test_platform_hub_json_store_roundtrip(tmp_path):
    store_path = tmp_path / "platform.json"
    first = PlatformHub(
        store_path=store_path,
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )
    first.action("save_agent", {"name": "Persistent Agent", "prompt": "Stay on disk."})

    second = PlatformHub(
        store_path=store_path,
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published2",
        browser_companion_dir=tmp_path / "companion2",
    )

    assert second.snapshot()["deployment"]["persistence"]["backend"] == "json"
    assert any(agent["name"] == "Persistent Agent" for agent in second.snapshot()["agents"])


def test_platform_hub_postgres_store_falls_back_to_json(monkeypatch, tmp_path):
    monkeypatch.setenv("MICA_PLATFORM_STORE", "postgres")
    monkeypatch.setenv("MICA_POSTGRES_URL", "postgresql://mica:mica@127.0.0.1:65432/mica")

    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )
    result = hub.action("save_agent", {"name": "Fallback Agent", "prompt": "Use fallback."})
    persistence = result["platform"]["deployment"]["persistence"]

    assert persistence["backend"] == "postgres"
    assert persistence["status"] in {"ready", "fallback-json"}
    assert (tmp_path / "platform.json").exists()


def test_agent_package_export_and_import_roundtrip(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
        agent_package_dir=tmp_path / "agent-packages",
    )

    saved = hub.action(
        "save_agent",
        {
            "name": "Packaged Analyst",
            "model": "accurate",
            "prompt": "Package this persona.",
            "tools": ["normalize_text", "weather_lookup"],
            "knowledge": ["local-documents"],
            "parameters": {"temperature": 0.1, "max_tokens": 900},
            "version": "2.1.0",
        },
    )["result"]
    exported = hub.action("export_agent_package", {"agent_id": saved["id"]})["result"]
    imported = hub.action("import_agent_package", {"package": exported["package"]})["result"]

    package_path = tmp_path / "agent-packages" / f"{exported['record']['id']}.json"
    assert package_path.exists()
    assert exported["package"]["format"] == "mica-agent-package/v1"
    assert exported["package"]["manifest"]["prompt"] == "Package this persona."
    assert exported["record"]["version"] == "2.1.0"
    assert imported["agent"]["id"].endswith("-import")
    assert imported["agent"]["tools"] == ["normalize_text", "weather_lookup"]
    assert hub.snapshot()["counts"]["agent_packages"] == 1


def test_openapi_import_creates_tools(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    result = hub.action(
        "import_openapi",
        {
            "spec": {
                "openapi": "3.0.0",
                "paths": {
                    "/tickets/{id}": {
                        "get": {
                            "operationId": "getTicket",
                            "summary": "Get ticket",
                            "parameters": [
                                {
                                    "name": "includeHistory",
                                    "in": "query",
                                    "schema": {"type": "boolean"},
                                }
                            ],
                        }
                    }
                },
            }
        },
    )

    assert result["result"]["count"] == 1
    tool = next(tool for tool in result["platform"]["tools"] if tool["name"] == "getticket")
    assert tool["schema"]["properties"]["id"]["description"] == "Path parameter"
    assert tool["schema"]["properties"]["includeHistory"]["type"] == "boolean"


def test_workflow_replay_and_sandbox_run(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )
    workflow_id = hub.snapshot()["workflows"][0]["id"]
    workflow = hub.snapshot()["workflows"][0]

    run = hub.action("run_workflow", {"workflow_id": workflow_id})
    resumed = hub.action("resume_workflow_run", {"run_id": run["result"]["id"], "decision": "approved", "comment": "Looks good"})
    sandbox = hub.action("run_sandbox", {"language": "python", "code": "print(40 + 2)"})

    assert "loops" in workflow["canvas"]["supports"]
    assert any(node["type"] == "loop" for node in workflow["nodes"])
    assert run["result"]["status"] == "waiting_for_human"
    assert run["result"]["steps"]
    assert run["result"]["debug"]["edges"]
    assert run["result"]["debug"]["branch_attempts"]["route"] >= 1
    assert run["result"]["debug"]["timeline_events"] == len(run["result"]["timeline"])
    assert any(step.get("human_required") for step in run["result"]["steps"])
    assert any(step.get("loop_iteration") == 1 for step in run["result"]["steps"])
    assert any(event["type"] == "tool_call" for event in run["result"]["timeline"])
    assert any(event["type"] == "retry" for event in run["result"]["timeline"])
    assert any(event["type"] == "human_wait" for event in run["result"]["timeline"])
    assert all("payload" in event for event in run["result"]["timeline"])
    assert [step["node"] for step in run["result"]["steps"]][:3] == ["input", "extract", "route"]
    assert resumed["result"]["status"] == "completed"
    assert resumed["result"]["debug"]["human_decision"] == "approved"
    assert resumed["result"]["debug"]["timeline_events"] == len(resumed["result"]["timeline"])
    assert resumed["result"]["timeline"][-2]["type"] == "human_decision"
    assert resumed["result"]["timeline"][-1]["type"] == "resume"
    assert sandbox["result"]["status"] == "completed"
    assert "42" in sandbox["result"]["stdout"]


def test_rbac_and_tool_test_execution(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    access = hub.action(
        "check_access",
        {"user_id": "u-builder", "permission": "tools:write"},
    )
    tool = hub.action(
        "save_tool",
        {
            "name": "Echo Tool",
            "kind": "function",
            "code": "return parameters.get('text', '').upper()",
        },
    )
    tested = hub.action(
        "test_tool",
        {"id": tool["result"]["id"], "parameters": {"text": "mica"}},
    )

    assert access["result"]["allowed"] is True
    assert tested["result"]["status"] == "ready"
    assert "M.I.C.A" in tested["result"]["test_result"]


def test_tool_editor_supports_filters_pipes_and_actions(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    filter_tool = hub.action(
        "save_tool",
        {
            "name": "Allow Text",
            "kind": "filter",
            "code": "return bool(parameters.get('text', '').strip())",
            "test_parameters": {"text": "go"},
        },
    )["result"]
    pipe_tool = hub.action(
        "save_tool",
        {
            "name": "Normalize Text",
            "kind": "pipe",
            "code": "return parameters.get('text', '').strip().lower()",
            "test_parameters": {"text": "  M.I.C.A  "},
        },
    )["result"]
    action_tool = hub.action(
        "save_tool",
        {
            "name": "Draft Note",
            "kind": "action",
            "code": "return {'title': parameters.get('title'), 'status': 'planned'}",
            "test_parameters": {"title": "Release note"},
        },
    )["result"]

    filter_test = hub.action("test_tool", {"id": filter_tool["id"]})
    pipe_test = hub.action("test_tool", {"id": pipe_tool["id"]})
    action_test = hub.action("test_tool", {"id": action_tool["id"]})

    assert filter_test["result"]["last_test"]["allowed"] is True
    assert pipe_test["result"]["last_test"]["transformed"] == "mica"
    assert action_test["result"]["last_test"]["dry_run"] is True
    assert "Release note" in action_test["result"]["test_result"]


def test_marketplace_install_and_publish_write_artifacts(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    hub.action("review_marketplace_item", {"id": "github-sync", "verdict": "approved"})
    hub.action("verify_marketplace_item", {"id": "github-sync", "signature": "mica:community-github-sync"})
    install = hub.action("install_marketplace_item", {"id": "github-sync"})
    publish = hub.action(
        "publish_agent",
        {"agent_id": "research-copilot", "kind": "embeddable-chat"},
    )

    assert install["status"] == "ok"
    assert (tmp_path / "plugins" / "github_sync.py").exists()
    assert (tmp_path / "plugins" / "github_sync.manifest.json").exists()
    assert publish["result"]["status"] == "published"
    assert (tmp_path / "published" / "research-copilot" / "manifest.json").exists()
    assert (tmp_path / "published" / "research-copilot" / "index.html").exists()


def test_marketplace_lifecycle_requires_review_and_supports_update_disable_uninstall(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    blocked = hub.action("install_marketplace_item", {"id": "github-sync"})
    reviewed = hub.action("review_marketplace_item", {"id": "github-sync", "verdict": "approved", "notes": "checksum accepted"})
    blocked_unsigned = hub.action("install_marketplace_item", {"id": "github-sync"})
    verified = hub.action("verify_marketplace_item", {"id": "github-sync", "signature": "mica:community-github-sync"})
    installed = hub.action("install_marketplace_item", {"id": "github-sync"})
    installed_enabled = installed["result"]["enabled"]
    installed_artifact_exists = (tmp_path / "plugins" / "github_sync.py").exists()
    disabled = hub.action("set_marketplace_item_enabled", {"id": "github-sync", "enabled": False})
    updated = hub.action("update_marketplace_item", {"id": "github-sync", "version": "1.2.0"})
    uninstalled = hub.action("uninstall_marketplace_item", {"id": "github-sync"})

    assert blocked["error"] == "marketplace item requires review before install"
    assert reviewed["result"]["review_status"] == "approved"
    assert blocked_unsigned["error"] == "marketplace item verification failed"
    assert verified["result"]["status"] == "passed"
    assert installed_enabled is True
    assert installed_artifact_exists
    assert disabled["result"]["enabled"] is False
    assert updated["result"]["version"] == "1.2.0"
    assert uninstalled["result"]["installed"] is False
    assert not (tmp_path / "plugins" / "github_sync.py").exists()


def test_marketplace_registry_sync_and_verification_gate(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    synced = hub.action(
        "sync_marketplace_registry",
        {
            "items": [
                {
                    "id": "signed-tool",
                    "name": "Signed Tool",
                    "kind": "tool",
                    "version": "2.0.0",
                    "checksum": "sha256:signed-tool-200",
                    "signature": "mica:signed-tool-200",
                    "review_status": "approved",
                    "trust": "community",
                    "entrypoint": "signed_tool",
                }
            ]
        },
    )
    verified = hub.action("verify_marketplace_item", {"id": "signed-tool"})
    installed = hub.action("install_marketplace_item", {"id": "signed-tool"})

    assert synced["result"]["items"][0]["id"] == "signed-tool"
    assert verified["result"]["status"] == "passed"
    assert installed["result"]["verification"]["status"] == "passed"
    assert (tmp_path / "plugins" / "signed_tool.manifest.json").exists()


def test_marketplace_policy_blocks_risky_permissions_until_policy_changes(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    hub.action(
        "sync_marketplace_registry",
        {
            "items": [
                {
                    "id": "secret-sync",
                    "name": "Secret Sync",
                    "kind": "connector",
                    "version": "1.0.0",
                    "checksum": "sha256:secret-sync-100",
                    "signature": "mica:secret-sync-100",
                    "review_status": "approved",
                    "trust": "community",
                    "publisher": "community-lab",
                    "permissions": ["tools:execute", "secrets:read"],
                    "entrypoint": "secret_sync",
                }
            ]
        },
    )
    verification = hub.action("verify_marketplace_item", {"id": "secret-sync"})["result"]
    blocked = hub.action("install_marketplace_item", {"id": "secret-sync"})
    policy = hub.action(
        "save_marketplace_policy",
        {"permission_denylist": [], "max_risk": "high", "trusted_publishers": ["mica", "community-lab"]},
    )["result"]
    verified_again = hub.action("verify_marketplace_item", {"id": "secret-sync"})["result"]
    installed = hub.action("install_marketplace_item", {"id": "secret-sync"})
    snapshot = hub.snapshot()

    assert verification["status"] == "failed"
    assert verification["risk"]["level"] == "medium"
    assert any(check["name"] == "trust_policy" and "denied permissions" in check["detail"] for check in verification["checks"])
    assert blocked["error"] == "marketplace item verification failed"
    assert policy["max_risk"] == "high"
    assert verified_again["status"] == "passed"
    assert installed["result"]["installed"] is True
    assert snapshot["marketplace_audit"][0]["action"] == "install"
    assert any(event["action"] == "install_blocked" for event in snapshot["marketplace_audit"])


def test_published_agent_manifest_and_invoke(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    manifest = hub.get_agent_manifest("research-copilot")
    invocation = hub.invoke_agent("research-copilot", {"message": "Summarize this"})

    assert manifest is not None
    assert manifest["endpoints"]["rest"] == "/api/agents/research-copilot/invoke"
    assert invocation["status"] == "completed"
    assert invocation["tool_plan"]


def test_published_agent_policy_and_deployment_readiness(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    published = hub.action(
        "publish_agent",
        {
            "agent_id": "research-copilot",
            "kind": "rest-api",
            "policy": {"auth": "api-key", "rate_limit_per_minute": 3, "secret_refs": ["MICA_AGENT_TOKEN"]},
        },
    )["result"]
    published_auth = published["policy"]["auth"]
    blocked = hub.invoke_agent("research-copilot", {"message": "No token"})
    unconfigured = hub.invoke_agent("research-copilot", {"message": "No issued key", "api_key": "test-key"})
    issued = hub.action("issue_publish_api_key", {"id": published["id"], "name": "CI Key"})
    invalid = hub.invoke_agent("research-copilot", {"message": "Bad token", "api_key": "test-key"})
    allowed = hub.invoke_agent("research-copilot", {"message": "Token", "api_key": issued["result"]["api_key"]})
    revoked = hub.action("revoke_publish_api_key", {"id": published["id"], "key_id": issued["result"]["key"]["id"]})
    revoked_call = hub.invoke_agent("research-copilot", {"message": "Token", "api_key": issued["result"]["api_key"]})
    publish_snapshot = hub.snapshot()
    published_snapshot = next(item for item in publish_snapshot["publishing"] if item["id"] == published["id"])
    policy = hub.action(
        "save_publish_policy",
        {"id": published["id"], "auth": "workspace", "rate_limit_per_minute": 10, "allowed_groups": ["core"]},
    )["result"]
    readiness = hub.action("check_deployment_readiness", {"target": "production"})["result"]
    manifest_path = tmp_path / "published" / "research-copilot" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert published_auth == "api-key"
    assert manifest["policy"]["auth"] == "api-key"
    assert manifest["policy"]["secret_refs"] == ["configured"]
    assert blocked["error"] == "api key required"
    assert unconfigured["error"] == "api key not configured"
    assert invalid["error"] == "invalid api key"
    assert allowed["status"] == "completed"
    assert revoked["result"]["key"]["status"] == "revoked"
    assert revoked_call["error"] in {"api key not configured", "invalid api key"}
    assert published_snapshot["policy"]["api_keys"][0]["status"] == "revoked"
    assert publish_snapshot["invocation_audit"][0]["status"] == "denied"
    assert policy["policy"]["auth"] == "workspace"
    assert readiness["status"] == "ready"
    assert any(check["name"] == "Dockerfile" for check in readiness["checks"])
    assert any(check["name"] == "Postgres migrations" for check in readiness["checks"])
    assert readiness["validation"]["status"] == "ready"
    validation_names = {check["name"] for check in readiness["validation"]["checks"]}
    assert "compose:postgres_service" in validation_names
    assert "compose:migration_mount" in validation_names
    assert "compose:env_substitution" in validation_names
    assert "compose:resource_limits" in validation_names
    assert "compose:replica_hint" in validation_names
    assert "dockerfile:non_root_user" in validation_names
    assert "helm:migration_configmap" in validation_names
    assert "helm:secret_values" in validation_names
    assert "helm:pod_security_context" in validation_names
    assert "helm:container_security_context" in validation_names
    assert "helm:resource_values" in validation_names
    assert readiness["checks"]


def test_database_migration_catalog_tracks_pending_and_applied(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    pending = hub.action("check_database_migrations", {})["result"]
    applied = hub.action("check_database_migrations", {"applied": ["001_platform_hub"]})["result"]

    assert pending["status"] == "pending"
    assert pending["pending"] == ["001_platform_hub"]
    assert pending["catalog"][0]["checksum"]
    assert "platform_agents" in pending["catalog"][0]["tables"]
    assert applied["status"] == "ready"
    assert applied["pending"] == []


def test_agent_publishing_exposes_web_embed_and_mcp_descriptor(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    web_app = hub.get_agent_web_app("research-copilot")
    embed = hub.get_agent_web_app("research-copilot", embedded=True)
    descriptor = hub.get_agent_mcp_descriptor("research-copilot")

    assert web_app is not None
    assert "Research Copilot" in web_app
    assert "/api/agents/research-copilot/invoke" in web_app
    assert embed is not None
    assert 'class="embed"' in embed
    assert descriptor is not None
    assert descriptor["tools"][0]["name"] == "invoke_agent"
    assert descriptor["manifest"]["endpoints"]["mcp"] == "/mcp/research-copilot"


def test_identity_provider_scim_and_knowledge_runs(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    provider = hub.action(
        "save_identity_provider",
        {
            "name": "Acme OIDC",
            "type": "oidc",
            "issuer": "https://login.acme.test",
            "client_id": "mica",
        },
    )
    tested = hub.action("test_identity_provider", {"id": provider["result"]["id"]})
    provisioned = hub.action(
        "provision_scim_user",
        {"name": "SCIM Person", "email": "scim@acme.test", "roles": "viewer", "groups": "core"},
    )
    claims = hub.action(
        "sync_identity_claims",
        {
            "provider_id": provider["result"]["id"],
            "claims": {"email": "claim@acme.test", "name": "Claim User", "groups": ["research"], "roles": ["builder"]},
        },
    )
    deprovisioned = hub.action("deprovision_scim_user", {"email": "scim@acme.test"})
    source = hub.action(
        "save_knowledge_source",
        {
            "source": "GitHub",
            "target": "Acme Repo",
            "uri": "https://github.com/acme/repo",
            "vector_db": "qdrant",
        },
    )
    synced = hub.action("sync_knowledge", {"id": source["result"]["id"]})
    search = hub.action("search_knowledge", {"query": "hybrid vector reranker", "source_ids": [source["result"]["id"]]})

    assert provider["status"] == "ok"
    assert tested["result"]["status"] == "verified"
    assert provisioned["result"]["event"]["status"] == "completed"
    assert claims["result"]["mapped_claims"]["groups"] == ["research"]
    assert deprovisioned["result"]["user"]["status"] == "deprovisioned"
    assert synced["result"]["run"]["status"] == "completed"
    assert synced["result"]["run"]["documents"] >= 1
    assert synced["result"]["run"]["chunks"] >= 1
    assert synced["result"]["run"]["index"]["bm25_terms"] >= 1
    assert search["result"]["retrieval"] == "hybrid:bm25+vector+cross-encoder-rerank"
    assert search["result"]["results"][0]["rerank_score"] >= search["result"]["results"][-1]["rerank_score"]
    assert [phase["name"] for phase in synced["result"]["run"]["phases"]] == [
        "fetch",
        "extract",
        "bm25_index",
        "vector_index",
        "cross_encoder_rerank_ready",
    ]


def test_sso_login_flows_create_sessions_and_mask_tokens(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    provider = hub.action(
        "save_identity_provider",
        {"name": "Flow OIDC", "type": "oidc", "issuer": "https://login.flow.test", "client_id": "mica"},
    )["result"]
    started = hub.action("start_sso_login", {"provider_id": provider["id"], "redirect_uri": "/callback"})["result"]
    completed = hub.action(
        "complete_sso_login",
        {
            "state": started["flow"]["state"],
            "claims": {"email": "flow@acme.test", "name": "Flow User", "groups": ["core"], "roles": ["builder"]},
        },
    )["result"]
    snapshot = hub.snapshot()

    assert "authorize" in started["authorization_url"]
    assert completed["flow"]["status"] == "completed"
    assert completed["session"]["status"] == "active"
    assert completed["user"]["email"] == "flow@acme.test"
    assert snapshot["sso"]["sessions"][0]["token"].startswith("***")
    assert snapshot["sso"]["events"][0]["action"] == "login_completed"


def test_oidc_callback_validates_signed_jwks_token(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )
    secret = "mica-test-oidc-secret"
    provider = hub.action(
        "save_identity_provider",
        {
            "name": "Signed OIDC",
            "type": "oidc",
            "issuer": "https://login.signed.test",
            "client_id": "mica",
            "audience": "mica",
            "jwks": {"keys": [{"kid": "local-dev", "kty": "oct", "alg": "HS256", "k": secret}]},
            "allowed_algs": ["HS256"],
        },
    )["result"]
    tested = hub.action("test_identity_provider", {"id": provider["id"]})["result"]
    started = hub.action("start_sso_login", {"provider_id": provider["id"], "redirect_uri": "/callback"})["result"]
    claims = {
        "iss": "https://login.signed.test",
        "aud": "mica",
        "exp": int(time.time()) + 600,
        "iat": int(time.time()),
        "nonce": started["flow"]["nonce"],
        "email": "signed@acme.test",
        "name": "Signed User",
        "groups": ["core"],
        "roles": ["builder"],
    }
    token = _signed_hs256_jwt({"alg": "HS256", "kid": "local-dev", "typ": "JWT"}, claims, secret)
    completed = hub.action(
        "complete_sso_login",
        {"state": started["flow"]["state"], "id_token": token, "device_name": "OIDC Browser"},
    )["result"]
    snapshot = hub.snapshot()

    assert {check["name"]: check["status"] for check in tested["checks"]}["jwks"] == "passed"
    assert completed["flow"]["status"] == "completed"
    assert completed["flow"]["token_validation"]["status"] == "passed"
    assert completed["user"]["email"] == "signed@acme.test"
    snapshot_provider = next(item for item in snapshot["identity_providers"] if item["id"] == provider["id"])
    assert snapshot_provider["jwks"]["keys"][0]["k"] == "***"
    assert snapshot["sso"]["events"][0]["details"]["token_validation"]["kid"] == "local-dev"


def test_oidc_callback_validates_rs256_jwks_token(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    provider = hub.action(
        "save_identity_provider",
        {
            "name": "Enterprise RS256",
            "type": "oidc",
            "discovery": {
                "issuer": "https://login.enterprise.test",
                "jwks_uri": "https://login.enterprise.test/.well-known/jwks.json",
                "authorization_endpoint": "https://login.enterprise.test/oauth2/v2.0/authorize",
                "token_endpoint": "https://login.enterprise.test/oauth2/v2.0/token",
            },
            "client_id": "mica-enterprise",
            "audience": "mica-enterprise",
            "jwks": {"keys": [_rsa_public_jwk(private_key, "rsa-key-1")]},
            "allowed_algs": ["RS256"],
        },
    )["result"]
    started = hub.action("start_sso_login", {"provider_id": provider["id"], "redirect_uri": "/callback"})["result"]
    token = _signed_rs256_jwt(
        {"alg": "RS256", "kid": "rsa-key-1", "typ": "JWT"},
        {
            "iss": "https://login.enterprise.test",
            "aud": ["mica-enterprise", "account"],
            "exp": int(time.time()) + 600,
            "iat": int(time.time()),
            "nonce": started["flow"]["nonce"],
            "email": "enterprise@acme.test",
            "name": "Enterprise User",
            "groups": ["platform"],
            "roles": ["admin"],
        },
        private_key,
    )
    completed = hub.action("complete_sso_login", {"state": started["flow"]["state"], "id_token": token})["result"]

    assert started["flow"]["authorization_endpoint"].endswith("/oauth2/v2.0/authorize")
    assert completed["flow"]["token_validation"]["status"] == "passed"
    assert completed["flow"]["token_validation"]["alg"] == "RS256"
    assert completed["user"]["roles"] == ["admin"]


def test_oidc_callback_rejects_invalid_audience(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )
    secret = "mica-test-oidc-secret"
    provider = hub.action(
        "save_identity_provider",
        {
            "name": "Audience OIDC",
            "type": "oidc",
            "issuer": "https://login.audience.test",
            "client_id": "mica",
            "audience": "mica",
            "jwks": {"keys": [{"kid": "audience-key", "kty": "oct", "alg": "HS256", "k": secret}]},
        },
    )["result"]
    started = hub.action("start_sso_login", {"provider_id": provider["id"]})["result"]
    token = _signed_hs256_jwt(
        {"alg": "HS256", "kid": "audience-key", "typ": "JWT"},
        {
            "iss": "https://login.audience.test",
            "aud": "other-client",
            "exp": int(time.time()) + 600,
            "nonce": started["flow"]["nonce"],
            "email": "wrong@acme.test",
        },
        secret,
    )
    rejected = hub.action("complete_sso_login", {"state": started["flow"]["state"], "id_token": token})["result"]

    assert rejected["error"] == "invalid token audience"
    assert rejected["flow"]["status"] == "failed"
    assert hub.snapshot()["sso"]["events"][0]["action"] == "login_failed"


def test_ldap_bind_login_creates_audited_session(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    provider = hub.action(
        "save_identity_provider",
        {"name": "Corp LDAP", "type": "ldap", "ldap_url": "ldaps://ldap.acme.test"},
    )["result"]
    login = hub.action("ldap_bind_login", {"provider_id": provider["id"], "username": "ldap.user", "groups": ["core"]})["result"]

    assert login["session"]["provider_id"] == provider["id"]
    assert login["user"]["email"] == "ldap.user@ldap.local"
    assert hub.snapshot()["sso"]["events"][0]["action"] == "ldap_bind"


def test_companion_workspace_files_and_terminal_are_guarded(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    files = hub.action("list_workspace_files", {"path": "."})
    readme = hub.action("read_workspace_file", {"path": "pyproject.toml", "max_bytes": 1200})
    outside = hub.action("read_workspace_file", {"path": "..\\outside.txt"})
    pairing = hub.action("create_companion_pairing", {"device_name": "Phone"})
    activated = hub.action(
        "activate_companion_session",
        {"code": pairing["result"]["code"], "device_name": "Phone"},
    )
    session_id = activated["result"]["session"]["id"]
    workspace = hub.action("get_companion_workspace", {"session_id": session_id})
    terminal = hub.action("run_companion_terminal", {"command": "python version", "session_id": session_id})
    revoked = hub.action("revoke_companion_session", {"session_id": session_id})
    denied_terminal = hub.action("run_companion_terminal", {"command": "format disk"})
    denied_after_revoke = hub.action("run_companion_terminal", {"command": "python version", "session_id": session_id})
    local_terminal = hub.action("run_local_terminal", {"command": "python version"})
    denied_local_terminal = hub.action("run_local_terminal", {"command": "format disk"})

    assert files["result"]["entries"]
    assert readme["result"]["name"] == "pyproject.toml"
    assert outside["error"] == "path outside workspace"
    assert activated["result"]["session"]["status"] == "active"
    assert workspace["result"]["status"] == "ready"
    assert terminal["result"]["status"] == "completed"
    assert local_terminal["result"]["status"] == "completed"
    assert denied_local_terminal["error"] == "command not allowed"
    assert revoked["result"]["session"]["status"] == "revoked"
    assert denied_terminal["error"] == "companion session required"
    assert denied_after_revoke["error"] == "companion session inactive"
    assert hub.snapshot()["companion"]["pairing_codes"][0]["code"].startswith("***")


def test_knowledge_scheduler_plans_and_runs_due_sources(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
        ingestion_dir=tmp_path / "ingestion",
        sandbox_artifact_dir=tmp_path / "sandbox",
    )

    source = hub.action(
        "save_knowledge_source",
        {
            "source": "Drive",
            "target": "Due Drive",
            "uri": "drive://due",
            "schedule": "hourly",
            "next_sync": "2000-01-01T00:00:00",
        },
    )["result"]
    scheduled = hub.action("schedule_knowledge_sync", {"id": source["id"], "schedule": "*/15 * * * *"})
    assert scheduled["result"]["status"] == "scheduled"
    assert scheduled["result"]["next_sync"]

    due = hub.action("run_due_knowledge_syncs", {"ids": [source["id"]], "force": True})

    assert due["result"]["scheduler"]["synced_sources"] == 1
    assert due["result"]["runs"][0]["source_id"] == source["id"]
    assert hub.snapshot()["knowledge_scheduler_runs"][0]["runs"]


def test_evaluation_runs_and_agent_chains(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )

    evaluation = hub.action("run_evaluation", {"id": "eval-support"})
    chain = hub.action(
        "run_agent_chain",
        {
            "agent_id": "research-copilot",
            "goal": "Investigate issue and return compact context.",
        },
    )

    assert evaluation["result"]["run"]["cases"]
    assert evaluation["result"]["evaluation"]["last_score"] > 0
    assert evaluation["result"]["run"]["pairs"]
    assert evaluation["result"]["run"]["gate"]["status"] == "passed"
    assert evaluation["result"]["run"]["winner"] in evaluation["result"]["run"]["elo_delta"]
    assert chain["result"]["status"] == "completed"
    assert len(chain["result"]["steps"]) >= 2
    assert "compact context" in chain["result"]["compact_result"]


def test_document_ingestion_and_sandbox_artifacts(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
        ingestion_dir=tmp_path / "ingestion",
        sandbox_artifact_dir=tmp_path / "sandbox",
    )

    config = hub.action(
        "configure_extraction",
        {"engine": "Docling", "tables": True, "layout": True, "ocr": True, "batch_size": 25},
    )
    ingestion = hub.action(
        "ingest_documents",
        {"files": ["contract.pdf", "scan.png"], "engine": "Docling"},
    )
    sandbox = hub.action(
        "run_sandbox",
        {"language": "python", "code": "print('chart-ready')"},
    )

    assert config["result"]["config"]["batch_size"] == 25
    assert ingestion["result"]["status"] == "completed"
    assert len(ingestion["result"]["documents"]) == 2
    assert ingestion["result"]["artifact_id"].startswith("artifact-")
    assert ingestion["result"]["documents"][0]["ocr_confidence"] >= 0.9
    assert ingestion["result"]["documents"][0]["ocr_spans"] >= 1
    assert ingestion["result"]["documents"][0]["rag_ready"] is True
    assert ingestion["result"]["documents"][0]["quality_gates"][0]["name"] == "ocr_confidence"
    assert ingestion["result"]["diagnostics"]["tables_total"] == 2
    assert ingestion["result"]["diagnostics"]["rag_ready"] is True
    assert ingestion["result"]["documents"][0]["searchable_path"].endswith("doc-1-searchable.json")
    assert hub.snapshot()["extraction"]["batch_queue"][-1]["status"] == "completed"
    assert (tmp_path / "ingestion" / ingestion["result"]["id"] / "doc-1.txt").exists()
    table_payload = json.loads((tmp_path / "ingestion" / ingestion["result"]["id"] / "doc-1-tables.json").read_text(encoding="utf-8"))
    searchable_payload = json.loads((tmp_path / "ingestion" / ingestion["result"]["id"] / "doc-1-searchable.json").read_text(encoding="utf-8"))
    report_payload = json.loads((tmp_path / "ingestion" / ingestion["result"]["id"] / "doc-1-report.json").read_text(encoding="utf-8"))
    assert table_payload[0]["cells"][0]["bbox"]
    assert searchable_payload["rerank_features"]["tables"] == 1
    assert report_payload["quality_gates"][-1]["name"] == "rag_ready"
    assert sandbox["result"]["artifacts"]
    assert (tmp_path / "sandbox" / sandbox["result"]["id"] / "chart.json").exists()


def test_artifact_versioning_and_rendering(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
        ingestion_dir=tmp_path / "ingestion",
        sandbox_artifact_dir=tmp_path / "sandbox",
    )

    created = hub.action(
        "create_artifact",
        {"title": "Decision Note", "kind": "mermaid", "content": "flowchart LR\nA-->B"},
    )["result"]
    created_version = created["version"]
    versioned = hub.action(
        "version_artifact",
        {"id": created["id"], "content": "flowchart LR\nA-->B\nB-->C"},
    )["result"]
    rendered = hub.action("render_artifact", {"id": created["id"]})["result"]

    assert created_version == 1
    assert versioned["version"] == 2
    assert len(versioned["versions"]) == 2
    assert rendered["status"] == "ready"
    assert rendered["artifact_id"] == created["id"]


def test_openapi_execution_plan_and_mcp_deferred_loading(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
        ingestion_dir=tmp_path / "ingestion",
        sandbox_artifact_dir=tmp_path / "sandbox",
    )

    imported = hub.action(
        "import_openapi",
        {
            "spec": {
                "openapi": "3.0.0",
                "servers": [{"url": "https://api.example.test"}],
                "paths": {
                    "/tickets/{id}": {
                        "get": {
                            "operationId": "getTicket",
                            "parameters": [
                                {"name": "verbose", "in": "query", "schema": {"type": "boolean"}}
                            ],
                        }
                    }
                },
            }
        },
    )
    tool = imported["result"]["imported"][0]
    execution = hub.action(
        "execute_openapi_tool",
        {"id": tool["id"], "parameters": {"id": "T-42", "verbose": True}},
    )
    discovered = hub.action("discover_mcp_tools", {"query": "files"})
    loaded = hub.action("load_mcp_tool", {"name": discovered["result"]["tools"][0]["name"]})
    unloaded = hub.action("unload_mcp_tool", {"name": loaded["result"]["name"]})

    assert execution["result"]["request"]["url"] == "https://api.example.test/tickets/T-42"
    assert execution["result"]["request"]["query"] == {"verbose": True}
    assert loaded["result"]["kind"] == "mcp"
    assert unloaded["result"]["status"] == "deferred"


def test_platform_action_metrics_are_recorded_and_aggregated(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
        ingestion_dir=tmp_path / "ingestion",
        sandbox_artifact_dir=tmp_path / "sandbox",
    )

    hub.action("run_agent_chain", {"agent_id": "research-copilot", "goal": "measure this"})
    hub.action("ingest_documents", {"files": ["a.pdf"]})
    aggregate = hub.action(
        "aggregate_metrics",
        {"dimensions": ["model", "tool", "user", "agent", "workflow"], "top_n": 5},
    )
    workflow_aggregate = hub.snapshot()["metrics_aggregate"]["workflow"]
    filtered = hub.action(
        "aggregate_metrics",
        {"dimensions": ["tool"], "filters": {"tool": "run_agent_chain"}, "top_n": 1},
    )

    assert aggregate["result"]["event_count"] >= 2
    assert aggregate["result"]["aggregates"]["tool"]
    assert any(row["key"] == "run_agent_chain" for row in aggregate["result"]["aggregates"]["tool"])
    assert filtered["result"]["event_count"] == 1
    assert filtered["result"]["aggregates"]["tool"][0]["key"] == "run_agent_chain"
    assert workflow_aggregate


def test_platform_actions_enforce_rbac_and_record_audit_events(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
        ingestion_dir=tmp_path / "ingestion",
        sandbox_artifact_dir=tmp_path / "sandbox",
    )

    viewer = hub.action(
        "save_user",
        {
            "name": "View Only",
            "email": "view@mica.local",
            "roles": ["viewer"],
        },
    )["result"]
    denied = hub.action(
        "save_tool",
        {
            "user": viewer["id"],
            "name": "Viewer Tool",
            "kind": "function",
            "code": "return 'nope'",
        },
    )
    allowed = hub.action(
        "save_tool",
        {
            "user": "u-builder",
            "name": "Builder Tool",
            "kind": "function",
            "code": "return parameters.get('text', '')",
        },
    )
    shared = hub.action(
        "share_agent",
        {
            "user": "u-admin",
            "agent_id": "research-copilot",
            "subjects": [{"type": "group", "id": "research", "access": "read"}],
        },
    )

    assert denied["error"] == "permission denied"
    assert denied["result"]["permission"] == "tools:write"
    assert allowed["status"] == "ok"
    assert shared["result"]["acl"]["resource"] == "agent:research-copilot"
    audit_events = hub.snapshot()["audit_events"]
    assert any(event["status"] == "denied" and event["action"] == "save_tool" for event in audit_events)
    assert any(event["status"] == "ok" and event["action"] == "share_agent" for event in audit_events)


def test_sandbox_blocks_unsafe_code_and_tracks_uploaded_files(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
        ingestion_dir=tmp_path / "ingestion",
        sandbox_artifact_dir=tmp_path / "sandbox",
    )

    blocked = hub.action("run_sandbox", {"code": "import socket\nprint('no')"})
    uploaded = hub.action(
        "run_sandbox",
        {
            "code": "print('uploaded')",
            "files": [{"name": "input.txt", "content": "hello"}],
        },
    )
    upload_blocked = hub.action(
        "run_sandbox",
        {
            "code": "print('too many uploads')",
            "files": [{"name": f"input-{index}.txt", "content": "x"} for index in range(12)],
        },
    )
    manifest_path = tmp_path / "sandbox" / uploaded["result"]["id"] / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot = hub.snapshot()

    assert blocked["result"]["status"] == "blocked"
    assert "import socket" in blocked["result"]["stderr"]
    assert uploaded["result"]["status"] == "completed"
    assert uploaded["result"]["policy"]["network"] == "disabled"
    assert uploaded["result"]["limits"]["timeout_seconds"] == 5
    assert uploaded["result"]["uploaded_files"][0]["name"] == "input.txt"
    assert any(artifact["kind"] == "files" for artifact in uploaded["result"]["artifacts"])
    assert any(artifact["kind"] == "manifest" for artifact in uploaded["result"]["artifacts"])
    assert manifest["policy"]["filesystem"] == "uploads-only"
    assert upload_blocked["result"]["status"] == "blocked"
    assert "blocked upload" in upload_blocked["result"]["stderr"]
    assert snapshot["sandbox"]["audit"][0]["status"] == "blocked"
    assert any(event["run_id"] == uploaded["result"]["id"] for event in snapshot["sandbox"]["audit"])


def test_javascript_sandbox_executes_and_blocks_unsafe_code(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
        ingestion_dir=tmp_path / "ingestion",
        sandbox_artifact_dir=tmp_path / "sandbox",
    )

    executed = hub.action(
        "run_sandbox",
        {
            "language": "javascript",
            "code": "console.log('js-ready'); return {answer: 42, uploadDir: Boolean(sandbox.uploadsDir)};",
            "files": [{"name": "input.txt", "content": "hello"}],
        },
    )
    blocked = hub.action(
        "run_sandbox",
        {"language": "javascript", "code": "const fs = require('fs'); console.log(fs.readdirSync('.'));"},
    )

    assert executed["result"]["status"] == "completed"
    assert "js-ready" in executed["result"]["stdout"]
    assert '"answer":42' in executed["result"]["stdout"].replace(" ", "")
    assert executed["result"]["policy"]["network"] == "disabled"
    assert executed["result"]["uploaded_files"][0]["name"] == "input.txt"
    assert any(artifact["kind"] == "manifest" for artifact in executed["result"]["artifacts"])
    assert any(artifact["kind"] == "files" for artifact in executed["result"]["artifacts"])
    assert blocked["result"]["status"] == "blocked"
    assert "require" in blocked["result"]["stderr"]


def test_agent_management_lifecycle_and_run_controls(tmp_path):
    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
        ingestion_dir=tmp_path / "ingestion",
        sandbox_artifact_dir=tmp_path / "sandbox",
        agent_package_dir=tmp_path / "agent-packages",
    )

    saved = hub.action(
        "save_agent",
        {
            "id": "ops-agent",
            "name": "Ops Agent",
            "model": "fast",
            "prompt": "Operate safely.",
            "tools": ["summarize_text"],
            "knowledge": ["local-documents"],
            "permissions": ["tools:execute", "knowledge:read"],
            "parameters": {"temperature": 0.2, "max_tokens": 900},
        },
    )
    assert saved["result"]["permissions"] == ["tools:execute", "knowledge:read"]

    started = hub.action("start_agent_run", {"agent_id": "ops-agent", "assignment": "Prüfe den Systemstatus."})
    run_id = started["result"]["id"]
    assert started["result"]["status"] == "running"
    assert hub.action("pause_agent_run", {"run_id": run_id})["result"]["status"] == "paused"
    assert hub.action("resume_agent_run", {"run_id": run_id})["result"]["status"] == "running"

    active_delete = hub.action("delete_agent", {"agent_id": "ops-agent"})
    assert active_delete["error"] == "agent has active runs"

    stopped = hub.action("stop_agent_run", {"run_id": run_id})
    assert stopped["result"]["status"] == "stopped"
    assert len(stopped["result"]["logs"]) == 4

    exported = hub.action("export_agent_package", {"agent_id": "ops-agent"})
    imported = hub.action("import_agent_package", {"package": exported["result"]["package"], "id": "ops-copy"})
    assert imported["result"]["agent"]["permissions"] == ["tools:execute", "knowledge:read"]
    assert imported["result"]["agent"]["id"] == "ops-copy-import"

    deleted = hub.action("delete_agent", {"agent_id": "ops-agent"})
    assert deleted["result"]["deleted"] is True
    snapshot = hub.snapshot()
    assert not any(agent["id"] == "ops-agent" for agent in snapshot["agents"])
    assert any(run["id"] == run_id and run["status"] == "stopped" for run in snapshot["agent_runs"])
