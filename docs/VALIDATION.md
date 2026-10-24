# Báo cáo kiểm thử V1.0

Cập nhật ngày 24/10/2026.

## Trạng thái mới nhất

**Build bản cập nhật đã thành công:** [run 40060639913](https://github.com/bongthao024/Havuconnect/actions/runs/40060639913), commit ứng dụng `692b1f5`, ngày 24/10/2026. [Tải artifact Windows](https://github.com/bongthao024/Havuconnect/actions/runs/40060639913/artifacts/12547685709) (cần đăng nhập GitHub).

Bằng chứng từ annotations của job build trên GitHub:

- Windows pytest: **25 tests, 0 skipped, 0 failed**, bao gồm cửa sổ native.
- `packaged-smoke` và `installed-smoke`: `passed=True`, platform `win32`. Mỗi bản đạt 9 kiểm tra: agent HTTPS, Actions HTTPS, phê duyệt, kết quả, python_version, whoami, hostname, list_processes và Chromium.
- `installer-smoke`: `passed=True`, mã thoát cài đặt 0, mã thoát gỡ cài đặt 0.
- Artifact `GPT-PC-Control-Windows-Setup`, ID `12547685709`, dung lượng 297.204.024 byte. SHA256 của ZIP artifact: `d48a87161263a8e6f0a133b287e7631d4c20ca6d178091623b3d206b77fece28` (khác SHA256 của riêng Setup.exe trong file SHA256.txt).
- Có cảnh báo deprecation runtime Node của các action v4; không có test bị bỏ qua hoặc thất bại trên Windows. Chưa chạy trên PC cá nhân/Windows 11 sạch hoặc kết nối GPT thật.


- Lần build Windows đầu tiên [39719856644](https://github.com/bongthao024/Havuconnect/actions/runs/39719856644) của commit `2ca1aa3` đã thành công và tạo artifact bộ cài. Các bước pytest, PyInstaller, EXE smoke và Inno Setup đều hoàn thành thành công theo API GitHub Actions.
- Bản cập nhật sửa chẩn đoán Python trong EXE (không gọi lại GUI), xử lý đóng/timeout tunnel và lỗi hiển thị. Linux: **24 passed, 1 skipped**, 1 cảnh báo deprecation TestClient/httpx. Bài native desktop bị skipped vì Linux không có display; trên Windows giờ bắt buộc chạy, không cho skip vì thiếu cửa sổ.
- Source desktop smoke trên Linux đạt: agent HTTPS, Actions HTTPS, approval, result, Python diagnostic và Chromium.
- Pipeline mới ghi `pytest-results.xml`, `packaged-smoke.json`, `installed-smoke.json` vào artifact. Chỉ coi bản mới đạt khi chính run cho commit đó thành công; báo cáo bản cũ không xác minh bản mới.
- Pipeline mới chạy thêm lệnh whoami, hostname, list_processes trong bản đóng gói trên Windows, cài installer vào thư mục test riêng, chạy lại smoke từ bản đã cài rồi gỡ cài đặt.
- Chưa chạy trên PC Windows 11 của người dùng, chưa kết nối tài khoản GPT thật qua Cloudflare. Các kiểm thử tự động không thay thế nghiệm thu này.

Lệnh Linux: `GPT_PC_CHROMIUM=/usr/bin/chromium .venv/bin/python -m pytest -q`.

## Phạm vi kiểm tra

Xác thực/tách vai trò; phê duyệt và từ chối; chặn chạy lại; hết hạn; giới hạn thư mục, traversal và symlink; thu hồi quyền; lệnh cố định và chặn injection; Origin/Host; URL trình duyệt; log không chứa khóa; retry không tạo trùng; scope gateway; giới hạn request/kết quả; TCP/HTTPS thực có xác minh chứng chỉ; thao tác web UI Chromium; dừng tiến trình tunnel thuộc ứng dụng, kể cả khi child không chịu terminate.

Web UI test dùng HTTP loopback riêng của fixture; HTTPS được kiểm tra riêng với đúng chứng chỉ, không tắt TLS. Browser test dùng trang mô phỏng, chưa chứng minh truy cập website ngoài.

## Giới hạn còn lại

Lần thử website ngoài trước đây gặp `ERR_CERT_AUTHORITY_INVALID` ở cloud; không tắt xác minh. Trên PC thật cần trust store hợp lệ. Chưa có kiểm thử junction/ACL toàn diện, signed code, MCP, remote đa người dùng hoặc đánh giá bảo mật độc lập. Bộ cài chưa ký Authenticode.

## Nghiệm thu trên PC Windows 11

1. Cài bằng tài khoản thường, mở shortcut, xác nhận không cần Python hoặc cloudflared cài trước.
2. Chọn một thư mục thử nghiệm với tệp UTF-8 tiếng Việt; cấp quyền đọc, thử tệp đúng scope, ngoài scope và thu hồi.
3. Trong tab Kết nối ChatGPT, bật gateway/tunnel, dùng hướng dẫn kèm ứng dụng để nhập schema/khóa vào GPT riêng.
4. Yêu cầu GPT kiểm tra phiên bản Python, tên máy, danh sách tiến trình; duyệt từng việc trên PC rồi yêu cầu GPT đọc kết quả. Chỉ công nhận kết nối GPT thật khi cả hai lượt gọi submitPcTask/getPcTask đúng.
5. Từ chối một việc, thử việc hết hạn; khóa Actions không thể cấp quyền hoặc duyệt. Thử admin qua tunnel phải 404.
6. Thử đọc tệp được cấp quyền. Chỉ duyệt dữ liệu muốn gửi qua Cloudflare và ChatGPT.
7. Ngắt tunnel, đóng ứng dụng, xác nhận kết nối dừng; khóa cũ không dùng được sau restart. Kiểm tra log không có khóa hoặc nội dung tệp.
8. Gỡ ứng dụng qua Settings. Không tắt Defender, SmartScreen hoặc TLS để vượt lỗi.
