# Ligter Voice

Ứng dụng Windows và tiện ích Chrome để dịch tiếng Trung/Anh sang tiếng Việt khi xem video Douyin web, hiển thị phụ đề theo thời gian và thuyết minh nam/nữ.

**Bản hiện tại:** app Windows 0.8.5; tiện ích Chrome 0.8.3. Bản Android cho Samsung Tab chưa được triển khai.

## Chức năng

- Chỉ xử lý video được người dùng chọn; chuyển video sẽ hủy phiên cũ.
- Có thể xem khi phần đầu đã có bản dịch và giọng; tùy chọn chờ chuẩn bị toàn bộ.
- Nhận diện tại máy bằng Whisper, dịch qua dịch vụ AI và tạo giọng Việt tại máy.
- Tiến độ dựa trên audio đã xử lý và số câu đã có giọng.
- Bản 0.8.4 phát hiện đầu ra dịch lặp trên nhiều mảnh lời khác nhau và dịch lại dữ liệu lỗi đã lưu.

## Giới hạn

Hiện hỗ trợ Douyin web trên Windows. Chưa có bản Android, hỗ trợ YouTube/Bilibili hay đối chiếu phụ đề nền tảng/OCR. Nhận diện và dịch vẫn có thể sai; mạng, hạn mức dịch vụ và tốc độ CPU ảnh hưởng độ trễ. Không bảo đảm dịch mọi thoại theo thời gian thực.

## Phát triển

Cần Python và Node.js tương thích với các thư viện trong requirements. Tạo môi trường Python, cài requirements; cài phụ thuộc kiểm thử bằng `npm install`. Chạy `python -m unittest discover -s tests -p "test_*.py"` và `npm test`.

Ứng dụng dùng các model nhận diện/giọng đặt trong thư mục `models` cạnh ứng dụng; model và runtime không nằm trong repo. Xem mã `local_asr.py`, `local_speech.py` và thư mục `licenses` để biết tên, bố trí và giấy phép thành phần. Repo mã nguồn này chưa phải bộ cài độc lập.

Chạy `python companion.py` để mở trung tâm xử lý; `build.ps1` đóng gói EXE bằng PyInstaller. Nhập khóa dịch vụ trong ứng dụng. Không lưu khóa vào mã nguồn. Cài tiện ích dạng unpacked từ thư mục `extension`, ghép mã kết nối từ app rồi sử dụng trên Douyin.

Xem [hướng dẫn sử dụng](HUONG-DAN.md) để biết chi tiết.

## Kiểm thử bản 0.8.5

65 kiểm thử Python và 8 bộ JavaScript đã qua trong môi trường phát triển Windows, gồm xem thẳng và tua lùi. Kiểm thử mô phỏng không thay thế việc nghe kiểm chứng toàn bộ video thực trên Chrome.

Khóa API, cấu hình cá nhân, cache, lịch sử video, model, EXE và dữ liệu kiểm thử của người dùng không được đưa lên repo. Giấy phép các thành phần bên thứ ba nằm trong `licenses`; chưa cấp giấy phép riêng cho toàn bộ dự án.

## Tối ưu tốc độ 0.8.5

- Nạp sẵn bộ nhận diện tại máy khi mở app, bên cạnh bộ giọng đã được nạp sẵn; không tải model từ mạng.
- Dùng lại kết nối HTTP theo worker, không dùng chung session có thể thay đổi giữa các luồng.
- Lưu kết quả nhận diện theo hash audio/cấu hình để không nhận diện lại sau khi khởi động lại hoặc thử lại bản dịch. Cache hỏng được bỏ qua để nhận diện lại.
- Tạo giọng của nhóm câu đã chốt trong lúc nhóm dịch tiếp theo còn chạy; không thêm lượt gọi AI để làm bước này.
- Video có cache hoàn chỉnh không mở nguồn media hoặc chạy ASR lại. Chỉ xử lý video người dùng chọn, không nạp video kế bên.
- Giữ bộ chặn bản dịch suy biến nhưng cho phép các câu đáp ngắn đồng nghĩa lặp thật.

Mẫu kiểm tra cục bộ cùng phần audio Douyin 7 giây: 0.8.4 khoảng 21,99 giây, 0.8.5 khoảng 6,85 giây sau khi nạp trước model, xem lại cache khoảng 0,08 giây. Thời gian nạp trước được đo riêng; mẫu có đoạn nhận diện chưa xác minh. Đây là một mẫu, chưa gồm mạng/CDN trình duyệt và không chứng minh mọi thoại đầy đủ hoặc mọi video nhanh tương tự.
