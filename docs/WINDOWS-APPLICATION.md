# Ứng dụng Windows và bộ cài EXE

Mục tiêu bàn giao là **GPT-PC-Control-Setup.exe**, không phải file ZIP mã nguồn. Người dùng cuối không phải cài Python hoặc chạy PowerShell. Bộ cài chứa Python runtime, tác nhân HTTPS, cửa sổ Tk/ttk, Chromium và cloudflared đã được kiểm tra SHA256.

## Trạng thái thực tế

Đã có mã cửa sổ desktop, quản lý vòng đời server/tunnel, cấu hình PyInstaller, Inno Setup và workflow build Windows. Môi trường phát triển hiện tại là Linux, không có Windows runner hay trình biên dịch Inno Setup. **Chưa tạo được Setup.exe, chưa chạy cài/gỡ trên Windows 11 và chưa có link tải bộ cài thật.**

20 kiểm thử hiện có đạt trên Linux. Bài kiểm thử cửa sổ native được bỏ qua trên Linux không có display; được cấu hình chạy trên Windows CI. Lệnh tự kiểm tra desktop runtime đã thực chạy trên Linux, xác minh server HTTPS, gateway Actions HTTPS, phê duyệt/kết quả và Chromium. Đây chưa phải kiểm thử file EXE.

## Người dùng cuối sẽ cài thế nào sau khi build đạt

1. Tải `GPT-PC-Control-Setup.exe` từ artifact của lần build đã thành công và kiểm tra SHA256 đi kèm.
2. Bấm đúp bộ cài, đọc giấy phép và chọn cài đặt. Cài theo user, không yêu cầu quyền Administrator.
3. Mở shortcut **GPT PC Control** trên Desktop hoặc Start Menu.
4. Trong tab **Kết nối ChatGPT**, bấm **Bật GPT Actions** rồi **Kết nối Internet bằng Cloudflare**. Binary tunnel đã nằm trong bộ cài; không cần tự tải riêng.
5. Lưu schema, sao chép hướng dẫn GPT và nhập khóa Actions vào Authentication/Bearer trong GPT Builder. Không nhập khóa vào chat. Giao diện che khóa và xóa khỏi clipboard ứng dụng sau 60 giây nếu clipboard vẫn chứa chính khóa đó; lịch sử clipboard/ứng dụng khác của Windows nằm ngoài kiểm soát của chương trình.
6. Gõ yêu cầu trong GPT. Xem và duyệt nhiệm vụ tại tab **Nhiệm vụ**, đọc kết quả ở phần chi tiết hoặc yêu cầu GPT kiểm tra kết quả.
7. Đóng ứng dụng sẽ dừng các server/tunnel do nó khởi tạo. Quyền thư mục, khóa và URL tunnel đổi theo phiên. Gỡ trong Settings → Apps khi không dùng nữa; log riêng của người dùng được giữ lại để người dùng chủ động xóa.

Bộ cài chưa có chữ ký Authenticode. Không hướng dẫn người dùng tắt Defender, SmartScreen hoặc chính sách bảo vệ. Trước khi phân phối rộng cần ký mã bằng chứng thư hợp lệ hoặc có quy trình phân phối tin cậy phù hợp.

## Build trên máy Windows

Yêu cầu cho **máy build**: Python 3.12 x64, Inno Setup 6, Internet. Người dùng cuối không cần các công cụ này.

```powershell
.\scripts\build-windows.ps1 -CloudflaredPath 'C:\build\cloudflared.exe' -CloudflaredSha256 'SHA256_CHINH_THUC_64_KY_TU' -CloudflaredLicensePath 'C:\build\LICENSE-cloudflared.txt'
```

Dùng binary và giấy phép từ bản phát hành chính thức cloudflare/cloudflared; không điền checksum giả. Nếu checksum không khớp, dừng để điều tra. Script sẽ cài dependency, tải Chromium qua Playwright, chạy pytest, đóng gói, chạy EXE tự kiểm tra rồi tạo installer bằng Inno Setup. Bộ cài và `SHA256.txt` ở `dist/installer/`.

## Build qua GitHub

Workflow `.github/workflows/windows-installer.yml` chạy trên Windows khi đẩy nhánh **build/windows-installer**, hoặc chọn **Actions → Build Windows application → Run workflow**. Workflow đọc metadata bản phát hành chính thức Cloudflare, tải binary, đối chiếu digest SHA256 do GitHub cung cấp cho artifact và lưu manifest version/digest. Nếu upstream không có digest, dừng; không bỏ xác minh. Có thể chọn tag cụ thể thay `latest` để tái lập một phiên bản.

Workflow chỉ upload **artifact của lần build**, không tự phát hành GitHub Release hoặc tạo link tải công khai. Sau build đạt, chủ repo đăng nhập GitHub, mở lần chạy → Artifacts → `GPT-PC-Control-Windows-Setup`, tải ZIP artifact và lấy Setup.exe bên trong. Github Actions có hạn mức theo tài khoản/repository; không cam kết không có phí nếu vượt hạn mức của GitHub. Chưa đẩy hay chạy workflow từ môi trường này.

## Nghiệm thu bắt buộc trước khi gọi bộ cài hoàn tất

- Build thành công trên Windows, test native window thực sự chạy (không skipped).
- Chạy EXE đóng gói `--self-test`, tất cả 5 kiểm tra đạt với Chromium được bundle.
- Cài/gỡ bằng tài khoản thường trên Windows 11 sạch, không Python, không cloudflared cài sẵn.
- Shortcut mở đúng cửa sổ, không xuất hiện console chứa khóa, không mở firewall hoặc tự khởi động nền.
- Kết nối tunnel, nhập schema/khóa vào GPT thật, gửi việc → duyệt trên PC → GPT nhận kết quả.
- Đóng cửa sổ dừng đúng tiến trình của ứng dụng; khởi động lại không dùng được khóa cũ.
- Rà soát giấy phép/thông báo các thành phần đi kèm, dung lượng installer và chữ ký trước phân phối.
