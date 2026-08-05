"""Windows system tray launcher for Inbox Relief.

Keeps Postgres/Qdrant containers running, starts the FastAPI backend (which
also serves the built frontend as static files, see backend/app/main.py),
and gives you a tray icon instead of a terminal window. Ollama is not
managed here — its own installer already runs it as a persistent background
service with its own tray presence.

Run with pythonw.exe (no console window) once things are working:
    venv\\Scripts\\pythonw.exe tray_app.py
Or with python.exe while developing, to see subprocess output:
    venv\\Scripts\\python.exe tray_app.py
"""

import subprocess
import sys
import threading
import urllib.request
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = REPO_ROOT / "backend"
VENV_PYTHON = BACKEND_DIR / "venv" / "Scripts" / "python.exe"
DASHBOARD_URL = "http://127.0.0.1:8000/"
API_BASE = "http://127.0.0.1:8000/api"

DOCKER_CONTAINERS = ["inbox-relief-pg", "inbox-relief-qdrant"]

_uvicorn_process: subprocess.Popen | None = None


def _ensure_docker_containers() -> None:
    for name in DOCKER_CONTAINERS:
        subprocess.run(
            ["docker", "start", name],
            capture_output=True,
            check=False,  # already running / Docker not up — don't crash the tray app over it
        )


def _start_backend() -> subprocess.Popen:
    return subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "app.main:app", "--port", "8000"],
        cwd=str(BACKEND_DIR),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


def _call_api(path: str) -> None:
    try:
        with urllib.request.urlopen(f"{API_BASE}{path}", timeout=600) as resp:
            resp.read()
    except Exception:
        pass  # fire-and-forget from a tray menu click — nothing to surface it to


def _make_icon_image() -> Image.Image:
    # Simple rust-on-navy mark — matches the app's own palette, not a generic icon.
    img = Image.new("RGBA", (64, 64), (28, 26, 43, 255))  # ink
    draw = ImageDraw.Draw(img)
    draw.ellipse((16, 16, 48, 48), fill=(192, 86, 33, 255))  # rust
    return img


def on_open_dashboard(icon, item):
    webbrowser.open(DASHBOARD_URL)


def on_sync_now(icon, item):
    threading.Thread(target=_call_api, args=("/ingest/gmail/sync?limit=200",), daemon=True).start()


def on_classify_now(icon, item):
    threading.Thread(target=_call_api, args=("/classify/gmail?limit=20",), daemon=True).start()


def on_quit(icon, item):
    global _uvicorn_process
    if _uvicorn_process is not None:
        _uvicorn_process.terminate()
    icon.stop()


def main():
    global _uvicorn_process
    _ensure_docker_containers()
    _uvicorn_process = _start_backend()

    menu = pystray.Menu(
        pystray.MenuItem("Open Dashboard", on_open_dashboard, default=True),
        pystray.MenuItem("Sync Now", on_sync_now),
        pystray.MenuItem("Classify Now", on_classify_now),
        pystray.MenuItem("Quit", on_quit),
    )
    icon = pystray.Icon("inbox-relief", _make_icon_image(), "Inbox Relief", menu)
    icon.run()


if __name__ == "__main__":
    main()
