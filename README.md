# GPT PC Control V1.0

Tác nhân PC cục bộ có giao diện tiếng Việt cho Windows 11, độc lập với VietTien Connect. Đây là bản V1 giới hạn quyền để thử nghiệm; không phải công cụ quản trị máy từ xa đã được chứng nhận an toàn.

Python + FastAPI + Playwright, mã nguồn mở MIT. Không cần server thuê, API AI trả phí hoặc tài khoản cloud để chạy. ChatGPT và API bên ngoài có thể có chính sách phí riêng; chương trình không tự gọi API AI.

## Bản ứng dụng Windows có bộ cài

Đã bổ sung cửa sổ desktop tiếng Việt và quy trình tạo `GPT-PC-Control-Setup.exe`, có shortcut Desktop/Start Menu, không cần Python trên máy người dùng cuối. **Chưa có file EXE build thành công:** cần chạy workflow Windows và nghiệm thu trước khi bàn giao. Xem [trạng thái bộ cài và hướng dẫn build](docs/WINDOWS-APPLICATION.md). Chạy từ mã nguồn bằng `.venv/bin/python -m gpt_pc_control.desktop` khi có desktop/display.

## Cài từ mã nguồn trên Windows 11

Cài Python **3.12 x64** từ python.org, mở PowerShell bằng tài khoản thường (không Run as Administrator), tải mã nguồn và chuyển vào thư mục dự án:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

`Bypass` chỉ áp dụng cho tiến trình chạy script do bạn vừa đọc, không thay đổi ExecutionPolicy toàn máy. Script tạo `.venv`, cài dependency, Chromium và chạy kiểm thử. Internet cần cho lần cài đầu. `requirements-lock.txt` ghi lại toàn bộ phiên bản của môi trường kiểm thử; muốn tái lập chính xác dùng `python -m pip install -r requirements-lock.txt` trong venv. Các wheel vẫn phụ thuộc nền tảng.

Mở địa chỉ HTTPS được in trong cửa sổ tác nhân trên **chính máy đó**. Chứng chỉ tự ký thay đổi mỗi phiên: trước khi chấp nhận chứng chỉ trong trình duyệt, đối chiếu SHA-256 với dấu vân tay được in ở cửa sổ khởi động. Không bỏ kiểm tra TLS trên client và không cài chứng chỉ vào kho tin cậy toàn hệ thống. Với client Python, dùng file chứng chỉ được in trong cửa sổ để xác minh kết nối.

Khởi động tạo hai khóa ngẫu nhiên 256 bit: khóa quản trị để đăng nhập giao diện và khóa gửi nhiệm vụ cho client. Chỉ hiển thị chúng ở terminal cục bộ, không lưu trong mã nguồn, URL hay trình duyệt. Đóng terminal bằng Ctrl+C để dừng; lần chạy sau đổi khóa và xóa hàng đợi/quyền cấp trong bộ nhớ. Chứng chỉ có hiệu lực một ngày; khởi động lại nếu chạy quá thời hạn.

## Kết nối trực tiếp GPT tùy chỉnh bằng Actions

Đã có gateway riêng để GPT gửi nhiệm vụ trực tiếp và đọc kết quả qua API. Anh không cần dán JSON cho từng việc khi đã cấu hình GPT. Xem [hướng dẫn kết nối Actions miễn phí qua tunnel](docs/CHATGPT-ACTIONS.md). Khởi động `scripts/start-actions.ps1`; chỉ đưa gateway cổng 8766 ra tunnel, không đưa giao diện quản trị cổng 8765. Mọi nhiệm vụ vẫn phải được duyệt trên PC.

Chế độ mặc định `scripts/start.ps1` vẫn chỉ cục bộ. Actions/tunnel là chế độ thử nghiệm bật riêng, chưa nghiệm thu trên Windows và chưa kết nối với tài khoản ChatGPT thật tại môi trường phát triển này.

## Dùng với ChatGPT bằng JSON cục bộ

ChatGPT web không thể tự truy cập localhost của bạn. Ở chế độ cục bộ mặc định, dùng JSON như dưới đây. Muốn GPT gọi API trực tiếp, dùng chế độ Actions được hướng dẫn bên trên; chưa hỗ trợ MCP.

1. Yêu cầu ChatGPT tạo JSON theo các mẫu dưới đây, không đưa khóa cho ChatGPT.
2. Đăng nhập giao diện bằng khóa quản trị.
3. Nếu cần đọc tệp, cấp quyền cho một thư mục thử nghiệm cụ thể.
4. Dán JSON vào mục “Nhận nhiệm vụ từ ChatGPT”, nhập khóa gửi nhiệm vụ và gửi.
5. Kiểm tra hành động/tham số trong hàng đợi rồi chọn duyệt hoặc từ chối. Mọi nhiệm vụ, kể cả đọc, đều cần duyệt và hết hạn sau 5 phút.

```json
{"action":"system_info","args":{}}
```
```json
{"action":"read_file","args":{"path":"C:\\Users\\Ban\\Documents\\ThuMucThuNghiem\\hello.txt"}}
```
```json
{"action":"run_command","args":{"command":"python_version"}}
```
```json
{"action":"browser_title","args":{"url":"https://example.org/"}}
```

Trình duyệt V1 mở Chromium tạm thời, điều hướng và lấy tiêu đề trang; chỉ cho phép HTTPS trên `example.org`, chặn miền khác/redirect ngoài miền và tải xuống, không dùng profile hay cookie cá nhân. Chưa có click, nhập biểu mẫu, đăng nhập hay tự động hóa website bất kỳ. Lệnh V1 có `python_version` và các lệnh Windows cố định `whoami`, `hostname`, `list_processes` (tasklist dạng CSV, kết quả giới hạn 4096 ký tự); không nhận tham số tùy ý hoặc PowerShell tùy ý. Quyền tệp chỉ đọc UTF-8 tối đa 1 MiB, không ghi/xóa. Chủ ý không thêm các thao tác phá hủy trong V1.

Có thể gửi từ PowerShell bằng client (khóa chỉ đặt trong phiên shell của bạn):

```powershell
$env:GPT_PC_TASK_TOKEN = Read-Host 'Khóa gửi nhiệm vụ'
.\.venv\Scripts\python.exe -m gpt_pc_control.client .\examples\system-info.json --cert 'DUONG_DAN_CHUNG_CHI_IN_TU_TAC_NHAN'
Remove-Item Env:GPT_PC_TASK_TOKEN
```

CLI trả ID nhiệm vụ; duyệt và xem kết quả trong giao diện. Khóa gửi nhiệm vụ có thể xem kết quả của các nhiệm vụ trong phiên, vì vậy chỉ cấp cho một client tin cậy. Không dùng chung phiên cho nhiều người dùng.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Bộ kiểm thử gồm xác thực, phân quyền, giới hạn thư mục, symlink, thu hồi, injection lệnh, hết hạn, xác nhận một lần, Origin/Host, audit, TCP/TLS thật và thao tác giao diện bằng Chromium thật. Bài trình duyệt dùng trang mô phỏng xác định để không phụ thuộc Internet. Kiểm thử TLS dùng chứng chỉ cụ thể, không tắt xác minh.

Xem [kết quả đã chạy và checklist Windows](docs/VALIDATION.md), [thiết kế và giới hạn bảo mật](docs/SECURITY.md).

## Dữ liệu và gỡ bỏ

Nhật ký JSONL ở `%USERPROFILE%\.gpt-pc-control\audit.jsonl`; có thể đổi thư mục bằng biến `GPT_PC_DATA` trước khi chạy. Nhật ký chứa thời gian, quyết định, ID, hành động và đường dẫn cấp quyền; không chứa khóa hay nội dung tệp/kết quả. Nhật ký cục bộ chưa chống sửa đổi và cần được quản lý dung lượng. Chỉ sử dụng tài khoản Windows cá nhân và thư mục dữ liệu có ACL riêng. Tài khoản cùng quyền có thể sửa log và bộ nhớ tiến trình: phần mềm không thay thế ranh giới bảo mật của Windows.

Gỡ bỏ: Ctrl+C, xóa thư mục mã nguồn/venv và thư mục dữ liệu nếu không cần giữ log. Không cài service, mở firewall hay cấu hình autorun.

## Phát triển trên Linux

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest -q
.venv/bin/python -m gpt_pc_control
```

Nếu máy có Chromium do hệ điều hành quản lý, đặt `GPT_PC_CHROMIUM` thành đường dẫn tuyệt đối tới executable đó. Đây là cấu hình do chủ máy đặt, không nhận từ nhiệm vụ. Trên môi trường cloud hiện tại dùng `/usr/bin/chromium`.
