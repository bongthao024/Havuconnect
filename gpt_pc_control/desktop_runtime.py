"""Runtime owned by the desktop window; no session credentials are printed."""
import os
from pathlib import Path
import re
import secrets
import ssl
import subprocess
import sys
import tempfile
import threading
import time

import httpx
import uvicorn

from .__main__ import certificate
from .actions import create_gateway, schema
from .app import create_app


def bundle_root():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))


class DesktopRuntime:
    def __init__(self, data_dir=None):
        self.data_dir = data_dir
        self.admin = secrets.token_urlsafe(32)
        self.worker = secrets.token_urlsafe(32)
        self.actions_key = secrets.token_urlsafe(32)
        self.temp = tempfile.TemporaryDirectory(prefix='gpt-pc-desktop-')
        self.cert, self.key, _ = certificate(Path(self.temp.name))
        self.context = ssl.create_default_context(cafile=str(self.cert))
        self.servers = []
        self.actions_enabled = False
        self.tunnel = None
        self.tunnel_timer = None
        self.public_url = ''
        self.tunnel_error = ''
        self.closed = False
        browsers = bundle_root() / 'browsers'
        if browsers.is_dir():
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(browsers)

    def _start(self, app, port):
        instance = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port,
            ssl_certfile=str(self.cert), ssl_keyfile=str(self.key),
            access_log=False, proxy_headers=False, log_config=None, log_level='error'))
        thread = threading.Thread(target=instance.run, daemon=True)
        self.servers.append((instance, thread))
        thread.start()
        deadline = time.monotonic() + 10
        while not instance.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.05)
        if not instance.started:
            instance.should_exit = True
            raise RuntimeError(f'Không mở được cổng {port}. Hãy đóng phiên GPT PC Control đang chạy rồi thử lại.')

    def start(self):
        if self.closed:
            raise RuntimeError('Phiên đã đóng')
        self._start(create_app(self.data_dir, self.admin, self.worker), 8765)
        self.request('GET', '/api/status')

    def request(self, method, path, body=None):
        with httpx.Client(base_url='https://127.0.0.1:8765', verify=self.context,
                          trust_env=False, timeout=30) as client:
            response = client.request(method, path, json=body,
                headers={'Authorization':'Bearer ' + self.admin})
            if response.status_code >= 400:
                raise RuntimeError(response.json().get('detail', 'Yêu cầu bị từ chối'))
            return response.json()

    def enable_actions(self):
        if not self.actions_enabled:
            self._start(create_gateway(self.actions_key, self.worker, self.cert), 8766)
            self.actions_enabled = True

    def start_tunnel(self, executable):
        if not self.actions_enabled:
            raise RuntimeError('Hãy bật gateway GPT Actions trước')
        if self.tunnel and self.tunnel.poll() is None:
            raise RuntimeError('Tunnel đang chạy')
        executable = Path(executable).resolve(strict=True)
        if not executable.is_file():
            raise RuntimeError('Không tìm thấy cloudflared')
        self.public_url, self.tunnel_error = '', ''
        self.tunnel = subprocess.Popen([str(executable), 'tunnel', '--url', 'https://127.0.0.1:8766',
            '--origin-ca-pool', str(self.cert)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors='replace', shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        process = self.tunnel

        def timeout():
            if self.tunnel is process and not self.closed and not self.public_url and process.poll() is None:
                self.tunnel_error = 'Tunnel chưa kết nối sau 60 giây. Kiểm tra mạng rồi thử lại.'
                process.terminate()

        self.tunnel_timer = threading.Timer(60, timeout)
        self.tunnel_timer.daemon = True
        self.tunnel_timer.start()
        timer = self.tunnel_timer

        def monitor():
            try:
                for line in process.stdout:
                    match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com\b', line)
                    if match and self.tunnel is process and not self.closed:
                        self.public_url = match.group(0)
                        timer.cancel()
                process.wait()
                if not self.closed and not self.tunnel_error and self.tunnel is process:
                    self.tunnel_error = 'Tunnel đã dừng. Bấm kết nối lại và cập nhật URL trong GPT.'
                    self.public_url = ''
            finally:
                process.stdout.close()
        threading.Thread(target=monitor, daemon=True).start()

    def stop_tunnel(self):
        if self.tunnel_timer:
            self.tunnel_timer.cancel()
        process, self.tunnel = self.tunnel, None
        self.public_url = ''
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def export_schema(self, path):
        if not self.public_url:
            raise RuntimeError('Tunnel chưa có URL công khai')
        import json
        Path(path).write_text(json.dumps(schema(self.public_url), ensure_ascii=False, indent=2), encoding='utf-8')

    def close(self):
        self.closed = True
        self.stop_tunnel()
        for instance, _ in self.servers:
            instance.should_exit = True
        for _, thread in reversed(self.servers):
            thread.join(10)
        if any(thread.is_alive() for _, thread in self.servers):
            raise RuntimeError('Dịch vụ chưa dừng xong; đóng ứng dụng và kiểm tra tiến trình trước khi chạy lại.')
        self.temp.cleanup()
