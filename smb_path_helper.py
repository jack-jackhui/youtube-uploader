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
    linux_path = os.path.abspath(linux_path)
    if linux_path.startswith(SMB_MOUNT_PATH + os.sep) or linux_path == SMB_MOUNT_PATH:
        # Preserve any relative subdirectories below the SMB mount.
        relative_path = os.path.relpath(linux_path, SMB_MOUNT_PATH)
        return WINDOWS_BASE_PATH + "\\" + relative_path.replace(os.sep, "\\")
    return linux_path


def windows_to_linux_path(windows_path):
    """Convert the configured Windows MCP video path back to the Linux SMB mount path."""
    if not isinstance(windows_path, str):
        return windows_path

    normalized_input = windows_path.replace("/", "\\")
    normalized_base = WINDOWS_BASE_PATH.replace("/", "\\").rstrip("\\")

    if normalized_input.lower() == normalized_base.lower():
        return SMB_MOUNT_PATH

    prefix = normalized_base + "\\"
    if normalized_input.lower().startswith(prefix.lower()):
        relative_path = normalized_input[len(prefix):].replace("\\", os.sep)
        return os.path.join(SMB_MOUNT_PATH, relative_path)

    return windows_path

def is_smb_mounted():
    """Check if SMB share is mounted."""
    return os.path.exists(SMB_MOUNT_PATH) and os.path.ismount(SMB_MOUNT_PATH)
