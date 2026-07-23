import json
import sqlite3
import uuid
import os
from datetime import datetime, timezone
from pathlib import Path
from colorama import Fore, Style, init

init(autoreset=True)

# ================= CONFIGURATION =================
DEFAULT_FILE = "sukses.txt"
NINEROUTER_DB = Path.home() / ".9router" / "db" / "data.sqlite"

def print_banner():
    banner = f"""
{Fore.CYAN}+--------------------------------------------------+
|          9Router Standalone Injector             |
|          (Read from txt -> SQLite DB)            |
+--------------------------------------------------+
| Buatan : setyaw.xyz                              |
| Web    : www.setyaw.xyz                          |
| Github : https://github.com/Utarasetyaw          |
|                                                  |
|    * Jangan lupa follow dan kasih bintang *      |
+--------------------------------------------------+{Style.RESET_ALL}
"""
    print(banner)

def inject_to_9router(email, access_token, refresh_token, expires_at):
    """Fungsi untuk inject data ke 9Router DB. Skip jika sudah ada."""
    if not NINEROUTER_DB.is_file():
        return False, "DB_NOT_FOUND"

    try:
        conn = sqlite3.connect(str(NINEROUTER_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Cek apakah akun sudah ada
        cur.execute("SELECT id FROM providerConnections WHERE provider = 'grok-cli' AND (email = ? OR name = ?) LIMIT 1", (email, email))
        row = cur.fetchone()

        if row:
            conn.close()
            return False, "ALREADY_EXISTS"

        # Jika belum ada, Insert akun baru
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        conn_id = str(uuid.uuid4())
        data = {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresAt": expires_at,
            "testStatus": "active",
            "errorCode": None,
            "lastRefreshAt": now,
            "clientId": "b1a00492-073a-47ea-816f-4c329264a828"
        }
        
        cur.execute(
            """INSERT INTO providerConnections 
            (id, provider, name, email, data, isActive, createdAt, updatedAt, authType) 
            VALUES (?, 'grok-cli', ?, ?, ?, 1, ?, ?, 'oauth2')""",
            (conn_id, email, email, json.dumps(data), now, now)
        )

        conn.commit()
        conn.close()
        return True, "SUCCESS"

    except Exception as e:
        return False, str(e)

def main():
    print_banner()
    
    # Meminta input nama file (default: sukses.txt)
    file_input = input(f"{Fore.CYAN}Masukkan nama file TXT (Enter untuk '{DEFAULT_FILE}'): {Style.RESET_ALL}").strip()
    target_file = file_input if file_input else DEFAULT_FILE

    print(f"\n{Fore.CYAN}>> Membaca data dari {target_file}...{Style.RESET_ALL}")
    
    if not os.path.exists(target_file):
        print(f"{Fore.RED}[!] File {target_file} tidak ditemukan di folder ini.{Style.RESET_ALL}")
        return

    with open(target_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        print(f"{Fore.YELLOW}[!] File {target_file} kosong.{Style.RESET_ALL}")
        return

    success_count = 0
    skip_count = 0
    fail_count = 0

    for idx, line in enumerate(lines, 1):
        parts = line.strip().split("|")
        # Format yang diharapkan: email|password|access_token|refresh_token|expires_at
        if len(parts) >= 5:
            email, pwd, acc_token, ref_token, expires = parts[:5]
            
            if not acc_token or not ref_token:
                print(f"  {Fore.RED}[Line {idx}] {email} - Token tidak lengkap. Dilewati.{Style.RESET_ALL}")
                fail_count += 1
                continue
                
            print(f"{Fore.YELLOW}[*] Mengekstrak: {email}{Style.RESET_ALL}")
            is_success, msg = inject_to_9router(email, acc_token, ref_token, expires)
            
            if is_success:
                print(f"  {Fore.GREEN}[+] SUCCESS: Data berhasil di-inject ke DB!{Style.RESET_ALL}")
                success_count += 1
            elif msg == "ALREADY_EXISTS":
                print(f"  {Fore.BLUE}[~] SKIP: Akun sudah terdaftar di 9Router.{Style.RESET_ALL}")
                skip_count += 1
            elif msg == "DB_NOT_FOUND":
                print(f"  {Fore.RED}[!] ERROR: Database 9Router tidak ditemukan di {NINEROUTER_DB}{Style.RESET_ALL}")
                return # Berhenti total jika DB tidak ada
            else:
                print(f"  {Fore.RED}[!] ERROR: {msg}{Style.RESET_ALL}")
                fail_count += 1
        else:
            print(f"  {Fore.RED}[Line {idx}] Format data salah, harus ada 5 bagian dipisah '|'. Dilewati.{Style.RESET_ALL}")
            fail_count += 1

    print(f"\n{Fore.CYAN}{'=' * 50}")
    print(f"  {Fore.WHITE}INJECTION REPORT")
    print(f"  {Fore.GREEN}Sukses Inject : {success_count}")
    print(f"  {Fore.BLUE}Di-skip (Ada) : {skip_count}")
    print(f"  {Fore.RED}Gagal/Error   : {fail_count}")
    print(f"{Fore.CYAN}{'=' * 50}{Style.RESET_ALL}\n")

if __name__ == "__main__":
    main()