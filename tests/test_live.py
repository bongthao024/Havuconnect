"""Real TCP/TLS and real Chromium checks; no network dependency or TLS bypass."""
import os
import socket
import ssl
import threading
import time

import httpx
import pytest
import uvicorn
from playwright.sync_api import sync_playwright, expect
from gpt_pc_control.app import create_app
from gpt_pc_control.__main__ import certificate


def server(tmp_path, tls, app=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    cert, key, _ = certificate(tmp_path)
    app = app or create_app(tmp_path / 'data', 'local-admin', 'local-worker')
    config = uvicorn.Config(app, log_level='error',
        **({'ssl_certfile': str(cert), 'ssl_keyfile': str(key)} if tls else {}))
    instance = uvicorn.Server(config)
    thread = threading.Thread(target=instance.run, kwargs={'sockets':[sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not instance.started and time.monotonic() < deadline:
        time.sleep(.02)
    assert instance.started
    return instance, thread, port, cert


def test_real_tls_approval(tmp_path):
    instance, thread, port, cert = server(tmp_path, True)
    try:
        context = ssl.create_default_context(cafile=str(cert))
        with httpx.Client(base_url=f'https://127.0.0.1:{port}', verify=context, trust_env=False) as c:
            assert c.get('/').status_code == 200
            assert c.get('/api/status').status_code == 401
            task = c.post('/api/tasks', headers={'Authorization':'Bearer local-worker'}, json={'action':'run_command', 'args':{'command':'python_version'}}).json()
            result = c.post(f"/api/tasks/{task['id']}/approve", headers={'Authorization':'Bearer local-admin'}).json()
            assert result['state'] == 'completed'
            assert result['result']['exit_code'] == 0
    finally:
        instance.should_exit = True; thread.join(10)
        assert not thread.is_alive()


def test_real_browser_ui(tmp_path):
    instance, thread, port, _ = server(tmp_path, False)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ.get('GPT_PC_CHROMIUM'))
            try:
                page = browser.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{port}')
                page.locator('#token').fill('local-admin')
                page.locator('#connect').click()
                expect(page.locator('#status')).to_contain_text('local-only')
                page.locator('#task-token').fill('local-worker')
                page.locator('#task-json').fill('{"action":"system_info","args":{}}')
                page.locator('#submit-task').click()
                page.get_by_text('Duyệt và thực hiện').wait_for()
                page.on('dialog', lambda dialog: dialog.accept())
                page.get_by_text('Duyệt và thực hiện').click()
                expect(page.locator('#tasks')).to_contain_text('completed')
                assert not errors
                # Actual Chromium navigation and title extraction with deterministic routed content.
                page.route('https://example.org/**', lambda route: route.fulfill(body='<title>Browser automation OK</title>', content_type='text/html'))
                page.goto('https://example.org/')
                assert page.title() == 'Browser automation OK'
            finally:
                browser.close()
    finally:
        instance.should_exit = True; thread.join(10)
        assert not thread.is_alive()


def test_real_actions_tls_to_agent_tls(tmp_path):
    from gpt_pc_control.actions import create_gateway
    agent, agent_thread, agent_port, agent_cert = server(tmp_path / 'agent', True)
    upstream = httpx.AsyncClient(base_url=f'https://127.0.0.1:{agent_port}',
        verify=ssl.create_default_context(cafile=str(agent_cert)), trust_env=False)
    action_key = 'actions-live-test-key-01234567890123456789'
    gateway_app = create_gateway(action_key, 'local-worker', upstream=upstream)
    gateway, gateway_thread, gateway_port, gateway_cert = server(tmp_path / 'gateway', True, gateway_app)
    try:
        with httpx.Client(base_url=f'https://127.0.0.1:{gateway_port}',
                verify=ssl.create_default_context(cafile=str(gateway_cert)), trust_env=False) as remote, \
             httpx.Client(base_url=f'https://127.0.0.1:{agent_port}',
                verify=ssl.create_default_context(cafile=str(agent_cert)), trust_env=False) as local:
            headers = {'Authorization':'Bearer ' + action_key}
            response = remote.post('/actions/tasks', headers=headers,
                json={'action':'run_command', 'command':'python_version', 'request_id':'live-action-id-00001'})
            assert response.status_code == 200
            ident = response.json()['id']
            assert remote.get('/actions/tasks/' + ident, headers=headers).json()['state'] == 'pending'
            local.post(f'/api/tasks/{ident}/approve', headers={'Authorization':'Bearer local-admin'}).raise_for_status()
            result = remote.get('/actions/tasks/' + ident, headers=headers).json()
            assert result['state'] == 'completed'
            assert result['result']['stdout'].startswith('Python 3.')
            assert remote.get('/api/tasks', headers=headers).status_code == 404
    finally:
        gateway.should_exit = True; gateway_thread.join(10)
        agent.should_exit = True; agent_thread.join(10)
        assert not gateway_thread.is_alive() and not agent_thread.is_alive()
