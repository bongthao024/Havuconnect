# Gõ lệnh trực tiếp trong GPT tùy chỉnh

Chế độ Actions dùng luồng:

**Anh gõ yêu cầu trong GPT → GPT gọi API Actions → Cloudflare Tunnel → gateway nhiệm vụ trên PC → anh duyệt tại PC → GPT đọc kết quả.**

Không phải dán JSON cho từng nhiệm vụ. Cần cấu hình GPT một lần cho mỗi phiên tunnel thử nghiệm. Cuộc chat đang viết mã này không tự nhận được công cụ mới; phải mở GPT riêng đã cấu hình Actions.

## Nếu đã cài bằng GPT-PC-Control-Setup.exe

Không cần cài Python, chạy PowerShell, dùng winget hoặc cài cloudflared riêng. Mở ứng dụng từ Desktop/Start Menu, vào tab **Kết nối ChatGPT**, bấm **Mở hướng dẫn kết nối từng bước**. Ứng dụng có sẵn các nút bật gateway/tunnel, sao chép khóa và xuất schema. Xem [hướng dẫn bản ứng dụng Windows](WINDOWS-APPLICATION.md). Cấu hình GPT Builder theo mục 4–5 bên dưới, lấy schema/khóa qua các nút trong ứng dụng.

**Các lệnh terminal ở mục 1–3 bên dưới chỉ dành cho chạy từ mã nguồn**, không dành cho người đã dùng bộ cài EXE.

## 1. Chuẩn bị PC Windows 11 khi chạy mã nguồn

Cài Python 3.12 x64 và chạy `scripts/setup.ps1` theo README. Cài công cụ tunnel mã nguồn mở bằng PowerShell:

```powershell
winget install --id Cloudflare.cloudflared --exact --source winget
```

Mở PowerShell mới nếu lệnh `cloudflared` chưa được tìm thấy. Không chạy agent bằng Administrator, không mở firewall và không port-forward router. Quick Tunnel dùng dịch vụ Cloudflare, không cần mua tên miền hoặc thuê máy chủ cho thử nghiệm. Tính sẵn có/giới hạn phụ thuộc nhà cung cấp; đây không phải cam kết dịch vụ vĩnh viễn.

## 2. Bật tác nhân và gateway

Trong thư mục dự án:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-actions.ps1
```

Giữ cửa sổ này mở. Chương trình in:

- Địa chỉ giao diện quản trị cục bộ, dấu vân tay và file chứng chỉ.
- Khóa quản trị để nhập vào giao diện trên PC.
- Khóa gửi nhiệm vụ cục bộ (không cần nhập vào GPT).
- **Khóa GPT Actions** để nhập vào phần Authentication của GPT Builder.
- Một lệnh `cloudflared tunnel ...` chứa đúng đường dẫn chứng chỉ phiên hiện tại.

Không gửi bất cứ khóa nào vào nội dung chat. Đăng nhập giao diện quản trị, đối chiếu chứng chỉ như README; giữ tab mở để xem nhiệm vụ mới tự cập nhật mỗi 3 giây.

## 3. Tạo địa chỉ HTTPS công khai miễn phí

Mở PowerShell khác, chạy **đúng lệnh cloudflared được in bởi tác nhân**, ví dụ dạng:

```powershell
cloudflared tunnel --url https://127.0.0.1:8766 --origin-ca-pool 'DUONG_DAN_CERT_IN_TU_TAC_NHAN'
```

Không dùng `--no-tls-verify`. Lệnh trên xác minh chứng chỉ phía PC bằng đúng CA/chứng chỉ tự ký của phiên. Cloudflare cung cấp URL HTTPS ngẫu nhiên dưới miền `trycloudflare.com`; sao chép URL thật đó.

Chỉ tunnel **8766**. Không đưa **8765** (quản trị) ra Internet. Gateway chỉ có 2 endpoint gửi nhiệm vụ và xem kết quả; không có cấp quyền, phê duyệt hay giao diện admin. Hai chặng tới Cloudflare và từ cloudflared tới gateway đều mã hóa, gateway tới agent cũng HTTPS có xác minh. Cloudflare kết thúc TLS tại biên nên nhà cung cấp tunnel nằm trong ranh giới tin cậy; đây không phải mã hóa đầu cuối che dữ liệu khỏi Cloudflare.

Nếu Quick Tunnel không khởi động, kiểm tra kết nối Internet và cấu hình Cloudflare sẵn có trên máy theo tài liệu Cloudflare. Không xóa cấu hình tunnel có sẵn hay tắt xác minh TLS để xử lý lỗi.

## 4. Xuất schema và tạo GPT riêng

Thay `https://URL_THAT_CUA_ANH.trycloudflare.com` bằng URL vừa nhận:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\export-actions.ps1 -PublicUrl 'https://URL_THAT_CUA_ANH.trycloudflare.com'
```

1. Mở **Create a GPT / Tạo GPT → Configure / Cấu hình** trong ChatGPT.
2. Đặt tên **GPT PC Control**.
3. Dán nội dung `integrations/GPT-INSTRUCTIONS.txt` vào **Instructions**.
4. Trong **Actions → Create new action**, nhập nội dung `.local/actions-openapi.json` vào **Schema**. Không dùng nguyên file template vì miền trong template không hoạt động.
5. Trong **Authentication**, chọn **API Key**, loại **Bearer**. Dán **khóa GPT Actions** từ terminal vào ô khóa bảo mật này. Không dùng khóa quản trị.
6. Lưu GPT ở phạm vi **Only me / Chỉ mình tôi** để thử nghiệm. Không chia sẻ GPT và khóa điều khiển.

Giao diện và khả năng tạo GPT/Actions phụ thuộc tài khoản ChatGPT. Nếu tài khoản không có mục Actions thì cần tài khoản/gói được OpenAI cho phép dùng tính năng này. Mã nguồn và Quick Tunnel không bắt buộc thuê server; không thể đảm bảo ChatGPT cung cấp tính năng tạo Actions miễn phí.

## 5. Ra lệnh trong GPT

Thử lần lượt:

- “Kiểm tra phiên bản Python trên PC của anh.”
- “Cho anh biết tên máy tính.”
- “Xem danh sách tiến trình đang chạy.”
- “Đọc tệp C:\\Users\\TEN_ANH\\Documents\\ThuMucThuNghiem\\hello.txt.” (Cấp quyền thư mục từ giao diện PC trước.)

GPT phải gọi `submitPcTask`, trả ID và thông báo chờ duyệt. Trên PC, kiểm tra nguồn **ChatGPT Actions**, hành động và tham số rồi duyệt. Sau đó nói trong GPT: **“Kiểm tra kết quả nhiệm vụ vừa rồi.”** GPT gọi `getPcTask` và trình bày kết quả.

GPT không thể chờ nền vô hạn: có thể cần anh yêu cầu kiểm tra kết quả sau khi duyệt. Mọi tác vụ hiện vẫn cần duyệt; ra lệnh trong chat không tự thay thế xác nhận tại PC. Nhiệm vụ có hạn 5 phút. Kết quả tệp sẽ đi qua Cloudflare và ChatGPT; chỉ duyệt dữ liệu anh muốn chia sẻ. Kết quả chuỗi được cắt tối đa 12.000 ký tự ở gateway, có cờ `truncated`.

Trong GPT Builder có thể thử riêng `submitPcTask` và `getPcTask`. Không tính việc xuất schema là đã kết nối thành công: chỉ nghiệm thu khi GPT thật gửi việc, PC thấy nguồn Actions, anh duyệt và GPT đọc đúng kết quả.

## 6. Dừng và thu hồi

Ctrl+C cửa sổ tunnel để ngắt Internet ngay. Ctrl+C cửa sổ tác nhân để xóa khóa, quyền và nhiệm vụ trong bộ nhớ. Lần chạy sau URL tunnel, chứng chỉ và khóa đổi: xuất lại schema và cập nhật Authentication trong GPT. Không lưu khóa vào repository, script hoặc nội dung chat.

## Khả năng hiện có

- Xem thông tin hệ thống; đọc tệp trong thư mục được cấp.
- Lệnh cố định: python_version, whoami, hostname, list_processes.
- Trình duyệt: lấy tiêu đề từ https://example.org, chưa hỗ trợ website tùy ý hoặc click/đăng nhập.

Không phải shell toàn quyền hay công cụ điều khiển chuột/bàn phím. Nếu muốn mở thêm thao tác, phải bổ sung code, scope và test riêng. Chế độ tunnel là thử nghiệm một người dùng, chưa phải bản remote production có OAuth đa người dùng, phân quyền thiết bị, rate limiting hay gateway được harden độc lập.
