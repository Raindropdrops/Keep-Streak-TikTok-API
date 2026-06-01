import os
import sys
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Cấu hình stdout sử dụng UTF-8 để tránh lỗi hiển thị tiếng Việt trên Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def main():
    print("====================================================")
    print("        SCRIPT TỰ ĐỘNG XUẤT COOKIES ĐĂNG NHẬP       ")
    print("====================================================")
    print("Trình duyệt Chrome (không chạy ẩn) sẽ được mở ngay bây giờ.")
    print("👉 Hãy đăng nhập tài khoản TikTok của bạn trên trình duyệt đó.")
    print("👉 Sau khi đăng nhập thành công vào trang chủ TikTok, hãy quay lại đây.")
    print("----------------------------------------------------")
    
    # Khởi tạo trình duyệt hiển thị trực quan
    chrome_options = Options()
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--start-maximized")
    # Tắt thông báo automation để TikTok đỡ chặn
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    browser = webdriver.Chrome(options=chrome_options)
    
    try:
        # Vào trang đăng nhập
        browser.get("https://www.tiktok.com/login")
        
        # Chờ người dùng đăng nhập xong và ấn Enter
        input("\n⌨️ SAU KHI ĐĂNG NHẬP THÀNH CÔNG, HÃY ẤN [ENTER] TẠI ĐÂY ĐỂ LƯU COOKIES...")
        
        # Lấy cookies
        cookies = browser.get_cookies()
        
        # Đường dẫn file cookies.json
        from config import COOKIES_FILE
        
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=4)
            
        print("\n✅ THÀNH CÔNG!")
        print(f"Đã lưu cookies đăng nhập vào file: {COOKIES_FILE}")
        print("Bây giờ bạn có thể đóng trình duyệt Chrome.")
        print("Hãy chạy lệnh 'git add cookies.json' và push lên GitHub để hoàn tất.")
        
    except Exception as e:
        print(f"\n❌ Có lỗi xảy ra: {e}")
    finally:
        browser.quit()

if __name__ == "__main__":
    main()
