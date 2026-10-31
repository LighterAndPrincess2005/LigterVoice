# Ligter Voice — app 0.8.5, tiện ích Chrome 0.8.3

1. Mở `D:\Long2026\LigterVoice\Ligter Voice.exe`. App nạp sẵn bộ nhận diện và bộ giọng tại máy; lần mở app vẫn cần thời gian khởi động model.
2. Chọn một video trên Douyin web, mở LV, chọn giọng rồi bấm **Dịch video này**. Không tự dịch video kế bên.
3. Khi phần đầu đã có chữ và giọng, bấm **Xem ngay**. Phần còn lại xử lý nền. Trong Tùy chọn có thể bật **Chờ chuẩn bị xong toàn bộ rồi xem**.
4. Video có thể chờ lúc bắt đầu theo yêu cầu chuẩn bị; app không tự pause hình liên tục. Nếu xử lý chậm hơn hình, giọng vẫn có thể trễ.
5. Sang video khác sẽ hủy lượt cũ. Bấm dịch lại khi cần. Đổi giọng/cách dịch bằng cách hủy trước rồi chọn lại.

Thanh tiến độ là phần audio đã xử lý, không phải điểm chính xác hay thời gian còn lại. 100% audio có thể còn chờ tạo giọng. Xem chỉ số Giọng X/Y và cảnh báo đoạn cần kiểm tra.

Bản 0.8.5 chỉ đổi app Windows; tiện ích giữ 0.8.3, không cần bấm tải lại tiện ích. Nếu đang có phiên cũ khi cập nhật backend, F5 tab Douyin rồi chọn dịch lại để bỏ hàng đợi cũ. Cache bản 0.8.4 được dùng lại. Dữ liệu nhận diện mới lưu cục bộ theo hash audio, không lưu khóa trong cache và không đưa cache lên GitHub.

Giữ EXE, `_internal` và `models` cạnh nhau. Khóa được mã hóa Windows DPAPI trong cấu hình riêng của người dùng. Máy chủ chỉ nghe 127.0.0.1:38479. Đóng cửa sổ app sẽ thu xuống khay; chọn Thoát trong khay để tắt hẳn.

Chưa hỗ trợ Android/Samsung Tab, YouTube/Bilibili, lấy phụ đề nền tảng hoặc OCR đối chiếu. Nhạc/chồng thoại/giọng nhỏ có thể khiến nhận diện thiếu hoặc sai. Hạn mức API và mạng vẫn ảnh hưởng tốc độ. Bản 0.8.5 có 65 kiểm thử Python và 8 bộ JavaScript; kết quả mẫu không thay thế việc nghe kiểm chứng hết video thực.
