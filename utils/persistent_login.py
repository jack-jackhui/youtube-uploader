"""
Persistent Login Module for XHS Platform using CDP Cookie Extraction

This module mimics the xiaohongshu-mcp login approach which extracts ALL browser
cookies (including HttpOnly) via Chrome DevTools Protocol, resulting in sessions
that last months instead of ~48 hours.

Key difference from standard DrissionPage cookie extraction:
- Uses CDP Network.getAllCookies to get ALL cookies
- Includes HttpOnly cookies with actual session tokens
- Matches go-rod's page.Browser().GetCookies() behavior
"""

import json
import os
import time
from datetime import datetime
from DrissionPage import Chromium, ChromiumOptions
from utils.chromium_utils import get_chromium_options
from core import config
import logging


class XhsPersistentLogin:
    """
    Persistent login handler using MCP-style CDP cookie extraction.
    
    Usage:
        login = XhsPersistentLogin()
        
        # Check if already logged in
        if login.check_login_status():
            print("Already logged in!")
        else:
            # Perform login (opens browser for QR code scan)
            login.do_login()
    """
    
    # XHS login detection selectors (same as xiaohongshu-mcp)
    LOGIN_SUCCESS_SELECTOR = '.main-container .user .link-wrapper .channel'
    QR_CODE_SELECTOR = '.login-container .qrcode-img'
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.cookie_path = config.xhs_config["cookie_path"]
        self.login_url = "https://www.xiaohongshu.com/explore"
        self.upload_url = config.xhs_config["up_site"]
        
    def do_login(self, timeout_minutes=10):
        """
        Open browser for QR code login, extract ALL cookies using CDP.
        
        This mimics xiaohongshu-mcp's login process:
        1. Navigate to XHS explore page
        2. Wait for user to scan QR code
        3. Extract ALL cookies via CDP (not just JS-accessible ones)
        4. Save cookies with timestamp
        
        Args:
            timeout_minutes: Max time to wait for user login
            
        Returns:
            bool: True if login successful, False otherwise
        """
        self.logger.info("🔐 Starting XHS login process...")
        
        # Non-headless so user can see and scan QR code
        co = get_chromium_options(headless=False, incognito=False)
        browser = Chromium(co)
        tab = browser.latest_tab
        
        try:
            # Navigate to login page
            tab.get(self.login_url)
            self.logger.info("📱 Please scan the QR code to login...")
            
            # Wait for login success indicator (user profile element)
            start_time = time.time()
            timeout_seconds = timeout_minutes * 60
            
            while time.time() - start_time < timeout_seconds:
                try:
                    # Check for logged-in state
                    logged_in_elem = tab.ele(self.LOGIN_SUCCESS_SELECTOR, timeout=5)
                    if logged_in_elem:
                        self.logger.info("✅ Login detected! Extracting cookies...")
                        
                        # MCP-STYLE: Extract ALL cookies via CDP
                        all_cookies = self._extract_all_cookies_cdp(tab)
                        
                        if all_cookies:
                            self._save_cookies(all_cookies)
                            self.logger.info(f"💾 Saved {len(all_cookies)} cookies (CDP extraction)")
                            
                            # Brief pause to let session establish
                            time.sleep(2)
                            return True
                        else:
                            self.logger.warning("⚠️ CDP extraction returned no cookies, trying fallback...")
                            fallback_cookies = tab.cookies(all_domains=True)
                            if fallback_cookies:
                                self._save_cookies(fallback_cookies)
                                self.logger.info(f"💾 Saved {len(fallback_cookies)} cookies (fallback)")
                                return True
                            
                except Exception as e:
                    self.logger.debug(f"Waiting for login... ({e})")
                
                time.sleep(2)
            
            self.logger.error("⏰ Login timeout - QR code not scanned in time")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Login error: {e}")
            return False
            
        finally:
            try:
                browser.quit()
            except:
                pass
    
    def _extract_all_cookies_cdp(self, tab):
        """
        Extract ALL cookies using Chrome DevTools Protocol.
        
        This is the key difference from standard extraction:
        - Uses Network.getAllCookies CDP command
        - Gets HttpOnly cookies (contain actual session tokens)
        - Gets Secure cookies
        - Gets all domain cookies
        
        This matches go-rod's page.Browser().GetCookies() behavior.
        """
        try:
            # CDP command to get ALL cookies from the browser
            result = tab.run_cdp('Network.getAllCookies')
            
            if result and 'cookies' in result:
                cookies = result['cookies']
                self.logger.info(f"📦 CDP extracted {len(cookies)} cookies")
                
                # Log cookie breakdown for debugging
                http_only = sum(1 for c in cookies if c.get('httpOnly', False))
                secure = sum(1 for c in cookies if c.get('secure', False))
                self.logger.debug(f"   HttpOnly: {http_only}, Secure: {secure}")
                
                return cookies
            
            self.logger.warning("CDP Network.getAllCookies returned empty")
            return None
            
        except Exception as e:
            self.logger.error(f"CDP cookie extraction failed: {e}")
            
            # Try alternative CDP command
            try:
                result = tab.run_cdp('Storage.getCookies')
                if result and 'cookies' in result:
                    return result['cookies']
            except:
                pass
            
            return None
    
    def _save_cookies(self, cookies):
        """
        Save cookies with metadata for tracking.
        
        Format matches what the uploader expects while adding
        extraction metadata for debugging.
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.cookie_path), exist_ok=True)
            
            storage = {
                "cookies": cookies,
                "timestamp": datetime.now().isoformat(),
                "extraction_method": "cdp_all_cookies",
                "cookie_count": len(cookies),
                "platform": "xhs"
            }
            
            with open(self.cookie_path, 'w', encoding='utf-8') as f:
                json.dump(storage, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"✅ Cookies saved to: {self.cookie_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save cookies: {e}")
            raise
    
    def check_login_status(self, headless=True):
        """
        Check if current saved cookies are valid.
        
        Args:
            headless: Run browser in headless mode
            
        Returns:
            bool: True if logged in, False otherwise
        """
        cookies = self._load_cookies()
        if not cookies:
            self.logger.info("No cookies found")
            return False
        
        self.logger.info(f"Checking login status with {len(cookies)} cookies...")
        
        co = get_chromium_options(headless=headless)
        browser = Chromium(co)
        tab = browser.latest_tab
        
        try:
            # Apply saved cookies
            tab.set.cookies(cookies)
            
            # Navigate to check login status
            tab.get(self.login_url)
            tab.wait(3)
            
            # Check for logged-in indicator
            logged_in_elem = tab.ele(self.LOGIN_SUCCESS_SELECTOR, timeout=10)
            
            if logged_in_elem:
                self.logger.info("✅ Login status: VALID")
                return True
            else:
                self.logger.info("❌ Login status: EXPIRED or INVALID")
                return False
                
        except Exception as e:
            self.logger.error(f"Login check error: {e}")
            return False
            
        finally:
            try:
                browser.quit()
            except:
                pass
    
    def _load_cookies(self):
        """Load cookies from saved file."""
        try:
            if not os.path.exists(self.cookie_path):
                return None
                
            with open(self.cookie_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both formats
            if isinstance(data, dict):
                cookies = data.get('cookies', [])
                timestamp = data.get('timestamp', 'unknown')
                self.logger.debug(f"Loaded cookies from {timestamp}")
                return cookies
            elif isinstance(data, list):
                return data
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to load cookies: {e}")
            return None
    
    def get_cookie_info(self):
        """Get information about saved cookies."""
        try:
            if not os.path.exists(self.cookie_path):
                return {"exists": False}
            
            with open(self.cookie_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict):
                cookies = data.get('cookies', [])
                return {
                    "exists": True,
                    "count": len(cookies),
                    "timestamp": data.get('timestamp'),
                    "extraction_method": data.get('extraction_method', 'unknown'),
                    "http_only_count": sum(1 for c in cookies if c.get('httpOnly', False)),
                    "secure_count": sum(1 for c in cookies if c.get('secure', False))
                }
            elif isinstance(data, list):
                return {
                    "exists": True,
                    "count": len(data),
                    "timestamp": None,
                    "extraction_method": "legacy"
                }
            
            return {"exists": False}
            
        except Exception as e:
            return {"exists": False, "error": str(e)}


# Standalone usage
if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description="XHS Persistent Login Tool")
    parser.add_argument('--check', action='store_true', help="Check login status only")
    parser.add_argument('--info', action='store_true', help="Show cookie info")
    parser.add_argument('--timeout', type=int, default=10, help="Login timeout in minutes")
    args = parser.parse_args()
    
    login = XhsPersistentLogin()
    
    if args.info:
        info = login.get_cookie_info()
        print(json.dumps(info, indent=2, default=str))
    elif args.check:
        status = login.check_login_status()
        print(f"Login status: {'✅ Valid' if status else '❌ Invalid/Expired'}")
    else:
        # Check first
        if login.check_login_status():
            print("✅ Already logged in! No action needed.")
        else:
            print("🔐 Starting login process...")
            if login.do_login(timeout_minutes=args.timeout):
                print("✅ Login successful! Cookies saved.")
            else:
                print("❌ Login failed or timed out.")
