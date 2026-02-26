"""
Helper to convert SMB mount paths to Windows paths for MCP server.
"""
import os

# SMB mount configuration
SMB_MOUNT_PATH = "/mnt/windows_videos"
WINDOWS_BASE_PATH = r"C:\Users\jack\Python_Apps\youtube-uploader\downloaded_videos"

def get_download_path():
    """Returns the SMB mount path for downloading videos."""
    if os.path.exists(SMB_MOUNT_PATH) and os.path.ismount(SMB_MOUNT_PATH):
        return SMB_MOUNT_PATH
    else:
        # Fallback to local path
        return os.path.abspath("downloaded_videos")

def linux_to_windows_path(linux_path):
    """Convert Linux SMB mount path to Windows path for MCP server."""
    if linux_path.startswith(SMB_MOUNT_PATH):
        # Extract filename from linux path
        filename = os.path.basename(linux_path)
        # Return Windows path with proper backslashes
        return WINDOWS_BASE_PATH + "\\" + filename
    return linux_path

def is_smb_mounted():
    """Check if SMB share is mounted."""
    return os.path.exists(SMB_MOUNT_PATH) and os.path.ismount(SMB_MOUNT_PATH)
