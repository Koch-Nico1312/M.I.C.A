import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from actions.pi_coding_agent import pi_coding_agent


HOST = os.getenv("MICA_PI_SERVER_HOST", "0.0.0.0")
PORT = int(os.getenv("MICA_PI_SERVER_PORT", "8080"))
TOKEN = os.getenv("MICA_PI_SERVER_TOKEN", "").strip()


class MicaPiHandler(BaseHTTPRequestHandler):
    server_version = "MicaPiServer/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[mica-pi-server] {self.address_string()} - {format % args}")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if not TOKEN:
            return True
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {TOKEN}"

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "service": "mica-pi",
                    "pi_enabled": os.getenv("MICA_PI_ENABLED", "").lower() == "true",
                    "workspace_root": os.getenv("MICA_PI_WORKSPACE_ROOT", "/workspace/projects"),
                },
            )
            return

        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/tool/pi_coding_agent":
            self._send_json(404, {"ok": False, "error": "not found"})
            return

        if not self._authorized():
            self._send_json(401, {"ok": False, "error": "unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"ok": False, "error": "invalid content length"})
            return

        try:
            raw_body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw_body or "{}")
        except json.JSONDecodeError as exc:
            self._send_json(400, {"ok": False, "error": f"invalid json: {exc}"})
            return

        if not isinstance(payload, dict):
            self._send_json(400, {"ok": False, "error": "request body must be a json object"})
            return

        try:
            result = pi_coding_agent(payload)
        except ValueError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})
            return

        status = 200 if not str(result).startswith("Invalid project_path") else 400
        self._send_json(status, {"ok": status == 200, "result": result})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), MicaPiHandler)
    print(f"[mica-pi-server] listening on {HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
