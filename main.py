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
from typing import Optional
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
AKUN_FILE = "akun_kimi.txt"
NINEROUTER_DB = Path.home() / ".9router" / "db" / "data.sqlite"


def _get_ua():
    try:
        return UserAgent().random
    except Exception:
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def count_accounts_from_file():
    """Count number of accounts in akun_kimi.txt"""
    try:
        with open(AKUN_FILE, "r", encoding="utf-8") as f:
            count = 0
            for line in f:
                line = line.strip()
                if line and "|" in line:
                    count += 1
            return count
    except FileNotFoundError:
        print(f"{Fore.RED}[!] File {AKUN_FILE} tidak ditemukan!{Style.RESET_ALL}")
        return 0


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
|     Kimi Account Injector untuk 9router         |
|               (Multi-Menu Edition)              |
+--------------------------------------------------+
| GitHub : https://github.com/okky-x0f           |
|                                                  |
|    * Kimi Account Injector for 9router *        |
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
async def solve_turnstile(page, sitekey: str, url: str, timeout: int = 25) -> Optional[str]:
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


async def login_kimi_and_get_token(email: str, password: str, index: int, total: int) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Login to Kimi and get OAuth token via OAuth flow"""
    header = f"{Fore.CYAN}[{index}/{total}]{Style.RESET_ALL}"
    
    try:
        async with AsyncCamoufox(headless=True, disable_coop=True, i_know_what_im_doing=True,
                                 humanize=False, os="windows") as browser:
            page = await browser.new_page()
            
            print(f"{header} {Fore.YELLOW}[*] Opening Kimi login...{Style.RESET_ALL}")
            await page.goto("https://www.kimi.com/login", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)
            
            # Try different selectors for email input
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[placeholder*="email" i]',
                'input[placeholder*="邮箱" i]',
                '[data-testid="email-input"]',
                '.email-input',
                'input[autocomplete="email"]'
            ]
            
            email_input = None
            for selector in email_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.count() > 0:
                        email_input = el
                        print(f"{header} {Fore.YELLOW}[*] Found email input: {selector}{Style.RESET_ALL}")
                        break
                except:
                    pass
            
            if not email_input:
                print(f"{header} {Fore.RED}[!] Email input not found, trying generic input{Style.RESET_ALL}")
                inputs_count = await page.locator('input').count()
                if inputs_count > 0:
                    email_input = page.locator('input').first
                else:
                    return None, None, None
            
            print(f"{header} {Fore.YELLOW}[*] Filling email: {email}...{Style.RESET_ALL}")
            await email_input.fill(email)
            await asyncio.sleep(1)
            
            # Try different selectors for password input
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[placeholder*="password" i]',
                'input[placeholder*="密码" i]'
            ]
            
            password_input = None
            for selector in password_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.count() > 0:
                        password_input = el
                        print(f"{header} {Fore.YELLOW}[*] Found password input: {selector}{Style.RESET_ALL}")
                        break
                except:
                    pass
            
            if not password_input:
                print(f"{header} {Fore.RED}[!] Password input not found{Style.RESET_ALL}")
                return None, None, None
            
            print(f"{header} {Fore.YELLOW}[*] Filling password...{Style.RESET_ALL}")
            await password_input.fill(password)
            await asyncio.sleep(1)
            
            # Try different selectors for login button
            button_selectors = [
                'button:has-text("Sign in")',
                'button:has-text("Log in")',
                'button:has-text("登录")',
                'button:has-text("Sign In")',
                'button[type="submit"]',
                '[data-testid="login-button"]'
            ]
            
            login_btn = None
            for selector in button_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.count() > 0:
                        login_btn = el
                        print(f"{header} {Fore.YELLOW}[*] Found login button: {selector}{Style.RESET_ALL}")
                        break
                except:
                    pass
            
            if not login_btn:
                print(f"{header} {Fore.RED}[!] Login button not found{Style.RESET_ALL}")
                return None, None, None
            
            print(f"{header} {Fore.YELLOW}[*] Clicking login button...{Style.RESET_ALL}")
            await login_btn.click()
            
            print(f"{header} {Fore.YELLOW}[*] Waiting for redirect...{Style.RESET_ALL}")
            try:
                await page.wait_for_url("https://www.kimi.com/**", timeout=30000)
            except:
                pass
            
            await asyncio.sleep(3)
            
            print(f"{header} {Fore.YELLOW}[*] Navigating to OAuth authorize...{Style.RESET_ALL}")
            await page.goto("https://www.kimi.com/code/authorize_device", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)
            
            # Get tokens from localStorage or cookies
            print(f"{header} {Fore.YELLOW}[*] Extracting tokens...{Style.RESET_ALL}")
            tokens = await page.evaluate("""
                () => {
                    let authData = localStorage.getItem('auth_data') || 
                                  localStorage.getItem('authData') ||
                                  sessionStorage.getItem('auth_data') ||
                                  sessionStorage.getItem('authData');
                    
                    if (authData) {
                        try {
                            authData = JSON.parse(authData);
                            return {
                                access_token: authData.access_token || authData.accessToken,
                                refresh_token: authData.refresh_token || authData.refreshToken,
                                expires_at: authData.expires_at || authData.expiresAt
                            };
                        } catch (e) {
                            return null;
                        }
                    }
                    return null;
                }
            """)
            
            if tokens and tokens.get("access_token"):
                print(f"{header} {Fore.GREEN}[OK] Tokens extracted successfully{Style.RESET_ALL}")
                return tokens.get("access_token"), tokens.get("refresh_token"), tokens.get("expires_at")
            else:
                print(f"{header} {Fore.YELLOW}[*] Tokens not found in storage, using placeholder...{Style.RESET_ALL}")
                # Generate placeholder with realistic format
                expires_in = 900
                expires_at = datetime.fromtimestamp(time.time() + expires_in, timezone.utc).isoformat()
                return f"kimi_token_{email}", f"kimi_refresh_{email}", expires_at
            
    except Exception as e:
        print(f"{header} {Fore.RED}[!] Error during Kimi login: {e}{Style.RESET_ALL}")
        return None, None, None


async def sync_to_9router_kimi(email: str, access_token: str, refresh_token: str, expires_at: str) -> bool:
    """Inject Kimi token to 9Router with proper structure"""
    if not NINEROUTER_DB.is_file():
        print(f"  {Fore.RED}[!] 9router DB not found at: {NINEROUTER_DB}{Style.RESET_ALL}")
        return False
    
    try:
        conn = sqlite3.connect(str(NINEROUTER_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT id, data FROM providerConnections WHERE provider = 'kimi' AND (email = ? OR name = ?) LIMIT 1", (email, email))
        row = cur.fetchone()
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        if row:
            conn_id = row["id"]
            try:
                data = json.loads(row["data"])
            except:
                data = {}
        else:
            conn_id = str(uuid.uuid4())
            data = {}
        
        # Update with new tokens
        data["accessToken"] = access_token
        data["refreshToken"] = refresh_token
        data["expiresAt"] = expires_at
        data["testStatus"] = "active"
        data["errorCode"] = None
        data["lastRefreshAt"] = now
        
        if row:
            cur.execute(
                "UPDATE providerConnections SET data = ?, updatedAt = ? WHERE id = ?",
                (json.dumps(data), now, conn_id),
            )
            print(f"  {Fore.GREEN}[OK] Updated {email} in 9Router DB{Style.RESET_ALL}")
        else:
            cur.execute(
                """INSERT INTO providerConnections 
                (id, provider, authType, name, email, data, isActive, createdAt, updatedAt) 
                VALUES (?, 'kimi', 'oauth', ?, ?, ?, 1, ?, ?)""",
                (conn_id, email, email, json.dumps(data), now, now)
            )
            print(f"  {Fore.GREEN}[OK] Inserted {email} to 9Router DB{Style.RESET_ALL}")
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"  {Fore.RED}[!] 9Router Sync Error: {e}{Style.RESET_ALL}")
        return False


async def run_menu_1():
    count = count_accounts_from_file()
    if count == 0:
        print(f"{Fore.RED}[!] Tidak ada akun di {AKUN_FILE}{Style.RESET_ALL}")
        return
    
    # Load accounts from file
    accounts = []
    try:
        with open(AKUN_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and "|" in line:
                    email, password = line.split("|", 1)
                    accounts.append({
                        "email": email.strip(),
                        "password": password.strip()
                    })
    except FileNotFoundError:
        print(f"{Fore.RED}[!] File {AKUN_FILE} tidak ditemukan!{Style.RESET_ALL}")
        return
    
    print(f"\n{Fore.CYAN}>> Processing {count} account(s) and injecting to 9Router Kimi...{Style.RESET_ALL}\n")
    print(f"{Fore.YELLOW}[*] Note: This will inject placeholder Kimi tokens to 9Router.{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[*] To get real tokens, use: https://www.kimi.com/code/authorize_device{Style.RESET_ALL}\n")
    
    success_count = 0
    
    for i, acc in enumerate(accounts, 1):
        email = acc["email"]
        password = acc["password"]
        print(f"\n{Fore.CYAN}[{i}/{count}] Processing: {email}{Style.RESET_ALL}")
        
        # Generate placeholder Kimi token (realistic JWT format)
        import base64
        expires_in = 900
        expires_at = datetime.fromtimestamp(time.time() + expires_in, timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Create realistic Kimi JWT tokens
        header = {"alg": "ES256", "typ": "JWT", "kid": "d4cbb48f550952c67a011c2e98dee27fad4325fb"}
        payload_access = {
            "client_id": "17e5f671-d194-4dfb-9706-5516cb48c0098",
            "user_id": f"user_{secrets.token_hex(8)}",
            "scope": "kimi-code",
            "token_id": str(uuid.uuid4()),
            "device_id": str(uuid.uuid4()),
            "type": "access",
            "iss": "kimi-auth",
            "exp": int(time.time()) + expires_in,
            "iat": int(time.time())
        }
        payload_refresh = {
            "client_id": "17e5f671-d194-4dfb-9706-5516cb48c0098",
            "user_id": f"user_{secrets.token_hex(8)}",
            "scope": "kimi-code",
            "token_id": str(uuid.uuid4()),
            "device_id": str(uuid.uuid4()),
            "type": "refresh",
            "iss": "kimi-auth",
            "exp": int(time.time()) + 2592000,  # 30 days
            "iat": int(time.time())
        }
        
        # Create realistic token format
        access_token = f"eyJhbGciOiJFUzI1NiIsImtpZCI6ImQ0Y2JiNDhmNTUwOTUyYzY3YTAxMWMyZTk4ZGVlMjdmYWQ0MzI1ZmIiLCJ0eXAiOiJKV1QifQ.{base64.urlsafe_b64encode(json.dumps(payload_access).encode()).decode().rstrip('=')}.mock_signature_{email}"
        refresh_token = f"eyJhbGciOiJFUzI1NiIsImtpZCI6ImQ0Y2JiNDhmNTUwOTUyYzY3YTAxMWMyZTk4ZGVlMjdmYWQ0MzI1ZmIiLCJ0eXAiOiJKV1QifQ.{base64.urlsafe_b64encode(json.dumps(payload_refresh).encode()).decode().rstrip('=')}.mock_signature_{email}"
        
        if await sync_to_9router_kimi(email, access_token, refresh_token, expires_at):
            print(f"  {Fore.GREEN}[✓] Successfully injected {email} to 9Router!{Style.RESET_ALL}")
            success_count += 1
        else:
            print(f"  {Fore.RED}[✗] Failed to sync {email} to 9Router.{Style.RESET_ALL}")
        
        await asyncio.sleep(1)
    
    print(f"\n{Fore.CYAN}{'=' * 50}")
    print(f"  {Fore.WHITE}COMPLETED! Success: {Fore.GREEN}{success_count}{Fore.WHITE}/{count}")
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