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

        """
        try:
            self.logger.info(f"Uploading video '{video_name}' to {self.platform}...")
            # cookie 加载
            with open(config.xhs_config["cookie_path"], 'r') as file:
                storage_state = json.load(file)
            async with (async_playwright() as playwright):
                # 登录
                self.logger.info(self.platform + ":登陆中")
                browser = await playwright.chromium.launch(headless=headless)
                context = await browser.new_context(storage_state=storage_state)

                page = await context.new_page()

                await page.goto(config.xhs_config["up_site"])
                await page.wait_for_url(config.xhs_config["up_site"])
                self.logger.info(self.platform + ":登陆成功")

                # 视频上传
                self.logger.info(self.platform + ":视频上传中")
                # 点击上传按钮
                # file_input_locator = page.locator('//*[@id="publish-container"]/div/div[2]/div[1]/div/input')
                file_input_locator = page.locator('input[type="file"]')
                # await file_input_locator.wait_for(state="visible")
                await file_input_locator.set_input_files([video_path])
                self.logger.info(f"{self.platform}: Video upload initiated")

                # Wait for the upload to complete
                self.logger.info(f"{self.platform}: Waiting for video upload to complete")
                await page.wait_for_selector('div.process-wrapper', state='hidden', timeout=600000)
                self.logger.info(f"{self.platform}: 视频上传完毕")

                # Ensure the cover image is generated and available
                self.logger.info(f"{self.platform}: Waiting for cover image to be generated")
                cover_image_locator = page.locator('div.coverImg[style*="background-image"]')
                await cover_image_locator.wait_for(state="visible", timeout=120000)  # Wait up to 2 minutes for the cover image
                
                if await cover_image_locator.is_visible():
                    self.logger.info(f"{self.platform}: Cover image successfully loaded")
                else:
                    self.logger.error(f"{self.platform}: Failed to load the cover image in time")
                    await browser.close()
                    return False

                # 填写作品名称 简介 话题
                self.logger.info(self.platform + ":设置标题")
                up_title = video_name + "|" + random.choice(config.key_sentence)
                # await page.locator('//*[@id="publish-container"]/div/div[3]/div[2]/div[3]/input').fill(up_title[:19])
                await page.fill('input.el-input__inner[placeholder="填写标题会有更多赞哦～"]', up_title[:40])

                # Set Description
                self.logger.info(f"{self.platform}: 设置简介")
                content_area = page.locator('p#post-textarea')
                await content_area.click()
                await content_area.type(description)

                # self.logger.info(self.platform + ":添加话题")

                # Add Topics
                if topics:
                    self.logger.info(f"{self.platform}: Adding topics")
                    topic_button = page.locator('button#topicBtn')
                    await topic_button.click()
                    for topic in topics:
                        # Typing topics directly into the placeholder and selecting them
                        topic_input = page.locator('p#post-textarea')
                        await topic_input.type(f'#{topic}')
                        await asyncio.sleep(0.5)
                        # In case there is a dropdown, select the first available suggestion (if needed)
                        suggestions = page.locator('li.publish-topic-item').first
                        if await suggestions.is_visible():
                            await suggestions.click()
                        else:
                            self.logger.warning(f"Topic '{topic}' not found or no suggestions.")
                        await asyncio.sleep(1)
                
                # Add Location
                self.logger.info(f"{self.platform}: Adding location")

                # Open the location selector
                location_button = page.locator('div.plugin:has-text("添加地点")')
                await location_button.click()

                # Type in the location (e.g., "Melbourne")
                location_input = page.locator('input.el-input__inner[placeholder="下拉选择地点"]')
                await location_input.fill("Melbourne")  # Adjust this if you want to pass a variable instead of a fixed location.
                await asyncio.sleep(1)  # Allow time for the dropdown to appear

                # Select the first location option from the list
                location_option = page.locator('ul.el-scrollbar__view li').first
                if await location_option.is_visible():
                    await location_option.click()
                else:
                    self.logger.warning("Location not found")

                await asyncio.sleep(0.5)  # Small delay after selecting location                

                # Publish
                self.logger.info(f"{self.platform}: Publishing")
                await page.wait_for_load_state('networkidle')  # Wait for no network activity
                await page.locator('button.el-button.publishBtn').click()

                # Wait for the success confirmation page
                self.logger.info(f"{self.platform}: Waiting for success confirmation")
                try:
                    await page.wait_for_url("https://creator.xiaohongshu.com/publish/success", timeout=6000)

                    # Check if success message appears
                    success_message = page.locator('span:has-text("发布成功")')
                    if await success_message.is_visible():
                        self.logger.info(f"{self.platform}: Video published successfully")
                        # Optionally, store in the database
                        excute_sqlite_sql(
                            config.table_add_sql,
                            (
                                self.platform,
                                video_name,
                                datetime.now().strftime('%Y%m%d'),
                                video_url,
                                video_path,
                                collection,
                                description
                            )
                        )
                        await asyncio.sleep(2)  # Handle any final redirect before closing
                        await browser.close()
                        return True
                    else:
                        self.logger.error(f"{self.platform}: '发布成功' message not found")
                except asyncio.TimeoutError:
                    self.logger.error(f"{self.platform}: Failed to load success page in time")

                await browser.close()
                return False
        """

        try:
            self.logger.info(f"Uploading video '{video_name}' to {self.platform}...")
            """
            # Ensure no Chromium instances are running
            if check_chromium_running():
                self.logger.info(f"Existing Chromium/Chrome processes detected. Killing them...")
                kill_chromium_processes()
                self.logger.info(f"All Chromium/Chrome processes killed.")
            """

            # Get the ChromiumOptions dynamically
            co = get_chromium_options(headless=headless)

            # Initialize Chromium browser
            self.logger.info(f"{self.platform}: Logging in")
            """
            co = ChromiumOptions()
            if headless:
                co.headless()  # Enable headless mode if specified
            co.incognito()  # Set browser to incognito mode
            co.auto_port(True)  # Automatically assign a free port
            co.set_argument('--disable-cache')  # Disables the cache
            co.set_argument('--disk-cache-size=0')  # Set cache size to zero
            co.set_argument('--media-cache-size=0')  # Disable media cache
            co.set_argument('--no-sandbox')  # Disable sandboxing
            co.set_argument('--disable-application-cache')  # Disable the application cache
            co.set_argument('--disable-site-isolation-trials')  # Disable site isolation for cache clearing
            # co.set_argument('--disable-web-security')  # Disable web security (for testing purposes)

            # Clear browser storage (cookies, local storage, etc.)
            co.set_argument('--clear-storage')  # Optional argument to clear storage on every run
            """

            browser = Chromium(co)

            # Load cookies from saved file and apply them to the session
            with open(config.xhs_config["cookie_path"], 'r') as file:
                storage_state = json.load(file)
                cookies = storage_state.get('cookies', [])

            tab = browser.latest_tab

            # Navigate to a page within the domain of the cookies to set them
            # tab.get('https://www.xiaohongshu.com')

            # Setting cookies using tab.set.cookies()
            tab.set.cookies(cookies)
            self.logger.info(f"{self.platform}: Cookies set successfully")

            # Now navigate to the upload page
            tab.get(config.xhs_config["up_site"])
            tab.wait.load_start()  # Wait for the page to fully load

            # Wait for the file input to be displayed
            # tab.wait.ele_displayed('input.upload-input[type="file"]', timeout=10)

            upload_button = tab.ele('tag:input@@class=upload-input@@type=file')

            # Ensure the upload button is found
            if not upload_button:
                self.logger.error(f"{self.platform}: Failed to find the upload button for video upload.")
                tab.get_screenshot(path='tmp', name='login_failed.png', full_page=True)
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
            cover_image = tab.wait.ele_displayed('tag:div@@class=coverImg', timeout=60)
            # tab.get_screenshot(path='tmp', name='screenshot_1.jpg', full_page=True)
            # Check if the cover image element is found
            if cover_image:
                self.logger.info(f"{self.platform}: Video cover image successfully loaded")
            else:
                # tab.get_screenshot(path='tmp', name='screenshot_2.jpg', full_page=True)
                self.logger.error(f"{self.platform}: Failed to load video cover image in time")
                browser.quit()
                return False  # Exit if cover image is not found

            """
            # Ensure the cover image is generated
            self.logger.info(f"{self.platform}: Waiting for cover image to be generated")
            cover_image = tab.wait.ele_displayed('div.coverImg[style*="background-image"]', timeout=120)
            if cover_image:
                self.logger.info(f"{self.platform}: Cover image successfully loaded")
            else:
                self.logger.error(f"{self.platform}: Failed to load cover image in time")
                browser.quit()
                return False
            """

            # Set title and description
            self.logger.info(f"{self.platform}: Setting title")
            title_input = tab.ele('tag:input@@placeholder=填写标题会有更多赞哦～')
            """
            input_tag_list = tab.eles('tag:input')
            for index, input_tag in enumerate(input_tag_list):
                print(f"Input Tags {index}: {input_tag.html}")
            """
            if not title_input:
                self.logger.error(f"{self.platform}: Title input not found.")
                browser.quit()
                return False  # Stop if title input is not found
            # up_title = video_name + "|" + random.choice(config.key_sentence)
            up_title = video_name
            title_input.input(up_title[:25])

            self.logger.info(f"{self.platform}: Setting description")
            description_area = tab.ele(
                'tag:p@@id=post-textarea@@placeholder=在这里输入正文描述，真诚有价值的分享予人温暖')
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
            publish_button = tab.ele('tag:button@@class=el-button publishBtn@@text()=发布')
            if not publish_button:
                self.logger.error(f"{self.platform}: Publish button not found.")
                browser.quit()
                return False  # Stop if publish button is not found

            url_before_publish = tab.url
            self.logger.info(f"Current URL before publishing: {url_before_publish}")

            publish_button.click()

            # Wait for success confirmation
            self.logger.info(f"{self.platform}: Waiting for success confirmation")

            """
            # Set up screencast recording
            self.logger.info(f"{self.platform}: Setting up screen recording...")
            tab.screencast.set_save_path('video_publish_recording.mp4')  # Set where the recording will be saved
            tab.screencast.set_mode.video_mode()  # Set the recording mode to continuous video
            tab.screencast.start()  # Start recording
            """

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
            print(f"An error occurred during the upload: {e}")
            return False
