from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import json
import asyncio
from typing import Dict
import logging
import os
from DrissionPage import ChromiumOptions


class SessionExpiredException(Exception):
    """Custom exception for session expiration detection"""
    pass


class SessionManager(ABC):
    """Abstract base class for platform session management"""
    
    def __init__(self, platform: str, config: Dict):
        self.platform = platform
        self.config = config
        self.logger = logging.getLogger(f"SessionManager.{platform}")
        self.session_data = self._load_session_data()
    
    @abstractmethod
    async def check_session_health(self) -> bool:
        """Check if current session is valid"""
        pass
    
    @abstractmethod
    async def renew_session(self) -> bool:
        """Perform automatic session renewal"""
        pass
    
    @abstractmethod
    async def get_browser_options(self, headless: bool = False) -> ChromiumOptions:
        """Get platform-specific browser configuration"""
        pass
    
    def _load_session_data(self) -> Dict:
        """Load session metadata (last renewal, expiry estimates)"""
        try:
            session_file = f"sessions/{self.platform}_session.json"
            if os.path.exists(session_file):
                with open(session_file, 'r') as f:
                    return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.warning(f"Could not load session data: {e}")
        
        return {"last_renewal": None, "estimated_expiry": None}
    
    def _save_session_data(self):
        """Save session metadata"""
        session_file = f"sessions/{self.platform}_session.json"
        os.makedirs(os.path.dirname(session_file), exist_ok=True)
        with open(session_file, 'w') as f:
            json.dump(self.session_data, f, indent=2)  # type: ignore[arg-type]


class XhsSessionManager(SessionManager):
    """XHS-specific session management implementation"""
    
    def __init__(self, config: Dict):
        super().__init__("xhs", config)
        self.cookie_path = config["cookie_path"]
        self.profile_path = f"profiles/xhs_profile"
    
    async def check_session_health(self) -> bool:
        """Check session validity by examining cookie expiry and age"""
        try:
            # Check if cookie file exists and is recent
            if not os.path.exists(self.cookie_path):
                self.logger.warning("No cookies file found")
                return False
            
            # Check file modification time - XHS sessions typically last ~14 days
            cookie_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(self.cookie_path))
            if cookie_age > timedelta(days=10):  # Conservative threshold
                self.logger.warning(f"Cookies are {cookie_age.days} days old - likely expired")
                return False
            
            # Check session metadata if available
            if self.session_data.get("estimated_expiry"):
                try:
                    expiry = datetime.fromisoformat(self.session_data["estimated_expiry"])
                    if datetime.now() > expiry:
                        self.logger.warning("Session has passed estimated expiry")
                        return False
                except ValueError:
                    pass  # Ignore invalid date format
            
            self.logger.info("Session appears healthy based on age and metadata")
            return True
                
        except Exception as e:
            self.logger.error(f"Session health check failed: {e}")
            return False
    
    async def renew_session(self) -> bool:
        """Automated session renewal process"""
        try:
            from DrissionPage import Chromium
            
            self.logger.info("Starting automated session renewal")
            
            # Launch browser with fresh session
            co = await self.get_browser_options(headless=False)
            browser = Chromium(co)
            tab = browser.latest_tab
            
            # Navigate to login page
            tab.get("https://www.xiaohongshu.com/explore")
            
            # Give the page time to fully load before starting monitoring
            await asyncio.sleep(3)
            
            # Wait for manual login (with timeout and user feedback)
            self.logger.info("=" * 60)
            self.logger.info("🚀 BROWSER OPENED FOR LOGIN")
            self.logger.info("=" * 60)
            self.logger.info("📋 Please complete these steps:")
            self.logger.info("1. 📱 Click the QR code button if available")
            self.logger.info("2. 📱 Scan the QR code with your mobile XHS app")
            self.logger.info("3. ✅ Complete login on your mobile device") 
            self.logger.info("4. ⏳ Wait for redirect to explore or creator page")
            self.logger.info("5. 🤖 System will automatically detect login and extract cookies")
            self.logger.info("6. ⚠️  DO NOT close the browser - it will close automatically")
            self.logger.info("=" * 60)
            print("🚀 BROWSER OPENED - Please log in to XHS using QR code...")
            print("📱 Look for the QR code button and scan with your mobile XHS app")
            print("⏳ System will wait patiently for up to 5 minutes...")
            print("💡 TIP: The page will NOT refresh automatically - you have full control")
            
            # Monitor for successful login with better feedback
            login_success = await self._wait_for_login(tab, timeout=300)  # 5 minutes
            
            if login_success:
                # Extract and save cookies
                cookies = tab.cookies()
                self._save_cookies(cookies)
                
                # Update session metadata
                self.session_data["last_renewal"] = datetime.now().isoformat()
                self.session_data["estimated_expiry"] = (
                    datetime.now() + timedelta(days=14)
                ).isoformat()
                self._save_session_data()
                
                self.logger.info("Session renewal completed successfully")
                browser.quit()
                return True
            else:
                self.logger.error("Session renewal failed - login timeout")
                browser.quit()
                return False
                
        except Exception as e:
            self.logger.error(f"Session renewal failed: {e}")
            return False
    
    async def get_browser_options(self, headless: bool = False) -> ChromiumOptions:
        """Get XHS-optimized browser configuration"""
        from utils.chromium_utils import get_chromium_options
        
        co = get_chromium_options(headless=headless)

        # Add persistent profile
        co.set_argument(f'--user-data-dir={self.profile_path}')
        
        # Mobile user agent for longer session life
        mobile_ua = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
            "XiaoHongShu/7.98.1 (iPhone; iOS 15.0; Scale/3.00)"
        )
        co.set_argument(f'--user-agent={mobile_ua}')
        
        # Additional session persistence options
        co.set_argument('--disable-web-security')
        co.set_argument('--disable-features=VizDisplayCompositor')
        
        return co
    
    async def _wait_for_login(self, tab, timeout: int = 300) -> bool:
        """Wait for user to complete login process"""
        start_time = datetime.now()
        last_feedback = start_time
        
        self.logger.info(f"⏳ Waiting for login... (timeout: {timeout//60} minutes)")
        self.logger.info("💡 TIP: If you see a QR code button, click it and scan with your mobile XHS app")
        
        while (datetime.now() - start_time).seconds < timeout:
            try:
                # Provide periodic feedback but less frequently
                current_time = datetime.now()
                if (current_time - last_feedback).seconds >= 30:  # Every 30 seconds
                    elapsed = (current_time - start_time).seconds
                    remaining = timeout - elapsed
                    self.logger.info(f"⏳ Still waiting for login... ({remaining}s remaining)")
                    print(f"⏳ Still waiting for login... ({remaining}s remaining)")
                    last_feedback = current_time
                
                # Get current URL without navigating away
                current_url = tab.url
                self.logger.debug(f"Current URL: {current_url}")
                
                # Check if we're on a success/logged-in page
                # Look for indicators that login was successful
                if any(indicator in current_url.lower() for indicator in ["explore", "creator", "home", "feed"]):
                    self.logger.info("✅ Login success detected - verifying upload access...")
                    print("✅ Login success detected - verifying upload access...")
                    
                    # Only navigate to upload page AFTER login is confirmed
                    try:
                        tab.get(self.config["up_site"])
                        upload_input = tab.ele('tag:input@@class=upload-input', timeout=8)
                        if upload_input:
                            self.logger.info("🎉 Login successful - upload access confirmed!")
                            print("🎉 Login successful - upload access confirmed!")
                            return True
                        else:
                            # Try a few more times before giving up
                            for retry in range(3):
                                await asyncio.sleep(3)
                                upload_input = tab.ele('tag:input@@class=upload-input', timeout=5)
                                if upload_input:
                                    self.logger.info("🎉 Login successful - upload access confirmed!")
                                    print("🎉 Login successful - upload access confirmed!")
                                    return True
                                self.logger.debug(f"Upload input retry {retry + 1}/3")
                            
                            # If still no upload access, login was successful but upload page has issues
                            self.logger.warning("⚠️  Login successful but upload page not accessible")
                            print("⚠️  Login successful but upload page not accessible - proceeding anyway")
                            return True  # Return success since login worked
                    except Exception as e:
                        self.logger.debug(f"Upload verification error: {e}")
                        await asyncio.sleep(5)
                        continue
                
                # Sleep longer to avoid interfering with user interactions
                await asyncio.sleep(5)  # Increased from 2 to 5 seconds
                
            except Exception as e:
                self.logger.debug(f"Login check error (normal): {e}")
                await asyncio.sleep(5)  # Increased from 2 to 5 seconds
                continue
        
        self.logger.error("❌ Login timeout - manual login was not completed in time")
        print("❌ Login timeout - manual login was not completed in time")
        return False
    
    def _load_and_set_cookies(self, tab):
        """Load cookies from file and apply to browser tab"""
        try:
            with open(self.cookie_path, 'r') as file:
                storage_state = json.load(file)
                cookies = storage_state.get('cookies', [])
            tab.set.cookies(cookies)
        except Exception as e:
            self.logger.error(f"Failed to load cookies: {e}")
    
    def _save_cookies(self, cookies):
        """Save cookies to storage file"""
        storage_state = {"cookies": cookies}
        os.makedirs(os.path.dirname(self.cookie_path), exist_ok=True)
        with open(self.cookie_path, 'w') as file:
            json.dump(storage_state, file, indent=2)  # type: ignore[arg-type]

