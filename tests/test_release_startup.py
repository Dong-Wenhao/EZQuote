"""A second launcher must not open or alter an already-running workspace."""
import importlib.util
import hashlib
from pathlib import Path
import socket
import sys

import pytest


def test_occupied_workspace_port_does_not_open_old_app_or_mobile_tunnel(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("quote_launcher", Path(__file__).resolve().parents[1] / "run.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["run.py", "--inside-venv", "--mobile"])
    called = []
    monkeypatch.setattr(launcher.webbrowser, "open", lambda *a: called.append("browser"))
    monkeypatch.setattr(launcher, "start_mobile", lambda: called.append("mobile"))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as existing:
        existing.bind(("127.0.0.1", 8765))
        existing.listen()
        with pytest.raises(SystemExit, match="Port 8765 is already in use"):
            launcher.main()
        assert existing.getsockname() == ("127.0.0.1", 8765)
        assert called == []
        assert not (tmp_path / "data").exists()


def test_normal_console_interrupt_waits_for_child_shutdown(monkeypatch, tmp_path, capsys):
    spec = importlib.util.spec_from_file_location("quote_launcher_interrupt", Path(__file__).resolve().parents[1] / "run.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["run.py"])
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("pre-provisioned test environment")
    directory = tmp_path / ".venv"
    python = directory / ("Scripts/python.exe" if launcher.os.name == "nt" else "bin/python")
    python.parent.mkdir(parents=True)
    python.touch()
    (directory / ".quote-dependencies").write_text(hashlib.sha256(requirements.read_bytes()).hexdigest())
    waits = []

    class Child:
        def wait(self, timeout=None):
            waits.append(timeout)
            if timeout is None:
                raise KeyboardInterrupt
            return 0

    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *a, **k: Child())
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as stopped:
        launcher.main()
    assert stopped.value.code == 0
    assert waits == [None, 8]
    assert "Stopping EzQuote" in capsys.readouterr().out

