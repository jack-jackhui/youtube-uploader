import sys
import os
import asyncio
from datetime import datetime

# Add the parent directory to the sys.path to import platform-specific uploaders
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from platforms.xhs.uploader import XhsUploader  # Ensure this is the updated uploader class


async def main():
    # Instantiate the XhsUploader
    xhs = XhsUploader()

    # Define test inputs
    video_path = "../downloaded_videos/_Can_AI-Powered_ChatGPT_Ace_Your_Toughest_Interview_Questions__.mp4"
    video_name = "人工智能能否通过高难度面试"
    description = "人工智能能否通过高难度面试"
    topics = ["人工智能", "技术未来"]
    cookie_path = "cookies.json"  # Path to your cookie file

    # Test process
    try:
        # Start the browser
        xhs.start_browser(headless=False)

        # Load cookies
        xhs.load_cookies()

        # Refresh the session
        xhs.refresh_session()

        # Upload the video
        success = xhs.upload_video(
            video_path=video_path,
            video_name=video_name,
            description=description,
            topics=topics,
            collection=None  # Optional: Provide a collection name if needed
        )

        if success:
            print(f"Test succeeded: Video '{video_name}' uploaded successfully.")
        else:
            print(f"Test failed: Video '{video_name}' upload encountered an issue.")

        # Save cookies for future runs
        xhs.save_cookies()

    except Exception as e:
        print(f"An error occurred during the test: {e}")

    finally:
        # Disconnect but keep the browser running
        xhs.stop_browser()


if __name__ == "__main__":
    # Run the asynchronous main function
    asyncio.run(main())