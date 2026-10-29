"""Run inside the backend container, exercising the real Nginx/API/model chain."""
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

BASE = "http://frontend:8080"
RECORD = Path("/app/data/.docker-smoke.json")
PDF = b"%PDF-1.7\nDocker synthetic fixture\n%%EOF\n"
CONFIG = {
    "candidate_config": {"language": "zh-CN", "education": "本科", "position": "docker-smoke"},
    "interviewer_config": {"role_identity": "面试官", "role_responsibilities": "技术面试"},
}


def request(path, *, method="GET", data=None, content_type=None, status=200):
    headers = {"Content-Type": content_type} if content_type else {}
    try:
        response = urlopen(Request(BASE + path, data=data, method=method, headers=headers), timeout=20)
    except HTTPError as error:
        response = error
    with response:
        body = response.read()
        assert response.status == status, (path, response.status, body[:500])
        return body


def get_json(path):
    return json.loads(request(path))


def configure(session, pdf=PDF, status=200):
    boundary = "docker-smoke-" + uuid4().hex
    parts = []
    for name, value in (("session_id", session), ("config", json.dumps(CONFIG))):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.extend([
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="resume.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode(),
        pdf, f"\r\n--{boundary}--\r\n".encode(),
    ])
    return json.loads(request("/interview/personal_information_config", method="POST", data=b"".join(parts),
                              content_type=f"multipart/form-data; boundary={boundary}", status=status))


def stream(session, chat_round, *, expect_progress=False):
    started = time.monotonic()
    data = json.dumps({"session_id": session, "chat_round": chat_round, "message": "Docker test"}).encode()
    req = Request(BASE + "/interview/stream", data=data, headers={"Content-Type": "application/json"})
    events = []
    with urlopen(req, timeout=20) as response:
        assert response.headers["Content-Type"].startswith("text/event-stream")
        assert response.headers.get("X-Accel-Buffering") in (None, "no")
        for line in response:
            if line.startswith(b"event: "):
                events.append((line.strip().split(b": ", 1)[1].decode(), time.monotonic() - started))
    assert "message" in [name for name, _ in events], events
    assert events[-1][0] == "done", events
    assert "error" not in [name for name, _ in events], events
    if expect_progress:
        progress = next(elapsed for name, elapsed in events if name == "progress")
        assert events[-1][1] - progress > 1, ("SSE was buffered", events)
    return events


def initial():
    assert get_json("/healthz") == {"status": "ok"}
    html = request("/").decode()
    assert '<div id="app">' in html
    assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html)
    assert assets
    for asset in assets:
        assert request(asset)
    request("/assets/missing.js", status=404)
    journal = get_json("/character-journal/index.json")
    assert journal["characters"]
    for character in journal["characters"]:
        for unit in [character["overview"], *character["chapters"]]:
            assert request("/" + unit["image"])
    schema = get_json("/openapi.json")
    operation = schema["paths"]["/interview/personal_information_config"]["post"]
    assert "multipart/form-data" in operation["requestBody"]["content"]
    assert b"swagger" in request("/docs").lower()
    session = get_json("/interview/begin")["session_id"]
    result = configure(session)
    assert Path(result["resume"]).read_bytes() == PDF
    first = stream(session, 0)
    second = stream(session, 1, expect_progress=True)
    state = get_json(f"/interview/sessions/{session}")
    assert state["chat_round"] == 2 and len(state["messages"]) == 4
    assert "docker-smoke.json" in get_json("/interview/read_preset")["files"]
    other = get_json("/interview/begin")["session_id"]
    # A full 10 MiB file must pass Nginx despite the multipart envelope.
    large_pdf = b"%PDF-" + b"x" * (10 * 1024 * 1024 - 5)
    large_result = configure(other, large_pdf)
    assert Path(large_result["resume"]).stat().st_size == len(large_pdf)
    configure(other, large_pdf + b"x", status=413)
    assert Path(large_result["resume"]).stat().st_size == len(large_pdf)
    paths = [Path(result["resume"]), Path("/app/data/interview_preset/docker-smoke.json"),
             Path(f"/app/data/state_status/{session}.json")]
    RECORD.write_text(json.dumps({"session": session, "files": {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }}))
    print(json.dumps({"phase": "initial", "status": "passed", "characters": len(journal["characters"]),
                      "sse_first": first, "sse_second": second, "upload_boundary": "10 MiB / 10 MiB + 1"}))


def persisted():
    record = json.loads(RECORD.read_text())
    for path, digest in record["files"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
    # Nginx must discover the recreated backend without restarting the frontend.
    for attempt in range(15):
        try:
            assert get_json("/healthz")["status"] == "ok"
            break
        except (AssertionError, OSError):
            if attempt == 14:
                raise
            time.sleep(1)
    request(f'/interview/sessions/{record["session"]}', status=404)
    assert get_json("/interview/begin")["session_id"] != record["session"]
    assert "docker-smoke.json" in get_json("/interview/read_preset")["files"]
    print(json.dumps({"phase": "recreated", "status": "passed", "files_preserved": len(record["files"])}))


{"initial": initial, "persisted": persisted}[sys.argv[1]]()
