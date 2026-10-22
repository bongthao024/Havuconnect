"""PyInstaller entry point; --self-test validates the packaged runtime on Windows."""
import argparse
import json
from pathlib import Path
import sys
import tempfile


def self_test(report):
    from gpt_pc_control.desktop_runtime import DesktopRuntime
    import httpx
    result = {'passed':False, 'platform':sys.platform}
    try:
        with tempfile.TemporaryDirectory(prefix='gpt-pc-smoke-') as temp:
            runtime = DesktopRuntime(Path(temp) / 'data')
            try:
                runtime.start()
                assert runtime.request('GET','/api/status')['mode'] == 'local-only'
                runtime.enable_actions()
                with httpx.Client(base_url='https://127.0.0.1:8766', verify=runtime.context, trust_env=False) as client:
                    headers = {'Authorization':'Bearer ' + runtime.actions_key}
                    receipt = client.post('/actions/tasks', headers=headers,
                        json={'action':'system_info','request_id':'packaged-smoke-00001'})
                    receipt.raise_for_status()
                    ident = receipt.json()['id']
                    assert receipt.json()['state'] == 'pending'
                    runtime.request('POST',f'/api/tasks/{ident}/approve')
                    completed = client.get('/actions/tasks/' + ident, headers=headers).json()
                    assert completed['state'] == 'completed'
                    assert completed['result']['platform'] == sys.platform
                # Confirm the browser driver and bundled executable actually launch.
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    import os
                    browser = p.chromium.launch(executable_path=os.environ.get('GPT_PC_CHROMIUM'))
                    try:
                        page = browser.new_page()
                        page.set_content('<title>GPT PC Control smoke</title>')
                        assert page.title() == 'GPT PC Control smoke'
                    finally:
                        browser.close()
                result['passed'] = True
                result['checks'] = ['agent_https','actions_https','approval','result','chromium']
            finally:
                runtime.close()
    except Exception as error:
        result['error'] = str(error)
    Path(report).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result['passed'] else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--report', default='desktop-smoke.json')
    args = parser.parse_args()
    if args.self_test:
        return self_test(args.report)
    from gpt_pc_control.desktop import main as desktop_main
    desktop_main()
    return 0


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    raise SystemExit(main())
