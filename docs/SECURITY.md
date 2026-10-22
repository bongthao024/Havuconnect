# Thiết kế bảo mật và điều khiển từ xa

## Luồng V1 đang triển khai

ChatGPT tạo JSON → người dùng/client cục bộ gửi bằng khóa nhiệm vụ → tác nhân kiểm tra schema → hàng đợi tối đa 100 nhiệm vụ → người dùng quản trị duyệt từng nhiệm vụ còn hạn → bộ thực thi có danh sách cho phép → kết quả trong bộ nhớ + nhật ký sự kiện.

Tác nhân bind cố định loopback IPv4, kiểm tra peer/Host/Origin và không bật CORS. HTTPS dùng chứng chỉ mỗi phiên. Hai vai trò dùng khóa khác nhau; khóa nhiệm vụ không cấp quyền thư mục hoặc tự duyệt. Mọi nhiệm vụ phải duyệt, được chuyển trạng thái trước khi chạy để ngăn duyệt hai lần. Lệnh dùng executable tuyệt đối, mảng tham số cố định, `shell=False` và timeout. Đường dẫn resolve trước khi kiểm tra thư mục gốc để chặn traversal/symlink ra ngoài. Tệp lớn/đặc biệt và alternate stream bị từ chối. Giao diện render nội dung bằng textContent, có CSP, không lưu token vào localStorage.

Không chạy agent với quyền Administrator. Không cấp quyền vào thư mục chứa mật khẩu, khóa SSH, trình duyệt hoặc mã nguồn không tin cậy. Kiểm soát đường dẫn ứng dụng không phải sandbox hệ điều hành: đối thủ cùng tài khoản có thể đổi junction/symlink giữa kiểm tra và đọc (TOCTOU). Không dùng trên thư mục đang bị một tiến trình không tin cậy sửa cấu trúc. Chưa hỗ trợ AppContainer, Windows handle-based path confinement, TPM/DPAPI, chữ ký mã hay kiểm toán độc lập. Browser dùng profile mới nhưng chưa là sandbox quyền OS của tác nhân; chỉ dùng miền thử nghiệm cố định.

Log không chứa nội dung nhạy cảm nhưng chứa đường dẫn cấp quyền. Log không chống xóa/sửa, chưa có rotation; hàng đợi không lưu qua restart. Kết quả đọc tệp chỉ ở bộ nhớ phiên nhưng có thể xuất hiện trên màn hình. Không chia sẻ khóa task cho bên không được phép đọc kết quả.

## Gateway Actions thử nghiệm — đã có mã, cần bật riêng

`--actions` chạy gateway HTTPS loopback 8766 riêng với một khóa Actions khác khóa admin/task. Chỉ hai endpoint `/actions/tasks` và `/actions/tasks/{task_id}` được export. Gateway dùng khóa task để gọi agent qua HTTPS xác minh chứng chỉ. Nhiệm vụ có nguồn `ChatGPT Actions`; UI cảnh báo chia sẻ kết quả ra ngoài. Không có endpoint duyệt hay cấp quyền qua gateway. Chỉ đọc được ID do gateway trong phiên này tạo. Request ID giúp chống tạo trùng khi retry; nội dung đổi với ID cũ trả conflict. Yêu cầu tối đa 8 KiB và kết quả chuỗi cắt 12.000 ký tự. Hàng đợi agent giới hạn 100 nhiệm vụ mỗi phiên.

Có thể kết nối Cloudflare Quick Tunnel tới 8766 với `--origin-ca-pool`, không tắt TLS verification. Đây là ngoại lệ **có chủ ý, bật riêng** cho gateway hẹp; tuyệt đối không tunnel admin 8765. Dữ liệu qua hạ tầng Cloudflare và ChatGPT. Khóa và URL đổi sau khi restart. Xem CHATGPT-ACTIONS.md. Chưa có rate limiting/gateway hardening hay OAuth đa người dùng; không coi đây là dịch vụ public production.

## Thiết kế từ xa mở rộng — chưa triển khai

Không đổi host admin thành `0.0.0.0`, không port-forward hoặc tunnel cổng 8765. Chỉ gateway riêng ở chế độ Actions được tunnel theo hướng dẫn. Không bỏ kiểm tra peer/Host của agent để triển khai từ xa.

Giai đoạn tiếp theo có thể dùng WireGuard tự quản lý và gateway HTTPS/mTLS trên máy chủ riêng (không bắt buộc thuê SaaS). Gateway chỉ nhận/gửi nhiệm vụ; kênh phê duyệt giữ tại PC, không chuyển quyền admin ra gateway. Cần khóa riêng cho từng thiết bị, ACL theo scope, task ID/nonce chống replay, hạn dùng, ký payload, thu hồi khóa và rate limiting. Agent chủ động pull việc qua kết nối outbound, tránh mở cổng vào PC. Cần quy định lưu trữ kết quả, log chống sửa và cơ chế dừng khẩn cấp.

Muốn kết nối trực tiếp ChatGPT Actions cần endpoint HTTPS được ChatGPT truy cập, schema tích hợp và xác thực phù hợp. Gateway Actions hiện cung cấp schema và xác thực API key cho thử nghiệm một người dùng qua tunnel. Việc sử dụng thực tế vẫn cần cấu hình GPT và nghiệm thu trên Windows. Phương án gateway self-hosted đa thiết bị/mTLS bên trên chưa được triển khai.
