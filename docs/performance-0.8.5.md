# Tốc độ và phạm vi kiểm thử 0.8.5

Ưu tiên giảm thời gian sau khi chọn dịch video, không thêm lượt gọi AI để phân tích lại từng câu và không nạp video kế bên.

## Thay đổi

- Nạp trước Whisper tại máy khi app mở; đây là chuyển công việc sang lúc khởi động app, không loại bỏ chi phí model.
- Dùng lại kết nối HTTP theo worker, không tự retry ngầm trong adapter.
- Cache nhận diện theo hash audio + ngôn ngữ + backend, lưu cục bộ; kiểm tra cấu trúc khi đọc và nhận diện lại nếu hỏng.
- Tạo giọng từ nhóm dịch đã chốt trước khi chờ nhóm chậm hơn. Không đưa lời chưa chốt vào hàng phát.
- Cache video đầy đủ không mở nguồn media. Dùng lại cache 0.8.4.
- Bộ chặn dịch lặp vẫn giữ các câu đáp ngắn đồng nghĩa thực sự.
- Ghi thời điểm quan sát thấy có thể xem vào metrics để đo thực tế.

## Mẫu đo

Cùng phần audio Douyin 7 giây đã lưu cục bộ, dùng ASR tại máy, Groq và giọng tại máy. Một mẫu cho mỗi trường hợp, không có độ tin cậy thống kê.

| Trường hợp | Nạp model trước phép đo | Từ yêu cầu xử lý tới ready |
|---|---:|---:|
| 0.8.4: giọng nạp trước, ASR chưa nạp | 13,917 s | 21,989 s |
| 0.8.5: giọng + ASR nạp trước | 10,626 s | 6,849 s |
| 0.8.5: xem lại cache đầy đủ | 10,512 s | 0,081 s |

Các phép đo chạy tuần tự trong cùng tiến trình benchmark; cache hệ điều hành và việc thư viện đã import có thể ảnh hưởng kết quả. Không nên diễn giải đây là hệ số tăng tốc trên mọi máy/video. Thời gian nạp model phải tính nếu người dùng bấm ngay khi app vừa mở.

Bản EXE thật 0.8.5 thử riêng qua cầu browser-range mô phỏng, tổng 9,397 s; đủ một file giọng cho một câu đã nhận diện. Đây không phải đo tab Douyin/CDN thật. Mẫu vẫn có một khoảng audio cần kiểm tra nhận diện; ready không chứng minh mọi thoại đã đúng và đủ. Việc kiểm thử nghe hết các video dài vẫn còn cần làm.

65 kiểm thử Python và 8 bộ JavaScript qua. Có kiểm tra TCP giữ cùng kết nối trong một worker, tách session giữa worker, cache hỏng, cache khác audio, cache sau mất bộ nhớ, giọng bắt đầu trước nhóm dịch chậm, nạp model một lần và xem video cached không mở media.

## Triển khai

App Windows 0.8.5, tiện ích vẫn 0.8.3. Chưa có lấy phụ đề gốc/OCR, hỗ trợ nền tảng khác hoặc Android. Không sao chép mã máy chủ Tolkora/Immersive Translate. Những tối ưu này là triển khai độc lập trên Ligter Voice.
