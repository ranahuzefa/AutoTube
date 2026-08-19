"""Contract-only local HTTPS server for licensing testing."""

from __future__ import annotations

import json
import ssl
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from .database import LicenseDatabase
from .generation import format_key
from .issuance import issue_activation, validate_activation
from .keypair import ensure_keypair


class LicensingHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._respond({"status": "invalid"}, 400)
            return

        if self.path == "/v1/activation":
            self._activation(body)
        elif self.path == "/v1/validate":
            self._validate(body)
        elif self.path == "/v1/deactivate":
            self._respond({"status": "deactivated"})
        else:
            self._respond({"status": "invalid"}, 400)

    def _activation(self, body: dict) -> None:
        db = self.server.db
        from .database import _hash_key

        product_key = str(body.get("product_key", "")).replace("-", "").upper()
        record = db.get_license_by_key_hash(_hash_key(product_key))
        if record is None:
            self._respond({"status": "invalid"}, 400)
            return
        private_key, _ = ensure_keypair()
        try:
            result = issue_activation(
                db,
                license_id=record.license_id,
                device_id_hash=str(body.get("device_id_hash")),
                private_key=private_key,
            )
        except ValueError as exc:
            self._respond({"status": "invalid", "detail": str(exc)}, 400)
            return
        self._respond(result)

    def _validate(self, body: dict) -> None:
        db = self.server.db
        _, public_key = ensure_keypair()
        result = validate_activation(
            db,
            license_id=str(body.get("license_id")),
            device_id_hash=str(body.get("device_id_hash")),
            activation_token=str(body.get("activation_token")),
            public_key=public_key,
        )
        self._respond(result)

    def _respond(self, data: dict, code: int = 200) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


def serve(host: str = "127.0.0.1", port: int = 8443, certfile: str | None = None, keyfile: str | None = None) -> HTTPServer:
    server = HTTPServer((host, port), LicensingHandler)
    server.db = LicenseDatabase()

    if certfile and keyfile:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile, keyfile)
        server.socket = context.wrap_socket(server.socket, server_side=True)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
