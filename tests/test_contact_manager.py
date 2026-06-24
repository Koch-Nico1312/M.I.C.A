import json


def test_contact_manager_upsert_search_and_delete(tmp_path, monkeypatch):
    from actions import contact_manager as module

    contacts_path = tmp_path / "contacts.json"
    monkeypatch.setattr(module, "CONTACTS_PATH", contacts_path)

    saved = json.loads(
        module.contact_manager(
            {
                "action": "upsert",
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "tags": "engineering, math",
            }
        )
    )
    contact_id = saved["contact"]["id"]

    matches = json.loads(module.contact_manager({"action": "search", "query": "ada"}))
    assert matches["contacts"][0]["email"] == "ada@example.com"

    listed = json.loads(module.contact_manager({"action": "list"}))
    assert listed["contacts"][0]["name"] == "Ada Lovelace"

    assert module.contact_manager({"action": "delete", "id": contact_id}) == "Contact deleted."
    assert json.loads(module.contact_manager({"action": "list"}))["contacts"] == []
