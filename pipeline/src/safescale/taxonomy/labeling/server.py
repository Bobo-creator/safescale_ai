"""A tiny local HTTP server for the labeling page (standard library only).

It listens on 127.0.0.1 only, accepts requests only for its own Host (so another website can't
reach it through DNS rebinding) and only JSON writes (so a plain cross-site form can't post to it).
"""

import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path

from safescale.taxonomy.categories import CATEGORIES
from safescale.taxonomy.labeling.gold import GoldSet, apply_label, save_gold

log = logging.getLogger(__name__)
HOST = "127.0.0.1"
MAX_BODY_BYTES = 64 * 1024


class LabelingServer(ThreadingHTTPServer):
    def __init__(self, gold: GoldSet, gold_path: Path, port: int = 0):
        super().__init__((HOST, port), _Handler)
        self.gold = gold
        self.gold_path = gold_path
        self.lock = threading.Lock()
        self.page = files("safescale.taxonomy.labeling").joinpath("page.html").read_bytes()

    @property
    def url(self) -> str:
        return f"http://{HOST}:{self.server_port}/"

    def allowed_hosts(self) -> set[str]:
        return {f"{HOST}:{self.server_port}", f"localhost:{self.server_port}"}


class _Handler(BaseHTTPRequestHandler):
    server: LabelingServer

    def do_GET(self) -> None:
        if not self._host_ok():
            return
        if self.path == "/":
            self._send(HTTPStatus.OK, self.server.page, "text/html; charset=utf-8")
        elif self.path == "/api/gold":
            with self.server.lock:
                body = {
                    "categories": [
                        {"code": c.code, "label": c.label, "description": c.description}
                        for c in CATEGORIES
                    ],
                    "items": [vars(item) for item in self.server.gold.items],
                }
            self._send_json(HTTPStatus.OK, body)
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_PUT(self) -> None:
        if not self._host_ok():
            return
        prefix = "/api/items/"
        if not self.path.startswith(prefix) or not self.path[len(prefix) :].isdigit():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "JSON only"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "too large"})
            return
        try:
            body = json.loads(self.rfile.read(length))
            labels = body["labels"]
            if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
                raise ValueError("labels must be a list of category codes")
            with self.server.lock:
                item = apply_label(
                    self.server.gold,
                    int(self.path[len(prefix) :]),
                    labels=labels,
                    violates_standard=bool(body.get("violates_standard", False)),
                    notes=str(body.get("notes", ""))[:2000],
                )
                save_gold(self.server.gold, self.server.gold_path)
        except KeyError:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "no such recall in the sample"})
            return
        except (ValueError, TypeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._send_json(HTTPStatus.OK, vars(item))

    def _host_ok(self) -> bool:
        if self.headers.get("Host") in self.server.allowed_hosts():
            return True
        self._send_json(HTTPStatus.FORBIDDEN, {"error": "bad host"})
        return False

    def _send_json(self, status: HTTPStatus, body: object) -> None:
        self._send(status, json.dumps(body).encode(), "application/json")

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        log.debug(format, *args)
