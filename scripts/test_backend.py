"""Run backend regression tests with a bounded local-loopback preflight."""

from pathlib import Path
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = """
import socket
with socket.socket() as listener, socket.socket() as client:
    listener.settimeout(3)
    client.settimeout(3)
    listener.bind(('127.0.0.1', 0))
    listener.listen()
    client.connect(listener.getsockname())
    peer, _ = listener.accept()
    peer.close()
# Test the actual asyncio initialization used by TestClient as well.
import asyncio
async def check():
    pass
asyncio.run(check())
"""


def main() -> int:
    try:
        result = subprocess.run(
            [sys.executable, "-c", PREFLIGHT],
            cwd=ROOT, capture_output=True, timeout=10,
        )
    except subprocess.TimeoutExpired:
        print("Backend preflight timed out: local socket/asyncio initialization is blocked.", file=sys.stderr)
        return 2
    if result.returncode:
        sys.stderr.buffer.write(result.stderr)
        print(
            "Backend tests were NOT run: local loopback/asyncio initialization failed. "
            "TestClient needs a local socket even with a mocked model. "
            "Run this command in your normal local terminal and check Windows "
            "socket permissions if WinError 10013 persists.",
            file=sys.stderr,
        )
        return 2
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(ROOT / "src"), environment.get("PYTHONPATH")])
    )
    try:
        return subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=ROOT, env=environment, timeout=180,
        ).returncode
    except subprocess.TimeoutExpired:
        print("Backend tests exceeded 180 seconds; regression is incomplete, not passed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
