import asyncio
import json
import re
import time
import sqlite3
import uuid
import urllib.request
import urllib.parse
import ssl
from typing import Optional, Dict
from datetime import datetime, timezone
from pathlib import Path
from colorama import Fore, Style, init
from fake_useragent import UserAgent
from camoufox.async_api import AsyncCamoufox

init(autoreset=True)

# ================= KONFIGURASI KIMI =================
KIMI_BASE_URL = "https://www.kimi.com"
KIMI_LOGIN_URL = "https://www.kimi.com/login"
SUCCESS_FILE = "kimi_sukses.txt"
AKUN_FILE = "akun_kimi.txt"
NINEROUTER_DB = Path.home() / ".9router" / "db" / "data.sqlite"

# Selector dari HTML yang diberikan
GOOGLE_LOGIN_SELECTOR = "div.google-login-btn"

def _get_ua():
    try:
        return UserAgent().random
    except:
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def print_banner():
    banner = f"""
{Fore.CYAN}+--------------------------------------------------+
|  Kimi Auto Injector - Full Automation        |
|    (Login → Extract → Inject to 9Router)       |
+--------------------------------------------------+
| GitHub : https://github.com/okky-x0f           |
|                                                  |
|   * Real Token Extraction & Auto Injection *   |
+--------------------------------------------------+{Style.RESET_ALL}
"""
    print(banner)

def load_accounts():
    """Load accounts from akun_kimi.txt"""
    try:
        with open(AKUN_FILE, "r", encoding="utf-8") as f:
            accounts = []
            for line in f:
                line = line.strip()
                if line and "|" in line:
                    email, password = line.split("|", 1)
                    accounts.append({
                        "email": email.strip(),
                        "password": password.strip()
                    })
            return accounts
    except FileNotFoundError:
        print(f"{Fore.RED}[!] File {AKUN_FILE} tidak ditemukan!{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}  Buat file {AKUN_FILE} dengan format: email|password{Style.RESET_ALL}")
        return []

def save_success(email, token_data):
    """Save successful login with proper format"""
    access_token = token_data.get("accessToken", "")
    refresh_token = token_data.get("refreshToken", "")
    expires_at = token_data.get("expiresAt", "")
    
    line = f"{email}|{access_token}|{refresh_token}|{expires_at}\n"
    
    with open(SUCCESS_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    
    print(f"  {Fore.GREEN}[OK] Saved to {SUCCESS_FILE}{Style.RESET_ALL}")
    
    # Backup full token data as JSON
    backup_file = f"kimi_backup_{email.replace('@', '_').replace('.', '_')}.json"
    try:
        # Remove non-serializable items
        backup_data = {k: v for k, v in token_data.items() if isinstance(v, (str, int, float, bool, type(None)))}
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2)
        print(f"  [DEBUG] Full data backup: {backup_file}")
    except Exception as e:
        print(f"  [DEBUG] Backup failed: {e}")

def remove_account(email):
    """Remove processed account from akun_kimi.txt"""
    accounts = load_accounts()
    accounts = [acc for acc in accounts if acc["email"] != email]
    
    with open(AKUN_FILE, "w", encoding="utf-8") as f:
        for acc in accounts:
            f.write(f"{acc['email']}|{acc['password']}\n")
    
    print(f"  {Fore.YELLOW}[OK] {email} removed from {AKUN_FILE}{Style.RESET_ALL}")

def sync_to_9router(email, token_data, provider="kimi"):
    """Inject token to 9Router database with proper format"""
    if not NINEROUTER_DB.is_file():
        print(f"  {Fore.RED}[!] 9Router DB not found at: {NINEROUTER_DB}{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}  Make sure 9Router is installed{Style.RESET_ALL}")
        return False
    
    # Validate token data
    access_token = token_data.get("accessToken", "")
    refresh_token = token_data.get("refreshToken", "")
    
    if not access_token:
        print(f"  {Fore.RED}[!] No access token to sync!{Style.RESET_ALL}")
        return False
    
    if len(access_token) < 10:
        print(f"  {Fore.RED}[!] Access token too short ({len(access_token)} chars){Style.RESET_ALL}")
        return False
    
    try:
        conn = sqlite3.connect(str(NINEROUTER_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Check existing connection
        cur.execute(
            "SELECT id, data FROM providerConnections WHERE provider = ? AND (email = ? OR name = ?) LIMIT 1",
            (provider, email, email)
        )
        row = cur.fetchone()
        
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Prepare data with correct camelCase format for 9Router
        data_to_save = {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresAt": token_data.get("expiresAt", ""),
            "testStatus": "active",
            "errorCode": None,
            "lastRefreshAt": now,
            "clientId": token_data.get("clientId", ""),
            "tokenType": token_data.get("tokenType", "Bearer"),
            "source": token_data.get("source", ""),
        }
        
        if row:
            # Update existing connection
            conn_id = row["id"]
            
            # Merge with old data if needed
            try:
                old_data = json.loads(row["data"])
                # Keep old refresh token if new one is empty
                if not refresh_token and old_data.get("refreshToken"):
                    data_to_save["refreshToken"] = old_data["refreshToken"]
                # Keep old clientId if new one is empty
                if not data_to_save["clientId"] and old_data.get("clientId"):
                    data_to_save["clientId"] = old_data["clientId"]
            except:
                pass
            
            cur.execute(
                "UPDATE providerConnections SET data = ?, updatedAt = ?, isActive = 1 WHERE id = ?",
                (json.dumps(data_to_save), now, conn_id)
            )
            print(f"  {Fore.GREEN}[OK] Updated existing 9Router connection{Style.RESET_ALL}")
            
        else:
            # Insert new connection
            conn_id = str(uuid.uuid4())
            
            cur.execute(
                """INSERT INTO providerConnections 
                (id, provider, name, email, data, isActive, createdAt, updatedAt, authType) 
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, 'oauth2')""",
                (
                    conn_id, 
                    provider, 
                    email, 
                    email, 
                    json.dumps(data_to_save), 
                    now, 
                    now
                )
            )
            print(f"  {Fore.GREEN}[OK] Inserted new connection to 9Router{Style.RESET_ALL}")
        
        conn.commit()
        
        # Verify data was saved correctly
        cur.execute("SELECT data FROM providerConnections WHERE id = ?", (conn_id,))
        saved = cur.fetchone()
        if saved:
            saved_data = json.loads(saved["data"])
            if saved_data.get("accessToken"):
                print(f"  {Fore.GREEN}[OK] Verified: Token saved correctly ({len(saved_data['accessToken'])} chars){Style.RESET_ALL}")
            else:
                print(f"  {Fore.RED}[!] Warning: Token may not be saved correctly{Style.RESET_ALL}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"  {Fore.RED}[!] 9Router Sync Error: {type(e).__name__}: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        return False

class KimiGoogleAuth:
    """Handle Kimi login via Google OAuth with popup support"""
    
    def __init__(self, headless=True):
        self.headless = headless
        self.browser = None
        self.page = None
        self.popup_page = None
    
    async def safe_goto(self, url, wait_until="domcontentloaded", timeout=30000, retries=3):
        """Safe navigation with retry logic"""
        for attempt in range(retries):
            try:
                await self.page.goto(url, wait_until=wait_until, timeout=timeout)
                await asyncio.sleep(2)
                return True
            except Exception as e:
                if attempt < retries - 1:
                    print(f"    Retry {attempt + 1}/{retries}: {str(e)[:50]}")
                    await asyncio.sleep(2)
                else:
                    print(f"    {Fore.RED}Failed after {retries} retries{Style.RESET_ALL}")
                    return False
        return False
    
    async def click_google_login(self):
        """Click Google login button and handle popup window"""
        print("  [*] Looking for Google login button...")
        
        try:
            # Wait for the Google login button
            google_btn = await self.page.wait_for_selector(
                GOOGLE_LOGIN_SELECTOR,
                state="visible",
                timeout=10000
            )
            
            if google_btn:
                btn_text = await google_btn.inner_text()
                print(f"  [OK] Found button: '{btn_text.strip()}'")
                
                # Setup popup listener and click
                async with self.page.expect_popup() as popup_info:
                    await google_btn.click()
                    print("  [OK] Clicked Google login, waiting for popup...")
                
                # Get the popup page
                self.popup_page = await popup_info.value
                
                if self.popup_page:
                    print(f"  [OK] Popup window detected!")
                    
                    # Wait for popup to load
                    try:
                        await self.popup_page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except:
                        pass
                    
                    await asyncio.sleep(2)
                    
                    popup_url = self.popup_page.url
                    print(f"  Popup URL: {popup_url[:100]}")
                    
                    if "accounts.google.com" in popup_url:
                        # Switch to popup for Google OAuth
                        self.page = self.popup_page
                        return True
                    else:
                        print(f"  [!] Popup URL not Google: {popup_url[:60]}")
                        return False
                else:
                    print(f"  [!] No popup detected")
                    
                    # Check if current page redirected to Google
                    current_url = self.page.url
                    if "accounts.google.com" in current_url:
                        print("  [OK] Redirected to Google (no popup)")
                        return True
                    
                    return False
            
            else:
                print(f"  {Fore.RED}[!] Google login button not found{Style.RESET_ALL}")
                return False
            
        except Exception as e:
            print(f"  {Fore.RED}[!] Error: {type(e).__name__}: {str(e)[:80]}{Style.RESET_ALL}")
            
            # Check if popup was created despite error
            if hasattr(self, 'popup_page') and self.popup_page:
                try:
                    if "accounts.google.com" in self.popup_page.url:
                        print("  [OK] Popup exists despite error")
                        self.page = self.popup_page
                        return True
                except:
                    pass
            
            return False
    
    async def handle_google_oauth(self, email, password):
        """Handle Google OAuth login flow in popup"""
        print(f"  [*] Google OAuth for: {email}")
        
        try:
            # Step 1: Email input
            print("  [*] Step 1: Entering email...")
            
            email_input = None
            email_selectors = [
                "input[type='email']",
                "input#identifierId",
                "input[name='identifier']",
                "input[aria-label*='email' i]",
                "input[aria-label*='Email' i]",
            ]
            
            for selector in email_selectors:
                try:
                    email_input = await self.page.wait_for_selector(
                        selector,
                        state="visible",
                        timeout=5000
                    )
                    if email_input:
                        print(f"  [OK] Email input found: {selector}")
                        break
                except:
                    continue
            
            if not email_input:
                # Debug: show page content
                print(f"  {Fore.RED}[!] Email input not found{Style.RESET_ALL}")
                try:
                    text = await self.page.evaluate("() => document.body.innerText")
                    print(f"  [DEBUG] Page text: {text[:300]}")
                except:
                    pass
                return False
            
            # Clear and fill email
            await email_input.click(click_count=3)
            await asyncio.sleep(0.3)
            await email_input.fill(email)
            await asyncio.sleep(1)
            
            # Click Next button
            next_clicked = await self.page.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        const text = btn.textContent.trim().toLowerCase();
                        if (text === 'next' || text === 'berikutnya' || text === 'lanjut') {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            
            if not next_clicked:
                print("  [*] Next button not found by text, trying alternatives...")
                try:
                    # Try common Google selectors
                    for selector in [
                        "#identifierNext",
                        "button[jsname='LgbsSe']",
                        "button:has(span:has-text('Next'))",
                    ]:
                        try:
                            next_btn = await self.page.wait_for_selector(selector, timeout=3000)
                            if next_btn:
                                await next_btn.click()
                                next_clicked = True
                                break
                        except:
                            continue
                except:
                    pass
                
                if not next_clicked:
                    await self.page.keyboard.press("Enter")
            
            await asyncio.sleep(3)
            
            # Step 2: Password input
            print("  [*] Step 2: Entering password...")
            
            pass_input = None
            pass_selectors = [
                "input[type='password']",
                "input[name='Passwd']",
                "input[name='password']",
                "input[aria-label*='password' i]",
            ]
            
            for selector in pass_selectors:
                try:
                    pass_input = await self.page.wait_for_selector(
                        selector,
                        state="visible",
                        timeout=5000
                    )
                    if pass_input:
                        print(f"  [OK] Password input found: {selector}")
                        break
                except:
                    continue
            
            if not pass_input:
                # Check if already logged in (session exists)
                current_url = self.page.url
                if "challenge" in current_url or "consent" in current_url:
                    print("  [*] Password skipped (existing session)")
                else:
                    print(f"  {Fore.RED}[!] Password input not found{Style.RESET_ALL}")
                    try:
                        text = await self.page.evaluate("() => document.body.innerText")
                        print(f"  [DEBUG] Page text: {text[:300]}")
                    except:
                        pass
                    return False
            else:
                await asyncio.sleep(1)
                await pass_input.fill(password)
                await asyncio.sleep(1)
                
                # Click Next
                await self.page.evaluate("""
                    () => {
                        const buttons = document.querySelectorAll('button');
                        for (const btn of buttons) {
                            const text = btn.textContent.trim().toLowerCase();
                            if (text === 'next' || text === 'berikutnya' || text === 'lanjut') {
                                btn.click();
                                return;
                            }
                        }
                    }
                """)
                
                await asyncio.sleep(3)
            
            # Step 3: Handle consent/verification screens
            print("  [*] Step 3: Handling consent screens...")
            
            # Check for 2FA/Verification
            try:
                page_text = await self.page.evaluate("() => document.body.innerText")
                
                if "verify" in page_text.lower():
                    if "phone" in page_text.lower() or "2-step" in page_text.lower() or "recovery" in page_text.lower():
                        print(f"  {Fore.RED}[!] 2FA/Verification required! Cannot automate.{Style.RESET_ALL}")
                        return False
            except:
                pass
            
            # Click consent/continue buttons
            consent_selectors = [
                "button:has-text('Continue')",
                "button:has-text('Allow')",
                "button:has-text('Lanjutkan')",
                "button:has-text('Izinkan')",
                "button:has-text('Accept')",
                "button:has-text('Setuju')",
                "button:has-text('Confirm')",
            ]
            
            for selector in consent_selectors:
                try:
                    consent_btn = await self.page.wait_for_selector(
                        selector,
                        state="visible",
                        timeout=3000
                    )
                    if consent_btn:
                        text = await consent_btn.inner_text()
                        print(f"  [OK] Clicking: '{text.strip()}'")
                        await consent_btn.click()
                        await asyncio.sleep(2)
                except:
                    continue
            
            # Step 4: Wait for OAuth completion
            print("  [*] Step 4: Waiting for OAuth completion...")
            
            max_wait = 30
            for i in range(max_wait):
                try:
                    # Check if popup closed (success)
                    if self.page.is_closed():
                        print(f"  [OK] Popup closed after {i}s (OAuth complete)")
                        return "popup_closed"
                    
                    # Check for errors
                    page_text = await self.page.evaluate("() => document.body.innerText")
                    
                    if "incorrect password" in page_text.lower() or "wrong password" in page_text.lower():
                        print(f"  {Fore.RED}[!] Wrong password!{Style.RESET_ALL}")
                        return False
                    
                    if "verify" in page_text.lower() and ("phone" in page_text.lower() or "2-step" in page_text.lower()):
                        print(f"  {Fore.RED}[!] 2FA required!{Style.RESET_ALL}")
                        return False
                    
                except:
                    # Page might be closed (success)
                    if i > 5:
                        print(f"  [OK] Popup appears closed (success)")
                        return "popup_closed"
                
                await asyncio.sleep(1)
            
            print(f"  {Fore.YELLOW}[!] Timeout waiting for OAuth, assuming success{Style.RESET_ALL}")
            return True
            
        except Exception as e:
            print(f"  {Fore.RED}[!] Google OAuth error: {type(e).__name__}: {str(e)[:100]}{Style.RESET_ALL}")
            
            # Check if popup closed (might be success)
            try:
                if self.page and self.page.is_closed():
                    print("  [OK] Popup closed (likely success)")
                    return "popup_closed"
            except:
                pass
            
            return False
    
    async def wait_for_kimi_after_oauth(self, original_page):
        """After Google popup closes, wait for Kimi to update"""
        print("  [*] Waiting for Kimi to update after OAuth...")
        
        # Switch back to original Kimi page
        self.page = original_page
        
        # Wait for page to reflect logged-in state
        max_wait = 30
        for i in range(max_wait):
            try:
                # Check URL
                current_url = self.page.url
                
                # Check for logged-in indicators
                is_logged_in = await self.page.evaluate("""
                    () => {
                        // Check for user avatar/menu
                        const avatar = document.querySelector(
                            'img[alt*="avatar" i], [class*="avatar"], [class*="user"], [class*="profile"]'
                        );
                        if (avatar) return true;
                        
                        // Check if login button is gone
                        const loginBtn = document.querySelector('div.google-login-btn');
                        if (!loginBtn) return true;
                        
                        // Check for chat/new chat elements
                        const chatElements = document.querySelector(
                            'textarea, [contenteditable="true"], [class*="chat"], [class*="conversation"]'
                        );
                        if (chatElements && !loginBtn) return true;
                        
                        return false;
                    }
                """)
                
                if is_logged_in:
                    print(f"  [OK] Kimi shows logged-in state after {i}s!")
                    return True
                
                if "login" not in current_url.lower() and "auth" not in current_url.lower():
                    print(f"  [*] URL changed from login: {current_url[:80]}")
                    await asyncio.sleep(2)
                    return True
                
            except Exception as e:
                pass
            
            # Refresh page periodically
            if i == 10 or i == 20:
                print(f"  [*] Refreshing page...")
                try:
                    await self.page.reload()
                    await asyncio.sleep(3)
                except:
                    pass
            
            await asyncio.sleep(1)
        
        # Final check
        try:
            current_url = self.page.url
            if "login" not in current_url.lower():
                print("  [OK] Not on login page, assuming success")
                return True
        except:
            pass
        
        print(f"  {Fore.YELLOW}[WARN] Cannot confirm login state{Style.RESET_ALL}")
        return False
    
    async def extract_tokens(self):
        """Extract tokens with proper format for 9Router"""
        print("  [*] Extracting tokens...")
        
        token_data = {
            "accessToken": "",       # CamelCase for 9Router
            "refreshToken": "",      # CamelCase for 9Router
            "expiresAt": "",         # CamelCase for 9Router
            "tokenType": "Bearer",
            "testStatus": "active",
            "errorCode": None,
            "lastRefreshAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "clientId": "",
            "source": "",
            "extracted_at": datetime.now(timezone.utc).isoformat()
        }
        
        tokens_found = False
        
        # Method 1: localStorage (primary source)
        try:
            storage = await self.page.evaluate("""
                () => {
                    const data = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        try {
                            const value = localStorage.getItem(key);
                            data[key] = value;
                        } catch(e) {}
                    }
                    return data;
                }
            """)
            
            print(f"  [DEBUG] localStorage keys ({len(storage)}): {list(storage.keys())}")
            
            for key, value in storage.items():
                if not value or len(value) < 10:
                    continue
                
                print(f"  [DEBUG] Checking: {key} ({len(value)} chars)")
                
                # Try parsing as JSON
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        # Check various possible field names
                        access = (parsed.get("access_token") or 
                                 parsed.get("accessToken") or 
                                 parsed.get("token") or 
                                 parsed.get("jwt") or
                                 parsed.get("id_token") or
                                 parsed.get("auth_token"))
                        
                        refresh = (parsed.get("refresh_token") or 
                                  parsed.get("refreshToken") or
                                  parsed.get("refresh"))
                        
                        expires = (parsed.get("expires_at") or 
                                  parsed.get("expiresAt") or 
                                  parsed.get("expires_in") or
                                  parsed.get("expiry"))
                        
                        if access:
                            token_data["accessToken"] = access
                            token_data["source"] = f"localStorage:{key}"
                            tokens_found = True
                            print(f"  [OK] Access token found in {key} ({len(access)} chars)")
                        
                        if refresh:
                            token_data["refreshToken"] = refresh
                            print(f"  [OK] Refresh token found in {key}")
                        
                        if expires:
                            if isinstance(expires, (int, float)) and expires < 10000000000:
                                # Unix timestamp
                                if expires > 1000000000:  # Milliseconds
                                    expires = expires / 1000
                                expires_dt = datetime.fromtimestamp(expires, timezone.utc)
                                token_data["expiresAt"] = expires_dt.isoformat().replace("+00:00", "Z")
                            else:
                                token_data["expiresAt"] = str(expires)
                        
                        if access:
                            break
                except:
                    pass
                
                # Check for JWT pattern
                if not tokens_found and len(value) > 50 and value.count('.') >= 2:
                    if value.startswith("eyJ"):
                        token_data["accessToken"] = value
                        token_data["source"] = f"localStorage:{key}"
                        tokens_found = True
                        print(f"  [OK] JWT token found in {key}")
                        break
                
                # Check by key name
                if not tokens_found:
                    key_lower = key.lower()
                    if any(term in key_lower for term in ["token", "auth", "session", "access", "bearer"]):
                        if len(value) > 20:
                            token_data["accessToken"] = value
                            token_data["source"] = f"localStorage:{key}"
                            tokens_found = True
                            print(f"  [OK] Token by key name: {key}")
                            break
                
        except Exception as e:
            print(f"  [!] localStorage error: {type(e).__name__}: {e}")
        
        # Method 2: Cookies
        if not tokens_found:
            print("  [*] Trying cookies...")
            try:
                cookies = await self.page.context.cookies()
                print(f"  [DEBUG] Found {len(cookies)} cookies")
                
                for cookie in cookies:
                    name_lower = cookie["name"].lower()
                    value = cookie["value"]
                    
                    if value and len(value) > 20:
                        # Check for token-related cookies
                        if any(term in name_lower for term in ["token", "auth", "session", "jwt", "access", "bearer"]):
                            token_data["accessToken"] = value
                            token_data["source"] = f"cookie:{cookie['name']}"
                            tokens_found = True
                            print(f"  [OK] Token from cookie: {cookie['name']}")
                            break
                        
                        # Check if value is JWT
                        if value.startswith("eyJ") and value.count('.') >= 2:
                            token_data["accessToken"] = value
                            token_data["source"] = f"cookie:{cookie['name']}"
                            tokens_found = True
                            print(f"  [OK] JWT from cookie: {cookie['name']}")
                            break
                        
            except Exception as e:
                print(f"  [!] Cookie error: {e}")
        
        # Method 3: sessionStorage
        if not tokens_found:
            print("  [*] Trying sessionStorage...")
            try:
                session = await self.page.evaluate("""
                    () => {
                        const data = {};
                        for (let i = 0; i < sessionStorage.length; i++) {
                            const key = sessionStorage.key(i);
                            data[key] = sessionStorage.getItem(key);
                        }
                        return data;
                    }
                """)
                
                print(f"  [DEBUG] sessionStorage keys: {list(session.keys())}")
                
                for key, value in session.items():
                    if value and len(value) > 20:
                        key_lower = key.lower()
                        if any(term in key_lower for term in ["token", "auth", "access", "bearer"]):
                            token_data["accessToken"] = value
                            token_data["source"] = f"sessionStorage:{key}"
                            tokens_found = True
                            print(f"  [OK] Token from sessionStorage: {key}")
                            break
                        
                        # Check JWT
                        if value.startswith("eyJ") and value.count('.') >= 2:
                            token_data["accessToken"] = value
                            token_data["source"] = f"sessionStorage:{key}"
                            tokens_found = True
                            print(f"  [OK] JWT from sessionStorage: {key}")
                            break
            except:
                pass
        
        # Method 4: Try to find refresh token
        if tokens_found and not token_data["refreshToken"]:
            print("  [*] Looking for refresh token...")
            try:
                # Check all storage again for refresh token
                all_storage = await self.page.evaluate("""
                    () => {
                        const results = {};
                        
                        // Check localStorage
                        for (let i = 0; i < localStorage.length; i++) {
                            const key = localStorage.key(i);
                            if (key.toLowerCase().includes('refresh')) {
                                results['local_' + key] = localStorage.getItem(key);
                            }
                        }
                        
                        // Check sessionStorage
                        for (let i = 0; i < sessionStorage.length; i++) {
                            const key = sessionStorage.key(i);
                            if (key.toLowerCase().includes('refresh')) {
                                results['session_' + key] = sessionStorage.getItem(key);
                            }
                        }
                        
                        return results;
                    }
                """)
                
                for key, value in all_storage.items():
                    if value and len(value) > 20:
                        # Could be JSON
                        try:
                            parsed = json.loads(value)
                            if isinstance(parsed, dict) and "refresh_token" in parsed:
                                token_data["refreshToken"] = parsed["refresh_token"]
                                print(f"  [OK] Refresh token from {key}")
                                break
                        except:
                            token_data["refreshToken"] = value
                            print(f"  [OK] Refresh token from {key}")
                            break
            except:
                pass
        
        # Set defaults
        if tokens_found:
            if not token_data["expiresAt"]:
                # Default 7 days from now
                expires = datetime.fromtimestamp(
                    time.time() + 604800,
                    timezone.utc
                ).isoformat().replace("+00:00", "Z")
                token_data["expiresAt"] = expires
            
            print(f"\n  {Fore.GREEN}[OK] Token extraction successful!{Style.RESET_ALL}")
            print(f"  Access Token: {token_data['accessToken'][:50]}...")
            if token_data["refreshToken"]:
                print(f"  Refresh Token: {token_data['refreshToken'][:50]}...")
        else:
            print(f"\n  {Fore.RED}[!] No tokens found!{Style.RESET_ALL}")
            # Save screenshot for debugging
            try:
                await self.page.screenshot(path="debug_kimi_no_token.png")
                print(f"  [DEBUG] Screenshot saved: debug_kimi_no_token.png")
            except:
                pass
        
        return token_data
    
    async def login(self, email, password):
        """Main login flow for Kimi with Google OAuth"""
        print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📧 Processing: {email}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        
        async with AsyncCamoufox(
            headless=self.headless,
            disable_coop=True,
            i_know_what_im_doing=True,
            humanize=False,
            os="windows",
            config={"forceScopeAccess": True}
        ) as browser:
            
            self.browser = browser
            self.page = await browser.new_page()
            
            # Set viewport
            await self.page.set_viewport_size({"width": 1280, "height": 1024})
            
            try:
                # Step 1: Go to Kimi login page
                print("\n📍 Step 1: Opening Kimi Login...")
                await self.safe_goto(KIMI_LOGIN_URL)
                await asyncio.sleep(3)
                
                # Save reference to original page
                original_page = self.page
                
                # Step 2: Click Google Login (handles popup)
                print("\n📍 Step 2: Clicking Google Login...")
                popup_success = await self.click_google_login()
                
                if not popup_success:
                    print(f"  {Fore.RED}[!] Failed to open Google login{Style.RESET_ALL}")
                    return None
                
                # Step 3: Google OAuth in popup
                print("\n📍 Step 3: Google OAuth...")
                oauth_result = await self.handle_google_oauth(email, password)
                
                if oauth_result == False:
                    print(f"  {Fore.RED}[!] Google OAuth failed{Style.RESET_ALL}")
                    return None
                
                # Step 4: Switch back to Kimi and wait for update
                print("\n📍 Step 4: Returning to Kimi...")
                kimi_ready = await self.wait_for_kimi_after_oauth(original_page)
                
                if not kimi_ready:
                    print(f"  {Fore.YELLOW}[WARN] Kimi may not be fully loaded{Style.RESET_ALL}")
                
                # Step 5: Extract tokens
                print("\n📍 Step 5: Extracting tokens...")
                await asyncio.sleep(3)
                token_data = await self.extract_tokens()
                
                if token_data and token_data.get("accessToken"):
                    print(f"\n{Fore.GREEN}{'='*50}{Style.RESET_ALL}")
                    print(f"{Fore.GREEN}[SUCCESS] {email}{Style.RESET_ALL}")
                    print(f"{Fore.GREEN}{'='*50}{Style.RESET_ALL}")
                    return token_data
                else:
                    print(f"\n{Fore.YELLOW}[PARTIAL] Login OK but no tokens extracted{Style.RESET_ALL}")
                    return token_data  # Return whatever we have
                
            except Exception as e:
                print(f"  {Fore.RED}[!] Unexpected error: {type(e).__name__}: {e}{Style.RESET_ALL}")
                import traceback
                traceback.print_exc()
                return None

async def process_accounts(headless=False):
    """Process all accounts from akun_kimi.txt"""
    accounts = load_accounts()
    
    if not accounts:
        print(f"{Fore.RED}[!] No accounts found in {AKUN_FILE}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}  Create {AKUN_FILE} with format: email@gmail.com|password{Style.RESET_ALL}")
        return
    
    print(f"\n{Fore.CYAN}📋 {len(accounts)} accounts loaded{Style.RESET_ALL}")
    for i, acc in enumerate(accounts, 1):
        print(f"  {i}. {acc['email']}")
    print()
    
    auth = KimiGoogleAuth(headless=headless)
    success_count = 0
    fail_count = 0
    
    for i, account in enumerate(accounts, 1):
        print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}[{i}/{len(accounts)}] Processing...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        
        token_data = await auth.login(account["email"], account["password"])
        
        if token_data and token_data.get("accessToken"):
            # Save to success file
            save_success(account["email"], token_data)
            
            # Sync to 9Router
            sync_to_9router(account["email"], token_data, provider="kimi")
            
            # Remove from account list
            remove_account(account["email"])
            
            success_count += 1
        else:
            print(f"\n  {Fore.RED}[FAILED] {account['email']}{Style.RESET_ALL}")
            fail_count += 1
            
            # Ask if want to continue
            if i < len(accounts):
                print(f"\n  {Fore.YELLOW}Continue with next account? (y/n){Style.RESET_ALL}")
                try:
                    choice = input("  > ").strip().lower()
                    if choice == 'n':
                        break
                except:
                    pass
        
        # Delay between accounts
        if i < len(accounts):
            wait_time = 5
            print(f"\n  {Fore.CYAN}Waiting {wait_time}s before next account...{Style.RESET_ALL}")
            await asyncio.sleep(wait_time)
    
    print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}✅ COMPLETED!{Style.RESET_ALL}")
    print(f"  Success: {Fore.GREEN}{success_count}{Style.RESET_ALL}")
    print(f"  Failed:  {Fore.RED}{fail_count}{Style.RESET_ALL}")
    print(f"  Total:   {len(accounts)}")
    print(f"  Output:  {SUCCESS_FILE}")
    print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}\n")

async def main():
    """Main menu"""
    print_banner()
    
    while True:
        print(f"\n{Fore.WHITE}╔══════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.WHITE}║{Style.RESET_ALL}  {Fore.CYAN}KIMI AI - Google OAuth Login{Style.RESET_ALL}    {Fore.WHITE}║{Style.RESET_ALL}")
        print(f"{Fore.WHITE}╠══════════════════════════════════════╣{Style.RESET_ALL}")
        print(f"{Fore.WHITE}║{Style.RESET_ALL}  1. {Fore.GREEN}Login (Visible Browser){Style.RESET_ALL}       {Fore.WHITE}║{Style.RESET_ALL}")
        print(f"{Fore.WHITE}║{Style.RESET_ALL}  2. {Fore.GREEN}Login (Headless/Background){Style.RESET_ALL}   {Fore.WHITE}║{Style.RESET_ALL}")
        print(f"{Fore.WHITE}║{Style.RESET_ALL}  3. {Fore.YELLOW}Test Single Account{Style.RESET_ALL}           {Fore.WHITE}║{Style.RESET_ALL}")
        print(f"{Fore.WHITE}║{Style.RESET_ALL}  0. {Fore.RED}Exit{Style.RESET_ALL}                          {Fore.WHITE}║{Style.RESET_ALL}")
        print(f"{Fore.WHITE}╚══════════════════════════════════════╝{Style.RESET_ALL}")
        
        choice = input(f"\n{Fore.YELLOW}Pilih menu (0-3): {Style.RESET_ALL}").strip()
        
        if choice == "1":
            await process_accounts(headless=False)
        elif choice == "2":
            await process_accounts(headless=True)
        elif choice == "3":
            # Test single account
            print(f"\n{Fore.CYAN}Test Single Account{Style.RESET_ALL}")
            email = input(f"  Email: ").strip()
            password = input(f"  Password: ").strip()
            
            if email and password:
                auth = KimiGoogleAuth(headless=False)
                token_data = await auth.login(email, password)
                
                if token_data:
                    print(f"\n{Fore.GREEN}Token Data:{Style.RESET_ALL}")
                    print(f"  Access Token: {token_data.get('accessToken', 'N/A')[:80]}...")
                    print(f"  Refresh Token: {token_data.get('refreshToken', 'N/A')[:80]}...")
                    print(f"  Source: {token_data.get('source', 'N/A')}")
                    
                    save = input(f"\n  {Fore.YELLOW}Save & sync to 9Router? (y/n): {Style.RESET_ALL}")
                    if save.lower() == 'y':
                        save_success(email, token_data)
                        sync_to_9router(email, token_data, provider="kimi")
            else:
                print(f"{Fore.RED}Email dan password diperlukan!{Style.RESET_ALL}")
                
        elif choice == "0":
            print(f"\n{Fore.GREEN}Goodbye! 👋{Style.RESET_ALL}")
            break
        else:
            print(f"{Fore.RED}Pilihan tidak valid!{Style.RESET_ALL}")

if __name__ == "__main__":
    asyncio.run(main())