import sys
import os
import json
import subprocess
import urllib.request
import urllib.error

# 1. Tự động kiểm tra và cài đặt thư viện PyNaCl phục vụ mã hóa bảo mật
try:
    import nacl.public
    import nacl.encoding
except ImportError:
    print("[Setup] Thư viện 'pynacl' dùng để mã hóa bảo mật chưa được cài đặt.")
    print("[Setup] Đang tự động cài đặt 'pynacl' bằng pip...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "pynacl"], check=True)
        import nacl.public
        import nacl.encoding
        print("[Setup] Cài đặt 'pynacl' thành công!\n")
    except Exception as e:
        print(f"[Setup] Lỗi tự động cài đặt: {e}")
        print("Vui lòng tự chạy lệnh sau trong Terminal rồi thử lại: pip install pynacl")
        sys.exit(1)

def github_request(url, token, method="GET", payload=None):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "TikTok-Streak-Setup-Bot",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_body = response.read().decode("utf-8")
            if res_body:
                return json.loads(res_body), response.status
            return {}, response.status
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
            msg = err_json.get("message", err_body)
        except:
            msg = err_body
        raise Exception(f"GitHub API Error ({e.code}): {msg}")
    except Exception as e:
        raise Exception(f"Lỗi kết nối: {e}")

def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """Mã hóa chuỗi ký tự bằng Public Key của repository"""
    pub_key_bytes = nacl.encoding.Base64Encoder.decode(public_key_b64)
    public_key = nacl.public.PublicKey(pub_key_bytes)
    sealed_box = nacl.public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return nacl.encoding.Base64Encoder.encode(encrypted).decode("utf-8")

def set_github_secret(token, owner, repo, secret_name, secret_value):
    # 1. Lấy Public Key của Repository
    url_key = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key"
    key_info, _ = github_request(url_key, token)
    
    key_id = key_info["key_id"]
    public_key_b64 = key_info["key"]
    
    # 2. Mã hóa dữ liệu mật
    encrypted_value = encrypt_secret(public_key_b64, secret_value)
    
    # 3. Ghi đè Secret lên repo
    url_secret = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{secret_name}"
    payload = {
        "encrypted_value": encrypted_value,
        "key_id": key_id
    }
    github_request(url_secret, token, method="PUT", payload=payload)
    print(f"   ✅ [Secrets] Đã cấu hình: {secret_name}")

def get_git_remote():
    """Tự động phát hiện owner và repo của dự án hiện tại qua cấu hình Git"""
    try:
        import subprocess
        import re
        res = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=True)
        url = res.stdout.strip()
        match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", url)
        if match:
            owner = match.group(1)
            repo = match.group(2)
            if repo.endswith(".git"):
                repo = repo[:-4]
            return owner, repo
    except:
        pass
    return None, None

def main():
    print("====================================================")
    print("      TIKTOK STREAK AUTO - 1-CLICK GITHUB SETUP     ")
    print("====================================================\n")
    print("Chào mừng! Script này sẽ giúp bạn tạo bản sao Private của dự án")
    print("hoặc cấu hình trực tiếp các biến bảo mật chạy ngầm miễn phí trên GitHub.\n")
    
    # Tự động phát hiện thông tin repo nguồn
    detected_owner, detected_repo = get_git_remote()
    if not detected_owner or not detected_repo:
        # Fallback về mặc định
        detected_owner = "Raindropdrops"
        detected_repo = "Keep-Streak-TikTok-API"
    
    # 1. Nhập Token GitHub
    print("Bước 1: Cấu hình liên kết tài khoản GitHub")
    print("------------------------------------------")
    print("Cách lấy GitHub Token (PAT):")
    print("1. Truy cập https://github.com/settings/tokens")
    print("2. Chọn 'Generate new token (classic)'")
    print("3. Tích chọn quyền: 'repo' và 'workflow'")
    print("4. Copy chuỗi token hiển thị.")
    token = input("👉 Nhập GitHub Token của bạn: ").strip()
    if not token:
        print("[Lỗi] Token không được để trống.")
        return

    # Xác thực token
    print("Đang kiểm tra kết nối tài khoản GitHub...")
    try:
        user_info, _ = github_request("https://api.github.com/user", token)
        gh_username = user_info["login"]
        print(f"🎉 Kết nối thành công tài khoản GitHub: @{gh_username}\n")
    except Exception as e:
        print(f"[Lỗi] Xác thực Token thất bại: {e}")
        return

    # 2. Nhập thông tin cấu hình Bot TikTok
    print("Bước 2: Nhập thông tin cấu hình gửi tin nhắn TikTok")
    print("--------------------------------------------------")
    
    while True:
        tiktok_username = input("👉 Nhập tài khoản TikTok (Email hoặc Username): ").strip()
        tiktok_password = input("👉 Nhập mật khẩu TikTok: ").strip()
        captcha_api = input("👉 Nhập Captcha API Key (Bỏ qua nếu chưa có): ").strip()
        message = input("👉 Nhập nội dung tin nhắn gửi bạn bè (Mặc định: 'Chao Buoi Sang Tinh Yeu <3'): ").strip()
        if not message:
            message = "Chao Buoi Sang Tinh Yeu <3"
            
        print("\nCấu hình báo cáo Telegram (Không bắt buộc - ấn Enter để bỏ qua):")
        tg_token = input("👉 Nhập Telegram Bot Token: ").strip()
        tg_chat_id = input("👉 Nhập Telegram Chat ID: ").strip()

        print("\nCấu hình Web & Database Portal (Không bắt buộc - ấn Enter để bỏ qua):")
        api_base_url = input("👉 Nhập URL Web Dashboard/API (Ví dụ: https://streak.nadh.id.vn): ").strip()
        api_key = input("👉 Nhập khóa bảo mật API Key (Đặt trong api.php): ").strip()

        # Xác thực tài khoản TikTok cục bộ
        print("\nĐang tiến hành xác thực tài khoản TikTok cục bộ để kiểm tra mật khẩu...")
        # Thiết lập biến môi trường tạm thời cho captcha nếu người dùng đã nhập
        if captcha_api:
            os.environ["CAPTCHA_API_KEY"] = captcha_api

        from utils import init_browser, login_tiktok, is_logged_in
        import time
        
        browser = None
        verified = False
        try:
            print("   [TikTok Verify] Khởi động trình duyệt kiểm tra (chạy ngầm)...")
            browser, wait = init_browser(headless=True)
            login_tiktok(browser, wait, tiktok_username, tiktok_password)
            
            # Điều hướng kiểm tra trang tin nhắn
            browser.get('https://www.tiktok.com/messages?lang=vi')
            time.sleep(5)
            
            if is_logged_in(browser):
                print("   ✅ [TikTok Verify] Xác thực tài khoản thành công! Thông tin đăng nhập chính xác.")
                verified = True
            else:
                print("   ❌ [TikTok Verify] Xác thực thất bại! Mật khẩu có thể sai hoặc TikTok yêu cầu giải Captcha.")
        except Exception as e:
            print(f"   ⚠️ [TikTok Verify] Có lỗi xảy ra khi xác thực tự động: {e}")
        finally:
            if browser:
                try:
                    browser.quit()
                except:
                    pass

        if verified:
            break

        # Menu hỗ trợ khắc phục khi xác thực thất bại
        print("\n[Hỗ trợ sửa lỗi] Lựa chọn hành động tiếp theo:")
        print("1. Chạy lại bằng trình duyệt hiển thị (Bạn có thể tự tay giải Captcha hoặc xem lỗi mật khẩu)")
        print("2. Nhập lại thông tin tài khoản / mật khẩu khác")
        print("3. Bỏ qua cảnh báo lỗi và tiếp tục thiết lập (Có thể bạn sẽ tự sửa mật khẩu trên GitHub sau)")
        print("4. Thoát chương trình")
        
        action = input("👉 Chọn số (1-4): ").strip()
        
        if action == "1":
            print("\nĐang khởi động trình duyệt hiển thị (Bạn sẽ thấy cửa sổ Chrome hiện lên)...")
            try:
                browser, wait = init_browser(headless=False)
                login_tiktok(browser, wait, tiktok_username, tiktok_password)
                
                print("\n💡 MẸO: Nếu thấy thanh trượt giải Captcha của TikTok, hãy dùng chuột kéo trượt để giải trực tiếp!")
                print("Hệ thống đang chờ bạn đăng nhập hoặc giải Captcha thành công (Chờ tối đa 60 giây)...")
                
                # Chờ người dùng giải captcha hoặc đăng nhập thành công
                for attempt in range(30):
                    time.sleep(2)
                    try:
                        if is_logged_in(browser) or "/messages" in browser.current_url:
                            print("   ✅ [TikTok Verify] Đã nhận diện đăng nhập thành công!")
                            verified = True
                            break
                    except:
                        pass
                
                if not verified:
                    print("   ❌ [TikTok Verify] Quá thời gian chờ hoặc đăng nhập vẫn thất bại.")
            except Exception as e:
                print(f"   ⚠️ Lỗi trình duyệt hiển thị: {e}")
            finally:
                if browser:
                    try:
                        browser.quit()
                    except:
                        pass
            
            if verified:
                break
                
        elif action == "2":
            print("\n--- Nhập lại thông tin TikTok ---")
            continue
        elif action == "3":
            print("⚠️ Bỏ qua cảnh báo xác thực. Tiếp tục thiết lập...")
            break
        else:
            print("Đã hủy thiết lập.")
            return
    
    # Kiểm tra xem người dùng có phải là chủ sở hữu của repo hiện tại không
    is_own_repo = (gh_username.lower() == detected_owner.lower())
    
    target_owner = gh_username
    target_repo = ""
    skip_creation = False
    new_repo_url = ""
    
    if is_own_repo:
        print(f"\nℹ️ Bạn đang là chủ sở hữu của repository hiện tại ({detected_owner}/{detected_repo}).")
        choice = input("👉 Bạn có muốn cấu hình trực tiếp các Secrets lên repository hiện tại này không? (Y/n): ").strip().lower()
        if choice in ("", "y", "yes"):
            skip_creation = True
            target_owner = detected_owner
            target_repo = detected_repo
            new_repo_url = f"https://github.com/{target_owner}/{target_repo}"
            print(f"✅ Sẽ cấu hình trực tiếp lên repository hiện tại của bạn: {target_owner}/{target_repo}\n")

    # 3. Khởi tạo bản sao Repository trên GitHub (nếu không phải chính chủ muốn đè lên repo cũ)
    if not skip_creation:
        print("\nBước 3: Khởi tạo bản sao Repository trên GitHub")
        print("------------------------------------------------")
        repo_name = input("👉 Nhập tên Repo mới muốn tạo (Mặc định: tiktok-streak-auto): ").strip()
        if not repo_name:
            repo_name = "tiktok-streak-auto"
            
        target_repo = repo_name
        
        print(f"Đang tiến hành nhân bản repo từ {detected_owner}/{detected_repo} thành {gh_username}/{repo_name}...")
        success = False
        
        # Thử phương thức 1: Tạo từ Template
        try:
            url_generate = f"https://api.github.com/repos/{detected_owner}/{detected_repo}/generate"
            payload_gen = {
                "owner": gh_username,
                "name": repo_name,
                "description": "Tự động gửi tin nhắn duy trì streak TikTok (Được tạo từ mẫu)",
                "include_all_branches": False,
                "private": True
            }
            res_gen, status = github_request(url_generate, token, method="POST", payload=payload_gen)
            target_repo = res_gen.get("name", repo_name)
            new_repo_url = res_gen.get("html_url", f"https://github.com/{gh_username}/{target_repo}")
            print(f"🎉 Khởi tạo repository Private thành công (phương thức Template): {new_repo_url}\n")
            success = True
        except Exception as e:
            # Nếu đã tồn tại
            if "already exists" in str(e):
                print(f"ℹ️ Repository '{repo_name}' đã tồn tại trên tài khoản của bạn.")
                print("Đang tiếp tục cập nhật Secrets lên repo hiện tại này...")
                new_repo_url = f"https://github.com/{gh_username}/{repo_name}"
                success = True
            else:
                print(f"⚠️ Tạo từ Template không khả dụng (Lỗi: {e}).")
                print("Đang chuyển hướng sang phương thức Fork (Tạo bản sao) repository...")

        # Thử phương thức 2: Tạo từ Fork (Dành cho trường hợp repo nguồn không được đánh dấu là template)
        if not success:
            try:
                url_fork = f"https://api.github.com/repos/{detected_owner}/{detected_repo}/forks"
                payload_fork = {
                    "name": repo_name,
                    "default_branch_only": True
                }
                res_fork, _ = github_request(url_fork, token, method="POST", payload=payload_fork)
                target_repo = res_fork.get("name", repo_name)
                new_repo_url = res_fork.get("html_url", f"https://github.com/{gh_username}/{target_repo}")
                print(f"🎉 Fork repository thành công: {new_repo_url}\n")
                success = True
            except Exception as e2:
                print(f"[Lỗi] Tất cả phương thức tạo bản sao đều thất bại: {e2}")
                return

        # Đợi 3 giây để GitHub đồng bộ hóa repository mới tạo
        import time
        time.sleep(3)
    else:
        # Gán target_repo trong trường hợp skip_creation
        target_repo = detected_repo

    # 4. Đẩy Secrets
    print("Bước 4: Thiết lập các biến môi trường Secrets bảo mật...")
    print("-----------------------------------------------------")
    try:
        set_github_secret(token, target_owner, target_repo, "TIKTOK_USERNAME", tiktok_username)
        set_github_secret(token, target_owner, target_repo, "TIKTOK_PASSWORD", tiktok_password)
        if captcha_api:
            set_github_secret(token, target_owner, target_repo, "CAPTCHA_API_KEY", captcha_api)
        set_github_secret(token, target_owner, target_repo, "MESSAGE", message)
        if tg_token and tg_chat_id:
            set_github_secret(token, target_owner, target_repo, "TELEGRAM_BOT_TOKEN", tg_token)
            set_github_secret(token, target_owner, target_repo, "TELEGRAM_CHAT_ID", tg_chat_id)
        if api_base_url and api_key:
            set_github_secret(token, target_owner, target_repo, "API_BASE_URL", api_base_url)
            set_github_secret(token, target_owner, target_repo, "API_KEY", api_key)
        print("🎉 Đã cấu hình Secrets thành công!\n")
    except Exception as e:
        print(f"[Lỗi] Ghi Secrets thất bại: {e}")
        return

    # 5. Kích hoạt Actions
    print("Bước 5: Kích hoạt chạy ngầm (GitHub Actions)")
    print("---------------------------------------------")
    url_permissions = f"https://api.github.com/repos/{target_owner}/{target_repo}/actions/permissions"
    try:
        github_request(url_permissions, token, method="PUT", payload={"enabled": True})
        print("✅ Đã kích hoạt chạy Actions thành công!")
    except Exception as e:
        print(f"⚠️ Không thể tự động kích hoạt Actions qua API: {e}")
        print("Bạn có thể cần bật thủ công bằng cách truy cập Tab 'Actions' trên repo và ấn nút 'I understand my workflows, go ahead and enable them'.")

    print("\n====================================================")
    print("               HOÀN THÀNH THIẾT LẬP!               ")
    print("====================================================")
    print(f"Dự án của bạn đã sẵn sàng chạy tại: {new_repo_url or f'https://github.com/{target_owner}/{target_repo}'}")
    print("\nHướng dẫn chạy thử lần đầu:")
    print(f"1. Truy cập {new_repo_url or f'https://github.com/{target_owner}/{target_repo}'}/actions")
    print("2. Chọn workflow 'TikTok Streak Auto Send' ở danh sách bên trái.")
    print("3. Ấn nút 'Run workflow' > Chọn nhánh main > Ấn 'Run workflow' để bắt đầu chạy.")
    print("Hệ thống sẽ tự động chạy hàng ngày vào lúc 19:00 (giờ Việt Nam). Cảm ơn bạn!")
    print("====================================================\n")

if __name__ == "__main__":
    main()

