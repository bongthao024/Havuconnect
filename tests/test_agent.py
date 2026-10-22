import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from gpt_pc_control.app import create_app

ADMIN = {'Authorization': 'Bearer test-admin-token'}
TASK = {'Authorization': 'Bearer test-task-token'}

@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / 'data', 'test-admin-token', 'test-task-token'))

def submit(client, action, **args):
    response = client.post('/api/tasks', headers=TASK, json={'action': action, 'args': args})
    assert response.status_code == 200
    return response.json()['id']

def approve(client, ident):
    return client.post(f'/api/tasks/{ident}/approve', headers=ADMIN)

def test_auth_and_role_separation(client):
    assert client.get('/api/status').status_code == 401
    assert client.get('/api/status', headers=TASK).status_code == 401
    assert client.post('/api/tasks', headers=ADMIN, json={'action':'system_info'}).status_code == 401
    assert client.post('/api/grants', headers=TASK, json={'path':'.'}).status_code == 401

def test_approval_command_and_single_execution(client):
    ident = submit(client, 'run_command', command='python_version')
    assert client.get(f'/api/tasks/{ident}', headers=TASK).json()['state'] == 'pending'
    result = approve(client, ident).json()
    assert result['state'] == 'completed'
    assert result['result']['stdout'].startswith('Python 3.')
    assert approve(client, ident).status_code == 409

def test_command_injection_rejected(client):
    ident = submit(client, 'run_command', command='python_version; whoami')
    assert approve(client, ident).json()['state'] == 'failed'
    assert client.post('/api/tasks', headers=TASK, json={'action':'shell', 'args':{'command':'whoami'}}).status_code == 400

def test_read_scope_traversal_revoke(client, tmp_path):
    root = tmp_path / 'allowed'; root.mkdir()
    target = root / 'hello.txt'; target.write_text('Xin chào', encoding='utf-8')
    outside = tmp_path / 'secret.txt'; outside.write_text('private')
    assert approve(client, submit(client, 'read_file', path=str(target))).json()['state'] == 'failed'
    assert client.post('/api/grants', headers=ADMIN, json={'path':str(root)}).status_code == 200
    assert approve(client, submit(client, 'read_file', path=str(target))).json()['result']['text'] == 'Xin chào'
    assert approve(client, submit(client, 'read_file', path=str(root / '..' / 'secret.txt'))).json()['state'] == 'failed'
    client.post('/api/grants', headers=ADMIN, json={'path':str(root), 'enabled':False})
    assert approve(client, submit(client, 'read_file', path=str(target))).json()['state'] == 'failed'

def test_symlink_escape(client, tmp_path):
    root = tmp_path / 'allowed'; root.mkdir()
    outside = tmp_path / 'private.txt'; outside.write_text('secret')
    try:
        (root / 'link').symlink_to(outside)
    except OSError:
        pytest.skip('Windows cần Developer Mode hoặc quyền tạo symlink')
    client.post('/api/grants', headers=ADMIN, json={'path':str(root)})
    assert approve(client, submit(client, 'read_file', path=str(root / 'link'))).json()['state'] == 'failed'

def test_reject_and_expiry(client, monkeypatch):
    ident = submit(client, 'system_info')
    assert client.post(f'/api/tasks/{ident}/reject', headers=ADMIN).json()['state'] == 'rejected'
    assert approve(client, ident).status_code == 409
    ident = submit(client, 'system_info')
    now = time.time()
    monkeypatch.setattr(time, 'time', lambda: now + 301)
    assert approve(client, ident).status_code == 409

def test_origin_and_host(client):
    assert client.get('/api/status', headers={**ADMIN, 'Origin':'https://evil.example'}).status_code == 403
    assert client.get('/api/status', headers={**ADMIN, 'Host':'evil.example'}).status_code == 403

def test_browser_blocks_local_and_unlisted(client):
    for url in ['http://127.0.0.1', 'https://localhost', 'https://example.org.evil.test', 'https://example.org:8080', 'https://user:pass@example.org']:
        assert approve(client, submit(client, 'browser_title', url=url)).json()['state'] == 'failed'

def test_audit_redaction(client, tmp_path):
    approve(client, submit(client, 'system_info'))
    events = [json.loads(line) for line in (tmp_path / 'data' / 'audit.jsonl').read_text().splitlines()]
    assert any(e['event'] == 'task_finished' for e in events)
    assert 'test-admin-token' not in str(events) and 'test-task-token' not in str(events)

def test_ui(client):
    assert 'GPT PC Control' in client.get('/').text
    assert "default-src 'self'" in client.get('/').headers['content-security-policy']
    assert client.get('/ui.js').status_code == 200
