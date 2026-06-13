# TikTok Streak Auto

Bot Selenium tự động gửi tin nhắn TikTok mỗi ngày cho danh sách liên hệ đã bật.

## Chức năng

- Chỉ gửi sau khi xác minh đúng username của người nhận.
- Tin nhắn thay đổi theo từng ngày trong tuần.
- Tự thử lại khi TikTok hiển thị popup hoặc gặp lỗi tạm thời.
- Không gửi trùng cho cùng một người trong ngày.
- Chạy trên GitHub Actions lúc 04:00, 06:00 và 08:00 giờ Việt Nam.
- Hỗ trợ báo cáo kết quả qua Telegram.

## Cài đặt

Yêu cầu Python 3.10 trở lên và Google Chrome.

```bash
pip install -r requirements.txt
```

Sao chép `.env.example` thành `.env`, sau đó điền tài khoản và cấu hình cần thiết.
Không commit `.env`, `cookies.json` hoặc thông tin đăng nhập.

## GitHub Secrets

Vào `Settings > Secrets and variables > Actions` và thêm:

```text
TIKTOK_USERNAME
TIKTOK_PASSWORD
TIKTOK_COOKIES
MESSAGES
MESSAGE_MON ... MESSAGE_SUN
API_BASE_URL
API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

`TIKTOK_COOKIES` phải chứa nội dung JSON của file cookie TikTok. Các biến Telegram
và tin nhắn riêng theo ngày là tùy chọn.

## Sử dụng

Gửi tin nhắn:

```bash
python streak_bot.py --send
```

Quét lại danh sách chat:

```bash
python streak_bot.py --resolve-contacts
```

Chạy test:

```bash
python -m unittest discover -s tests -v
```

## GitHub Actions

Workflow chạy chính lúc 04:00 và chạy bù lúc 06:00, 08:00 giờ Việt Nam. Các lần
chạy bù chỉ xử lý người chưa nhận trong ngày. Workflow sẽ báo lỗi nếu chưa gửi đủ.

Có thể chọn `validate_only` khi chạy thủ công để kiểm tra workflow mà không gửi tin.

## Lưu ý

TikTok có thể thay đổi giao diện hoặc yêu cầu xác minh đăng nhập. Khi không xác minh
được chính xác người nhận, bot sẽ bỏ qua thay vì gửi nhầm.
