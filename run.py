"""Cross-platform first-run setup and a local-only application launcher."""
import hashlib
import errno
import os
import re
import secrets
from pathlib import Path
import subprocess
import shutil
import socket
import sys
import threading
import time
import urllib.request
import venv
import webbrowser

ROOT = Path(__file__).resolve().parent


def reserve_workspace():
    """Own the local port before opening a browser or starting a phone tunnel."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == "nt":
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 8765))
        return listener
    except OSError as error:
        listener.close()
        if error.errno == errno.EADDRINUSE or getattr(error, "winerror", None) == 10048:
            raise SystemExit("Port 8765 is already in use. Close the old EzQuote / Quote Desk service window, "
                             "then start this version again. Keep your data and .venv folders.") from None
        raise SystemExit(f"Could not open local port 8765: {error}") from None


def start_mobile():
    binary = shutil.which("cloudflared")
    local = ROOT / "tools" / ("cloudflared.exe" if os.name == "nt" else "cloudflared")
    if not binary and local.is_file():
        binary = str(local)
    if not binary:
        print("\nMobile mode needs cloudflared. Install it, then run this launcher again.")
        print("Windows: winget install --id Cloudflare.cloudflared --exact")
        print("https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/")
        print("The local workspace will still start. Phone jobs wait until the mobile gateway is available.\n", flush=True)
        return []
    from backend.connections import Connections
    settings = Connections(os.getenv("WA_QUOTE_DATA") or ROOT / "data")
    instance = secrets.token_urlsafe(18)
    gateway = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.mobile_gateway:app",
                                "--host", "127.0.0.1", "--port", "8766"], cwd=ROOT,
                               env={**os.environ, "WA_QUOTE_GATEWAY_INSTANCE": instance})
    gateway_ready = False
    import json
    for _ in range(50):
        if gateway.poll() is not None:
            break
        try:
            with urllib.request.urlopen("http://127.0.0.1:8766/health", timeout=.3) as response:
                gateway_ready = json.loads(response.read(2048)).get("instance") == instance
            if gateway_ready:
                break
        except Exception:
            pass
        time.sleep(.1)
    if not gateway_ready:
        if gateway.poll() is None:
            gateway.terminate()
        print("Could not start this project's mobile gateway on port 8766. No tunnel was opened.", flush=True)
        return []
    try:
        tunnel = subprocess.Popen([binary, "tunnel", "--url", "http://127.0.0.1:8766"],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                   encoding="utf-8", errors="replace")
    except OSError:
        gateway.terminate()
        print("Could not run cloudflared. The local workspace will still start.", flush=True)
        return []
    ready = threading.Event()

    def read_tunnel():
        for line in tunnel.stdout:
            print("[mobile] " + line.rstrip(), flush=True)
            match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if match and not ready.is_set():
                try:
                    settings.set_tunnel_origin(match[0])
                    print("\nMobile origin detected. Open Connection settings in the boss workspace.\n", flush=True)
                    ready.set()
                except ValueError:
                    pass
    threading.Thread(target=read_tunnel, daemon=True).start()
    try:
        obtained = ready.wait(20)
    except BaseException:
        for process in (tunnel, gateway):
            if process.poll() is None:
                process.terminate()
        raise
    if not obtained:
        print("A mobile tunnel URL was not obtained. Starting the local workspace only.", flush=True)
        for process in (tunnel, gateway):
            if process.poll() is None:
                process.terminate()
        return []
    def watch_gateway():
        while tunnel.poll() is None:
            if gateway.poll() is not None:
                tunnel.terminate()
                print("The mobile gateway stopped. Its tunnel was closed.", flush=True)
                return
            time.sleep(.5)
    threading.Thread(target=watch_gateway, daemon=True).start()
    return [tunnel, gateway]


def main():
    if sys.version_info < (3, 10):
        raise SystemExit("Python 3.10 or newer is required: https://www.python.org/downloads/")
    os.chdir(ROOT)
    if "--inside-venv" not in sys.argv:
        directory = ROOT / ".venv"
        python = directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not python.exists():
            print("Creating the project Python environment...", flush=True)
            venv.EnvBuilder(with_pip=True).create(directory)
        digest = hashlib.sha256((ROOT / "requirements.txt").read_bytes()).hexdigest()
        marker = directory / ".quote-dependencies"
        if not marker.exists() or marker.read_text() != digest:
            print("Installing dependencies (internet needed on the first run)...", flush=True)
            subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(ROOT / "requirements.txt")], check=True)
            marker.write_text(digest)
        flags = [arg for arg in sys.argv[1:] if arg != "--inside-venv"]
        child = subprocess.Popen([str(python), str(ROOT / "run.py"), "--inside-venv", *flags])
        try:
            code = child.wait()
        except KeyboardInterrupt:
            # Ctrl+C also reaches the child in the same console. Let Uvicorn
            # finish its shutdown before considering a forced termination.
            print("\nStopping EzQuote...", flush=True)
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            code = 0
        raise SystemExit(code)
    listener = reserve_workspace()
    children = []
    stopped = threading.Event()
    try:
        import uvicorn
        server = uvicorn.Server(uvicorn.Config("backend.app:app", host="127.0.0.1", port=8765, log_level="info"))
        if "--mobile" in sys.argv:
            children = start_mobile()
        print("\nEzQuote: http://127.0.0.1:8765\nKeep this terminal open. Press Ctrl+C to stop.\n", flush=True)

        def open_browser():
            # Health from another process must never open an old or unrelated app.
            for _ in range(100):
                if stopped.wait(.1):
                    return
                if server.started:
                    webbrowser.open("http://127.0.0.1:8765/")
                    return

        threading.Thread(target=open_browser, daemon=True).start()
        try:
            server.run(sockets=[listener])
        except KeyboardInterrupt:
            # Server.run re-raises the console signal after graceful shutdown.
            return
        if not server.started:
            raise SystemExit("EzQuote did not start. Read the error above and try again.")
    finally:
        stopped.set()
        listener.close()
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == "__main__":
    main()
