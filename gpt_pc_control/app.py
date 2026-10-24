import asyncio
import hmac
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

STATIC = Path(__file__).parent / 'static'


class Task(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: str
    args: dict[str, str] = Field(default_factory=dict)


class Grant(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str
    enabled: bool = True


def create_app(data_dir=None, admin_token=None, task_token=None):
    data = Path(data_dir or os.environ.get('GPT_PC_DATA', Path.home() / '.gpt-pc-control'))
    data.mkdir(parents=True, exist_ok=True)
    # Tokens are supplied by the launcher; importing the app never opens a server.
    admin = admin_token or secrets.token_urlsafe(32)
    worker = task_token or secrets.token_urlsafe(32)
    if hmac.compare_digest(admin, worker):
        raise ValueError('Admin and task tokens must differ')
    app = FastAPI(title='GPT PC Control', version='1.0.0', docs_url=None, redoc_url=None)
    pending, grants = {}, set()
    idempotency = {}
    lock = threading.RLock()
    audit_path = data / 'audit.jsonl'
    browser_domains = {'example.org'}
    command_names = ['python_version', 'whoami', 'hostname', 'list_processes']

    def audit(event, **fields):
        # No tokens, file contents, URLs or command output in the audit log.
        with lock:
            with audit_path.open('a', encoding='utf-8') as f:
                f.write(json.dumps({'time': time.time(), 'event': event, **fields}, ensure_ascii=False) + '\n')

    def authenticate(value, expected):
        if not value or not hmac.compare_digest(value, 'Bearer ' + expected):
            audit('authentication_denied')
            raise HTTPException(401, 'Thông tin xác thực không hợp lệ')

    def owner(authorization: str | None = Header(default=None)):
        authenticate(authorization, admin)

    def agent(authorization: str | None = Header(default=None)):
        authenticate(authorization, worker)

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        from fastapi.responses import JSONResponse
        # Enforce both peer and Host: protects against accidental public binding and DNS rebinding.
        host = request.headers.get('host', '').split(':')[0].lower()
        peer = request.client.host if request.client else ''
        if host not in {'127.0.0.1', 'localhost', 'testserver'} or peer not in {'127.0.0.1', '::1', 'testclient'}:
            return JSONResponse({'detail': 'Chỉ chấp nhận kết nối cục bộ'}, status_code=403)
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail': 'Origin không được phép'}, status_code=403)
        response = await call_next(request)
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        return response

    def permitted_file(raw):
        if raw.startswith(('\\\\', '//')):
            raise ValueError('Không hỗ trợ đường dẫn mạng hoặc thiết bị')
        path = Path(raw).expanduser().resolve(strict=True)
        if not any(path.is_relative_to(root) for root in grants):
            raise ValueError('Đường dẫn nằm ngoài thư mục được cấp quyền')
        # Reject Windows alternate streams, device names and special files.
        if ':' in path.name or not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError('Chỉ đọc tệp thường tối đa 1 MiB')
        return path

    async def execute(task):
        if task.action == 'system_info':
            return {'platform': sys.platform, 'python': sys.version.split()[0]}
        if task.action == 'read_file':
            return {'text': permitted_file(task.args['path']).read_text(encoding='utf-8')}
        if task.action == 'run_command':
            # Fixed executable and arguments: no shell, PATH search, scripts or user arguments.
            name = task.args.get('command')
            if name == 'python_version':
                if getattr(sys, 'frozen', False):
                    # In a packaged build sys.executable is our GUI, not python.exe.
                    return {'exit_code': 0, 'stdout': 'Python ' + sys.version.split()[0] + '\n'}
                command = [sys.executable, '--version']
            elif name in {'whoami', 'hostname', 'list_processes'} and sys.platform == 'win32':
                system32 = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32'
                executable, args = {'whoami': ('whoami.exe', []), 'hostname': ('hostname.exe', []),
                                    'list_processes': ('tasklist.exe', ['/FO', 'CSV'])}[name]
                command = [str(system32 / executable), *args]
            else:
                raise ValueError('Lệnh chưa được cho phép hoặc cần Windows 11')
            result = await asyncio.to_thread(subprocess.run, command,
                                             capture_output=True, text=True, errors='replace', timeout=10, shell=False,
                                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            return {'exit_code': result.returncode, 'stdout': result.stdout[:4096]}
        if task.action == 'browser_title':
            url = task.args['url']
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or parsed.hostname not in browser_domains or parsed.username or parsed.password or parsed.port not in (None, 443):
                raise ValueError('Trình duyệt chỉ cho phép https://example.org')
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, executable_path=os.environ.get('GPT_PC_CHROMIUM'))
                try:
                    context = await browser.new_context(accept_downloads=False, service_workers='block')
                    async def route_handler(route):
                        u = urlsplit(route.request.url)
                        if u.scheme == 'https' and u.hostname in browser_domains and u.port in (None, 443):
                            await route.continue_()
                        else:
                            await route.abort()
                    await context.route('**/*', route_handler)
                    page = await context.new_page()
                    await page.goto(url, wait_until='domcontentloaded', timeout=20000)
                    return {'title': await page.title()}
                finally:
                    await browser.close()
        raise ValueError('Hành động chưa được hỗ trợ')

    @app.get('/')
    def index():
        return FileResponse(STATIC / 'index.html')

    @app.get('/ui.js')
    def js():
        return FileResponse(STATIC / 'ui.js', media_type='text/javascript')

    @app.get('/style.css')
    def css():
        return FileResponse(STATIC / 'style.css', media_type='text/css')

    @app.get('/api/status', dependencies=[Depends(owner)])
    def status():
        return {'version': '1.0.0', 'mode': 'local-only', 'grants': sorted(map(str, grants)),
                'commands': command_names, 'browser_domains': sorted(browser_domains)}

    @app.post('/api/grants', dependencies=[Depends(owner)])
    def grant(body: Grant):
        if body.path.startswith(('\\\\', '//')):
            raise HTTPException(400, 'Chỉ cấp quyền thư mục cục bộ')
        path = Path(body.path).expanduser().resolve()
        if not path.is_dir() or path == Path(path.anchor):
            raise HTTPException(400, 'Chọn thư mục cụ thể đang tồn tại, không chọn ổ đĩa gốc')
        with lock:
            if body.enabled:
                grants.add(path)
            else:
                grants.discard(path)
            audit('grant_changed', path=str(path), enabled=body.enabled)
        return {'grants': sorted(map(str, grants))}

    @app.post('/api/tasks', dependencies=[Depends(agent)])
    def submit(body: Task, request_id: str | None = Header(default=None, alias='Idempotency-Key'),
               source: str | None = Header(default=None, alias='X-Task-Source')):
        fields = {'system_info': set(), 'read_file': {'path'}, 'run_command': {'command'}, 'browser_title': {'url'}}
        if body.action not in fields or set(body.args) != fields[body.action] or any(len(v) > 2048 for v in body.args.values()):
            raise HTTPException(400, 'Hành động hoặc tham số không hợp lệ')
        if request_id is not None and (not 16 <= len(request_id) <= 128 or not all(c.isascii() and (c.isalnum() or c in '_-') for c in request_id)):
            raise HTTPException(400, 'Idempotency-Key không hợp lệ')
        fingerprint = json.dumps(body.model_dump(), sort_keys=True)
        with lock:
            if request_id in idempotency:
                previous, ident = idempotency[request_id]
                if previous != fingerprint:
                    raise HTTPException(409, 'request_id đã dùng với nội dung khác')
                return pending[ident]
            if len(pending) >= 100:
                raise HTTPException(429, 'Hàng đợi đầy; khởi động lại để xóa lịch sử trong bộ nhớ')
            ident = secrets.token_urlsafe(16)
            pending[ident] = {'id': ident, 'task': body.model_dump(), 'state': 'pending', 'expires': time.time() + 300,
                              'source': 'ChatGPT Actions' if source == 'ChatGPT Actions' else 'local'}
            if request_id is not None:
                idempotency[request_id] = (fingerprint, ident)
            audit('task_submitted', id=ident, action=body.action)
        return pending[ident]

    def expire(item):
        if item['state'] == 'pending' and item['expires'] < time.time():
            item['state'] = 'expired'
            audit('task_expired', id=item['id'])
        return item

    @app.get('/api/tasks', dependencies=[Depends(owner)])
    def tasks():
        with lock:
            return [expire(item) for item in pending.values()]

    @app.get('/api/tasks/{ident}', dependencies=[Depends(agent)])
    def result(ident: str):
        if ident not in pending:
            raise HTTPException(404, 'Không tìm thấy nhiệm vụ')
        with lock:
            return expire(pending[ident])

    @app.post('/api/tasks/{ident}/{decision}', dependencies=[Depends(owner)])
    async def decide(ident: str, decision: str):
        with lock:
            item = pending.get(ident)
            if not item:
                raise HTTPException(404, 'Không tìm thấy nhiệm vụ')
            if decision not in {'approve', 'reject'}:
                raise HTTPException(400, 'Quyết định không hợp lệ')
            if item['state'] != 'pending' or item['expires'] < time.time():
                raise HTTPException(409, 'Nhiệm vụ đã xử lý hoặc hết hạn')
            item['state'] = 'running' if decision == 'approve' else 'rejected'
            audit('task_decision', id=ident, decision=decision)
        if decision == 'approve':
            try:
                item['result'] = await execute(Task(**item['task']))
                item['state'] = 'completed'
            except Exception as exc:
                item['state'] = 'failed'
                item['error'] = str(exc)[:1000]
            audit('task_finished', id=ident, state=item['state'])
        return item

    return app
