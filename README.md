# TikTok Streak Auto

Dự án tự động gửi tin nhắn duy trì streak trên TikTok Web sử dụng Selenium, hỗ trợ tự động giải captcha, quản lý danh bạ thông minh (Phase 2), báo cáo qua Telegram, và chạy hoàn toàn tự động qua GitHub Actions.

---

## Hướng Dẫn Cài Đặt Tự Động 1-Click (Dành Cho Người Mới)

Nếu bạn muốn chia sẻ cho bạn bè hoặc tự tạo bản sao tự động chạy 24/7 trên Cloud miễn phí của riêng mình, chỉ cần làm theo các bước tự động sau:

1. **Chuẩn bị Token GitHub (PAT):**
   * Truy cập: [GitHub Token Settings](https://github.com/settings/tokens).
   * Ấn **Generate new token (classic)**.
   * Tích chọn 2 quyền quan trọng: **`repo`** và **`workflow`**.
   * Nhấn tạo token ở cuối trang và sao chép (copy) chuỗi ký tự hiển thị.

2. **Chạy Script Thiết Lập Tự Động:**
   * Tải file [setup_github.py](file:///d:/Nam%202(D)/Tiktokstreak/tiktok-streak-dev/setup_github.py) về máy.
   * Mở Terminal (Command Prompt / PowerShell) tại thư mục chứa file và chạy lệnh:
     ```sh
     python setup_github.py
     ```
   * Nhập GitHub Token bạn vừa copy, nhập tài khoản/mật khẩu TikTok của bạn, và làm theo hướng dẫn của script.
   * Script sẽ tự động tạo repository Private trên tài khoản của bạn, cấu hình các biến bảo mật Secrets, kích hoạt GitHub Actions.

3. **Hoàn tất và Chạy thử:**
   * Truy cập đường dẫn repository Private mới vừa được tạo trên tài khoản GitHub của bạn.
   * Vào tab **Actions** > Chọn **TikTok Streak Auto Send** ở cột bên trái.
   * Nhấn **Run workflow** > Chọn nhánh `main` > Nhấn **Run workflow** để chạy thử.
   * Bot sẽ tự động chạy hàng ngày vào lúc 19:00 (giờ Việt Nam). Bạn có thể tắt máy tính hoàn toàn yên tâm!

---

## Environment Variables

Tạo file `.env` ở thư mục gốc của dự án và khai báo các biến môi trường sau:

```
CAPTCHA_API_KEY="api_key_ocacaptcha"
TIKTOK_USERNAME="username_hoac_email"
TIKTOK_PASSWORD="password"
MESSAGE="tin nhắn duy trì streak"

# Cấu hình báo cáo Telegram (Tùy chọn)
TELEGRAM_BOT_TOKEN="token_bot_telegram"
TELEGRAM_CHAT_ID="id_chat_nhan_bao_cao"
```

---

## Quản Lý Danh Bạ & Chạy Bot (CLI)

Hệ thống sử dụng file danh bạ định dạng JSON (`contacts.json`) lưu trữ nâng cao: các tên hiển thị, tên phụ (aliases), và ID cuộc trò chuyện (`conversation_id`, `user_id`, `sec_uid`) để không bao giờ bị lạc mất liên kết khi bạn bè đổi tên hiển thị.

Khi khởi chạy lần đầu, bot tự động đọc file `friends.csv` cũ (nếu có) và convert sang `contacts.json`.

### 1. Khởi chạy CLI mới `streak_bot.py`
Để chạy bot, sử dụng tập lệnh `streak_bot.py`:

* **Gửi tin nhắn hàng ngày (mặc định):**
  ```sh
  python streak_bot.py --send
  ```
  *(Các file `main.py` và `my-friends.py` vẫn hoạt động bình thường dưới dạng wrapper tương thích ngược)*

* **Quét và đồng bộ danh bạ (Resolve Contacts):**
  Bot sẽ mở danh sách chat TikTok, tự động cuộn tìm bạn bè, trích xuất các ID ổn định và lưu lại:
  ```sh
  python streak_bot.py --resolve-contacts
  ```

* **Chạy với chế độ Debug lưu ảnh chụp màn hình/HTML:**
  ```sh
  python streak_bot.py --send --debug-screenshots --debug-html
  ```

---

## Quản Lý Danh Bạ Qua API Server

Dự án cung cấp một API Server nhẹ bằng **FastAPI** giúp bạn xem và cập nhật danh bạ từ xa.

### Khởi động API Server:
```sh
pip install fastapi uvicorn pydantic
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```
Sau khi chạy, truy cập đường dẫn `http://localhost:8000/docs` trên trình duyệt để sử dụng giao diện Swagger UI tương tác.

### Danh sách API:
* `GET /v1/contacts`: Trả về danh sách bạn bè kèm độ tin cậy của việc resolve (`resolve_confidence`) và trạng thái đồng bộ.
* `POST /v1/contacts/resolve`: Ra lệnh cho bot mở trình duyệt chạy Resolver dưới nền (`BackgroundTasks`) để quét/quản lý danh bạ.
* `PATCH /v1/contacts/{identifier}`: Cập nhật thủ công danh bạ (ví dụ: kích hoạt/hủy kích hoạt gửi tin nhắn bằng `enabled`, cập nhật biệt danh cũ bằng `aliases`).

---

---

## Cổng Quản Trị Web & Database Portal (Phase 3 - Mới)

Nếu bạn không muốn chạy API FastAPI cục bộ và muốn quản trị danh sách bạn bè một cách trực quan từ xa bằng Điện thoại hoặc Máy tính mà không cần Commit lại code lên Git, dự án hỗ trợ kết nối trực tiếp với một database MySQL (ví dụ trên Hosting Tenten của bạn) thông qua một cổng trung gian API PHP Proxy cực kỳ an toàn.

### Các bước cài đặt cổng quản trị:

1. **Khởi tạo Database (MySQL):**
   * Truy cập phpMyAdmin trên Hosting của bạn.
   * Tạo một Database mới (hoặc dùng database sẵn có).
   * Mở tab **SQL**, copy nội dung file [schema.sql](file:///d:/Nam%202(D)/Tiktokstreak/tiktok-streak-dev/schema.sql) và chạy lệnh để tạo bảng `tiktok_contacts`.

2. **Cấu hình & Upload API PHP:**
   * Mở file [api.php.example](file:///d:/Nam%202(D)/Tiktokstreak/tiktok-streak-dev/api.php.example).
   * Điền thông tin kết nối Database của bạn và tự tạo một chuỗi `API_KEY` (Khóa bảo mật của bạn).
   * Đổi tên file thành `api.php`.
   * Mở file [index.php.example](file:///d:/Nam%202(D)/Tiktokstreak/tiktok-streak-dev/index.php.example).
   * Đổi tên file thành `index.php`.
   * Upload cả 2 file `api.php` và `index.php` lên hosting của bạn (ví dụ vào thư mục subdomain `streak.nadh.id.vn`).

3. **Cấu hình cho Bot chạy trên GitHub:**
   * Bạn chỉ cần chạy script `setup_github.py` để nhập thông tin URL API và API Key của bạn. Script sẽ tự động đồng bộ chúng lên GitHub Secrets với 2 tên biến sau:
     * `API_BASE_URL`: Địa chỉ website quản trị của bạn (ví dụ: `https://streak.nadh.id.vn`)
     * `API_KEY`: Khóa bảo mật tương ứng bạn đã đặt.
   * Khi 2 biến này tồn tại, Bot trên GitHub Actions sẽ tự động đọc/ghi đồng bộ dữ liệu bạn bè trực tiếp từ Database MySQL của bạn thay vì dùng file cục bộ.

4. **Sử dụng Dashboard:**
   * Truy cập trang web của bạn (`https://yourdomain.com`).
   * Nhập khóa `API_KEY` của bạn khi hệ thống yêu cầu lần đầu tiên (sẽ được lưu an toàn trong trình duyệt của bạn).
   * Bạn có thể dễ dàng:
     * Bật/Tắt trạng thái hoạt động của từng người bạn (`enabled`).
     * Xem thống kê lượt gửi thành công/thất bại, thời gian gửi cuối thời gian thực.
     * Thêm tài khoản mới trực tiếp hoặc chỉnh sửa biệt danh phụ (`aliases`) của họ ngay từ điện thoại!

---

## Bảo Mật Trên GitHub Actions (Public Repo)

Vì repository của bạn có thể ở chế độ **Public**, thông tin nhạy cảm của bạn bè trong file `contacts.json` sẽ **không được push lên GitHub** nhờ cấu hình `.gitignore`.

Thay vào đó, dự án sử dụng cơ chế **GitHub Actions Cache** (`actions/cache`) tự động lưu và khôi phục file `contacts.json` giữa các ngày chạy. Bạn hoàn toàn có thể yên tâm chạy tự động lifetime mà không lo rò rỉ dữ liệu.

### Thiết lập GitHub Secrets:
Truy cập vào cài đặt repo trên GitHub (`Settings > Secrets and variables > Actions`) và thêm các secret tương ứng với file `.env`:
* `TIKTOK_USERNAME`
* `TIKTOK_PASSWORD`
* `CAPTCHA_API_KEY`
* `MESSAGE`
* `TELEGRAM_BOT_TOKEN` (Tùy chọn)
* `TELEGRAM_CHAT_ID` (Tùy chọn)

---

## Hướng Dẫn Khi Bạn Bè Đổi Tên Hiển Thị
1. Nếu bạn biết trước họ đổi tên, bạn có thể gọi API `PATCH /v1/contacts/{username}` để thêm tên cũ/mới của họ vào trường `aliases`.
2. Chạy quét resolver: `python streak_bot.py --resolve-contacts` để bot tự nhận diện lại cuộc hội thoại dựa trên profile URL / Room ID và tự cập nhật lại thông tin mới nhất vào `contacts.json`.

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=huuthang201/tiktok-streak&type=Date)](https://www.star-history.com/#huuthang201/tiktok-streak&Date)
