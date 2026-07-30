#!/usr/bin/env python3
"""
Kimi Account Injector - Full Automation
Login → Extract Real Token → Inject to 9Router

All-in-one script untuk menginjeksi akun Kimi ke 9Router database
dengan otomatis melakukan login Google OAuth dan extract token real.
"""

import asyncio
import json
import sqlite3
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path
from colorama import Fore, Style, init

try:
    from camoufox.async_api import AsyncCamoufox
except ImportError:
    print(f"{Fore.RED}[!] Camoufox not found. Install: pip install camoufox{Style.RESET_ALL}")
    exit(1)

init(autoreset=True)

# ================= CONFIGURATION =================
AKUN_FILE = "akun_kimi.txt"
NINEROUTER_DB = Path.home() / ".9router" / "db" / "data.sqlite"
KIMI_AUTH_URL = "https://www.kimi.com/code/authorize_device"

def load_accounts():
    """Load accounts from akun_kimi.txt (format: email|password)"""
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
        return []

def print_banner():
    """Print banner"""
    banner = f"""
{Fore.CYAN}+--------------------------------------------------+
|    Kimi Auto Injector - Full Automation        |
|    (Login → Extract → Inject to 9Router)       |
+--------------------------------------------------+
| GitHub : https://github.com/okky-x0f           |
|                                                  |
|   * Real Token Extraction & Auto Injection *   |
+--------------------------------------------------+{Style.RESET_ALL}
"""
    print(banner)

async def wait_for_app_loaded(page, timeout=30):
    """Wait for React app to load"""
    try:
        await asyncio.wait_for(
            page.wait_for_selector(".loading, #loading-wrapper, [class*='loading']", state="hidden"),
            timeout=5
        )
    except:
        pass
    
    await asyncio.sleep(2)

async def find_and_click_google_button(page):
    """Find and click Google login button"""
    print(f"  {Fore.YELLOW}[*] Looking for Google login button...{Style.RESET_ALL}")
    
    try:
        button = page.locator('div.google-login-btn')
        if await button.count() > 0:
            await button.first.click()
            print(f"  {Fore.GREEN}[✓] Clicked Google button{Style.RESET_ALL}")
            await asyncio.sleep(3)
            return True
    except:
        pass
    
    # Fallback: search for button with text
    try:
        buttons = page.locator("button, a")
        count = await buttons.count()
        for i in range(count):
            btn = buttons.nth(i)
            try:
                text = (await btn.text_content() or "").lower()
                if "google" in text:
                    await btn.click()
                    print(f"  {Fore.GREEN}[✓] Clicked Google button (fallback){Style.RESET_ALL}")
                    await asyncio.sleep(3)
                    return True
            except:
                pass
    except:
        pass
    
    print(f"  {Fore.RED}[✗] Google button not found{Style.RESET_ALL}")
    return False

async def handle_google_login(page, email, password):
    """Handle Google OAuth login flow - properly click Next buttons after email and password"""
    print(f"  {Fore.YELLOW}[*] Logging in with Google...{Style.RESET_ALL}")
    
    await asyncio.sleep(3)
    
    try:
        # Step 1: Fill Email
        print(f"  {Fore.YELLOW}[*] Step 1: Filling email...{Style.RESET_ALL}")
        email_input = page.locator("input[type='email'], input[id='identifierId']").first
        
        if await email_input.count() > 0:
            await email_input.click()
            await asyncio.sleep(0.5)
            await email_input.fill(email)
            await asyncio.sleep(1)
            print(f"  {Fore.GREEN}[✓] Email filled: {email}{Style.RESET_ALL}")
            
            # Click Next button after email
            buttons = await page.query_selector_all("button")
            for btn in buttons:
                try:
                    text = await btn.text_content()
                    if text and ("next" in text.lower() or "berikutnya" in text.lower()):
                        print(f"  {Fore.YELLOW}[*] Clicking Next button...{Style.RESET_ALL}")
                        await btn.click()
                        await asyncio.sleep(3)
                        break
                except:
                    pass
        
        # Step 2: Fill Password
        print(f"  {Fore.YELLOW}[*] Step 2: Filling password...{Style.RESET_ALL}")
        pass_input = page.locator("input[type='password'], input[name='Passwd']").first
        
        if await pass_input.count() > 0:
            await pass_input.click()
            await asyncio.sleep(0.5)
            await pass_input.fill(password)
            await asyncio.sleep(1)
            print(f"  {Fore.GREEN}[✓] Password filled{Style.RESET_ALL}")
            
            # Click Next button after password
            buttons = await page.query_selector_all("button")
            for btn in buttons:
                try:
                    text = await btn.text_content()
                    if text and ("next" in text.lower() or "berikutnya" in text.lower()):
                        print(f"  {Fore.YELLOW}[*] Clicking Next button...{Style.RESET_ALL}")
                        await btn.click()
                        await asyncio.sleep(3)
                        break
                except:
                    pass
        
        # Step 3: Handle Consent/Allow screen
        print(f"  {Fore.YELLOW}[*] Step 3: Handling consent screen...{Style.RESET_ALL}")
        await asyncio.sleep(2)
        
        consent_buttons = page.locator("button:has-text('Continue'), button:has-text('Allow'), button:has-text('Lanjutkan'), button:has-text('确认')")
        if await consent_buttons.count() > 0:
            print(f"  {Fore.YELLOW}[*] Clicking consent button...{Style.RESET_ALL}")
            await consent_buttons.first.click()
            await asyncio.sleep(3)
        
    except Exception as e:
        print(f"  {Fore.YELLOW}[!] Google login step error: {str(e)[:80]}{Style.RESET_ALL}")
    
    # Wait for redirect back to Kimi
    print(f"  {Fore.YELLOW}[*] Waiting for redirect to Kimi...{Style.RESET_ALL}")
    for i in range(60):
        try:
            current_url = page.url
            
            if "kimi.com" in current_url and "accounts.google" not in current_url and "auth" not in current_url.lower():
                print(f"  {Fore.GREEN}[✓] Redirected to Kimi!{Style.RESET_ALL}")
                await asyncio.sleep(2)
                return True
        except:
            pass
        
        await asyncio.sleep(1)
    
    print(f"  {Fore.YELLOW}[!] Redirect timeout (may still be logged in){Style.RESET_ALL}")
    return False

async def extract_tokens_comprehensive(page):
    """Extract tokens from localStorage - Kimi stores them directly as 'access_token' and 'refresh_token'"""
    print(f"  {Fore.YELLOW}[*] Extracting tokens from localStorage...{Style.RESET_ALL}")
    
    try:
        result = await page.evaluate("""
            () => {
                // Kimi stores tokens directly in localStorage with these exact keys
                const access_token = localStorage.getItem('access_token');
                const refresh_token = localStorage.getItem('refresh_token');
                
                if (access_token && access_token.length > 50) {
                    return {
                        found: true,
                        access_token: access_token,
                        refresh_token: refresh_token || '',
                        expires_in: 900
                    };
                }
                
                return { found: false };
            }
        """)
        
        if result.get("found") and result.get("access_token"):
            print(f"  {Fore.GREEN}[✓] Access token extracted! ({len(result['access_token'])} chars){Style.RESET_ALL}")
            if result.get("refresh_token"):
                print(f"  {Fore.GREEN}[✓] Refresh token extracted! ({len(result['refresh_token'])} chars){Style.RESET_ALL}")
            return result
        else:
            print(f"  {Fore.RED}[✗] Tokens not found in localStorage{Style.RESET_ALL}")
    except Exception as e:
        print(f"  {Fore.RED}[!] Extract error: {str(e)[:100]}{Style.RESET_ALL}")
    
    return None

def inject_token_to_9router(email, access_token, refresh_token, expires_at):
    """Inject token to 9Router database"""
    if not NINEROUTER_DB.is_file():
        print(f"  {Fore.RED}[!] 9Router DB not found{Style.RESET_ALL}")
        return False
    
    try:
        conn = sqlite3.connect(str(NINEROUTER_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Check if exists
        cur.execute(
            "SELECT id, data FROM providerConnections WHERE provider = 'kimi' AND email = ? LIMIT 1",
            (email,)
        )
        row = cur.fetchone()
        
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
            
            cur.execute(
                "UPDATE providerConnections SET data = ?, updatedAt = ? WHERE id = ?",
                (json.dumps(data), now, conn_id)
            )
            print(f"  {Fore.GREEN}[✓] Updated: {email}{Style.RESET_ALL}")
        else:
            conn_id = str(uuid.uuid4())
            data = {
                "accessToken": access_token,
                "refreshToken": refresh_token,
                "expiresAt": expires_at,
                "testStatus": "active"
            }
            cur.execute(
                """INSERT INTO providerConnections 
                (id, provider, authType, name, email, data, isActive, createdAt, updatedAt) 
                VALUES (?, 'kimi', 'oauth', ?, ?, ?, 1, ?, ?)""",
                (conn_id, email, email, json.dumps(data), now, now)
            )
            print(f"  {Fore.GREEN}[✓] Inserted: {email}{Style.RESET_ALL}")
        
        conn.commit()
        conn.close()
        return True
    
    except Exception as e:
        print(f"  {Fore.RED}[!] DB error: {str(e)[:80]}{Style.RESET_ALL}")
        return False

async def process_account(page, email, password, index, total):
    """Process account"""
    header = f"{Fore.CYAN}[{index}/{total}]{Style.RESET_ALL}"
    
    try:
        print(f"{header} {Fore.YELLOW}[1/4] Opening page...{Style.RESET_ALL}")
        try:
            await page.goto(KIMI_AUTH_URL, wait_until="domcontentloaded")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"{header} {Fore.RED}[✗] Failed: {str(e)[:50]}{Style.RESET_ALL}")
            return False
        
        await wait_for_app_loaded(page)
        
        print(f"{header} {Fore.YELLOW}[2/4] Google login...{Style.RESET_ALL}")
        if not await find_and_click_google_button(page):
            return False
        
        print(f"{header} {Fore.YELLOW}[3/4] Authenticating...{Style.RESET_ALL}")
        await handle_google_login(page, email, password)
        
        # CRITICAL: Wait for tokens to be set in localStorage
        print(f"{header} {Fore.YELLOW}[*] Waiting for tokens to be stored...{Style.RESET_ALL}")
        token_found = False
        for attempt in range(30):  # Try for 30 seconds
            try:
                has_token = await page.evaluate("""
                    () => {
                        const access_token = localStorage.getItem('access_token');
                        return access_token && access_token.length > 50;
                    }
                """)
                
                if has_token:
                    print(f"{header} {Fore.GREEN}[✓] Tokens detected in storage!{Style.RESET_ALL}")
                    token_found = True
                    break
                
                await asyncio.sleep(1)
            except Exception as e:
                print(f"{header} {Fore.YELLOW}[*] Check attempt {attempt+1}...{Style.RESET_ALL}")
                await asyncio.sleep(1)
        
        if not token_found:
            print(f"{header} {Fore.YELLOW}[!] Tokens not yet in storage, continuing anyway...{Style.RESET_ALL}")
        
        await asyncio.sleep(2)
        
        print(f"{header} {Fore.YELLOW}[4/4] Extracting tokens...{Style.RESET_ALL}")
        
        # Retry token extraction up to 3 times
        tokens = None
        for retry in range(3):
            try:
                tokens = await extract_tokens_comprehensive(page)
                if tokens and tokens.get("access_token"):
                    break
                if retry < 2:
                    print(f"{header} {Fore.YELLOW}[*] Retry {retry+1}...{Style.RESET_ALL}")
                    await asyncio.sleep(2)
            except Exception as e:
                print(f"{header} {Fore.YELLOW}[*] Extract attempt {retry+1} error: {str(e)[:50]}{Style.RESET_ALL}")
                if retry < 2:
                    await asyncio.sleep(2)
        
        if not tokens or not tokens.get("access_token"):
            print(f"{header} {Fore.RED}[✗] No tokens found - may need manual extraction{Style.RESET_ALL}")
            return False
        
        # Calculate expires_at
        expires_at = datetime.fromtimestamp(
            time.time() + tokens.get("expires_in", 900),
            timezone.utc
        ).isoformat()
        
        print(f"{header} {Fore.YELLOW}[*] Injecting to 9Router...{Style.RESET_ALL}")
        if inject_token_to_9router(
            email,
            tokens.get("access_token"),
            tokens.get("refresh_token", ""),
            expires_at
        ):
            print(f"{header} {Fore.GREEN}[✓] COMPLETE!{Style.RESET_ALL}")
            return True
        
        return False
    
    except Exception as e:
        print(f"{header} {Fore.RED}[✗] Process error: {str(e)[:100]}{Style.RESET_ALL}")
        return False

async def main():
    print_banner()
    
    accounts = load_accounts()
    if not accounts:
        print(f"{Fore.RED}[!] No accounts{Style.RESET_ALL}")
        return
    
    print(f"\n{Fore.CYAN}>> Processing {len(accounts)} account(s)...{Style.RESET_ALL}\n")
    print(f"{Fore.YELLOW}[!] Browser will open - complete Google login when prompted{Style.RESET_ALL}\n")
    
    success_count = 0
    failed_count = 0
    
    for i, account in enumerate(accounts, 1):
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"[{i}/{len(accounts)}] {account['email']}")
        print(f"{'='*70}{Style.RESET_ALL}")
        
        try:
            async with AsyncCamoufox(headless=False, disable_coop=True, i_know_what_im_doing=True) as browser:
                page = await browser.new_page()
                
                success = await process_account(page, account["email"], account["password"], i, len(accounts))
                
                if success:
                    success_count += 1
                else:
                    failed_count += 1
                
                await page.close()
        except Exception as e:
            print(f"  {Fore.RED}[✗] Error: {str(e)[:80]}{Style.RESET_ALL}")
            failed_count += 1
        
        if i < len(accounts):
            print(f"\n{Fore.YELLOW}[*] Waiting before next account...{Style.RESET_ALL}")
            await asyncio.sleep(3)
    
    # Summary
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"  {Fore.WHITE}AUTOMATION COMPLETE!{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}Success: {success_count}/{len(accounts)}{Style.RESET_ALL}")
    if failed_count > 0:
        print(f"  {Fore.RED}Failed: {failed_count}/{len(accounts)}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
    
    if success_count > 0:
        print(f"{Fore.GREEN}[✓] Real tokens injected to 9Router!{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[*] Test connection in 9Router now{Style.RESET_ALL}\n")

if __name__ == "__main__":
    asyncio.run(main())
