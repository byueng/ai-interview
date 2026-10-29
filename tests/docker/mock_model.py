"""OpenAI-compatible deterministic HTTP fixture, used only by Docker smoke tests."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import time


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.respond({"status": "ok"})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        attachment = any(
            isinstance(message.get("content"), list)
            and any(part.get("type") == "file" for part in message["content"])
            for message in payload["messages"]
        )
        # Make the second interview round emit progress before the final reply.
        time.sleep(3 if attachment else 0.1)
        self.respond({
            "id": "chatcmpl-docker-smoke", "object": "chat.completion",
            "created": int(time.time()), "model": payload["model"],
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant",
                "content": "Docker resume analysis" if attachment else "Docker interview reply",
            }}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })


ThreadingHTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
