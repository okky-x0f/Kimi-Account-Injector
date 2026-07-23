import asyncio
import json
import re
import time
import random
import string
import secrets
import urllib.request
import urllib.parse
import ssl
import sqlite3
import uuid
import base64
import hashlib
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
from pathlib import Path
from colorama import Fore, Style, init
from fake_useragent import UserAgent
from camoufox.async_api import AsyncCamoufox

init(autoreset=True)

# ================= CONFIGURATION =================
MAIL_API_BASE = "https://mail.cskh-group.com"
XAI_SEND_CODE_URL = "https://console.x.ai/api/auth/send-verification-code"
XAI_VERIFY_URL = "https://console.x.ai/api/auth/sign-up/verify-email"
XAI_CREATE_ACCOUNT_URL = "https://console.x.ai/api/auth/sign-up/create-account"
TARGET_DOMAIN = "vin-groupvn.com"
TURNSTILE_SITEKEY = "0x4AAAAAAAhr9JGVDZbrZOo0"
CODE_PATTERN = re.compile(r"SpaceXAI confirmation code:\s*([A-Z0-9\-]+)")
SUCCESS_FILE = "sukses.txt"
NINEROUTER_DB = Path.home() / ".9router" / "db" / "data.sqlite"


def _get_ua():
    try:
        return UserAgent().random
    except Exception:
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def generate_random_identity():
    vowels = "aeiou"
    consonants = "bcdfghjklmnpqrstvwxyz"

    def _gen_name(min_len=4, max_len=7):
        length = random.randint(min_len, max_len)
        name = [random.choice(string.ascii_uppercase)]
        for i in range(1, length):
            if name[-1].lower() in vowels:
                name.append(random.choice(consonants))
            else:
                name.append(random.choice(vowels))
        return "".join(name)

    given_name = _gen_name()
    family_name = _gen_name(min_len=5, max_len=8)

    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = ''.join(secrets.choice(chars) for _ in range(14))
        if (any(c.isupper() for c in pwd) and
            any(c.islower() for c in pwd) and
            any(c.isdigit() for c in pwd) and
            any(c in "!@#$%^&*" for c in pwd)):
            break

    return given_name, family_name, pwd


def save_success(email, password, access_token="", refresh_token="", expires_at=""):
    line = f"{email}|{password}|{access_token}|{refresh_token}|{expires_at}\n"
    with open(SUCCESS_FILE, "a", encoding="utf-8") as f:
        f.write(line)


def print_banner():
    banner = f"""
{Fore.CYAN}+--------------------------------------------------+
|        X.AI Auto Register + 9Router Sync         |
|               (Multi-Menu Edition)               |
+--------------------------------------------------+
| Buatan : setyaw.xyz                              |
| Web    : www.setyaw.xyz                          |
| Github : https://github.com/Utarasetyaw          |
|                                                  |
|    * Jangan lupa follow dan kasih bintang *      |
+--------------------------------------------------+{Style.RESET_ALL}
"""
    print(banner)


# ================= OAUTH PKCE HELPERS =================
def generate_pkce_pair():
    raw = secrets.token_bytes(96)
    verifier = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def extract_code_from_url(url):
    try:
        parsed = urlparse(url)
        if "/callback" in (parsed.path or "") or "code=" in url:
            params = parse_qs(parsed.query)
            vals = params.get("code")
            return vals[0] if vals else None
    except:
        pass
    return None


def refresh_oauth_token(refresh_token):
    form = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "client_id": "b1a00492-073a-47ea-816f-4c329264a828",
        "refresh_token": refresh_token,
    }).encode("utf-8")
    
    req = urllib.request.Request(
        "https://auth.x.ai/oauth2/token",
        data=form,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return None


# ================= EMAIL HANDLER =================
def create_temp_email(domain=TARGET_DOMAIN):
    endpoint = f"{MAIL_API_BASE}/api/new"
    payload = json.dumps({"domain": domain}).encode("utf-8")
    req = urllib.request.Request(endpoint, data=payload, method="POST", headers={
        "Accept": "application/json", "Content-Type": "application/json", "User-Agent": _get_ua()
    })
    try:
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def check_inbox(email_address):
    url = f"{MAIL_API_BASE}/api/inbox/{email_address}"
    req = urllib.request.Request(url, method="GET", headers={
        "Accept": "application/json", "User-Agent": _get_ua()
    })
    try:
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def extract_code(inbox_data):
    if not inbox_data or not isinstance(inbox_data, dict):
        return None
    for email in inbox_data.get("emails", []):
        for field in ("subject", "preview"):
            match = CODE_PATTERN.search(email.get(field, ""))
            if match:
                return match.group(1)
    return None


# ================= 9ROUTER DB SYNC HANDLER =================
def sync_to_9router(email, access_token, refresh_token, expires_at, skip_if_exists=False):
    if not NINEROUTER_DB.is_file():
        print(f"  {Fore.RED}[!] 9router DB not found at: {NINEROUTER_DB}{Style.RESET_ALL}")
        return False

    try:
        conn = sqlite3.connect(str(NINEROUTER_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT id, data FROM providerConnections WHERE provider = 'grok-cli' AND (email = ? OR name = ?) LIMIT 1", (email, email))
        row = cur.fetchone()
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        if row and skip_if_exists:
            print(f"  {Fore.YELLOW}[SKIP] Account {email} is already in 9router DB.{Style.RESET_ALL}")
            conn.close()
            return True

        if row:
            conn_id = row["id"]
            try:
                data = json.loads(row["data"])
            except:
                data = {}

            data["accessToken"] = access_token
            data["refreshToken"] = refresh_token
            data["expiresAt"] = expires_at
            data["testStatus"] = "active"
            data["errorCode"] = None
            data["lastRefreshAt"] = now

            cur.execute(
                "UPDATE providerConnections SET data = ?, updatedAt = ? WHERE id = ?",
                (json.dumps(data), now, conn_id),
            )
        else:
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
        return True
    except Exception as e:
        print(f"  {Fore.RED}[!] 9router Sync Error: {e}{Style.RESET_ALL}")
        return False


# ================= BROWSER API HELPER =================
async def xai_api_call(page, url, payload_dict):
    response = await page.evaluate("""
        async ([url, payload]) => {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify(payload)
            });
            const status = res.status;
            let body = null;
            try { body = await res.json(); } catch(e) { body = await res.text(); }
            return { status, body };
        }
    """, [url, payload_dict])
    return response


# ================= TURNSTILE SOLVER =================
async def solve_turnstile(page, sitekey: str, url: str, timeout: int = 25) -> str | None:
    if not url.endswith("/"):
        url += "/"
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async></script>
<style>body{{margin:0;height:100vh;display:flex;justify-content:center;align-items:center;background:#1a1a1a}}</style>
</head><body><div class="cf-turnstile" data-sitekey="{sitekey}"></div></body></html>"""

    route_url = f"{url}__turnstile_solver__"

    async def handle_route(route):
        await route.fulfill(status=200, content_type="text/html", body=html)

    await page.route(route_url, handle_route)
    try:
        await page.goto(route_url, wait_until="domcontentloaded")
        await page.wait_for_selector(".cf-turnstile", timeout=8000)
    except Exception:
        return None

    start = time.time()
    for _ in range(30):
        try:
            await page.locator(".cf-turnstile").click(timeout=500, force=True)
        except Exception:
            pass
        token = await page.evaluate("""() => {
            const el = document.querySelector('input[name="cf-turnstile-response"]');
            return el && el.value.length > 30 ? el.value : null;
        }""")
        if token:
            elapsed = time.time() - start
            print(f"{header} {Fore.GREEN}[OK] Turnstile solved in {elapsed:.1f}s{Style.RESET_ALL}")
            return token
        await asyncio.sleep(0.4)
    return None


# ================= MENU 1: CREATE -> TOKEN -> INJECT =================
async def register_one_account(index, total):
    global header
    header = f"{Fore.CYAN}[{index}/{total}]{Style.RESET_ALL}"
    acc_start = time.time()

    given_name, family_name, password = generate_random_identity()
    print(f"{header} Identity: {given_name} {family_name}")

    print(f"{header} {Fore.YELLOW}[*] Creating temporary email...{Style.RESET_ALL}")
    mail_result = create_temp_email()
    if not mail_result or "email" not in mail_result:
        print(f"{header} {Fore.RED}[!] Failed to create email.{Style.RESET_ALL}")
        return False, time.time() - acc_start
    temp_email = mail_result["email"]
    print(f"{header} {Fore.GREEN}[OK] Email: {temp_email}{Style.RESET_ALL}")

    async with AsyncCamoufox(headless=True, disable_coop=True, i_know_what_im_doing=True,
                             humanize=False, os="windows", config={"forceScopeAccess": True}) as browser:
        page = await browser.new_page()

        print(f"{header} {Fore.YELLOW}[*] Initializing x.ai session...{Style.RESET_ALL}")
        await page.goto("https://console.x.ai/", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(2)

        print(f"{header} {Fore.YELLOW}[*] Sending verification code...{Style.RESET_ALL}")
        send_res = await xai_api_call(page, XAI_SEND_CODE_URL, {"email": temp_email})
        if not send_res or send_res.get("status") != 200:
            print(f"{header} {Fore.RED}[!] Failed to send code.{Style.RESET_ALL}")
            return False, time.time() - acc_start
        print(f"{header} {Fore.GREEN}[OK] Code sent{Style.RESET_ALL}")

        print(f"{header} {Fore.YELLOW}[*] Waiting for verification code...{Style.RESET_ALL}")
        code, elapsed, max_wait = None, 0, 60
        while elapsed < max_wait:
            await asyncio.sleep(3)
            elapsed += 3
            print(f"  {Fore.BLUE}[{elapsed}s]{Style.RESET_ALL} Checking inbox...")
            code = extract_code(check_inbox(temp_email))
            if code:
                print(f"{header} {Fore.GREEN}[OK] Code found: {code}{Style.RESET_ALL}")
                break
        if not code:
            print(f"{header} {Fore.RED}[!] Timeout.{Style.RESET_ALL}")
            return False, time.time() - acc_start

        print(f"{header} {Fore.YELLOW}[*] Verifying email...{Style.RESET_ALL}")
        verify_res = await xai_api_call(page, XAI_VERIFY_URL, {"email": temp_email, "code": code})
        if verify_res.get("status") != 200:
            print(f"{header} {Fore.RED}[!] Verification failed.{Style.RESET_ALL}")
            return False, time.time() - acc_start
        
        print(f"{header} {Fore.YELLOW}[*] Solving Turnstile challenge...{Style.RESET_ALL}")
        turnstile_token = await solve_turnstile(page, TURNSTILE_SITEKEY, "https://console.x.ai/login?mode=sign-up")
        if not turnstile_token:
            return False, time.time() - acc_start

        print(f"{header} {Fore.YELLOW}[*] Creating account...{Style.RESET_ALL}")
        create_payload = {
            "email": temp_email,
            "password": password,
            "givenName": given_name,
            "familyName": family_name,
            "emailValidationCode": code,
            "turnstileToken": turnstile_token
        }
        create_res = await xai_api_call(page, XAI_CREATE_ACCOUNT_URL, create_payload)
        is_success = create_res.get("status") == 200
        duration = time.time() - acc_start

        if is_success:
            print(f"{header} {Fore.GREEN}Account Created Successfully{Style.RESET_ALL}")
            
            print(f"{header} {Fore.YELLOW}[*] Executing OAuth PKCE...{Style.RESET_ALL}")
            verifier, challenge = generate_pkce_pair()
            state, nonce = secrets.token_urlsafe(24), secrets.token_hex(16)
            
            params = {
                "response_type": "code",
                "client_id": "b1a00492-073a-47ea-816f-4c329264a828",
                "redirect_uri": "http://127.0.0.1:56121/callback",
                "scope": "openid profile email offline_access grok-cli:access api:access conversations:read conversations:write",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": state, "nonce": nonce, "plan": "generic", "referrer": "cli-proxy-api",
            }
            auth_url = f"https://auth.x.ai/oauth2/authorize?{urllib.parse.urlencode(params)}"
            auth_code = {"code": None}

            async def _handle_route(route):
                req_url = route.request.url
                if "/callback" in req_url and ("127.0.0.1" in req_url or "localhost" in req_url):
                    c = extract_code_from_url(req_url)
                    if c: auth_code["code"] = c
                    try: await route.abort()
                    except: pass
                    return
                try: await route.continue_()
                except: pass

            await page.route("**/*", _handle_route)
            try: await page.goto(auth_url, wait_until="domcontentloaded", timeout=45000)
            except: pass

            for _ in range(15):
                if auth_code.get("code"): break
                try:
                    allow_btn = page.locator('button:has-text("Allow"), button:has-text("Authorize")').first
                    if await allow_btn.count() > 0 and await allow_btn.is_visible(): await allow_btn.click()
                except: pass
                try:
                    if await page.locator('input[type="password"]').count() > 0:
                        email_in = page.locator('input[type="email"]').first
                        if await email_in.count() > 0: await email_in.fill(temp_email)
                        pw_in = page.locator('input[type="password"]').first
                        if await pw_in.count() > 0: await pw_in.fill(password)
                        login_btn = page.locator('button:has-text("Log in"), button:has-text("Sign in")').first
                        if await login_btn.count() > 0: await login_btn.click()
                except: pass
                await asyncio.sleep(1)

            try: await page.unroute("**/*")
            except: pass

            code = auth_code.get("code")
            access_token, refresh_token, expires_at = "", "", ""

            if code:
                print(f"{header} {Fore.GREEN}[OK] OAuth Code captured. Fetching tokens...{Style.RESET_ALL}")
                form = urllib.parse.urlencode({
                    "grant_type": "authorization_code",
                    "client_id": "b1a00492-073a-47ea-816f-4c329264a828",
                    "code": code,
                    "redirect_uri": "http://127.0.0.1:56121/callback",
                    "code_verifier": verifier,
                }).encode("utf-8")
                
                req = urllib.request.Request("https://auth.x.ai/oauth2/token", data=form, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        token_res = json.loads(resp.read().decode("utf-8"))
                        access_token = token_res.get("access_token", "")
                        refresh_token = token_res.get("refresh_token", "")
                        expires_in = int(token_res.get("expires_in", 21600))
                        expires_at = datetime.fromtimestamp(time.time() + expires_in, timezone.utc).isoformat().replace("+00:00", "Z")
                except Exception as e:
                    print(f"{header} {Fore.RED}[!] Token exchange error: {e}{Style.RESET_ALL}")
            
            save_success(temp_email, password, access_token, refresh_token, expires_at)
            
            if access_token:
                if sync_to_9router(temp_email, access_token, refresh_token, expires_at, skip_if_exists=False):
                    print(f"{header} {Fore.GREEN}[OK] Successfully Synced to 9router DB!{Style.RESET_ALL}")
                else:
                    print(f"{header} {Fore.RED}[!] Failed injecting to 9router DB.{Style.RESET_ALL}")
            else:
                print(f"{header} {Fore.RED}[!] No 'access_token' found. Skipping DB sync.{Style.RESET_ALL}")
        else:
            print(f"{header} {Fore.RED}Account Creation Failed.{Style.RESET_ALL}")

        print(f"{header} {Fore.WHITE}Time elapsed: {duration:.1f}s{Style.RESET_ALL}")
        return is_success, duration


async def run_menu_1():
    while True:
        raw = input(f"{Fore.CYAN}Berapa akun yang ingin dibuat? {Style.RESET_ALL}").strip()
        if raw.isdigit() and int(raw) > 0:
            count = int(raw)
            break
        print(f"{Fore.RED}Masukkan angka positif!{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}>> Starting creation of {count} account(s)...{Style.RESET_ALL}\n")
    success_count = 0
    durations = []

    for i in range(1, count + 1):
        ok, dur = await register_one_account(i, count)
        durations.append(dur)
        if ok: success_count += 1
        print()

    total_time = sum(durations)
    print(f"\n{Fore.CYAN}{'=' * 50}")
    print(f"  {Fore.WHITE}COMPLETED! Success: {Fore.GREEN}{success_count}{Fore.WHITE}/{count}")
    print(f"  {Fore.WHITE}Total time  : {total_time:.1f}s")
    print(f"  {Fore.WHITE}Output file : {Fore.YELLOW}{SUCCESS_FILE}")
    print(f"{Fore.CYAN}{'=' * 50}{Style.RESET_ALL}\n")


# ================= MENU 2: REFRESH TOKEN =================
def run_menu_2():
    print(f"\n{Fore.CYAN}>> Membaca data dari {SUCCESS_FILE}...{Style.RESET_ALL}")
    try:
        with open(SUCCESS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"{Fore.RED}[!] File {SUCCESS_FILE} belum ada.{Style.RESET_ALL}")
        return

    new_lines = []
    success_refresh = 0

    for line in lines:
        parts = line.strip().split("|")
        if len(parts) >= 5:
            email, pwd, acc_token, ref_token, expires = parts[:5]
            if ref_token:
                print(f"{Fore.YELLOW}[*] Refreshing token untuk: {email}{Style.RESET_ALL}")
                new_tok = refresh_oauth_token(ref_token)
                if new_tok:
                    acc_token = new_tok.get("access_token", acc_token)
                    ref_token = new_tok.get("refresh_token", ref_token)
                    exp_in = new_tok.get("expires_in", 21600)
                    expires = datetime.fromtimestamp(time.time() + exp_in, timezone.utc).isoformat().replace("+00:00", "Z")
                    print(f"  {Fore.GREEN}[OK] Berhasil mendapatkan token baru!{Style.RESET_ALL}")
                    success_refresh += 1
                else:
                    print(f"  {Fore.RED}[!] Gagal merefresh token.{Style.RESET_ALL}")
            new_lines.append(f"{email}|{pwd}|{acc_token}|{ref_token}|{expires}\n")
        else:
            new_lines.append(line)

    with open(SUCCESS_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print(f"\n{Fore.CYAN}>> Proses Refresh Selesai. ({success_refresh} akun diupdate){Style.RESET_ALL}\n")


# ================= MENU 3: MANUAL INJECT TO 9ROUTER =================
def run_menu_3():
    print(f"\n{Fore.CYAN}>> Membaca data dari {SUCCESS_FILE} untuk di-inject ke 9router...{Style.RESET_ALL}")
    try:
        with open(SUCCESS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"{Fore.RED}[!] File {SUCCESS_FILE} belum ada.{Style.RESET_ALL}")
        return

    for line in lines:
        parts = line.strip().split("|")
        if len(parts) >= 5:
            email, pwd, acc_token, ref_token, expires = parts[:5]
            if acc_token and ref_token:
                print(f"{Fore.YELLOW}[*] Mengecek akun: {email}{Style.RESET_ALL}")
                sync_to_9router(email, acc_token, ref_token, expires, skip_if_exists=True)
            else:
                print(f"  {Fore.RED}[!] {email} tidak memiliki access/refresh token lengkap.{Style.RESET_ALL}")
        else:
            print(f"  {Fore.YELLOW}[-] Baris tidak memiliki format token yang lengkap, di-skip.{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}>> Proses Inject Selesai.{Style.RESET_ALL}\n")


# ================= MAIN MENU =================
async def main():
    while True:
        print_banner()
        print(f" {Fore.WHITE}1. Create - Get Token - Inject 9router (Full Auto){Style.RESET_ALL}")
        print(f" {Fore.WHITE}2. Get/Refresh Token (via sukses.txt){Style.RESET_ALL}")
        print(f" {Fore.WHITE}3. Manual Inject to 9router DB (via sukses.txt){Style.RESET_ALL}")
        print(f" {Fore.RED}0. Exit{Style.RESET_ALL}")
        
        choice = input(f"\n{Fore.CYAN}Pilih Menu (0-3): {Style.RESET_ALL}").strip()
        
        if choice == "1":
            await run_menu_1()
        elif choice == "2":
            run_menu_2()
        elif choice == "3":
            run_menu_3()
        elif choice == "0":
            print(f"{Fore.GREEN}Terima kasih! Exiting...{Style.RESET_ALL}")
            break
        else:
            print(f"{Fore.RED}Pilihan tidak valid!{Style.RESET_ALL}\n")

if __name__ == "__main__":
    asyncio.run(main())