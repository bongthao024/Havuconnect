# Báo cáo kiểm thử V1.0

Ngày 22/10/2026. Môi trường thực chạy: Debian 13, Python 3.12.14, Chromium hệ thống `/usr/bin/chromium`. Chưa chạy trên Windows 11. Không coi test Linux là chứng nhận Windows.

## Kết quả đã xác minh

Lệnh: `GPT_PC_CHROMIUM=/usr/bin/chromium .venv/bin/python -m pytest -q`.

- 20 test đạt (gồm 12 bài local ban đầu và 8 bài Actions/TLS mới): xác thực/tách vai trò; duyệt và chạy executable thật; chặn injection/lệnh lạ; đọc UTF-8 trong scope và chặn traversal; thu hồi; chặn symlink ra ngoài; từ chối/hết hạn; Host/Origin; URL trình duyệt không hợp lệ; log không chứa token; tài nguyên UI; TCP/HTTPS thực với chứng chỉ được xác minh; Chromium thực đăng nhập, dán JSON, gửi và duyệt nhiệm vụ đến trạng thái completed.
- Bài giao diện dùng HTTP loopback của fixture để Chromium không phải bỏ xác minh chứng chỉ tự ký. HTTPS được kiểm tra riêng bằng client tin cậy đúng chứng chỉ. Launcher sản phẩm luôn dùng HTTPS.
- Bài điều hướng Chromium tới `example.org` dùng phản hồi mô phỏng qua Playwright routing; không chứng minh Internet hay TLS của website ngoài hoạt động.
- Gateway Actions: khóa riêng, không export admin, không đọc nhiệm vụ local khác, retry cùng request_id không tạo trùng, đổi nội dung bị conflict, giới hạn request/kết quả và kiểm tra schema.
- Kiểm thử chuỗi **client Actions HTTPS → gateway HTTPS → agent HTTPS → phê duyệt local → kết quả qua gateway** đã đạt với hai server TCP thật và xác minh chứng chỉ trên cả hai chặng. Không tắt TLS.
- `pip check`: không có dependency xung đột. `node --check gpt_pc_control/static/ui.js`: đạt.
- Một cảnh báo deprecation của Starlette TestClient/httpx; không làm bỏ qua test.

## Chưa đạt / chưa thực hiện

- Cài Chromium qua Playwright bị proxy cloud trả 403 `Domain forbidden` cho miền tải. Đã dùng Chromium hệ thống để kiểm thử. Danh sách miền cần thiết đã được thêm vào bản nháp cấu hình cloud, chưa khẳng định áp dụng vào runtime.
- Nhiệm vụ `browser_title` thực tới `https://example.org/` trả `ERR_CERT_AUTHORITY_INVALID` trong môi trường cloud. Không dùng `ignore_https_errors`, không tắt kiểm tra chứng chỉ. Cần xác minh lại trên Windows với trust store hợp lệ hoặc cấu hình CA doanh nghiệp chính thức. Chưa xác minh thành công luồng agent → website Internet → tiêu đề trang.
- Chưa chạy script PowerShell, lệnh `whoami`/`hostname`/`tasklist`, junction/ACL hoặc cài mới trên Windows 11.
- Đã viết gateway/schema và hướng dẫn ChatGPT Actions, nhưng chưa mở tunnel Internet và chưa gắn với GPT/tài khoản ChatGPT thật. Chưa nghiệm thu luồng ChatGPT thật → Cloudflare → PC Windows. Cần thực hiện docs/CHATGPT-ACTIONS.md trên máy người dùng.
- Chưa có installer EXE, ký mã, MCP, remote đa người dùng hoặc đánh giá bảo mật độc lập.

## Checklist nghiệm thu trên Windows 11

1. Dùng tài khoản thường, Python 3.12 x64; chạy `scripts/setup.ps1`, ghi lại kết quả pytest. Test symlink có thể skipped nếu chưa bật Developer Mode; ghi rõ thay vì tính là passed.
2. Chạy `scripts/start.ps1`, kiểm tra chứng chỉ, đăng nhập, thử khóa sai và khóa task trong vị trí admin (phải bị từ chối).
3. Tạo thư mục thử nghiệm có `hello.txt` tiếng Việt và một tệp bên ngoài. Cấp quyền, duyệt đọc đúng tệp; tệp bên ngoài phải failed. Thu hồi quyền và thử lại.
4. Gửi các lệnh `python_version`, `whoami`, `hostname`, `list_processes`, duyệt từng lệnh. Gửi `whoami & calc.exe` phải failed và không mở Calculator.
5. Gửi nhiệm vụ rồi từ chối; thử duyệt lại phải lỗi. Chờ 5 phút trước khi duyệt nhiệm vụ mới phải bị từ chối do hết hạn.
6. Duyệt `examples/browser-title.json`: mong đợi completed, title `Example Domain`. URL localhost, HTTP hoặc miền khác phải failed. Giải quyết lỗi CA bằng trust store được quản lý; không tắt TLS.
7. Kiểm tra audit không có khóa/nội dung tệp. Dừng, khởi động lại: khóa cũ không dùng được, quyền cấp và nhiệm vụ cũ biến mất.
8. Thử từ máy khác trong LAN: cổng không kết nối được. Không mở firewall để vượt giới hạn này.

Chỉ sau khi hoàn tất checklist mới gọi bản này đã được nghiệm thu trên Windows 11.

## Nghiệm thu GPT Actions trên máy người dùng

Theo docs/CHATGPT-ACTIONS.md. Chỉ đạt kết nối trực tiếp khi có đủ bằng chứng: GPT gọi submitPcTask thật; PC hiển thị nguồn ChatGPT Actions với đúng tham số; người dùng duyệt local; GPT gọi getPcTask và đọc đúng kết quả. Thử khóa sai phải bị từ chối, thử admin qua tunnel phải 404, dừng tunnel phải ngắt truy cập. Các bước này chưa thực hiện trong môi trường Linux hiện tại.

## Bổ sung ứng dụng desktop và installer

- Đã chạy `desktop_entry.py --self-test` trên Linux: agent HTTPS, Actions HTTPS, approval/result và Chromium đều đạt. Báo cáo `passed=true`, platform=linux.
- Bộ pytest: 20 passed, 1 skipped. Bài native desktop bị skipped vì không có display; không tính là đã kiểm thử giao diện Windows.
- Chưa chạy PyInstaller Windows, Inno Setup, file EXE hay cài/gỡ Windows. Chưa tạo artifact Setup.exe.
- Cấu hình GitHub workflow đã chuẩn bị nhưng chưa đẩy/chạy. Metadata release Cloudflare qua API bị proxy cloud chặn 403; không dùng checksum tự đặt hoặc bỏ xác minh. Workflow Windows sẽ lấy và kiểm tra digest từ nguồn chính thức trước khi dùng binary.
