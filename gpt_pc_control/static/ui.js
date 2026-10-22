'use strict';
const el = id => document.getElementById(id);
let token = '';
async function api(path, method = 'GET', body) {
  const response = await fetch(path, {method, headers: {'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json'}, body: body === undefined ? undefined : JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Yêu cầu không hợp lệ');
  return data;
}
async function refresh() {
  el('status').textContent = JSON.stringify(await api('/api/status'), null, 2);
  const tasks = await api('/api/tasks');
  el('tasks').replaceChildren();
  for (const task of tasks) {
    const card = document.createElement('article');
    const text = document.createElement('pre');
    text.textContent = JSON.stringify(task, null, 2);
    card.append(text);
    if (task.state === 'pending') for (const [decision, label] of [['approve', 'Duyệt và thực hiện'], ['reject', 'Từ chối']]) {
      const button = document.createElement('button'); button.textContent = label;
      button.onclick = () => run(async () => {
        if (decision === 'approve' && !window.confirm('Bạn xác nhận thực hiện nhiệm vụ với đúng các tham số hiển thị? Nếu nguồn là ChatGPT Actions, kết quả (kể cả nội dung tệp) sẽ được gửi cho ChatGPT khi yêu cầu.')) return;
        await api(`/api/tasks/${task.id}/${decision}`, 'POST'); await refresh();
      });
      card.append(button);
    }
    el('tasks').append(card);
  }
}
async function run(fn) { try { await fn(); el('message').textContent = ''; } catch (e) { el('message').textContent = e.message; } }
el('connect').onclick = () => run(async () => { token = el('token').value; el('token').value = ''; await refresh(); });
el('logout').onclick = () => { token = ''; el('tasks').replaceChildren(); el('status').textContent = 'Đã xóa khóa'; };
el('refresh').onclick = () => run(refresh);
for (const [id, enabled] of [['grant', true], ['revoke', false]]) el(id).onclick = () => run(async () => {
  if (!window.confirm(`${enabled ? 'Cấp quyền đọc' : 'Thu hồi quyền'} thư mục đã nhập?`)) return;
  await api('/api/grants', 'POST', {path: el('folder').value, enabled}); await refresh();
});

el('submit-task').onclick = () => run(async () => {
  const body = JSON.parse(el('task-json').value);
  const response = await fetch('/api/tasks', {method:'POST', headers:{'Content-Type':'application/json', Authorization:'Bearer ' + el('task-token').value}, body:JSON.stringify(body)});
  el('task-token').value = '';
  const result = await response.json();
  if (!response.ok) throw new Error(JSON.stringify(result.detail));
  await refresh();
});

let polling = false;
setInterval(async () => {
  if (!token || document.hidden || polling) return;
  polling = true;
  try { await run(refresh); } finally { polling = false; }
}, 3000);
