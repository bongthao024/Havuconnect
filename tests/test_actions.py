import httpx
import pytest
from fastapi.testclient import TestClient

from gpt_pc_control.actions import create_gateway, schema, valid_public_url
from gpt_pc_control.app import create_app

ADMIN_KEY = 'admin-key-used-only-in-tests'
TASK_KEY = 'worker-key-used-only-in-tests'
ACTION_KEY = 'actions-key-used-only-in-tests-0123456789'
AUTH = {'Authorization': 'Bearer ' + ACTION_KEY}

@pytest.fixture
def pair(tmp_path):
    agent = create_app(tmp_path / 'data', ADMIN_KEY, TASK_KEY)
    upstream = httpx.AsyncClient(transport=httpx.ASGITransport(app=agent), base_url='http://127.0.0.1')
    with TestClient(agent) as local, TestClient(create_gateway(ACTION_KEY, TASK_KEY, upstream=upstream)) as gateway:
        yield local, gateway


def send(gateway, **kwargs):
    return gateway.post('/actions/tasks', headers=AUTH,
                        json={'action':'system_info', 'request_id':'unique-task-00001', **kwargs})


def test_direct_chat_flow_with_pc_approval(pair):
    local, gateway = pair
    response = send(gateway)
    assert response.status_code == 200
    ident = response.json()['id']
    assert response.json()['state'] == 'pending'
    state = gateway.get('/actions/tasks/' + ident, headers=AUTH).json()
    assert state == {'id': ident, 'state': 'pending'}
    item = local.get('/api/tasks', headers={'Authorization':'Bearer ' + ADMIN_KEY}).json()[0]
    assert item['source'] == 'ChatGPT Actions'
    assert local.post(f'/api/tasks/{ident}/approve', headers=AUTH).status_code == 401
    assert local.post(f'/api/tasks/{ident}/approve', headers={'Authorization':'Bearer ' + ADMIN_KEY}).json()['state'] == 'completed'
    state = gateway.get('/actions/tasks/' + ident, headers=AUTH).json()
    assert state['state'] == 'completed'
    assert 'python' in state['result']


def test_actions_never_exports_administration(pair):
    _, gateway = pair
    assert send(gateway, command='whoami').status_code == 400
    assert gateway.post('/actions/tasks', json={'action':'system_info', 'request_id':'unique-task-00001'}).status_code == 401
    for path in ['/', '/api/status', '/api/grants', '/api/tasks', '/openapi.json']:
        assert gateway.get(path, headers=AUTH).status_code == 404
    assert gateway.post('/api/tasks/anything/approve', headers=AUTH).status_code == 404
    assert gateway.get('/actions/tasks/foreign', headers=AUTH).status_code == 404


def test_retry_is_idempotent_and_changed_payload_conflicts(pair):
    local, gateway = pair
    first = send(gateway).json()
    assert send(gateway).json()['id'] == first['id']
    assert send(gateway, action='run_command', command='python_version').status_code == 409
    assert len(local.get('/api/tasks', headers={'Authorization':'Bearer ' + ADMIN_KEY}).json()) == 1


def test_scope_does_not_leak_local_tasks(pair):
    local, gateway = pair
    task = local.post('/api/tasks', headers={'Authorization':'Bearer ' + TASK_KEY}, json={'action':'system_info'}).json()
    assert gateway.get('/actions/tasks/' + task['id'], headers=AUTH).status_code == 404


def test_gateway_limits_and_origin(pair):
    _, gateway = pair
    assert gateway.post('/actions/tasks', headers={**AUTH, 'Origin':'https://evil.example'}, json={}).status_code == 403
    assert gateway.post('/actions/tasks', headers=AUTH, content=b'x' * 8193).status_code == 413
    assert gateway.post('/actions/tasks', headers=AUTH, content=iter([b'x' * 4096, b'x' * 4097])).status_code == 413
    assert send(gateway, action='shell', command='whoami').status_code == 422
    assert send(gateway, action='run_command', command='whoami & calc.exe').status_code == 422


def test_approved_file_result_is_bounded_and_disclosure_explicit(pair, tmp_path):
    local, gateway = pair
    root = tmp_path / 'files'; root.mkdir()
    (root / 'test.txt').write_text('x' * 15000)
    local.post('/api/grants', headers={'Authorization':'Bearer ' + ADMIN_KEY}, json={'path':str(root)})
    ident = send(gateway, action='read_file', path=str(root / 'test.txt')).json()['id']
    local.post(f'/api/tasks/{ident}/approve', headers={'Authorization':'Bearer ' + ADMIN_KEY})
    result = gateway.get('/actions/tasks/' + ident, headers=AUTH).json()
    assert result['truncated'] is True
    assert len(result['result']['text']) == 12000


def test_schema_contains_only_safe_actions():
    spec = schema('https://pc-control.example.com')
    assert set(spec['paths']) == {'/actions/tasks', '/actions/tasks/{task_id}'}
    assert spec['paths']['/actions/tasks']['post']['x-openai-isConsequential'] is True
    assert spec['security'] == [{'ActionsKey': []}]
    assert 'Authorization' not in str(spec['paths'])
    for url in ['http://example.com','https://localhost','https://127.0.0.1','https://user:pass@example.com','https://example.com/private']:
        with pytest.raises(ValueError):
            valid_public_url(url)
