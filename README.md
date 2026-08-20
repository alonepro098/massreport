# Telegram Mass Reporting Bot 🤖⚡

A Telegram Bot for mass reporting channels, groups, messages, or users directly within Telegram chat using multiple user account sessions (`StringSession`s).

---

## ✨ Features

- 🚀 **Interactive Telegram UI**: Control everything via `/start`, inline button menus, and step-by-step reporting wizards directly inside Telegram chat.
- 🎯 **Multi-Target Mass Reporting**:
  - 📢 **Channels / Groups** (`@username` or `https://t.me/...`)
  - 💬 **Specific Messages** (`https://t.me/c/.../123`)
  - 👤 **User Accounts**
- ⚠️ **8 Official Report Reasons**:
  - 🚫 Spam
  - ⚔️ Violence
  - 🔞 Pornography / NSFW
  - 🚸 Child Abuse
  - ⚖️ Copyright Infringement
  - 💊 Illegal Drugs
  - 👤 Personal Details (Doxxing)
  - ❓ Other
- 🔑 **Session Manager**: Easily add, test, list, and remove Telethon `StringSession` strings for your worker accounts.
- ⚡ **Concurrent Execution & Real-Time Progress**: Sends report requests across all active sessions in parallel and updates the progress bar live in Telegram.
- 🔍 **Target Verifier**: Check target name, ID, member count, and entity type before launching a report.
- 📊 **Report History & SQLite Logs**: Keep complete history of all mass report operations.

---

## 🛠️ Installation & Setup

### 1. Prerequisites
- Python 3.8+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Telegram `API_ID` & `API_HASH` (from [my.telegram.org](https://my.telegram.org))

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file from `.env.example`:
```ini
BOT_TOKEN=your_bot_token_from_botfather
API_ID=123456
API_HASH=your_api_hash_here
ADMIN_IDS=your_telegram_user_id
```

---

## 🚀 Running the Bot

Start the Telegram Bot:
```bash
python bot.py
```

### Generating String Sessions
To convert a Telegram phone number into a `StringSession`:
```bash
python generate_session.py
```
Copy the output `StringSession` and add it inside your Bot via **Session Manager** -> **➕ Add String Session**.

---

## 📜 Commands

- `/start` or `/menu` - Open Main Dashboard & Control Center
- `/report` - Launch Mass Report Wizard
- `/sessions` - Open Session Manager
- `/verify` - Open Target Verifier
- `/history` - View Mass Report Logs & History
