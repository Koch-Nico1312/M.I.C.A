"""Approval-gated telephone integration for M.I.C.A.

The adapter deliberately keeps provider-specific code small.  Twilio is
supported through its REST API without adding a mandatory SDK dependency,
while SIP deployments can provide an HTTP bridge with the same payload shape.
No call is ever placed unless the caller supplies explicit confirmation and
the destination is on the configured allow-list.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from html import escape
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from urllib import error, parse, request

from config.config_loader import get_config


def normalize_phone_number(value: str) -> str:
    """Return a conservative E.164-like number or an empty string."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    prefix = "+" if raw.startswith("+") else ""
    digits = re.sub(r"\D", "", raw)
    if not 7 <= len(digits) <= 15:
        return ""
    return prefix + digits


@dataclass
class CallRecord:
    id: str
    direction: str
    number: str
    status: str
    created_at: str
    provider: str
    purpose: str = ""
    provider_id: str = ""
    error: str = ""


class TelephonyGateway:
    """Small provider gateway with opt-in and contact allow-list safeguards."""

    def __init__(self, config: Any | None = None):
        self.config = config or get_config()
        self._calls: list[CallRecord] = []

    def _settings(self) -> dict[str, Any]:
        value = self.config.get("communications.telephony", {})
        return value if isinstance(value, dict) else {}

    def _allowed_numbers(self) -> set[str]:
        configured = self._settings().get("allowed_numbers", [])
        if isinstance(configured, str):
            configured = [item.strip() for item in configured.split(",")]
        return {number for item in configured for number in [normalize_phone_number(item)] if number}

    def status(self) -> dict[str, Any]:
        settings = self._settings()
        provider = str(settings.get("provider") or "twilio").lower()
        credentials_ready = False
        if provider == "twilio":
            credentials_ready = bool(
                settings.get("account_sid")
                and settings.get("auth_token")
                and settings.get("from_number")
            )
        elif provider == "sip":
            credentials_ready = bool(settings.get("bridge_url") and settings.get("bridge_token"))
        return {
            "enabled": bool(settings.get("enabled", False)),
            "provider": provider,
            "credentials_ready": credentials_ready,
            "webhook_url": str(settings.get("webhook_url") or ""),
            "allowed_numbers": sorted(self._allowed_numbers()),
            "allow_inbound": bool(settings.get("allow_inbound", True)),
            "allow_proactive_calls": bool(settings.get("allow_proactive_calls", False)),
            "verify_webhook_signature": bool(settings.get("verify_webhook_signature", True)),
            "history": [asdict(item) for item in reversed(self._calls[-25:])],
        }

    def validate_webhook(self, parameters: dict[str, str], signature: str, url: str = "") -> bool:
        """Validate a Twilio request signature without exposing the auth token."""
        settings = self._settings()
        if str(settings.get("provider") or "twilio").lower() != "twilio":
            return True
        if not bool(settings.get("verify_webhook_signature", True)):
            return True
        token = str(settings.get("auth_token") or "")
        public_url = str(url or settings.get("webhook_url") or "")
        if not token or not public_url or not signature:
            return False
        signed = public_url + "".join(f"{key}{parameters[key]}" for key in sorted(parameters))
        expected = base64.b64encode(
            hmac.new(token.encode("utf-8"), signed.encode("utf-8"), hashlib.sha1).digest()
        ).decode("ascii")
        return hmac.compare_digest(expected, signature)

    def place_call(
        self,
        number: str,
        message: str,
        *,
        confirmed: bool = False,
        purpose: str = "",
    ) -> dict[str, Any]:
        settings = self._settings()
        normalized = normalize_phone_number(number)
        if not settings.get("enabled", False):
            return {"ok": False, "error": "telephony is disabled", "status": self.status()}
        if not confirmed:
            return {"ok": False, "approval_required": True, "error": "explicit confirmation required"}
        if not normalized:
            return {"ok": False, "error": "invalid destination number"}
        allowed = self._allowed_numbers()
        if not allowed or normalized not in allowed:
            return {"ok": False, "error": "destination is not in the telephony allow-list"}
        text = str(message or "").strip()
        if not text:
            return {"ok": False, "error": "call message is required"}

        provider = str(settings.get("provider") or "twilio").lower()
        record = CallRecord(
            id=f"call-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            direction="outbound",
            number=normalized,
            status="queued",
            created_at=datetime.now().isoformat(),
            provider=provider,
            purpose=str(purpose or ""),
        )
        self._calls.append(record)
        try:
            if provider == "twilio":
                response = self._place_twilio_call(normalized, text, settings)
            elif provider == "sip":
                response = self._place_sip_call(normalized, text, settings)
            else:
                raise ValueError(f"unsupported telephony provider: {provider}")
            record.status = str(response.get("status") or "queued")
            record.provider_id = str(response.get("sid") or response.get("id") or "")
            return {"ok": True, "call": asdict(record), "provider_response": response}
        except Exception as exc:
            record.status = "failed"
            record.error = str(exc)
            return {"ok": False, "error": str(exc), "call": asdict(record)}

    def _place_twilio_call(self, number: str, message: str, settings: dict[str, Any]) -> dict[str, Any]:
        sid = str(settings.get("account_sid") or "")
        token = str(settings.get("auth_token") or "")
        from_number = normalize_phone_number(str(settings.get("from_number") or ""))
        if not sid or not token or not from_number:
            raise RuntimeError("Twilio credentials or source number are incomplete")
        payload: dict[str, str] = {"To": number, "From": from_number}
        webhook_url = str(settings.get("webhook_url") or "").strip()
        if webhook_url:
            payload["Url"] = webhook_url
        else:
            payload["Twiml"] = self.voice_response(message, gather=False)
        encoded = parse.urlencode(payload).encode("utf-8")
        api_url = f"https://api.twilio.com/2010-04-01/Accounts/{parse.quote(sid)}/Calls.json"
        auth = base64.b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")
        req = request.Request(
            api_url,
            data=encoded,
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            # The URL above is a fixed Twilio HTTPS endpoint.
            with request.urlopen(req, timeout=20) as response:  # nosec B310
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Twilio call failed ({exc.code}): {details[:300]}") from exc

    def _place_sip_call(self, number: str, message: str, settings: dict[str, Any]) -> dict[str, Any]:
        bridge_url = str(settings.get("bridge_url") or "").strip()
        bridge_token = str(settings.get("bridge_token") or "").strip()
        if not bridge_url or not bridge_token:
            raise RuntimeError("SIP bridge URL or token is missing")
        parsed_url = parse.urlparse(bridge_url)
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if parsed_url.scheme != "https" and not (
            parsed_url.scheme == "http" and parsed_url.hostname in local_hosts
        ):
            raise RuntimeError("SIP bridge must use HTTPS (HTTP is allowed only for localhost)")
        body = json.dumps({"to": number, "message": message, "voice": settings.get("voice", "alice")}).encode("utf-8")
        req = request.Request(
            bridge_url,
            data=body,
            headers={"Authorization": f"Bearer {bridge_token}", "Content-Type": "application/json"},
            method="POST",
        )
        # The scheme and localhost exception are validated above.
        with request.urlopen(req, timeout=20) as response:  # nosec B310
            decoded = response.read().decode("utf-8")
            return json.loads(decoded) if decoded else {"status": "queued"}

    def voice_response(self, message: str, *, gather: bool = True) -> str:
        """Create TwiML for spoken output and optional speech input."""
        safe_message = escape(str(message or "Hallo, hier ist M.I.C.A."))
        settings = self._settings()
        language = escape(str(settings.get("language") or "de-DE"))
        voice = escape(str(settings.get("voice") or "alice"))
        say = f'<Say language="{language}" voice="{voice}">{safe_message}</Say>'
        if not gather:
            return f'<?xml version="1.0" encoding="UTF-8"?><Response>{say}</Response>'
        action = escape(str(settings.get("inbound_action_url") or "/api/communications/telephony"))
        gather_xml = f'<Gather input="speech" action="{action}" method="POST" speechTimeout="auto">{say}</Gather>'
        return f'<?xml version="1.0" encoding="UTF-8"?><Response>{gather_xml}<Say language="{language}">Auf Wiederhören.</Say></Response>'


_telephony_gateway: TelephonyGateway | None = None


def get_telephony_gateway() -> TelephonyGateway:
    global _telephony_gateway
    if _telephony_gateway is None:
        _telephony_gateway = TelephonyGateway()
    return _telephony_gateway


def reset_telephony_gateway() -> None:
    global _telephony_gateway
    _telephony_gateway = None


__all__ = ["CallRecord", "TelephonyGateway", "get_telephony_gateway", "normalize_phone_number", "reset_telephony_gateway"]
