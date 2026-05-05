import argparse
from platforms.bili.uploader import BiliUploader
from platforms.douyin.uploader import DouyinUploader
from platforms.toutiao.uploader import ToutiaoUploader
from platforms.xhs.uploader import XhsUploader
from platforms.xhs.uploader_mcp_final import XhsMcpUploader
from utils.util_sqlite import check
from smb_path_helper import linux_to_windows_path, windows_to_linux_path
import os

# Define a dictionary that maps platform names to their respective uploader classes
UPLOADERS = {
    'bili': BiliUploader,
    'douyin': DouyinUploader,
    'toutiao': ToutiaoUploader,
    'xhs': XhsUploader
}


def _is_windows_path(path):
    return isinstance(path, str) and len(path) >= 3 and path[1:3] in (":\\", ":/")


def _local_video_path(video_path):
    """Return a Linux-local path suitable for the DrissionPage fallback."""
    local_path = windows_to_linux_path(video_path)
    if _is_windows_path(local_path):
        return local_path
    return os.path.abspath(local_path)


def _mcp_video_path(video_path):
    """Return the path to send to the Windows MCP server."""
    if _is_windows_path(video_path):
        return video_path
    return linux_to_windows_path(os.path.abspath(video_path))


async def main(platform_name, video_url, video_path, video_name, cover_path, description, topics, headless=False, use_mcp=False, dry_run=False):
    db_platform_name = 'xhs' if platform_name == 'xhs' else platform_name

    if platform_name not in UPLOADERS:
        print(f"Unsupported platform: {platform_name}")
        return False

    if not dry_run and check(db_platform_name, video_name) != 0:
        print(f"Oops!! the {db_platform_name}:{video_name} have already existed")
        return False

    local_video_path = _local_video_path(video_path)

    # MCP is primary for XHS when enabled; DrissionPage is fallback only.
    # XhsMcpUploader sends visibility=仅自己可见 by default.
    if platform_name == 'xhs' and use_mcp and not dry_run:
        try:
            mcp_path = _mcp_video_path(video_path)
            print(f"[MCP] Initializing MCP uploader for XHS")
            print(f"[MCP] Video path being used: {mcp_path}")
            mcp_uploader = XhsMcpUploader()
            upload_success = await mcp_uploader.upload_video(
                video_url, mcp_path, video_name, cover_path, description, topics, headless=headless
            )
            if upload_success:
                print(f"Upload to {db_platform_name} successful using MCP!")
                return True
            print("[MCP] Upload failed; falling back to DrissionPage uploader")
        except Exception as e:
            print(f"[MCP] Error: {e}; falling back to DrissionPage uploader")

    try:
        uploader_class = UPLOADERS[platform_name]()
        upload_kwargs = {"headless": headless}
        if db_platform_name == 'xhs':
            upload_kwargs["dry_run"] = dry_run
        upload_success = await uploader_class.upload_video(
            video_url, local_video_path, video_name, cover_path, description, topics, **upload_kwargs
        )
        if upload_success:
            if dry_run:
                print(f"Dry-run validation for {db_platform_name} successful using DrissionPage; final Publish was not clicked.")
            else:
                print(f"Upload to {db_platform_name} successful using DrissionPage!")
            return True
        else:
            print(f"Upload to {db_platform_name} failed!")
            return False
    except Exception as e:
        print(f"MAIN:An error occurred: {e}")
        return False


if __name__ == "__main__":
    # Set up the argument parser
    parser = argparse.ArgumentParser(description="Upload videos to various platforms.")
    parser.add_argument('--platforms', required=True,
                        help="The platform to upload the video to (e.g., 'toutiao', 'douyin', 'bili', 'xhs').")
    parser.add_argument('--video_url', required=True, help="Url of the video file.")
    parser.add_argument('--video_path', required=True, help="Path to the video file.")
    parser.add_argument('--video_name', required=True, help="Title of the video.")
    parser.add_argument('--cover_path', required=False, help="Cover of the video.")
    parser.add_argument('--description', required=False, default="", help="Description of the video.")
    parser.add_argument('--headless', required=False, action='store_true',
                        help="Run in headless mode (default: %(default)s)",
                        default=False)
    parser.add_argument('--use_mcp', required=False, action='store_true',
                        help="Use MCP server for Xiaohongshu uploads instead of DrissionPage (default: %(default)s)",
                        default=False)
    parser.add_argument('--dry-run', required=False, action='store_true',
                        help="For supported uploaders, validate UI but do not click final Publish",
                        default=False)

    # Parse the arguments
    args = parser.parse_args()

    # Call the main function with the parsed arguments
    import asyncio

    asyncio.run(
        main(args.platforms, args.video_url, args.video_path, args.video_name, args.cover_path, args.description,
             [], args.headless, args.use_mcp, args.dry_run))
