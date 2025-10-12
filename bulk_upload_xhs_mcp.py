#!/usr/bin/env python3
"""
Bulk video upload script for Xiaohongshu via MCP
Uploads all videos from a specified folder on the MCP server to Xiaohongshu

Usage:
    python bulk_upload_xhs_mcp.py [folder_path]

Example:
    python bulk_upload_xhs_mcp.py "C:\\Users\\jack\\Python-Apps\\youtube-uploader\\downloaded_videos"
"""
import sys
import os
import asyncio
import re
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv('.env.development')

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from platforms.xhs.uploader_mcp_final import XhsMcpUploader


def clean_filename_to_title(filename):
    """
    Convert filename to a clean Chinese title
    Removes file extension and common separators
    Converts underscores to spaces for better readability

    Example: "AIHua_Hua_Bi_Sai__Bi_Bi_Shui_De_Chuang_Yi_Geng_Zha_Lie__.mp4"
    -> "AI画画比赛 比比谁的创意更炸裂"
    """
    # Get just the filename without path
    filename = os.path.basename(filename)

    # Remove file extension
    title = Path(filename).stem

    # Remove multiple underscores and replace with single space
    title = re.sub(r'_+', ' ', title)

    # Remove leading/trailing spaces
    title = title.strip()

    # Limit to 20 characters for XHS (Chinese characters count)
    if len(title) > 20:
        title = title[:20]

    return title


def generate_description(title, filename):
    """
    Generate a description based on the title
    """
    # Create a simple description that includes the title
    description = f"{title}。"

    # Add some generic engaging text
    # You can customize this based on your content
    description += " 你怎么看？欢迎评论分享你的看法！"

    return description


def extract_tags(title):
    """
    Extract relevant tags from the title
    Returns a list of tags
    """
    tags = []

    # Common keywords that make good tags
    keywords = {
        'AI': 'AI',
        '科技': '科技',
        '技术': '技术',
        'ChatGPT': 'ChatGPT',
        '面试': '面试',
        '换脸': '换脸技术',
        '画画': '绘画',
        '比赛': '比赛',
        '创意': '创意',
    }

    # Check for keywords in title
    for keyword, tag in keywords.items():
        if keyword in title:
            tags.append(tag)

    # Always add some default tags if we don't have enough
    if not tags:
        tags = ['科技', '生活', '分享']

    # Limit to 5 tags
    return tags[:5]


async def upload_single_video(uploader, video_path, video_name, description, tags):
    """
    Upload a single video to Xiaohongshu
    Returns True if successful, False otherwise
    """
    try:
        print(f"\n{'='*60}")
        print(f"📹 Uploading: {video_name}")
        print(f"📝 Description: {description}")
        print(f"🏷️  Tags: {', '.join(tags)}")
        print(f"{'='*60}")

        success = await uploader.upload_video(
            video_url="",
            video_path=video_path,
            video_name=video_name,
            cover_path=None,
            description=description,
            topics=tags
        )

        if success:
            print(f"✅ Successfully uploaded: {video_name}")
            return True
        else:
            print(f"❌ Failed to upload: {video_name}")
            return False

    except Exception as e:
        print(f"❌ Error uploading {video_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def bulk_upload_videos(folder_path, file_pattern="*.mp4", delay_seconds=5):
    """
    Bulk upload all videos from a folder to Xiaohongshu

    Args:
        folder_path: Path to the folder containing videos (on MCP server)
        file_pattern: File pattern to match (default: *.mp4)
        delay_seconds: Delay between uploads in seconds (default: 5)
    """
    print("=" * 60)
    print("Bulk Video Upload to Xiaohongshu via MCP")
    print("=" * 60)
    print(f"📁 Folder path (on MCP server): {folder_path}")
    print(f"🔍 File pattern: {file_pattern}")
    print(f"⏱️  Delay between uploads: {delay_seconds} seconds")
    print()

    # Check if MCP is enabled
    mcp_enabled = os.getenv('XHS_MCP_ENABLED', 'false').lower() == 'true'
    if not mcp_enabled:
        print("❌ XHS_MCP_ENABLED is not set to true")
        print("To enable MCP mode, set XHS_MCP_ENABLED=true in .env.development")
        return

    # Initialize the uploader
    try:
        uploader = XhsMcpUploader()
        print("✅ MCP Uploader initialized successfully\n")

        # Check login status
        print("🔐 Checking login status...")
        is_logged_in = await uploader.check_login_status()

        if not is_logged_in:
            print("❌ Not logged in to Xiaohongshu")
            print("Please login through the MCP server interface first")
            return

        print("✅ Logged in to Xiaohongshu\n")

    except Exception as e:
        print(f"❌ Failed to initialize uploader: {e}")
        return

    # Note: We can't actually list files on the remote server from here
    # So we'll need to get the file list from the user or via MCP tool
    # For now, we'll create a sample list that the user should modify

    print("=" * 60)
    print("📋 Video Upload Queue")
    print("=" * 60)
    print("\nNote: Please provide the list of video files to upload.")
    print("Since the files are on the remote MCP server, you need to:")
    print("1. List the files on the server")
    print("2. Update this script with the file list")
    print("3. Or use a remote file listing tool")
    print()

    # Example video list (user should replace this with actual files)
    # You can get this list by running: dir /b "C:\Users\jack\Python-Apps\youtube-uploader\downloaded_videos\*.mp4"
    # on the Windows server
    video_files = [
        # Add your video files here, example:
        # r"C:\Users\jack\Python-Apps\youtube-uploader\downloaded_videos\video1.mp4",
        # r"C:\Users\jack\Python-Apps\youtube-uploader\downloaded_videos\video2.mp4",
    ]

    if not video_files:
        print("⚠️  No video files specified in the video_files list.")
        print("Please edit this script and add your video file paths to the video_files list.")
        print("\nExample:")
        print('video_files = [')
        print('    r"C:\\Users\\jack\\Python-Apps\\youtube-uploader\\downloaded_videos\\video1.mp4",')
        print('    r"C:\\Users\\jack\\Python-Apps\\youtube-uploader\\downloaded_videos\\video2.mp4",')
        print(']')
        return

    print(f"Found {len(video_files)} videos to upload\n")

    # Upload statistics
    total = len(video_files)
    successful = 0
    failed = 0

    # Upload each video
    for idx, video_path in enumerate(video_files, 1):
        print(f"\n{'#'*60}")
        print(f"Processing video {idx}/{total}")
        print(f"{'#'*60}")

        try:
            # Extract filename
            filename = os.path.basename(video_path)

            # Generate title and description
            video_name = clean_filename_to_title(filename)
            description = generate_description(video_name, filename)
            tags = extract_tags(video_name)

            # Upload the video
            success = await upload_single_video(
                uploader,
                video_path,
                video_name,
                description,
                tags
            )

            if success:
                successful += 1
            else:
                failed += 1

            # Wait before next upload (avoid rate limiting)
            if idx < total:
                print(f"\n⏳ Waiting {delay_seconds} seconds before next upload...")
                await asyncio.sleep(delay_seconds)

        except Exception as e:
            print(f"❌ Error processing {video_path}: {e}")
            failed += 1
            continue

    # Print summary
    print("\n" + "=" * 60)
    print("📊 Upload Summary")
    print("=" * 60)
    print(f"Total videos: {total}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"Success rate: {(successful/total*100) if total > 0 else 0:.1f}%")
    print("=" * 60)


async def bulk_upload_with_file_list(video_files, delay_seconds=5):
    """
    Bulk upload videos from a provided list of file paths

    Args:
        video_files: List of full video file paths on the MCP server
        delay_seconds: Delay between uploads in seconds (default: 5)
    """
    print("=" * 60)
    print("Bulk Video Upload to Xiaohongshu via MCP")
    print("=" * 60)
    print(f"📋 Videos to upload: {len(video_files)}")
    print(f"⏱️  Delay between uploads: {delay_seconds} seconds")
    print()

    # Check if MCP is enabled
    mcp_enabled = os.getenv('XHS_MCP_ENABLED', 'false').lower() == 'true'
    if not mcp_enabled:
        print("❌ XHS_MCP_ENABLED is not set to true")
        print("To enable MCP mode, set XHS_MCP_ENABLED=true in .env.development")
        return []

    # Initialize the uploader
    try:
        uploader = XhsMcpUploader()
        print("✅ MCP Uploader initialized successfully\n")

        # Check login status
        print("🔐 Checking login status...")
        is_logged_in = await uploader.check_login_status()

        if not is_logged_in:
            print("❌ Not logged in to Xiaohongshu")
            print("Please login through the MCP server interface first")
            return []

        print("✅ Logged in to Xiaohongshu\n")

    except Exception as e:
        print(f"❌ Failed to initialize uploader: {e}")
        return []

    # Upload statistics
    total = len(video_files)
    successful_uploads = []
    failed_uploads = []

    # Upload each video
    for idx, video_path in enumerate(video_files, 1):
        print(f"\n{'#'*60}")
        print(f"Processing video {idx}/{total}")
        print(f"{'#'*60}")

        try:
            # Extract filename
            filename = os.path.basename(video_path)

            # Generate title and description
            video_name = clean_filename_to_title(filename)
            description = generate_description(video_name, filename)
            tags = extract_tags(video_name)

            # Upload the video
            success = await upload_single_video(
                uploader,
                video_path,
                video_name,
                description,
                tags
            )

            if success:
                successful_uploads.append(video_path)
            else:
                failed_uploads.append(video_path)

            # Wait before next upload (avoid rate limiting)
            if idx < total:
                print(f"\n⏳ Waiting {delay_seconds} seconds before next upload...")
                await asyncio.sleep(delay_seconds)

        except Exception as e:
            print(f"❌ Error processing {video_path}: {e}")
            failed_uploads.append(video_path)
            continue

    # Print summary
    print("\n" + "=" * 60)
    print("📊 Upload Summary")
    print("=" * 60)
    print(f"Total videos: {total}")
    print(f"✅ Successful: {len(successful_uploads)}")
    print(f"❌ Failed: {len(failed_uploads)}")
    print(f"Success rate: {(len(successful_uploads)/total*100) if total > 0 else 0:.1f}%")

    if failed_uploads:
        print("\n❌ Failed uploads:")
        for video in failed_uploads:
            print(f"   - {os.path.basename(video)}")

    print("=" * 60)

    return successful_uploads


def main():
    """Main function"""

    # Example usage with a list of video files
    # Replace these with your actual video file paths on the MCP server
    video_files = [
        r"C:\Users\jack\Python-Apps\youtube-uploader\downloaded_videos\pending_upload\AIBao_Huo_Bei_Hou__Ni_Zhen_De_Liao_Jie_Ren_Gong_Zhi_Neng_Ma__.mp4",
        r"C:\Users\jack\Python-Apps\youtube-uploader\downloaded_videos\pending_upload\AIHuan_Lian_Ji_Zhu_An_Quan_Ma__Qin_Ce_Jie_Mi__.mp4",
        r"C:\Users\jack\Python-Apps\youtube-uploader\downloaded_videos\pending_upload\AIHua_Hua_Bi_Sai__Bi_Bi_Shui_De_Chuang_Yi_Geng_Zha_Lie__.mp4",
        r"C:\Users\jack\Python-Apps\youtube-uploader\downloaded_videos\pending_upload\ChatGPTBao_Huo_Bei_Hou_De_Mi_Mi_Ni_Zhi_Dao_Ma__.mp4",
    ]

    # If command line argument provided, use it as folder path
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
        print(f"Folder path provided: {folder_path}")
        print("Note: Automatic file listing from remote server is not yet implemented.")
        print("Please edit the script and add video file paths manually to video_files list.")
        return

    # Run the bulk upload
    print("Starting bulk video upload...")
    print(f"Videos in queue: {len(video_files)}")
    print()

    if not video_files:
        print("⚠️  No video files specified!")
        print("\nTo use this script:")
        print("1. Edit this file (bulk_upload_xhs_mcp.py)")
        print("2. Add your video file paths to the video_files list")
        print("3. Run the script again")
        print("\nExample:")
        print('video_files = [')
        print('    r"C:\\Users\\jack\\Python-Apps\\youtube-uploader\\downloaded_videos\\video1.mp4",')
        print('    r"C:\\Users\\jack\\Python-Apps\\youtube-uploader\\downloaded_videos\\video2.mp4",')
        print(']')
        return

    # Run the bulk upload with the file list
    successful = asyncio.run(bulk_upload_with_file_list(video_files, delay_seconds=5))

    print(f"\n✅ Bulk upload completed! {len(successful)} videos uploaded successfully.")


if __name__ == "__main__":
    main()
