import argparse
import threading
import time
import datetime
import ipaddress
from pathlib import Path
import secrets
import ssl
import tempfile

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from .app import create_app


def certificate(folder):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'GPT PC Control Local')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([
                x509.DNSName('localhost'), x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
            .sign(key, hashes.SHA256()))
    cert_path, key_path = folder / 'local.crt', folder / 'local.key'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                         serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key_path.chmod(0o600)
    return cert_path, key_path, cert.fingerprint(hashes.SHA256()).hex()


def main():
    parser = argparse.ArgumentParser(description='GPT PC Control — tác nhân cục bộ')
    parser.add_argument('--actions', action='store_true', help='Bật gateway riêng cho GPT Actions trên cổng 8766')
    args = parser.parse_args()
    admin, task = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    # Temporary private key is removed after a normal shutdown; no persistent tokens.
    with tempfile.TemporaryDirectory(prefix='gpt-pc-tls-') as temp:
        cert, key, fingerprint = certificate(Path(temp))
        print('GPT PC Control V1.0 — chỉ chạy cục bộ')
        print('Mở https://127.0.0.1:8765')
        print('Chứng chỉ tự ký, kiểm tra dấu vân tay SHA256:', fingerprint)
        print('Chứng chỉ để client xác minh TLS:', cert)
        print('Khóa quản trị (chỉ nhập trong giao diện):', admin)
        print('Khóa gửi nhiệm vụ (cấp cho client tin cậy):', task)
        print('Khóa đổi khi khởi động lại. Không chia sẻ khóa quản trị.')
        gateway = None
        gateway_thread = None
        if args.actions:
            from .actions import create_gateway
            action_key = secrets.token_urlsafe(32)
            gateway = uvicorn.Server(uvicorn.Config(create_gateway(action_key, task, cert),
                host='127.0.0.1', port=8766, ssl_certfile=str(cert), ssl_keyfile=str(key),
                proxy_headers=False, access_log=False, log_level='warning'))
            gateway_thread = threading.Thread(target=gateway.run, daemon=True)
            gateway_thread.start()
            deadline = time.monotonic() + 10
            while not gateway.started and gateway_thread.is_alive() and time.monotonic() < deadline:
                time.sleep(.05)
            if not gateway.started:
                gateway.should_exit = True
                gateway_thread.join(5)
                raise RuntimeError('Không khởi động được gateway Actions; kiểm tra cổng 8766')
            print('Khóa GPT Actions (chỉ nhập vào phần Authentication của GPT Builder):', action_key)
            print('Mở PowerShell khác và chạy:')
            print(f'cloudflared tunnel --url https://127.0.0.1:8766 --origin-ca-pool "{cert}"')
            print('Chỉ gateway nhiệm vụ được phép đưa ra tunnel; không tunnel cổng quản trị 8765.')
        try:
            uvicorn.run(create_app(admin_token=admin, task_token=task), host='127.0.0.1', port=8765,
                    ssl_certfile=str(cert), ssl_keyfile=str(key), ssl_version=ssl.PROTOCOL_TLS_SERVER,
                    access_log=False, proxy_headers=False)
        finally:
            if gateway:
                gateway.should_exit = True
                gateway_thread.join(10)


if __name__ == '__main__':
    main()
