"""
import asyncio
import os
from platforms.xhs.uploader import XhsUploader  # Ensure this is the updated uploader class

async def main():
    uploader = XhsUploader()

    # Define test inputs
    video_path = "../downloaded_videos/_Can_AI-Powered_ChatGPT_Ace_Your_Toughest_Interview_Questions__.mp4"
    video_name = "人工智能可以通过最难的面试吗？"
    description = "人工智能可以通过最难的面试吗？"
    topics = ["面试", "人工智能"]

    # Start the browser
    uploader.start_browser(headless=False)

    # Load cookies and refresh session
    uploader.load_cookies()
    uploader.refresh_session()

    # Upload the video
    success = await uploader.upload_video(
        video_path=video_path,
        video_name=video_name,
        description=description,
        topics=topics
    )

    if success:
        print(f"Video '{video_name}' uploaded successfully.")
    else:
        print(f"Failed to upload video '{video_name}'.")

    # Save cookies for future sessions
    uploader.save_cookies()

    # Do not stop the browser (keeps the session alive)
    uploader.stop_browser()

if __name__ == "__main__":
    # Run the asynchronous main function
    asyncio.run(main())

"""

import sys
import io
import asyncio
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add the parent directory to sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.append(parent_dir)
from platforms.xhs.uploader import XhsUploader  # Ensure this is your old uploader class

async def main():
    uploader = XhsUploader()

    # Define test inputs
    video_url = ""  # Provide the video URL if necessary; in your old code, this parameter is required
    video_path = "../downloaded_videos/Ren_Gong_Zhi_Neng_Hui_Qu_Dai_Ni_De_Gong_Zuo_Ma__.mp4"
    video_name = "人工智能会取代你的工作吗？"
    description = "人工智能会取代你的工作吗？"
    topics = ["面试", "人工智能"]

    # Since the old code initializes the browser and loads cookies within upload_video,
    # we don't need to call start_browser or load_cookies.

    # Upload the video using the old code's upload_video method
    success = await uploader.upload_video(
        video_url=video_url,
        video_path=video_path,
        video_name=video_name,
        description=description,
        topics=topics,
        headless=False  # Set to True if you want to run the browser in headless mode
    )

    # Safe print using UTF-8
    if success:
        sys.stdout.buffer.write(f"视频 '{video_name}' 上传成功！\n".encode('utf-8'))
    else:
        sys.stdout.buffer.write(f"视频 '{video_name}' 上传失败\n".encode('utf-8'))

    # No need to call save_cookies or stop_browser since the old code handles browser closure internally.

if __name__ == "__main__":
    # Run the asynchronous main function
    asyncio.run(main())