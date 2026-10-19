from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        marker = Path(os.environ.get("MOCK_ENGINE_HEALTH_FILE", "/nonexistent"))
        unhealthy = marker.exists() and marker.read_text().strip() == "fail"
        self.send_response(503 if unhealthy else 200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if payload["messages"][0]["content"] == "__fail__":
            self.send_response(503)
            self.end_headers()
            return
        body = json.dumps({"choices": [{"message": {"content": "推理链路验证成功"}}], "usage": {"prompt_tokens": 8, "completion_tokens": 5}}, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


ThreadingHTTPServer(("127.0.0.1", int(os.getenv("MOCK_ENGINE_PORT", "18102"))), Handler).serve_forever()
