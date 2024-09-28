# chromium_utils.py
import platform
import shutil
import os
from DrissionPage import ChromiumOptions


def get_chromium_path():
    """
    Returns the path to the Chromium or Chrome executable depending on the OS.
    """
    # For Linux/Ubuntu
    if platform.system() == "Linux":
        # Try to find Chromium or Chrome
        paths = ['chromium-browser', 'google-chrome']
        for path in paths:
            chromium_path = shutil.which(path)
            if chromium_path:
                return chromium_path

    # For macOS
    elif platform.system() == "Darwin":  # Darwin is the system name for macOS
        chromium_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        if os.path.exists(chromium_path):
            return chromium_path

    # For Windows
    elif platform.system() == "Windows":
        possible_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path

    # Return None if not found
    return None


def get_chromium_options(headless=False):
    """
    Configures ChromiumOptions with dynamic path detection for Chromium/Chrome.
    """
    chromium_path = get_chromium_path()
    if not chromium_path:
        raise Exception("Could not find Chromium or Chrome on this system.")

    co = ChromiumOptions()
    co.set_browser_path(chromium_path)  # Set the detected path

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
    co.set_argument('--start-maximized')

    # Clear browser storage (cookies, local storage, etc.)
    co.set_argument('--clear-storage')  # Optional argument to clear storage on every run

    return co
