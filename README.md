# TikTok Streak Bot v2.0

![Created by Duc Anh](https://img.shields.io/badge/Created%20by-Duc%20Anh-blue)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-green)
![Version](https://img.shields.io/badge/Version-2.0.0-orange)

Automatically send TikTok streak messages to your friends — runs on PC locally or **free on GitHub Actions** (24/7 cloud).

## ✨ Features

### Core
- 🤖 **Browser Automation** — DrissionPage (Chromium) for reliable TikTok interaction
- 🔒 **API Key Auth** — Protected endpoints with `X-API-Key` header
- 📱 **Telegram Notifications** — Detailed run summaries delivered to your phone
- 📚 **Auto Documentation** — Swagger UI and ReDoc included

### v2.0 Upgrades
- ⏭️ **Daily Cooldown** — Skip contacts already messaged today
- 🔄 **Skip Unreachable** — Continue with next contact when one fails
- 🔁 **Smart Retry** — 4 attempts with exponential backoff (2s → 4s → 8s)
- 📡 **Network Check** — Verify internet before starting
- 🎯 **Better Selectors** — `data-e2e` based selectors + fallbacks
- 📊 **Run History** — Track last 50 runs with detailed results
- 📋 **Per-Contact Tracking** — `last_sent`, `success_count`, `failure_count`
- ⏰ **Interval Scheduling** — Run every X minutes (default: 23 hours)
- 🚀 **GitHub Actions** — Free 24/7 cloud automation

## 🛠️ Setup

### 1. Clone & Install

```bash
git clone https://github.com/Raindropdrops/Keep-Streak-TikTok-API.git
cd Keep-Streak-TikTok-API
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux/Mac
```

Edit `.env`:

```env
API_KEY=your-secure-api-key-here
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
STREAK_MESSAGE=🔥 Streak! 🔥
```

### 3. Setup TikTok Cookies

1. Login to TikTok in Chrome
2. Use an extension like "EditThisCookie" to export cookies
3. Save as `cookies.json` in the project root

### 4. Add Contacts

Create `contacts.json`:

```json
{
  "contacts": ["username1", "username2"]
}
```

> The bot will auto-upgrade this to the enhanced format with tracking on first run.

## 🚀 Usage

### Run Directly (PC)

```bash
# Run immediately
python streak_bot.py --now

# Test mode (find contacts, don't send)
python streak_bot.py --test

# Custom message
python streak_bot.py --now -m "Hey! Streak 🔥"

# Skip daily cooldown
python streak_bot.py --now --skip-cooldown

# Schedule: run every 23 hours (interval mode)
python streak_bot.py --interval

# Schedule: run daily at fixed time
python streak_bot.py
```

Or use the batch scripts:

```cmd
run_bot.bat       # Run bot immediately
run_api.bat       # Start API server
```

### Run via API

```bash
python api.py
# API available at http://localhost:8000/docs
```

### ☁️ Run on GitHub Actions (Free 24/7)

See [GitHub Actions Setup](#-github-actions-setup) below.

## 📚 API Endpoints

| Method   | Endpoint                  | Auth | Description      |
| -------- | ------------------------- | ---- | ---------------- |
| `GET`    | `/`                       | ❌   | Welcome message  |
| `GET`    | `/health`                 | ❌   | Health check     |
| `GET`    | `/status`                 | ❌   | Server status    |
| `POST`   | `/v1/streak`              | ✅   | Run streak bot   |
| `GET`    | `/v1/contacts`            | ✅   | List contacts    |
| `POST`   | `/v1/contacts`            | ✅   | Add contact      |
| `DELETE` | `/v1/contacts/{nickname}` | ✅   | Remove contact   |
| `GET`    | `/v1/history`             | ✅   | Run history (50) |

### Authentication

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/v1/contacts
```

## ☁️ GitHub Actions Setup

Run the bot **free on GitHub cloud** — no VPS needed!

### Step 1: Push to GitHub

```bash
git remote add origin https://github.com/YOUR/REPO.git
git push -u origin main
```

### Step 2: Add GitHub Secrets

Go to repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name          | Value                          |
| -------------------- | ------------------------------ |
| `TIKTOK_COOKIES`     | Base64 of `cookies.json`       |
| `CONTACTS_JSON`      | Base64 of `contacts.json`      |
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token        |
| `TELEGRAM_CHAT_ID`   | Your Telegram chat ID          |

### Step 3: Encode files as Base64

**PowerShell (Windows):**

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("cookies.json"))
[Convert]::ToBase64String([IO.File]::ReadAllBytes("contacts.json"))
```

**Bash (Linux/Mac):**

```bash
base64 -w 0 cookies.json
base64 -w 0 contacts.json
```

Copy the output → paste into the GitHub Secret.

### Step 4: Run

- Go to **Actions** tab → **TikTok Streak Bot** → **Run workflow**
- Or wait for the daily cron (runs at 07:00 Vietnam time / 00:00 UTC)
- Results are sent via Telegram + saved in Actions artifacts

### Updating Cookies

When TikTok cookies expire:
1. Export new cookies from browser
2. Encode as Base64
3. Update the `TIKTOK_COOKIES` secret in GitHub

## 📁 Project Structure

```
Keep-Streak-TikTok-API/
├── api.py                          # FastAPI REST API
├── config.py                       # Configuration (.env loader)
├── streak_bot.py                   # Bot core logic (v2.0)
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
├── .gitignore                      # Git exclusions
├── run_api.bat                     # Start API server (Windows)
├── run_bot.bat                     # Run bot directly (Windows)
├── .github/workflows/streak.yml    # GitHub Actions workflow
└── README.md
```

## ⚠️ Security Notes

- **Never commit** `.env`, `cookies.json`, `contacts.json`, `run_history.json`
- **Use strong API keys** — generate random secure keys
- **Rotate Telegram tokens** if exposed
- **Keep cookies private** — they contain your TikTok session
- **Use private repo** for GitHub Actions if storing sensitive data

## 📄 License

MIT License

---

**Created by Duc Anh** · v2.0
