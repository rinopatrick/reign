"""Tests: desktop helpers (port resolve, wait, datadir, env wiring)."""

import socket
import sys

import pytest

from reign import desktop
from reign.desktop import _run_server


def test_get_data_dir_creates(tmp_path, monkeypatch):
    if sys.platform == "win32":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    elif sys.platform == "darwin":
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    else:
        monkeypatch.setenv("HOME", str(tmp_path))
    d = desktop.get_data_dir()
    assert d.exists() and d.name == "Reign"


def test_resolve_port_free_returns_requested():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free = s.getsockname()[1]
    assert desktop.resolve_port("127.0.0.1", free) == free


def test_resolve_port_occupied_picks_ephemeral():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    try:
        taken = srv.getsockname()[1]
        picked = desktop.resolve_port("127.0.0.1", taken)
        assert picked != taken and picked > 0
    finally:
        srv.close()


def test_wait_for_server_timeout_fast():
    assert desktop.wait_for_server("127.0.0.1", 1, tries=2, delay=0.01) is False


def test_wait_for_server_success():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    try:
        port = srv.getsockname()[1]
        assert desktop.wait_for_server("127.0.0.1", port, tries=5, delay=0.01) is True
    finally:
        srv.close()


def test_main_wires_env_and_opens_browser(tmp_path, monkeypatch):
    monkeypatch.setattr(desktop, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(desktop.time, "sleep", lambda _s: None)
    monkeypatch.setattr(desktop.webbrowser, "open", lambda _url: None)
    monkeypatch.setattr(desktop, "wait_for_server", lambda _h, _p: True)

    started = {}

    class FakeProc:
        daemon = True

        def start(self):
            started["started"] = True

        def terminate(self):
            started["terminated"] = True

        def join(self, timeout=None):  # noqa: ARG002
            started["joined"] = True

    def fake_spawn(host, port):
        proc = FakeProc()
        proc.start()
        started["target"] = _run_server
        started["args"] = (host, port)
        return proc

    monkeypatch.setattr(desktop, "_spawn_server", fake_spawn)

    calls = {"n": 0}

    def fake_sleep(_x):
        calls["n"] += 1
        if calls["n"] > 1:
            raise KeyboardInterrupt

    monkeypatch.setattr(desktop.time, "sleep", fake_sleep)

    with pytest.raises(SystemExit) as ei:
        desktop.main()
    assert ei.value.code == 0
    assert started.get("started") is True
    assert started.get("terminated") is True
    assert "DATABASE_URL" in desktop.os.environ
    assert "REIGN_BACKUPS_DIR" in desktop.os.environ
