"""Lifecycle checks for processes owned by the desktop window."""
import subprocess
import sys
import threading
import time

import pytest

from gpt_pc_control.desktop_runtime import DesktopRuntime
import gpt_pc_control.desktop_runtime as desktop_runtime


def wait_until(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        time.sleep(.02)
    assert predicate()


def test_disconnect_stops_owned_process_and_clears_connection_state(tmp_path, monkeypatch):
    child = tmp_path / 'fake_tunnel.py'
    child.write_text('''import signal, sys, time
if sys.platform != 'win32':
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
print('https://owned-test.trycloudflare.com', flush=True)
while True:
    time.sleep(.1)
''')
    actual_popen = subprocess.Popen
    calls = []

    def launch(command, **kwargs):
        calls.append(command)
        return actual_popen([sys.executable, '-u', str(child)], **kwargs)

    monkeypatch.setattr(desktop_runtime.subprocess, 'Popen', launch)
    runtime = DesktopRuntime(tmp_path / 'data')
    runtime.actions_enabled = True
    try:
        runtime.start_tunnel(sys.executable)
        wait_until(lambda: bool(runtime.public_url))
        process, monitor = runtime.tunnel, runtime.tunnel_thread
        runtime.tunnel_error = 'previous connection error'
        runtime.stop_tunnel()
        assert process.poll() is not None
        assert not monitor.is_alive()
        assert runtime.public_url == ''
        assert runtime.tunnel_error == ''
        assert calls[0][1:] == ['tunnel', '--url', 'https://127.0.0.1:8766', '--origin-ca-pool', str(runtime.cert)]
    finally:
        runtime.close()


def test_closed_runtime_cannot_reopen_services_or_tunnels(tmp_path):
    runtime = DesktopRuntime(tmp_path / 'data')
    runtime.close()
    for operation in [runtime.start, runtime.enable_actions,
                      lambda: runtime.start_tunnel(sys.executable),
                      lambda: runtime.request('GET', '/api/status'),
                      lambda: runtime.export_schema(tmp_path / 'schema.json')]:
        with pytest.raises(RuntimeError, match='Phiên đã đóng'):
            operation()
    assert not runtime.servers
    assert runtime.tunnel is None


def test_tunnel_cleanup_failure_still_stops_local_services(tmp_path, monkeypatch):
    runtime = DesktopRuntime(tmp_path / 'data')
    class Service:
        should_exit = False
    service = Service()
    def run():
        while not service.should_exit:
            time.sleep(.01)
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    runtime.servers.append((service, thread))
    def fail_tunnel_cleanup():
        raise OSError('Cannot stop tunnel')
    monkeypatch.setattr(runtime, 'stop_tunnel', fail_tunnel_cleanup)
    try:
        with pytest.raises(OSError, match='Cannot stop tunnel'):
            runtime.close()
        assert service.should_exit
        assert not thread.is_alive()
    finally:
        runtime.temp.cleanup()
