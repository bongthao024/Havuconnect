"""Native window workflow: runs on Windows CI, skips when no display is available."""
import time
import sys
import tkinter as tk

import httpx
import pytest


def test_native_window_approval_and_folder_grant(tmp_path, monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError as error:
        if sys.platform == 'win32':
            pytest.fail('Windows build must exercise the native window: ' + str(error))
        pytest.skip('Không có desktop/display; cần chạy bài cửa sổ trên Windows')
    from gpt_pc_control.desktop import DesktopApp
    from gpt_pc_control.desktop_runtime import DesktopRuntime
    import gpt_pc_control.desktop as desktop
    monkeypatch.setattr(desktop, 'DesktopRuntime', lambda: DesktopRuntime(tmp_path / 'data'))
    monkeypatch.setattr(desktop.messagebox, 'askyesno', lambda *a, **k: True)
    errors = []
    monkeypatch.setattr(desktop.messagebox, 'showerror', lambda *a, **k: errors.append(a))
    app = DesktopApp(root)

    def until(predicate):
        deadline = time.monotonic() + 15
        while not predicate() and time.monotonic() < deadline:
            root.update()
            time.sleep(.02)
        assert predicate(), errors

    try:
        until(lambda: app.ready and not app.busy)
        folder = tmp_path / 'readable'; folder.mkdir()
        monkeypatch.setattr(desktop.filedialog, 'askdirectory', lambda **k: str(folder))
        app.add_folder()
        until(lambda: str(folder) in app.folders.get(0,'end'))
        with httpx.Client(base_url='https://127.0.0.1:8765', verify=app.runtime.context, trust_env=False) as client:
            response = client.post('/api/tasks', headers={'Authorization':'Bearer ' + app.runtime.worker}, json={'action':'system_info'})
        ident = response.json()['id']
        app.refresh()
        until(lambda: ident in app.items)
        app.tree.selection_set(ident)
        app.decide('approve')
        until(lambda: app.items.get(ident,{}).get('state') == 'completed')
        app.enable_actions()
        until(lambda: app.key.get() == app.runtime.actions_key)
        assert not errors
    finally:
        app.close()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                if not root.winfo_exists():
                    break
                root.update()
            except tk.TclError:
                break
            time.sleep(.02)
        assert all(not thread.is_alive() for _, thread in app.runtime.servers)
