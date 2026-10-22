"""Submit ChatGPT-generated JSON without giving ChatGPT the administrator key."""
import argparse
import json
import os
import ssl
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Gửi nhiệm vụ JSON từ ChatGPT tới tác nhân cục bộ')
    parser.add_argument('task', type=Path)
    parser.add_argument('--cert', type=Path, required=True, help='Chứng chỉ hiện tại in trong cửa sổ tác nhân')
    args = parser.parse_args()
    token = os.environ.get('GPT_PC_TASK_TOKEN')
    if not token:
        parser.error('Đặt GPT_PC_TASK_TOKEN bằng khóa gửi nhiệm vụ, không dùng khóa quản trị')
    body = json.loads(args.task.read_text(encoding='utf-8-sig'))
    request = urllib.request.Request('https://127.0.0.1:8765/api/tasks',
        data=json.dumps(body).encode(), headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, context=ssl.create_default_context(cafile=str(args.cert)), timeout=10) as response:
        print(response.read().decode())


if __name__ == '__main__':
    main()
