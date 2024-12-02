import json
import os
from datetime import datetime
from time import sleep
from DrissionPage import Chromium
from utils.chromium_utils import get_chromium_options
from core.upload import Upload
from core import config


class XhsUploader(Upload):
    """
    Handles video uploads to XHS while maintaining a persistent browser session and refreshing cookies.
    """
    platform = "xhs"

    def __init__(self):
        self.browser = None
        self.tab = None

    def start_browser(self, headless=False, user_data_dir="browser_data"):
        """
        Starts or reconnects to the browser session.
        """
        if not self.browser or not self.browser.states.is_alive:
            print("Starting browser...")
            co = get_chromium_options(headless=headless, user_data_dir=user_data_dir)
            self.browser = Chromium(co)

        # Ensure a tab is active
        if not self.tab or not self.tab.states.is_alive:
            self.tab = self.browser.get_tab() or self.browser.new_tab()
        print("Browser started or reconnected successfully.")

    def load_cookies(self):
        """
        Loads cookies from the config-defined path after navigating to the domain.
        """
        cookie_path = config.xhs_config["cookie_path"]
        if not os.path.exists(cookie_path):
            print(f"Cookie file not found: {cookie_path}")
            return

        # Navigate to the domain before setting cookies
        print("Navigating to the domain to set cookies...")
        self.tab.get("https://www.xiaohongshu.com")
        self.tab.wait.load_start()

        # Load and set cookies
        with open(cookie_path, 'r') as file:
            cookie_data = json.load(file)
        cookies = cookie_data.get("cookies", [])
        for cookie in cookies:
            if "domain" not in cookie:
                cookie["domain"] = ".xiaohongshu.com"  # Ensure the domain is set
        self.tab.set.cookies(cookies)
        print("Cookies loaded and set successfully.")

    def save_cookies(self):
        """
        Saves current cookies to the config-defined path in JSON format.
        """
        cookie_save_path = config.xhs_config["cookie_save_path"]
        try:
            # Retrieve cookies as a list of dictionaries
            cookies_list = self.tab.cookies()

            # Save cookies to the file
            with open(cookie_save_path, 'w') as file:
                json.dump({"cookies": cookies_list}, file, indent=4)
            print(f"Cookies saved to {cookie_save_path}.")
        except Exception as e:
            print(f"An error occurred while saving cookies: {e}")

    def refresh_session(self):
        """
        Refreshes the session by visiting the dashboard or another authenticated page.
        """
        print("Refreshing session...")
        self.tab.get(config.xhs_config["dashboard_url"])  # Use the dashboard URL from config
        self.tab.wait.load_start()
        print("Session refreshed successfully.")

    def upload_video(self, video_path, video_name, description=None, topics=None, collection=None):
        """
        Uploads a video to XHS with the given details.
        """
        try:
            print(f"Uploading video '{video_name}'...")

            # Navigate to the upload page URL
            print("Navigating to the upload page...")
            upload_url = config.xhs_config["up_site"]  # Ensure this is defined in your config
            self.tab.get(upload_url)
            self.tab.wait.load_start()
            print("Arrived at the upload page.")

            # Locate the upload button
            upload_button = self.tab.ele('tag:input@@class=upload-input@@type=file')
            if not upload_button:
                print("Upload button not found.")
                return False

            # Start video upload
            upload_button.input(video_path)
            print("Video upload initiated.")

            # Wait for cover image to be generated
            cover_image = self.tab.wait.ele_displayed('tag:div@@class=coverImg', timeout=60)
            if not cover_image:
                print("Failed to load video cover image.")
                return False

            # Set title and description
            title_input = self.tab.ele('tag:input@@placeholder=填写标题会有更多赞哦～')
            if title_input:
                title_input.input(video_name[:25])
                print("Title set successfully.")
            else:
                print("Title input not found.")

            if description:
                description_area = self.tab.ele('@@tag()=div@@data-placeholder=输入正文描述，真诚有价值的分享予人温暖')
                if description_area:
                    description_area.click()
                    description_area.input(description)
                    print("Description set successfully.")
                else:
                    print("Description input not found.")

            # Add topics
            if topics:
                topic_button = self.tab.ele('tag:button@@id=topicBtn@@class=contentBtn')
                if topic_button:
                    topic_button.click()
                    for topic in topics:
                        topic_input = self.tab.ele('@@tag()=div@@data-placeholder=输入正文描述，真诚有价值的分享予人温暖')
                        topic_input.input(f"#{topic}")
                        sleep(1)
                        suggestion = self.tab.ele('tag:ul li@@class=publish-topic-item')
                        if suggestion:
                            suggestion.click()
                            print(f"Topic '{topic}' added.")
                        else:
                            print(f"Topic '{topic}' not found.")

            # Publish the video
            publish_button = self.tab.ele('@@tag()=span@@text()=发布')
            if publish_button:
                publish_button.click()
                self.tab.wait.url_change('publish/success', timeout=20)
                if "publish/success" in self.tab.url:
                    print(f"Video '{video_name}' published successfully.")
                    return True
                else:
                    print("Failed to publish the video.")
            else:
                print("Publish button not found.")
            return False

        except Exception as e:
            print(f"An error occurred: {e}")
            return False

    def stop_browser(self):
        """
        Keeps the browser running but disconnects from it.
        """
        if self.browser and self.browser.states.is_alive:
            print("Disconnecting from the browser. It will remain running for future use.")
            self.browser.reconnect()


# Usage Example
if __name__ == "__main__":
    uploader = XhsUploader()

    # Start the browser
    uploader.start_browser(headless=False)

    # Load cookies and refresh session
    uploader.load_cookies()
    uploader.refresh_session()

    # Upload a video
    video_path = "path/to/video.mp4"
    video_name = "My Test Video"
    description = "This is a test upload"
    topics = ["TestTopic1", "TestTopic2"]
    uploader.upload_video(video_path, video_name, description, topics)

    # Save cookies for future sessions
    uploader.save_cookies()

    # Do not stop the browser (keeps the session alive)
    uploader.stop_browser()