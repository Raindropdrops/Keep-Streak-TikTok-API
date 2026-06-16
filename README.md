# TikTok Streak Auto

Bot Selenium gửi tin nhắn TikTok hằng ngày cho danh sách người nhận được chọn rõ ràng.

## An toàn người nhận

Bot chỉ gửi khi thỏa cả hai điều kiện:

- Contact đang bật `enabled`.
- Username nằm trong allowlist `TIKTOK_SELECTED_RECIPIENTS`.

Nếu `TIKTOK_SELECTED_RECIPIENTS` trống, bot không gửi cho ai. Đây là lớp khóa bắt buộc để tránh gửi nhầm khi database contact bị sai hoặc bật quá rộng.

Ví dụ secret:

```text
user_a,user_b
@user_c
```

## GitHub Secrets

Thêm trong `Settings > Secrets and variables > Actions`:

```text
TIKTOK_USERNAME
TIKTOK_PASSWORD
TIKTOK_COOKIES
TIKTOK_SELECTED_RECIPIENTS
MESSAGES
MESSAGE_MON ... MESSAGE_SUN
API_BASE_URL
API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

`TIKTOK_COOKIES`, `TELEGRAM_*`, `MESSAGE_*`, `API_BASE_URL`, `API_KEY` tùy theo cách bạn đang chạy bot. Không commit `.env`, `cookies.json` hoặc thông tin đăng nhập.

## Chạy local

```bash
pip install -r requirements.txt
python streak_bot.py --send
```

Lệnh `python streak_bot.py` không có tham số sẽ dừng lại và không mở browser.

Quét lại danh sách chat:

```bash
python streak_bot.py --resolve-contacts
```

Chạy test:

```bash
python -m unittest discover -s tests -v
```

## GitHub Actions

Workflow đang được thiết kế để chạy lúc 04:00, 06:00 và 08:00 giờ Việt Nam, nhưng hiện đã bị disable thủ công trên GitHub để tránh gửi tiếp.

Chỉ bật lại workflow sau khi đã set chính xác `TIKTOK_SELECTED_RECIPIENTS`.
