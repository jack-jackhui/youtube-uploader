import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from platforms.douyin.uploader import DouyinUploader
from platforms.xhs.uploader import XhsUploader
from platforms.bili.uploader import BiliUploader
import asyncio

async def main():
    xhs = XhsUploader()
    await xhs.upload_video(
        video_url="",          # Replace with your actual video URL or a placeholder
        video_path="../downloaded_videos/_Unleashing_the_power_of_AI_in_transforming_our_digital_world_-_how_artificial_intelligence_is_shaping_the_future_of_technology__.mp4",   # Replace with the correct path to your video file
        video_name="释放人工智能在变革我们数字世界中的力量 —— 人工智能如何塑造技术的未来",             # Replace with your desired video title
        cover_path=None,                     # If you have a cover image, provide the path; otherwise, use None
        description="释放人工智能在变革我们数字世界中的力量 —— 人工智能如何塑造技术的未来",                    # Replace with your video description
        topics=None,                         # Optional: Provide a list of topics
        collection=None,                     # Optional: Provide a collection name
        headless=False                      # Set to True if you want to run the browser in headless mode
    )

    # bili = BiliUploader()
    # await bili.upload_video("https://00.mp4", "../files/test/00.mp4", "00", "20240114", [], "测试")
    # douyin = DouyinUploader()
    # await douyin.upload_video("https://00.mp4", "../files/test/00.mp4", "00", "20240114", [], "测试")


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
