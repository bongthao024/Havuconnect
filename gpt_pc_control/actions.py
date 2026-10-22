"""Narrow ChatGPT Actions gateway. Never exports administration routes."""
from contextlib import asynccontextmanager
import argparse
import hmac
import json
import ssl
import threading
from typing import Literal
from urllib.parse import urlsplit

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .app import Task


class DirectTask(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['system_info', 'read_file', 'run_command', 'browser_title']
    request_id: str = Field(min_length=16, max_length=128, pattern=r'^[a-zA-Z0-9_-]+$',
                            description='Unique random ID for this task. Reuse this ID only when retrying the identical request.')
    path: str | None = Field(default=None, max_length=2048)
    command: Literal['python_version', 'whoami', 'hostname', 'list_processes'] | None = None
    url: str | None = Field(default=None, max_length=2048)

    def local_task(self):
        args = {key: value for key, value in self.model_dump(exclude={'action', 'request_id'}).items() if value is not None}
        required = {'system_info': set(), 'read_file': {'path'}, 'run_command': {'command'}, 'browser_title': {'url'}}
        if set(args) != required[self.action]:
            raise HTTPException(400, 'Chỉ gửi đúng tham số của hành động đã chọn')
        return Task(action=self.action, args=args)


class Receipt(BaseModel):
    id: str
    state: str
    message: str


class TaskStatus(BaseModel):
    id: str
    state: str
    result: dict[str, str | int] | None = None
    truncated: bool = False
    error: str | None = None


def valid_public_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ('', '/') or parsed.port not in (None, 443)):
        raise ValueError('Cần URL gốc HTTPS công khai, không chứa đường dẫn, user, query hoặc port khác 443')
    import ipaddress
    if parsed.hostname in {'localhost', 'testserver'}:
        raise ValueError('ChatGPT không truy cập được localhost')
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError('Cần địa chỉ Internet công khai')
    return url.rstrip('/')


def create_gateway(action_key, task_key, cert_path=None, *, upstream=None):
    if len(action_key) < 32 or hmac.compare_digest(action_key, task_key):
        raise ValueError('Khóa Actions phải riêng biệt và tối thiểu 32 ký tự')
    # Tests inject an ASGI client. Production always verifies the local agent certificate.
    if upstream is None:
        if not cert_path:
            raise ValueError('Thiếu chứng chỉ tác nhân')
        upstream = httpx.AsyncClient(base_url='https://127.0.0.1:8765',
            verify=ssl.create_default_context(cafile=str(cert_path)), trust_env=False, timeout=25)
    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            if hasattr(upstream, 'aclose'):
                await upstream.aclose()

    app = FastAPI(lifespan=lifespan, title='GPT PC Control Actions', version='1.0.0',
                  docs_url=None, redoc_url=None, openapi_url=None)
    known_ids = set()
    lock = threading.Lock()

    def auth(authorization: str | None = Header(default=None)):
        if not authorization or not hmac.compare_digest(authorization, 'Bearer ' + action_key):
            raise HTTPException(401, 'Khóa Actions không hợp lệ')

    @app.middleware('http')
    async def boundary(request: Request, call_next):
        # Public tunnel is a local process; direct remote access is not accepted.
        if not request.client or request.client.host not in {'127.0.0.1', '::1', 'testclient'}:
            return JSONResponse({'detail':'Gateway chỉ nhận từ tunnel cục bộ'}, status_code=403)
        if request.headers.get('origin'):
            return JSONResponse({'detail':'Không hỗ trợ yêu cầu từ trang web'}, status_code=403)
        length = request.headers.get('content-length')
        if length and (not length.isdigit() or int(length) > 8192):
            return JSONResponse({'detail':'Yêu cầu quá lớn'}, status_code=413)
        # Also bound chunked requests before JSON decoding.
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 8192:
                return JSONResponse({'detail':'Yêu cầu quá lớn'}, status_code=413)
        request._body = bytes(body)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    async def forward(method, path, **kwargs):
        try:
            response = await upstream.request(method, path,
                headers={'Authorization': 'Bearer ' + task_key, 'X-Task-Source':'ChatGPT Actions',
                         **kwargs.pop('headers', {})}, **kwargs)
        except httpx.HTTPError:
            raise HTTPException(503, 'Tác nhân chưa sẵn sàng; dùng lại cùng request_id khi thử lại')
        if response.status_code >= 400:
            code = response.status_code if response.status_code in {400, 404, 409, 422, 429} else 503
            raise HTTPException(code, 'Tác nhân từ chối yêu cầu hoặc phiên đã kết thúc')
        return response.json()

    @app.post('/actions/tasks', operation_id='submitPcTask', dependencies=[Depends(auth)], response_model=Receipt,
              openapi_extra={'x-openai-isConsequential': True})
    async def submit(body: DirectTask):
        """Queue a task on the PC. Requires approval on the PC; never executes immediately."""
        local = body.local_task()
        item = await forward('POST', '/api/tasks', json=local.model_dump(),
                             headers={'Idempotency-Key': body.request_id})
        with lock:
            known_ids.add(item['id'])
        return {'id': item['id'], 'state': item['state'],
                'message':('Chờ người dùng duyệt trên PC. Chưa thực hiện cho đến khi được duyệt.'
                           if item['state'] == 'pending' else 'Nhiệm vụ đã tồn tại; gọi getPcTask để xem kết quả.')}

    @app.get('/actions/tasks/{task_id}', operation_id='getPcTask', dependencies=[Depends(auth)], response_model=TaskStatus, response_model_exclude_unset=True,
             openapi_extra={'x-openai-isConsequential': False})
    async def result(task_id: str):
        """Read status/result for a task submitted by this gateway. Do not claim success while pending."""
        with lock:
            if task_id not in known_ids:
                raise HTTPException(404, 'Nhiệm vụ không thuộc phiên Actions này')
        item = await forward('GET', '/api/tasks/' + task_id)
        result = {'id': item['id'], 'state': item['state']}
        if 'result' in item:
            content = item['result'].copy()
            truncated = False
            for key, value in content.items():
                if isinstance(value, str) and len(value) > 12000:
                    content[key] = value[:12000]
                    truncated = True
            result['result'] = content
            result['truncated'] = truncated
        if 'error' in item:
            result['error'] = item['error'][:1000]
        return result

    return app


def schema(public_url):
    # OpenAPI export needs no live credentials or server.
    app = create_gateway('schema-only-placeholder-not-a-key-000', 'unused', upstream=object())
    spec = app.openapi()
    spec['servers'] = [{'url': valid_public_url(public_url)}]
    spec['components']['securitySchemes'] = {
        'ActionsKey': {'type':'http', 'scheme':'bearer', 'bearerFormat':'API key'}}
    spec['security'] = [{'ActionsKey': []}]
    # Auth is declared above, not a model-visible header argument.
    for path in spec['paths'].values():
        for operation in path.values():
            if isinstance(operation, dict) and 'parameters' in operation:
                operation['parameters'] = [p for p in operation['parameters'] if p['name'].lower() != 'authorization']
    return spec


def main():
    parser = argparse.ArgumentParser(description='Xuất schema GPT Actions, không chứa khóa')
    parser.add_argument('--public-url', required=True)
    parser.add_argument('--output', default='actions-openapi.json')
    args = parser.parse_args()
    from pathlib import Path
    Path(args.output).write_text(json.dumps(schema(args.public_url), indent=2, ensure_ascii=False), encoding='utf-8')
    print('Đã xuất schema Actions. Nhập file vào GPT Builder sau khi tunnel hoạt động.')


if __name__ == '__main__':
    main()
