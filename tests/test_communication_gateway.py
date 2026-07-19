from __future__ import annotations

from pathlib import Path
import base64
import hashlib
import hmac

from core.communication_gateway import CommunicationGateway
from core.telephony import TelephonyGateway, normalize_phone_number


class FakeConfig:
    def __init__(self, values: dict):
        self.values = values

    def get(self, key: str, default=None):
        value = self.values
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value


class FakeCrossDevice:
    telegram_bot = object()
    discord_bot = None

    def __init__(self, updates=None):
        self.updates = updates or []
        self.replies = []

    def sync_get_telegram_updates(self, offset=0, timeout=0):
        return self.updates

    def sync_download_telegram_file(self, file_id, destination):
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"voice")
        return str(target)

    def sync_answer_telegram_callback(self, callback_query_id, text=""):
        return True

    def sync_send_summary(self, text, channel):
        return True


def gateway_config():
    return FakeConfig(
        {
            "cross_device": {
                "telegram": {
                    "enabled": True,
                    "chat_id": "42",
                    "allowed_sender_ids": ["42"],
                },
                "discord": {"enabled": False},
            },
            "communications": {
                "telephony": {"enabled": False},
                "proactive": {"channels": ["telegram"]},
            },
        }
    )


def test_pairing_requires_confirmation_and_persists(tmp_path, monkeypatch):
    fake = FakeCrossDevice()
    monkeypatch.setattr("core.communication_gateway.get_cross_device", lambda: fake)
    monkeypatch.setattr("core.communication_gateway.get_telephony_gateway", lambda: TelephonyGateway(gateway_config()))
    path = tmp_path / "communications.json"
    gateway = CommunicationGateway(path, gateway_config())

    denied = gateway.pair_identity("telegram", "99")
    paired = gateway.pair_identity("telegram", "99", label="Phone", confirmed=True)
    restored = CommunicationGateway(path, gateway_config())

    assert denied["approval_required"] is True
    assert paired["ok"] is True
    assert restored.is_sender_allowed("telegram", "99") is True


def test_authorized_telegram_text_is_forwarded(tmp_path, monkeypatch):
    fake = FakeCrossDevice()
    monkeypatch.setattr("core.communication_gateway.get_cross_device", lambda: fake)
    monkeypatch.setattr("core.communication_gateway.get_telephony_gateway", lambda: TelephonyGateway(gateway_config()))
    received = []
    gateway = CommunicationGateway(tmp_path / "communications.json", gateway_config())
    gateway.set_command_handler(received.append)
    monkeypatch.setattr(gateway, "_send_telegram_reply", lambda text, chat_id: True)

    result = gateway.process_telegram_update(
        {"update_id": 7, "message": {"chat": {"id": 42}, "text": "Erstelle eine Zusammenfassung"}}
    )
    for thread in __import__("threading").enumerate():
        if thread.name == "MICACommunicationCommand":
            thread.join(timeout=1)

    assert result["ok"] is True
    assert received == ["[telegram von 42] Erstelle eine Zusammenfassung"]
    assert result["event"]["status"] == "queued"


def test_unauthorized_telegram_sender_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr("core.communication_gateway.get_cross_device", lambda: FakeCrossDevice())
    monkeypatch.setattr("core.communication_gateway.get_telephony_gateway", lambda: TelephonyGateway(gateway_config()))
    gateway = CommunicationGateway(tmp_path / "communications.json", gateway_config())

    result = gateway.process_telegram_update(
        {"update_id": 8, "message": {"chat": {"id": 9001}, "text": "/status"}}
    )

    assert result == {"ok": False, "error": "sender is not paired", "sender_id": "9001"}


def test_telephony_requires_enable_confirmation_and_allow_list(monkeypatch):
    disabled = TelephonyGateway(FakeConfig({"communications": {"telephony": {"enabled": False}}}))
    assert disabled.place_call("+431234567", "Test", confirmed=True)["error"] == "telephony is disabled"

    config = FakeConfig(
        {
            "communications": {
                "telephony": {
                    "enabled": True,
                    "provider": "twilio",
                    "account_sid": "AC-test",
                    "auth_token": "secret",
                    "from_number": "+431111111",
                    "allowed_numbers": ["+432222222"],
                }
            }
        }
    )
    gateway = TelephonyGateway(config)
    assert gateway.place_call("+432222222", "Test")["approval_required"] is True
    assert "allow-list" in gateway.place_call("+433333333", "Test", confirmed=True)["error"]
    monkeypatch.setattr(gateway, "_place_twilio_call", lambda number, message, settings: {"sid": "CA1", "status": "queued"})
    result = gateway.place_call("+43 222 2222", "Test", confirmed=True)
    assert result["ok"] is True
    assert result["call"]["provider_id"] == "CA1"


def test_phone_normalization_and_twiml_escape():
    gateway = TelephonyGateway(FakeConfig({"communications": {"telephony": {"language": "de-DE"}}}))
    xml = gateway.voice_response("M.I.C.A & du", gather=True)

    assert normalize_phone_number("+43 (660) 1234567") == "+436601234567"
    assert normalize_phone_number("12") == ""
    assert "M.I.C.A &amp; du" in xml
    assert "<Gather" in xml


def test_twilio_webhook_signature_is_verified():
    url = "https://example.test/api/communications/telephony"
    config = FakeConfig(
        {"communications": {"telephony": {"provider": "twilio", "auth_token": "secret", "webhook_url": url}}}
    )
    gateway = TelephonyGateway(config)
    parameters = {"From": "+432222222", "SpeechResult": "Hallo"}
    signed = url + "".join(f"{key}{parameters[key]}" for key in sorted(parameters))
    signature = base64.b64encode(hmac.new(b"secret", signed.encode(), hashlib.sha1).digest()).decode()

    assert gateway.validate_webhook(parameters, signature) is True
    assert gateway.validate_webhook(parameters, "invalid") is False
