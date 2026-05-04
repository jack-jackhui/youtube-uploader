# import asyncio
import json
import time
# from playwright.async_api import async_playwright
from DrissionPage import Chromium, ChromiumOptions
# import random
from core import config
from core.upload import Upload
from utils.util_sqlite import excute_sqlite_sql
from datetime import datetime
import os
from utils.chromium_utils import get_chromium_options, check_chromium_running, kill_chromium_processes
from utils.persistent_login import XhsPersistentLogin


class XhsUploader(Upload):
    """
    XHS (Xiaohongshu) Video Uploader using DrissionPage with persistent login.
    
    Features:
    1. Pre-flight login check before upload
    2. CDP-based cookie extraction for long-lasting sessions (months, not hours)
    3. Automatic cookie loading and validation
    
    Upload steps:
    1. Video name  2. Video description  3. Add topics  4. Select collection
    On success, records to SQLite database.
    
    Selectors updated 2026-05-04 based on xiaohongshu-mcp (xpzouying/xiaohongshu-mcp).
    """
    platform = "xhs"

    def _wait_for_publish_button_ready(self, tab, timeout=600):
        """
        Wait for the publish button to be clickable (not disabled).
        This is the MCP server's approach - wait for video processing to complete
        by checking if the publish button becomes enabled.
        
        Args:
            tab: DrissionPage tab
            timeout: Maximum wait time in seconds (default 10 minutes for video processing)
        
        Returns:
            The publish button element if found and enabled, None otherwise
        """
        start = time.time()
        interval = 2  # Check every 2 seconds
        
        self.logger.info(f"{self.platform}: Waiting for publish button to become ready (timeout={timeout}s)...")
        
        last_log = 0
        while time.time() - start < timeout:
            elapsed = int(time.time() - start)
            
            # Find the publish button by iterating through all buttons
            # The selector 'button@@text()=发布' doesn't work reliably in headless mode
            try:
                all_buttons = tab.eles('tag:button', timeout=3)
                publish_btn = None
                
                for btn in all_buttons:
                    btn_text = btn.text or ''
                    if '发布' in btn_text and '暂存' not in btn_text:  # "发布" but not "暂存离开"
                        publish_btn = btn
                        break
                
                if publish_btn:
                    # Get the full class attribute
                    class_attr = publish_btn.attr('class') or ''
                    
                    # Check if button is ready (has bg-red class)
                    if 'bg-red' in class_attr:
                        self.logger.info(f"{self.platform}: ✅ Publish button is ready! (after {elapsed}s)")
                        return publish_btn
                    elif 'white' in class_attr:
                        # Still processing
                        if elapsed - last_log >= 30:
                            self.logger.info(f"{self.platform}: Video processing... button has 'white' class ({elapsed}s elapsed)")
                            last_log = elapsed
                    else:
                        # Button found with different state - might be ready anyway
                        # Check if it's clickable (not disabled)
                        disabled = publish_btn.attr('disabled')
                        if disabled is None:
                            # No disabled attribute and no white class - assume ready
                            self.logger.info(f"{self.platform}: ✅ Publish button ready (class: {class_attr[:80]}) (after {elapsed}s)")
                            return publish_btn
                        else:
                            if elapsed - last_log >= 30:
                                self.logger.info(f"{self.platform}: Button found but disabled ({elapsed}s elapsed)")
                                last_log = elapsed
                else:
                    if elapsed - last_log >= 30:
                        self.logger.info(f"{self.platform}: Waiting for publish button... found {len(all_buttons)} buttons ({elapsed}s elapsed)")
                        last_log = elapsed
            except Exception as e:
                if elapsed - last_log >= 30:
                    self.logger.warning(f"{self.platform}: Error finding button: {e} ({elapsed}s elapsed)")
                    last_log = elapsed
            
            time.sleep(interval)
        
        self.logger.error(f"{self.platform}: Timeout waiting for publish button to become ready")
        return None

    def _find_title_input(self, tab):
        """
        Find title input using multiple selector strategies.
        Based on MCP server: div.d-input input
        """
        # Strategy 1: MCP server's selector (most reliable)
        title_input = tab.ele('div.d-input input', timeout=5)
        if title_input:
            self.logger.info(f"{self.platform}: Title input found via 'div.d-input input'")
            return title_input
        
        # Strategy 2: Fallback to old placeholder-based selector
        title_input = tab.ele('tag:input@@placeholder=填写标题会有更多赞哦～', timeout=3)
        if title_input:
            self.logger.info(f"{self.platform}: Title input found via placeholder")
            return title_input
        
        # Strategy 3: Try partial placeholder match
        title_input = tab.ele('tag:input@@placeholder:填写标题', timeout=3)
        if title_input:
            self.logger.info(f"{self.platform}: Title input found via partial placeholder")
            return title_input
        
        # Strategy 4: Generic input in title container
        title_input = tab.ele('div.title-container input', timeout=3)
        if title_input:
            self.logger.info(f"{self.platform}: Title input found via title-container")
            return title_input
        
        return None

    def _find_description_input(self, tab):
        """
        Find description/content input using multiple selector strategies.
        Based on MCP server: uses Race() between div.ql-editor and p[data-placeholder]
        """
        # Strategy 1: Quill editor (used by MCP server)
        desc_input = tab.ele('div.ql-editor', timeout=5)
        if desc_input:
            self.logger.info(f"{self.platform}: Description input found via 'div.ql-editor'")
            return desc_input
        
        # Strategy 2: Parent element with role="textbox" containing ql-editor
        desc_input = tab.ele('[role="textbox"] .ql-editor', timeout=3)
        if desc_input:
            self.logger.info(f"{self.platform}: Description input found via role=textbox")
            return desc_input
        
        # Strategy 3: Old placeholder-based selector (partial match)
        desc_input = tab.ele('@@tag()=p@@data-placeholder:输入正文描述', timeout=3)
        if desc_input:
            self.logger.info(f"{self.platform}: Description input found via partial placeholder")
            return desc_input
        
        # Strategy 4: Full placeholder match (original)
        desc_input = tab.ele('@@tag()=p@@data-placeholder=输入正文描述，真诚有价值的分享予人温暖', timeout=3)
        if desc_input:
            self.logger.info(f"{self.platform}: Description input found via full placeholder")
            return desc_input
        
        # Strategy 5: Edit container
        desc_input = tab.ele('div.edit-container .ql-editor', timeout=3)
        if desc_input:
            self.logger.info(f"{self.platform}: Description input found via edit-container")
            return desc_input
        
        return None

    def _find_publish_button(self, tab):
        """
        Find publish button using multiple selector strategies.
        Based on MCP server: .publish-page-publish-btn button.bg-red
        """
        # Strategy 1: MCP server's selector (most reliable)
        btn = tab.ele('.publish-page-publish-btn button.bg-red', timeout=5)
        if btn:
            self.logger.info(f"{self.platform}: Publish button found via MCP selector")
            return btn
        
        # Strategy 2: Old text-based selector
        btn = tab.ele('@@tag()=span@@text()=发布', timeout=3)
        if btn:
            self.logger.info(f"{self.platform}: Publish button found via text selector")
            return btn
        
        # Strategy 3: Button with text
        btn = tab.ele('button@@text():发布', timeout=3)
        if btn:
            self.logger.info(f"{self.platform}: Publish button found via button text")
            return btn
        
        return None

    async def upload_video(self, video_url, video_path, video_name, cover_path=None, description=None, topics=None,
                           collection=None,
                           headless=False, dry_run=None, dry_run_attach_media=None):
        if topics is None:
            topics = []
        topics = topics + config.keywords
        if dry_run is None:
            dry_run = bool(config.xhs_config.get("dry_run", False))
        if dry_run_attach_media is None:
            dry_run_attach_media = bool(config.xhs_config.get("dry_run_attach_media", False))

        try:
            if dry_run:
                self.logger.info(
                    f"DRY RUN: validating XHS upload UI for '{video_name}' "
                    f"(attach_media={dry_run_attach_media}); final Publish will NOT be clicked"
                )
            else:
                self.logger.info(f"Uploading video '{video_name}' to {self.platform}...")

            # ============================================================
            # PRE-FLIGHT: Check creator auth using persistent login module
            # ============================================================
            persistent_login = XhsPersistentLogin(logger=self.logger)
            use_profile = bool(config.xhs_config.get("use_persistent_profile", False))
            cookie_info = persistent_login.get_cookie_info()

            if use_profile:
                self.logger.info(f"{self.platform}: Using persistent DrissionPage profile: "
                                 f"{config.xhs_config.get('profile_dir')}")
            else:
                if not cookie_info.get('exists'):
                    self.logger.error(f"{self.platform}: No cookies found!")
                    self.logger.error(f"{self.platform}: Please run 'python xhs_login.py --refresh-session' or 'python xhs_login.py'")
                    return False
                self.logger.info(f"{self.platform}: Found {cookie_info.get('count', 0)} cookies "
                                 f"(extraction: {cookie_info.get('extraction_method', 'unknown')})")

            # Verify creator publish UI, not just main-site login.
            self.logger.info(f"{self.platform}: Verifying creator auth/upload UI...")
            if not persistent_login.check_creator_auth(headless=True, use_profile=use_profile):
                self.logger.error(f"{self.platform}: Creator auth is invalid or upload UI is unavailable")
                self.logger.error(f"{self.platform}: Run 'python xhs_login.py --refresh-session --timeout 15' to refresh the persistent session")
                return False

            self.logger.info(f"{self.platform}: ✅ Creator auth verified, proceeding with upload...")
            # ============================================================

            # Get the ChromiumOptions dynamically
            co = get_chromium_options(
                headless=headless,
                user_data_dir=config.xhs_config.get("profile_dir") if use_profile else None,
                profile_name=config.xhs_config.get("profile_name") if use_profile else None,
            )

            # Initialize Chromium browser
            browser = Chromium(co)
            tab = browser.latest_tab

            if not use_profile:
                # Load cookies from saved file and apply them to the session
                with open(config.xhs_config["cookie_path"], 'r') as file:
                    storage_state = json.load(file)
                    # Handle both formats: {"cookies": [...]} or [...]
                    if isinstance(storage_state, dict):
                        cookies = storage_state.get('cookies', [])
                    elif isinstance(storage_state, list):
                        cookies = storage_state
                    else:
                        raise ValueError(f"Unexpected cookie format: {type(storage_state)}")

                # Setting cookies using tab.set.cookies()
                tab.set.cookies(cookies)
                self.logger.info(f"{self.platform}: Cookies applied ({len(cookies)} cookies)")
            else:
                self.logger.info(f"{self.platform}: Using cookies from persistent browser profile (no manual cookie injection)")

            # Now navigate to the upload page
            tab.get(config.xhs_config["up_site"])
            tab.wait.load_start()  # Wait for the page to fully load

            # Wait for DOM to stabilize (like MCP server does)
            tab.wait(2)

            # Wait for the file input to be displayed
            input_displayed = tab.wait.ele_displayed('tag:input')

            # Find upload button with retry logic
            max_retries = 3
            retry_count = 0
            upload_button = None

            while retry_count < max_retries:
                # Try MCP server's selector first, then fallback
                upload_button = tab.ele('.upload-input', timeout=3) or tab.ele('tag:input@@type=file', timeout=3)
                if upload_button:
                    self.logger.info(f"{self.platform}: Upload button found on attempt {retry_count + 1}")
                    break
                else:
                    self.logger.warning(f"{self.platform}: Upload button not found on attempt {retry_count + 1}. Retrying in 1 second...")
                    tab.wait(1)  # Wait 1 second before retrying
                    retry_count += 1

            # Ensure the upload button is found
            if not upload_button:
                self.logger.error(f"{self.platform}: Failed to find the upload button for video upload.")
                self.logger.error(f"{self.platform}: This likely means cookies are invalid - please run 'python xhs_login.py'")
                tab.get_screenshot(path='tmp', name='login_failed.png', full_page=True)
                html_file = os.path.join('tmp', 'xhs_page_source.html')
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(tab.html)
                self.logger.error(f"Page source written to: {html_file}")
                browser.quit()
                return False

            # Use the natural click-to-upload method to handle file selection
            # Ensure the video path is an absolute path
            video_path = os.path.abspath(video_path)

            if dry_run and not dry_run_attach_media:
                self.logger.info(
                    f"{self.platform}: DRY RUN - upload input is available; "
                    "skipping media attachment to avoid uploading to XHS/creating drafts"
                )
                try:
                    tab.get_screenshot(path='tmp', name='xhs_dry_run_upload_ui.png', full_page=True)
                except Exception as e:
                    self.logger.warning(f"{self.platform}: Dry-run screenshot failed: {e}")
                browser.quit()
                return True

            if not os.path.exists(video_path):
                self.logger.error(f"{self.platform}: Video file not found: {video_path}")
                browser.quit()
                return False

            # Use the absolute path in the uploader logic
            self.logger.info(f"Uploading video '{video_path}' to {self.platform}...")

            # Use input() directly instead of click.to_upload()
            # click.to_upload() doesn't work reliably in headless mode
            # but input() works like go-rod's MustSetFiles()
            upload_button.input(video_path)
            self.logger.info(f"{self.platform}: Video upload initiated via input()")
            
            # Wait for the page to start processing the upload
            # This is critical - the page needs time to transition from dropzone to upload form
            # The debug script showed 15s is enough for the button to appear with bg-red
            tab.wait(15)
            
            # Verify upload started by checking for video filename or upload progress
            page_html = tab.html
            video_filename = os.path.basename(video_path)
            upload_started = (
                video_filename in page_html or 
                '上传中' in page_html or 
                '视频处理' in page_html or
                '%' in page_html  # Upload percentage
            )
            
            if upload_started:
                self.logger.info(f"{self.platform}: ✅ Upload started successfully - page shows upload indicators")
                
                # For dry_run, we can return success here since upload is confirmed working
                if dry_run:
                    self.logger.info(f"{self.platform}: DRY RUN SUCCESS - Video uploaded and processing. Not waiting for publish button.")
                    try:
                        tab.get_screenshot(path='tmp', name='xhs_dry_run_success.png', full_page=True)
                        self.logger.info(f"{self.platform}: Screenshot saved to tmp/xhs_dry_run_success.png")
                    except Exception as e:
                        self.logger.warning(f"{self.platform}: Screenshot failed: {e}")
                    browser.quit()
                    return True
            else:
                # Take diagnostic screenshot
                tab.get_screenshot(path='tmp', name='xhs_upload_not_started.png', full_page=True)
                self.logger.warning(f"{self.platform}: ⚠️ Upload may not have started - no upload indicators found in page")
                self.logger.warning(f"{self.platform}: Check tmp/xhs_upload_not_started.png for diagnostics")
                if dry_run:
                    # Even in dry_run, if upload didn't start, that's a problem
                    browser.quit()
                    return False

            # ============================================================
            # CRITICAL FIX: Wait for video processing using MCP approach
            # Instead of waiting for specific text, wait for publish button
            # to become enabled (indicates video processing complete)
            # ============================================================
            self.logger.info(f"{self.platform}: Waiting for video to be processed...")
            
            # First, give the upload a moment to start
            tab.wait(3)
            
            # Now wait for publish button to become ready (up to 10 minutes for video processing)
            publish_button = self._wait_for_publish_button_ready(tab, timeout=600)
            
            if not publish_button:
                self.logger.error(f"{self.platform}: Video processing timed out or publish button not found")
                tab.get_screenshot(path='tmp', name='xhs_video_processing_timeout.png', full_page=True)
                browser.quit()
                return False
            
            self.logger.info(f"{self.platform}: ✅ Video processed, ready to fill metadata")

            # Set title using robust selector
            self.logger.info(f"{self.platform}: Setting title")
            title_input = self._find_title_input(tab)

            if not title_input:
                self.logger.error(f"{self.platform}: Title input not found.")
                tab.get_screenshot(path='tmp', name='xhs_title_not_found.png', full_page=True)
                # Save HTML for debugging
                with open('tmp/xhs_title_not_found.html', 'w', encoding='utf-8') as f:
                    f.write(tab.html)
                browser.quit()
                return False
            
            up_title = video_name
            # XHS has 20 char limit for titles (per MCP docs)
            title_input.input(up_title[:20])
            self.logger.info(f"{self.platform}: Title set: '{up_title[:20]}'")

            # Wait a moment after title input (MCP does this)
            tab.wait(1)

            # Set description using robust selector
            self.logger.info(f"{self.platform}: Setting description")
            description_area = self._find_description_input(tab)
            
            if not description_area:
                self.logger.error(f"{self.platform}: Description input not found.")
                tab.get_screenshot(path='tmp', name='xhs_desc_not_found.png', full_page=True)
                with open('tmp/xhs_desc_not_found.html', 'w', encoding='utf-8') as f:
                    f.write(tab.html)
                browser.quit()
                return False

            description_area.click()
            description_area.input(description)
            self.logger.info(f"{self.platform}: Description set")

            # Click back on title to stabilize (MCP does this)
            title_input.click()
            tab.wait(1)

            # Add topics/tags
            if topics:
                self.logger.info(f"{self.platform}: Adding topics")
                # Limit to 10 tags per XHS rules (from MCP docs)
                topics_to_add = topics[:10]
                
                for topic in topics_to_add:
                    try:
                        self.logger.info(f"Trying to add topic: {topic}")
                        # Click on description area and add hashtag
                        description_area.click()
                        description_area.input("#" + topic)
                        tab.wait(1)  # Wait for suggestions to load
                        
                        # Try to find and click suggestion
                        suggestion_list = tab.ele('tag:ul li@@class:publish-topic-item', timeout=2)
                        if suggestion_list:
                            suggestion_list.click()
                            self.logger.info(f"Topic '{topic}' added")
                        else:
                            # Just press Enter to confirm the tag
                            description_area.input('\n')
                            self.logger.info(f"Topic '{topic}' added (no suggestion)")
                    except Exception as e:
                        self.logger.warning(f"Error adding topic '{topic}': {e}")

            # Add location
            if collection:
                self.logger.info(f"{self.platform}: Adding location")
                try:
                    location_button = tab.ele('div.plugin:has-text("添加地点")', timeout=3)
                    if location_button:
                        location_button.click()
                        tab.wait(1)
                        
                        location_input = tab.ele('input[placeholder*="地点"]', timeout=3)
                        if location_input:
                            location_input.input(collection)
                            tab.wait(1)
                            
                            first_location = tab.ele('ul.el-scrollbar__view li', timeout=3)
                            if first_location:
                                first_location.click()
                                self.logger.info(f"Location '{collection}' added")
                            else:
                                self.logger.warning(f"Location '{collection}' not found in dropdown")
                except Exception as e:
                    self.logger.warning(f"Error adding location: {e}")

            # Re-find publish button (in case DOM changed)
            self.logger.info(f"{self.platform}: Publishing video")
            publish_button = self._find_publish_button(tab)
            
            if not publish_button:
                self.logger.error(f"{self.platform}: Publish button not found.")
                tab.get_screenshot(path='tmp', name='publishbutton_error.png', full_page=True)
                browser.quit()
                return False

            url_before_publish = tab.url
            self.logger.info(f"Current URL before publishing: {url_before_publish}")

            if dry_run:
                self.logger.info(
                    f"{self.platform}: DRY RUN - publish button found; stopping before final Publish click"
                )
                try:
                    tab.get_screenshot(path='tmp', name='xhs_dry_run_publish_ready.png', full_page=True)
                except Exception as e:
                    self.logger.warning(f"{self.platform}: Dry-run screenshot failed: {e}")
                browser.quit()
                return True

            publish_button.click()

            # Wait for success confirmation
            self.logger.info(f"{self.platform}: Waiting for success confirmation")

            tab.wait.url_change('publish/success', timeout=30)
            current_url = tab.url
            self.logger.info(f"Current URL after publishing: {current_url}")

            if "publish/success" in tab.url:
                self.logger.info(f"{self.platform}: ✅ Video published successfully!")
                try:
                    excute_sqlite_sql(
                        config.table_add_sql,
                        (
                            self.platform, video_name, datetime.now().strftime('%Y%m%d'),
                            video_url, video_path, collection, description
                        )
                    )
                except Exception as e:
                    self.logger.error(f"Database error: {e}")
                browser.quit()
                return True
            else:
                self.logger.error(f"{self.platform}: URL did not change to success page, upload may have failed")
                tab.get_screenshot(path='tmp', name='xhs_publish_failed.png', full_page=True)

            browser.quit()
            return False

        except FileNotFoundError as e:
            self.logger.error(f"Cookie file not found: {e}")
            self.logger.error(f"Please run 'python xhs_login.py' to login and create cookies")
            return False
        except Exception as e:
            self.logger.error(f"An error occurred during the upload: {e}")
            import traceback
            traceback.print_exc()
            return False
