X.AI Auto Register + 9Router Sync 🤖

![Version](https://img.shields.io/badge/Version-Multi--Menu_Edition-blue.svg)
![Python](https://img.shields.io/badge/Python-3.8%2B-green.svg)

This is a complete, single-file Python automation tool designed to register X.AI accounts sequentially, extract OAuth PKCE tokens securely, and sync them directly into the 9Router SQLite database using the **Camoufox** anti-detection browser.

### 👤 Author Information
- **Creator** : [setyaw.xyz](https://www.setyaw.xyz)
- **GitHub** : [Utarasetyaw](https://github.com/Utarasetyaw)
- ⭐ *Jangan lupa follow dan kasih bintang (star) di repository ini!*

---

## ✨ Features

- **Interactive 3-Menu System:**
  1. **Full Auto (Create -> Token -> Inject):** Automatically generates a temp email, registers an X.AI account, solves Turnstile CAPTCHA, fetches OAuth tokens, and directly injects them into the 9Router DB.
  2. **Token Refresher:** Reads your saved accounts and silently refreshes expired `access_token` using the API.
  3. **Manual Injector:** Reads your saved accounts and manually injects them into 9Router DB (automatically skips accounts that already exist).
- **Anti-Detection Browser:** Powered by Camoufox to bypass modern bot protections.
- **In-Browser API Calls & Network Idle Handling.**
- **Automatic Storage:** Saves all successful results safely in `sukses.txt`.

---

## 🛠️ Requirements

- **OS:** Windows, Linux (Ubuntu/Debian, Fedora), or macOS
- **Python:** Version 3.8 or higher

---

## 🚀 Installation

1. **Clone the repository**
   ```bash
   git clone [git@github.com:Utarasetyaw/AutocreateGrok.git](git@github.com:Utarasetyaw/AutocreateGrok.git)
   cd xgrok_auto
Install Python dependencies

Bash
pip install -r requirements.txt
Fetch Camoufox Browser Engine

Bash
camoufox fetch
🐧 Linux Missing Dependencies Fix (If Camoufox Fails to Launch)
If you are running this on a Linux VPS or Desktop and encounter shared library errors (e.g., XPCOM errors), run the command corresponding to your OS:

Ubuntu / Debian / Kali Linux:

Bash
sudo apt update
sudo apt-get install -y libgtk-3-0 libgtk-3-dev libdbus-glib-1-2 libxt6 libx11-xcb1 libxcb-shm0 libasound2t64 libpangocairo-1.0-0 libatk1.0-0 libcairo-gobject2 libgdk-pixbuf-2.0-0 libnss3 libnspr4 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxkbcommon0
Fedora / RHEL / CentOS:

Bash
sudo dnf install -y gtk3 libX11 alsa-lib dbus-glib libXt libXcomposite libXdamage libXrandr mesa-libgbm pango cairo libxkbcommon
(Note: Windows users usually do not need extra dependencies to run Camoufox).

🎮 Usage
Run the main script:

Bash
python main_V2.py
(If your file is named main.py, adjust the command accordingly).

You will be presented with a menu interface. Type the number of the menu you want to execute and follow the on-screen prompts.

📁 Output Data Format
Successfully created accounts and extracted tokens are saved to a file named sukses.txt in the same directory. The data is stored in the following format:

Plaintext
email|password|access_token|refresh_token|expires_at
(Only successfully registered and verified accounts will be recorded).

⚠️ Warning / Disclaimer
This script is provided for EDUCATIONAL and RESEARCH PURPOSES ONLY.
It demonstrates browser automation, API interaction, OAuth PKCE flows, and CAPTCHA handling techniques. Use at your own risk. The author assumes no liability for any misuse, or account bans resulting from the use of this code.