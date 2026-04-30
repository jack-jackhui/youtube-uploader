# import asyncio
import json
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
    """
    platform = "xhs"

    async def upload_video(self, video_url, video_path, video_name, cover_path=None, description=None, topics=None,
                           collection=None,
                           headless=False):
        if topics is None:
            topics = []
        topics = topics + config.keywords

        try:
            self.logger.info(f"Uploading video '{video_name}' to {self.platform}...")

            # ============================================================
            # PRE-FLIGHT: Check login status using persistent login module
            # ============================================================
            persistent_login = XhsPersistentLogin(logger=self.logger)
            
            # Check if cookies exist
            cookie_info = persistent_login.get_cookie_info()
            if not cookie_info.get('exists'):
                self.logger.error(f"{self.platform}: No cookies found!")
                self.logger.error(f"{self.platform}: Please run 'python xhs_login.py' to login first")
                return False
            
            self.logger.info(f"{self.platform}: Found {cookie_info.get('count', 0)} cookies "
                           f"(extraction: {cookie_info.get('extraction_method', 'unknown')})")
            
            # Verify cookies are still valid
            self.logger.info(f"{self.platform}: Verifying login status...")
            if not persistent_login.check_login_status(headless=True):
                self.logger.error(f"{self.platform}: Cookies expired or invalid!")
                self.logger.error(f"{self.platform}: Please run 'python xhs_login.py' to login again")
                return False
            
            self.logger.info(f"{self.platform}: ✅ Login verified, proceeding with upload...")
            # ============================================================

            # Get the ChromiumOptions dynamically
            co = get_chromium_options(headless=headless)

            # Initialize Chromium browser
            browser = Chromium(co)

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

            tab = browser.latest_tab

            # Setting cookies using tab.set.cookies()
            tab.set.cookies(cookies)
            self.logger.info(f"{self.platform}: Cookies applied ({len(cookies)} cookies)")

            # Now navigate to the upload page
            tab.get(config.xhs_config["up_site"])
            tab.wait.load_start()  # Wait for the page to fully load

            # Wait for the file input to be displayed
            input_displayed = tab.wait.ele_displayed('tag:input')

            # Find upload button with retry logic
            max_retries = 3
            retry_count = 0
            upload_button = None

            while retry_count < max_retries:
                upload_button = tab.ele('tag:input@@class=upload-input@@type=file')
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

            # Use the absolute path in the uploader logic
            self.logger.info(f"Uploading video '{video_path}' to {self.platform}...")

            upload_button.click.to_upload(video_path)
            self.logger.info(f"{self.platform}: Video upload initiated")

            # Wait for the video upload to complete
            video_upload_complete = tab.wait.ele_displayed('@text()=上传成功')

            # Set title and description
            self.logger.info(f"{self.platform}: Setting title")
            title_input = tab.ele('tag:input@@placeholder=填写标题会有更多赞哦～')

            if not title_input:
                self.logger.error(f"{self.platform}: Title input not found.")
                browser.quit()
                return False  # Stop if title input is not found
            
            up_title = video_name
            title_input.input(up_title[:25])

            self.logger.info(f"{self.platform}: Setting description")
            description_area = tab.ele(
                '@@tag()=p@@data-placeholder=输入正文描述，真诚有价值的分享予人温暖')
            if not description_area:
                self.logger.error(f"{self.platform}: Description input not found.")
                browser.quit()
                return False  # Stop if description input is not found

            description_area.click()
            description_area.input(description)

            # Add topics
            if topics:
                self.logger.info(f"{self.platform}: Adding topics")
                topic_button = tab.ele('tag:button@@id=topicBtn@@class=contentBtn')
                topic_button.click()

                for topic in topics:
                    try:
                        self.logger.info(f"Trying to add topic: {topic}")
                        topic_input = description_area
                        topic_input.input("#" + topic)
                        tab.wait(1)  # Wait for suggestions to load
                        suggestion_list = tab.ele('tag:ul li@@class=publish-topic-item')
                        if suggestion_list:
                            suggestion_list.click()
                            self.logger.info(f"Topic '{topic}' added")
                        else:
                            self.logger.warning(f"Topic '{topic}' not found")
                    except Exception as e:
                        self.logger.error(f"Error adding topic '{topic}': {e}")

            # Add location
            if collection:
                self.logger.info(f"{self.platform}: Adding location")
                location_button = tab.ele('div.plugin:has-text("添加地点")')
                location_button.click()

                location_input = tab.ele('input.el-input__inner[placeholder="下拉选择地点"]')
                location_input.input(collection)
                tab.wait(1)  # Wait for the dropdown to appear

                first_location = tab.ele('ul.el-scrollbar__view li')
                if first_location:
                    first_location.click()
                else:
                    self.logger.warning(f"Location '{collection}' not found")

            # Publish the video
            self.logger.info(f"{self.platform}: Publishing video")
            publish_button = tab.ele('@@tag()=span@@text()=发布')
            if not publish_button:
                self.logger.error(f"{self.platform}: Publish button not found.")
                tab.get_screenshot(path='tmp', name='publishbutton_error.jpg', full_page=True)
                browser.quit()
                return False  # Stop if publish button is not found

            url_before_publish = tab.url
            self.logger.info(f"Current URL before publishing: {url_before_publish}")

            publish_button.click()

            # Wait for success confirmation
            self.logger.info(f"{self.platform}: Waiting for success confirmation")

            tab.wait.url_change('publish/success', timeout=20)
            current_url = tab.url
            self.logger.info(f"Current URL after publishing: {current_url}")

            if "publish/success" in tab.url:
                self.logger.info(f"{self.platform}: Video published successfully")
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
                self.logger.error(f"{self.platform}: url did not change, upload may have failed")

            browser.quit()
            return False

        except FileNotFoundError as e:
            self.logger.error(f"Cookie file not found: {e}")
            self.logger.error(f"Please run 'python xhs_login.py' to login and create cookies")
            return False
        except Exception as e:
            self.logger.error(f"An error occurred during the upload: {e}")
            return False
