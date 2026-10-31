# Ligter Voice — app 0.8.4, tiện ích 0.8.3

App Windows và tiện ích Chrome 0.8.3 dịch video được chọn trên Douyin web. Chưa hỗ trợ YouTube/Bilibili, chưa có lấy phụ đề nền tảng hoặc OCR để đối chiếu.

## Cách dùng

1. Mở D:\Long2026\LigterVoice\Ligter Voice.exe. App nằm trên màn hình phụ nếu có.
2. Trên Douyin, chọn video, mở LV, chọn giọng Nam/Nữ/Tắt rồi bấm **Dịch video này**.
3. Video được tạm dừng một lần khi bạn yêu cầu chuẩn bị. Mặc định tiện ích đệm phần đầu có chữ và giọng rồi hiện **Xem ngay**; phần còn lại tiếp tục xử lý nền. Trong Tùy chọn có thể bật **Chờ chuẩn bị xong toàn bộ rồi xem**. thanh tiến độ cập nhật bước đang chạy, thời lượng đã xử lý và số câu có giọng.
4. Khi sẵn sàng, bấm **Xem bản dịch** để xem từ đầu hoặc dùng nút phát trên video. Không tự pause hình liên tục để chờ từng câu.
5. Sang video khác sẽ hủy lượt cũ và dừng giọng; video mới chỉ được xử lý khi bạn bấm dịch. Không chuẩn bị video kế bên. Bấm **Hủy** để dừng. Muốn đổi giọng/cách dịch, hủy rồi chọn trước khi chuẩn bị lại; dữ liệu đã xử lý có thể được dùng lại.

## Đọc thanh tiến độ

Thanh chính là thời lượng audio đã xử lý theo các khoảng thực tế; các khoảng chồng lặp không bị cộng hai lần. Đây không phải điểm chính xác của bản dịch và không phải ước lượng thời gian còn lại. 100% audio có thể vẫn đang tạo giọng: xem chỉ số **Giọng X/Y câu** và trạng thái hiện tại. Khi chưa đo được phần hoàn thành, thanh chỉ báo đang hoạt động, không tự tăng phần trăm.

Có tiến độ trên app Windows, popup, bảng hội thoại và lớp trên video. Nếu mất cập nhật từ tab, popup giữ số đo cũ và báo mất kết nối. Lỗi audio/dịch/giọng được báo riêng. Đoạn âm thanh chưa chắc được đánh dấu cần kiểm tra; nếu chọn xem phần đã dịch, không có nghĩa mọi thoại đã được xác minh đầy đủ.

## Nâng cấp

App đang được cập nhật tại chỗ. Trên chrome://extensions, người dùng bấm ↻ trong ô Ligter Voice để hiện **0.8.3**, sau đó F5 tab Douyin. Lần nâng cấp này có sửa tiện ích; phiên bản app và tiện ích đều là 0.8.3. Quyền tiện ích không mở rộng.

Giữ EXE, _internal và models cạnh nhau. Khóa được giữ trong settings.bin mã hóa Windows DPAPI, không có trong gói nguồn. Máy chủ chỉ nghe loopback 127.0.0.1:38479. Đóng cửa sổ app thu xuống khay; chọn Thoát trong khay mới tắt app.

## Kiểm tra và giới hạn

56 kiểm thử Python và 8 bộ JavaScript đã qua: tiến độ theo coverage thực, tách đủ chữ/đủ giọng, lỗi/kết nối, không tự bắt đầu khi mở popup, không nhận video kế bên, hủy khi chuyển video và bỏ kết quả cũ trả muộn. Kiểm thử full pipeline audio thật của bản 0.8.2 vẫn là bằng chứng bản cũ; 0.8.3 đã kiểm thử riêng điều kiện xem sớm, chờ toàn bộ, giọng chạy quá 6 câu và giữ tiến độ cache cũ. Chưa đo thời gian khởi động trên video Douyin mới bằng tiện ích 0.8.3. Giao diện popup được render kiểm tra ở 296 x 400 px trong trạng thái đang làm việc.

Kết quả mẫu không chứng minh tốc độ/độ chính xác của mọi video Douyin. Vẫn cần kiểm thử bản tiện ích đã nạp trên video thực. Nhạc, chồng thoại, giọng nhỏ hoặc địa phương có thể khiến nhận diện thiếu/sai. Chưa tuyên bố đạt cơ chế đối chiếu phụ đề/OCR như yêu cầu chất lượng cuối cùng.

## Tốc độ 0.8.3

Tạo giọng chạy gối với nhận diện/dịch toàn bộ các câu đã có, không giữ ở 6 câu đầu. Yêu cầu dịch dùng danh sách từ gọn hơn; giữ timestamp ở máy để căn câu. Phần đầu lấy 5 giây cộng ngữ cảnh; phần sau xử lý theo cụm tối đa 30 giây để giảm số lượt gọi. Khi gặp HTTP 429, tôn trọng Retry-After thay vì gửi tiếp qua model khác. Xem sớm vẫn có thể gặp đoạn dịch đến muộn nếu tốc độ xử lý thấp hơn video; không tự pause hình liên tục, không loại thoại để chạy nhanh. Giới hạn dịch vụ còn ảnh hưởng thời gian chuẩn bị.

## Bản sửa 0.8.4 (app Windows)

Chặn đầu ra model lặp cùng câu dịch trên nhiều mảnh lời khác nhau và sửa dữ liệu đã lưu theo lời gốc. Tiện ích vẫn là 0.8.3; không cần nạp lại tiện ích cho bản sửa này. Sau cập nhật app, F5 tab Douyin rồi bấm Dịch video này để xóa hàng đợi giọng cũ. 58 kiểm thử Python và 8 bộ JavaScript đã qua, gồm xem thẳng và tua lùi.
