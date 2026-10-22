"""Vietnamese native desktop UI. Packaged on Windows with PyInstaller."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import queue
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .desktop_runtime import DesktopRuntime, bundle_root


class DesktopApp:
    def __init__(self, root):
        self.root = root
        self.runtime = DesktopRuntime()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.events = queue.Queue()
        self.ready, self.busy, self.closing = False, False, False
        self.items = {}
        root.title('GPT PC Control V1.0')
        root.geometry('1020x760')
        root.minsize(850, 650)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10))
        style.configure('Title.TLabel', font=('Segoe UI', 23, 'bold'))
        outer = ttk.Frame(root, padding=20); outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='GPT PC Control', style='Title.TLabel').pack(anchor='w')
        ttk.Label(outer, text='Điều khiển PC từ GPT • Bạn duyệt trước khi tác nhân thực hiện').pack(anchor='w', pady=(0, 10))
        self.status = tk.StringVar(value='Đang khởi động tác nhân bảo mật…')
        ttk.Label(outer, textvariable=self.status, wraplength=930).pack(anchor='w', pady=5)
        tabs = ttk.Notebook(outer); tabs.pack(fill='both', expand=True)
        tasks = ttk.Frame(tabs, padding=12); folders = ttk.Frame(tabs, padding=12); connect = ttk.Frame(tabs, padding=12)
        tabs.add(tasks, text='Nhiệm vụ'); tabs.add(folders, text='Quyền thư mục'); tabs.add(connect, text='Kết nối ChatGPT')
        self.tree = ttk.Treeview(tasks, columns=('action','source','state'), show='headings', height=8)
        for key, label in [('action','Hành động'),('source','Nguồn'),('state','Trạng thái')]:
            self.tree.heading(key, text=label); self.tree.column(key, width=210)
        self.tree.pack(fill='x')
        self.tree.bind('<<TreeviewSelect>>', lambda event: self.show_selected())
        buttons = ttk.Frame(tasks); buttons.pack(fill='x', pady=8)
        ttk.Button(buttons, text='Duyệt và thực hiện', command=lambda: self.decide('approve')).pack(side='left', padx=(0,8))
        ttk.Button(buttons, text='Từ chối', command=lambda: self.decide('reject')).pack(side='left')
        ttk.Button(buttons, text='Làm mới', command=self.refresh).pack(side='right')
        self.details = tk.Text(tasks, height=12, wrap='word', state='disabled', font=('Consolas', 10))
        self.details.pack(fill='both', expand=True)
        ttk.Label(folders, text='Chỉ cấp thư mục thử nghiệm. Không cấp thư mục chứa mật khẩu hoặc khóa riêng.', wraplength=850).pack(anchor='w', pady=10)
        self.folders = tk.Listbox(folders, height=12); self.folders.pack(fill='both', expand=True)
        ttk.Button(folders, text='Chọn thư mục và cấp quyền đọc…', command=self.add_folder).pack(anchor='w', pady=10)
        ttk.Button(folders, text='Thu hồi thư mục đã chọn', command=self.revoke_folder).pack(anchor='w')
        ttk.Label(connect, text='1. Bật gateway; 2. Kết nối Internet; 3. Xuất schema và nhập vào GPT Builder.', wraplength=850).pack(anchor='w', pady=10)
        self.actions_button = ttk.Button(connect, text='1. Bật GPT Actions', command=self.enable_actions)
        self.actions_button.pack(anchor='w', pady=5)
        self.key = tk.StringVar()
        ttk.Label(connect, text='Khóa Actions — chỉ nhập vào Authentication / Bearer trong GPT Builder:').pack(anchor='w', pady=(12,4))
        ttk.Entry(connect, textvariable=self.key, show='•', width=65, state='readonly').pack(anchor='w')
        ttk.Button(connect, text='Sao chép khóa Actions', command=lambda: self.copy(self.key.get())).pack(anchor='w', pady=5)
        ttk.Button(connect, text='2. Kết nối Internet bằng Cloudflare', command=self.connect_tunnel).pack(anchor='w', pady=8)
        self.url = tk.StringVar(value='Chưa có kết nối Internet')
        ttk.Entry(connect, textvariable=self.url, width=85, state='readonly').pack(anchor='w', pady=5)
        ttk.Button(connect, text='3. Lưu schema cho GPT…', command=self.export_schema).pack(anchor='w', pady=8)
        ttk.Button(connect, text='Sao chép hướng dẫn cho GPT', command=self.copy_instructions).pack(anchor='w', pady=5)
        ttk.Button(connect, text='Ngắt kết nối Internet', command=self.disconnect).pack(anchor='w', pady=5)
        ttk.Label(connect, text='Kết quả duyệt sẽ đi qua Cloudflare và ChatGPT. Khóa và địa chỉ thử nghiệm đổi khi khởi động lại. Không chia sẻ GPT với người khác.', wraplength=850).pack(anchor='w', pady=12)
        ttk.Label(outer, text='Đóng ứng dụng sẽ dừng tác nhân và tunnel. Không cài dịch vụ nền, không tự mở firewall.').pack(anchor='w', pady=(10,0))
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.tick)
        root.after(3000, self.poll)
        self.work(self.runtime.start, self.started)

    def work(self, function, success=None):
        if self.closing:
            return
        def done(future):
            try:
                value = future.result()
                self.events.put((success, value, None))
            except Exception as error:
                self.events.put((None, None, str(error)))
        self.executor.submit(function).add_done_callback(done)

    def tick(self):
        while True:
            try:
                callback, result, error = self.events.get_nowait()
            except queue.Empty:
                break
            if error:
                self.busy = False
                self.status.set(error)
                messagebox.showerror('GPT PC Control', error, parent=self.root)
            elif callback:
                callback(result)
        if self.runtime.tunnel_error:
            self.url.set(self.runtime.tunnel_error)
        elif self.runtime.public_url:
            self.url.set(self.runtime.public_url)
        if not self.closing:
            self.root.after(100, self.tick)

    def started(self, _):
        self.ready = True
        self.status.set('Tác nhân đã sẵn sàng • Chỉ nhận việc đã được duyệt')
        self.refresh()

    def refresh(self):
        if not self.ready or self.busy:
            return
        self.busy = True
        def fetch():
            return self.runtime.request('GET','/api/tasks'), self.runtime.request('GET','/api/status')
        self.work(fetch, self.render)

    def poll(self):
        if not self.closing:
            self.refresh()
            self.root.after(3000, self.poll)

    def render(self, data):
        self.busy = False
        tasks, status = data
        selection = self.tree.selection()
        self.items = {item['id']:item for item in tasks}
        self.tree.delete(*self.tree.get_children())
        labels = {'pending':'Chờ duyệt','running':'Đang chạy','completed':'Đã xử lý','failed':'Thất bại','expired':'Hết hạn','rejected':'Đã từ chối'}
        for item in reversed(tasks):
            self.tree.insert('', 'end', iid=item['id'], values=(item['task']['action'],item['source'],labels.get(item['state'],item['state'])))
        if selection and selection[0] in self.items:
            self.tree.selection_set(selection[0])
        self.show_selected()
        folder_selection = self.folders.curselection()
        selected_path = self.folders.get(folder_selection[0]) if folder_selection else None
        self.folders.delete(0, 'end')
        for index, path in enumerate(status['grants']):
            self.folders.insert('end', path)
            if path == selected_path:
                self.folders.selection_set(index)

    def show_selected(self):
        selected = self.tree.selection()
        item = self.items.get(selected[0]) if selected else None
        self.details.configure(state='normal')
        self.details.delete('1.0','end')
        if item:
            self.details.insert('1.0',json.dumps(item, ensure_ascii=False, indent=2))
        self.details.configure(state='disabled')

    def decide(self, decision):
        selected = self.tree.selection()
        if not selected or self.items[selected[0]]['state'] != 'pending':
            return
        item = self.items[selected[0]]
        if decision == 'approve' and not messagebox.askyesno('Xác nhận thực hiện',
            json.dumps(item['task'],ensure_ascii=False,indent=2) + '\n\nNếu nguồn là ChatGPT Actions, kết quả (kể cả nội dung tệp) sẽ được gửi qua Cloudflare và ChatGPT. Anh đồng ý?', parent=self.root):
            return
        self.work(lambda: self.runtime.request('POST', f"/api/tasks/{item['id']}/{decision}"), lambda _: self.refresh())

    def add_folder(self):
        if not self.ready:
            return
        path = filedialog.askdirectory(parent=self.root, title='Chọn thư mục cho phép đọc')
        if path and messagebox.askyesno('Cấp quyền đọc', 'Cho phép đọc tệp trong thư mục này?\n' + path, parent=self.root):
            self.work(lambda: self.runtime.request('POST','/api/grants',{'path':path}), lambda _: self.refresh())

    def revoke_folder(self):
        selected = self.folders.curselection()
        if selected:
            path = self.folders.get(selected[0])
            self.work(lambda: self.runtime.request('POST','/api/grants',{'path':path,'enabled':False}), lambda _: self.refresh())

    def enable_actions(self):
        if self.ready:
            self.work(self.runtime.enable_actions, self.actions_ready)

    def actions_ready(self, _):
        self.key.set(self.runtime.actions_key)
        self.actions_button.configure(state='disabled')
        self.status.set('Gateway Actions sẵn sàng • Chưa công khai cho đến khi bật tunnel')

    def connect_tunnel(self):
        if not self.runtime.actions_enabled:
            messagebox.showinfo('GPT Actions', 'Hãy bấm “Bật GPT Actions” trước.', parent=self.root)
            return
        candidate = bundle_root() / 'tools' / 'cloudflared.exe'
        path = str(candidate) if candidate.is_file() else shutil.which('cloudflared')
        if not path:
            path = filedialog.askopenfilename(parent=self.root, title='Chọn cloudflared.exe chính thức', filetypes=[('Cloudflare tunnel','cloudflared.exe')])
        if path and messagebox.askyesno('Kết nối với ChatGPT', 'Bật tunnel Internet chỉ cho API nhiệm vụ? Người có khóa Actions có thể gửi nhiệm vụ chờ anh duyệt.', parent=self.root):
            self.url.set('Đang kết nối…')
            self.work(lambda: self.runtime.start_tunnel(path))

    def disconnect(self):
        self.work(self.runtime.stop_tunnel, lambda _: self.url.set('Đã ngắt kết nối Internet'))

    def export_schema(self):
        if not self.runtime.public_url:
            messagebox.showinfo('GPT Actions', 'Chưa có URL tunnel. Hãy kết nối Internet trước.', parent=self.root)
            return
        path = filedialog.asksaveasfilename(parent=self.root, title='Lưu schema để nhập vào GPT Builder', defaultextension='.json', initialfile='GPT-PC-Control-Actions.json')
        if path:
            self.work(lambda: self.runtime.export_schema(path), lambda _: messagebox.showinfo('Đã lưu', 'Nhập file JSON vào GPT Builder → Actions. Khóa Actions nhập riêng vào Authentication → Bearer.', parent=self.root))

    def copy(self, value):
        if value:
            self.root.clipboard_clear(); self.root.clipboard_append(value)
            if value == self.runtime.actions_key:
                self.root.after(60000, self.clear_key_clipboard)

    def clear_key_clipboard(self):
        try:
            if self.root.clipboard_get() == self.runtime.actions_key:
                self.root.clipboard_clear()
        except tk.TclError:
            pass

    def copy_instructions(self):
        path = bundle_root() / 'integrations' / 'GPT-INSTRUCTIONS.txt'
        self.copy(path.read_text(encoding='utf-8'))

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.clear_key_clipboard()
        self.status.set('Đang dừng tác nhân và kết nối…')
        future = self.executor.submit(self.runtime.close)
        def finish():
            if not future.done():
                self.root.after(100, finish)
                return
            try:
                future.result()
            except Exception as error:
                messagebox.showerror('Dừng ứng dụng', str(error), parent=self.root)
            self.executor.shutdown(wait=False)
            self.root.destroy()
        finish()


def main():
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
