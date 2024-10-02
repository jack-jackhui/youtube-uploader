# chromium_utils.py
import platform
import shutil
import os
import signal
import subprocess
from DrissionPage import ChromiumOptions
import psutil
# import tempfile

def kill_chromium_processes():
    """
    Kills all running Chromium or Chrome processes on Linux, macOS, and Windows.
    """
    try:
        # Define process names to look for
        process_names = ['chromium', 'chrome', 'chromedriver', 'chrome.exe', 'chromium.exe']

        for proc in psutil.process_iter(['pid', 'name']):
            try:
                # Check if process name matches any in our list
                if proc.info['name'].lower() in process_names:
                    proc.kill()
                    print(f"Killed process {proc.info['name']} (PID: {proc.pid})")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        print(f"Error stopping Chromium/Chrome processes: {e}")


def check_chromium_running():
    """
    Checks if any Chromium or Chrome processes are running.
    Returns True if they are running, otherwise False.
    """
    try:
        # Define process names to look for
        process_names = ['chromium', 'chrome', 'chromedriver', 'chrome.exe', 'chromium.exe']
        running = False

        for proc in psutil.process_iter(['name']):
            if proc.info['name'].lower() in process_names:
                print(f"Chromium/Chrome is running with PID: {proc.pid}")
                running = True

        return running
    except Exception as e:
        print(f"Error checking Chromium/Chrome processes: {e}")
        return True  # Assume something is running if there's an error


def check_chromium_running():
    """
    Checks if any Chromium or Chrome processes are running.
    Returns True if they are running, otherwise False.
    """
    try:
        # Define process names to look for
        process_names = ['chromium', 'chrome', 'chromedriver', 'chrome.exe', 'chromium.exe']
        running = False

        for proc in psutil.process_iter(['name']):
            if proc.info['name'].lower() in process_names:
                print(f"Chromium/Chrome is running with PID: {proc.pid}")
                running = True

        return running
    except Exception as e:
        print(f"Error checking Chromium/Chrome processes: {e}")
        return True  # Assume something is running if there's an error


def get_chromium_path():
    """
    Returns the path to the Chromium or Chrome executable depending on the OS.
    """
    # Define the custom Chromium path based on your installation script
    custom_chromium_path = '/home/ubuntu/chromium/chromium-latest-linux/latest/chrome'  # Update this path as needed

    system_name = platform.system()

    if system_name == "Linux":
        # Check if custom Chromium path exists
        if os.path.exists(custom_chromium_path):
            return custom_chromium_path
        else:
            # Try to find Chromium or Chrome in standard locations
            paths = ['chromium-browser', 'google-chrome', 'chromium', '/snap/bin/chromium']
            for path in paths:
                chromium_path = shutil.which(path)
                if chromium_path:
                    return chromium_path
            # If Chromium is not found, raise an exception
            raise Exception("Chromium executable not found. Please ensure Chromium is installed.")

    elif system_name == "Darwin":  # macOS
        chromium_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        if os.path.exists(chromium_path):
            return chromium_path
        else:
            # Try to find Chromium in standard locations
            paths = ['chromium-browser', 'google-chrome']
            for path in paths:
                chromium_path = shutil.which(path)
                if chromium_path:
                    return chromium_path
            raise Exception("Chromium executable not found. Please ensure Chromium is installed.")

    elif system_name == "Windows":
        # Common installation paths for Chrome on Windows
        possible_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        # Use shutil.which to find chrome.exe in PATH
        chromium_path = shutil.which('chrome.exe')
        if chromium_path:
            return chromium_path
        raise Exception("Chromium executable not found. Please ensure Chrome is installed.")

    else:
        raise Exception(f"Unsupported operating system: {system_name}")
def get_chromium_options(headless=False):
    """
    Configures ChromiumOptions with dynamic path detection for Chromium/Chrome.
    """
    chromium_path = get_chromium_path()
    if not chromium_path:
        raise Exception("Could not find Chromium or Chrome on this system.")

    # temp_dir = tempfile.mkdtemp()

    co = ChromiumOptions()
    co.set_browser_path(chromium_path)  # Set the detected path

    if headless:
        co.headless()  # Enable headless mode if specified
        co.set_argument('--headless=new')
    co.new_env()
    co.incognito()  # Set browser to incognito mode
    co.set_argument('--no-first-run')
    co.auto_port(True)  # Automatically assign a free port
    # co.set_argument(f'--user-data-dir={temp_dir}')
    # Set custom user agent
    user_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/115.0.0.0 Safari/537.36')
    co.set_argument(f'--user-agent={user_agent}')

    # Other arguments to prevent detection
    co.set_argument('--disable-blink-features=AutomationControlled')
    co.set_argument('--disable-gpu')
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--disable-setuid-sandbox')
    co.set_argument('--disable-cache')  # Disables the cache
    co.set_argument('--disk-cache-size=0')  # Set cache size to zero
    co.set_argument('--media-cache-size=0')  # Disable media cache
    co.set_argument('--disable-application-cache')  # Disable the application cache
    co.set_argument('--aggressive-cache-discard')
    co.set_argument('--disable-site-isolation-trials')  # Disable site isolation for cache clearing
    # co.set_argument('--disable-web-security')  # Disable web security (for testing purposes)
    co.set_argument('--window-size=1920,1080')
    # co.set_argument('--guest')
    # Clear browser storage (cookies, local storage, etc.)
    co.set_argument('--clear-storage')  # Optional argument to clear storage on every run

    return co
