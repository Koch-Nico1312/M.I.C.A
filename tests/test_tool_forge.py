import json
from pathlib import Path

from core.plugin_system import PluginManager
from core.tool_forge import ToolForge


def test_tool_forge_plan_forge_validate_activate_flow(tmp_path):
    forge = ToolForge(root=tmp_path)

    plan = forge.plan_tool(
        "Echo a short text payload for diagnostics.",
        tool_name="diagnostic_echo",
        permissions=["text:read"],
    )

    assert plan["tool_name"] == "diagnostic_echo"
    assert plan["approval_required"]["before_code_generation"] is True
    assert Path(plan["quarantine_dir"]).parts[-3:] == ("plugins", "generated", "diagnostic_echo")

    blocked = forge.forge_tool(plan["plan_id"], approved_plan=False)
    assert blocked["ok"] is False
    assert "approval" in blocked["error"].lower()

    forged = forge.forge_tool(plan["plan_id"], approved_plan=True)
    assert forged["ok"] is True

    manifest_path = tmp_path / "plugins" / "generated" / "diagnostic_echo" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["enabled"] is False

    manager = PluginManager(plugins_dir=tmp_path / "plugins" / "generated")
    assert manager.load_all_plugins() == []

    not_activated = forge.activate_tool("diagnostic_echo", activation_approved=False)
    assert not_activated["ok"] is False

    activated = forge.activate_tool("diagnostic_echo", activation_approved=True)
    assert activated["ok"] is True
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["enabled"] is True

    manager = PluginManager(plugins_dir=tmp_path / "plugins" / "generated")
    loaded = manager.load_all_plugins()
    assert len(loaded) == 1
    assert manager.execute_tool("diagnostic_echo", {"text": "hello"}) == "diagnostic_echo received: hello"


def test_tool_forge_rejects_disallowed_permissions(tmp_path):
    forge = ToolForge(root=tmp_path)
    plan = forge.plan_tool(
        "Run arbitrary shell commands.",
        tool_name="shell_runner",
        permissions=["subprocess:run"],
    )
    forged = forge.forge_tool(plan["plan_id"], approved_plan=True)

    assert forged["ok"] is False
    checks = {check["check"]: check for check in forged["validation"]["checks"]}
    assert checks["permission_check"]["ok"] is False


def test_personality_changes_are_proposed_then_versioned_on_apply(tmp_path):
    forge = ToolForge(root=tmp_path)

    proposal = forge.propose_personality_change("Rede lockerer und direkter.")
    assert proposal["status"] == "proposed"
    assert "Proposed Style Adjustment" in proposal["diff"]

    blocked = forge.apply_personality_change(proposal["proposal_id"], approved=False)
    assert blocked["ok"] is False

    applied = forge.apply_personality_change(proposal["proposal_id"], approved=True)
    assert applied["ok"] is True
    assert Path(applied["backup_path"]).exists()
    assert "Rede lockerer und direkter." in Path(applied["soul_path"]).read_text(encoding="utf-8")
