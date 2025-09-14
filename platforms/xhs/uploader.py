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
from utils.cookie_manager import XhsCookieManager


class XhsUploader(Upload):
    """
    开始上传,包括以下几个部分:
    1.作品名称 2.作品简介 3.添加话题 4.选择合集
    若是上传成功之后,将数据写入sqlite数据库,没成功就不写入
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

            # Get the ChromiumOptions dynamically
            co = get_chromium_options(headless=headless)

            # Initialize enhanced cookie manager
            cookie_manager = XhsCookieManager(logger=self.logger)
            
            # Check if cookies exist and are valid
            cookies = cookie_manager.load_cookies()
            if not cookies:
                self.logger.info(f"{self.platform}: No cookies found, manual login required")
                if not cookie_manager.renew_cookies_with_manual_login(headless=headless):
                    self.logger.error(f"{self.platform}: Failed to obtain cookies")
                    return False
                cookies = cookie_manager.load_cookies()
            
            # Initialize Chromium browser
            self.logger.info(f"{self.platform}: Logging in")
            browser = Chromium(co)
            tab = browser.latest_tab
            
            # Set cookies
            tab.set.cookies(cookies)
            self.logger.info(f"{self.platform}: Cookies set successfully")
            
            # Validate cookies by testing access to upload page
            if not cookie_manager.are_cookies_valid(tab):
                cookie_age = cookie_manager.get_cookie_age()
                self.logger.warning(f"{self.platform}: Cookies invalid (age: {cookie_age:.1f}h), renewing...")
                
                browser.quit()  # Close current browser before opening renewal browser
                
                if cookie_manager.renew_cookies_with_manual_login(headless=headless):
                    self.logger.info(f"{self.platform}: Cookies renewed successfully, retrying upload")
                    cookies = cookie_manager.load_cookies()
                    
                    # Restart with new cookies
                    browser = Chromium(co)
                    tab = browser.latest_tab
                    tab.set.cookies(cookies)
                    self.logger.info(f"{self.platform}: New cookies set successfully")
                else:
                    self.logger.error(f"{self.platform}: Failed to renew cookies")
                    return False

            # Now navigate to the upload page
            tab.get(config.xhs_config["up_site"])
            # print(config.xhs_config["up_site"])
            tab.wait.load_start()  # Wait for the page to fully load

            # Wait for the file input to be displayed
            input_displayed = tab.wait.ele_displayed('tag:input')
            # print(input_displayed)

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
                    self.logger.warning(
                        f"{self.platform}: Upload button not found on attempt {retry_count + 1}. Retrying in 1 second...")
                    tab.wait(1)  # Wait 1 second before retrying
                    retry_count += 1

            # Ensure the upload button is found
            if not upload_button:
                self.logger.error(f"{self.platform}: Failed to find the upload button for video upload.")
                tab.get_screenshot(path='tmp', name='login_failed.png', full_page=True)
                html_file = os.path.join('tmp', 'xhs_page_source.html')
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(tab.html)
                self.logger.error(f"Page source written to: {html_file}")
                # print(upload_button)
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

            # cover_image = tab.wait.ele_displayed('tag:div@@class=coverImg', timeout=60)
            # tab.get_screenshot(path='tmp', name='screenshot_1.jpg', full_page=True)
            # Check if the cover image element is found
            # if cover_image:
            #    self.logger.info(f"{self.platform}: Video cover image successfully loaded")
            # else:
            # tab.get_screenshot(path='tmp', name='screenshot_2.jpg', full_page=True)
            #    self.logger.error(f"{self.platform}: Failed to load video cover image in time")
            #    browser.quit()
            #    return False  # Exit if cover image is not found

            # Set title and description
            self.logger.info(f"{self.platform}: Setting title")
            title_input = tab.ele('tag:input@@placeholder=填写标题会有更多赞哦～')

            if not title_input:
                self.logger.error(f"{self.platform}: Title input not found.")
                browser.quit()
                return False  # Stop if title input is not found
            # up_title = video_name + "|" + random.choice(config.key_sentence)
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
                # tab.screencast.stop()
                browser.quit()
                return True
            else:
                self.logger.error(f"{self.platform}: url did not change, upload may have failed")

            # tab.screencast.stop()
            browser.quit()
            return False

        except Exception as e:
            self.logger.error(f"An error occurred during the upload: {e}")
            return False