# chromium_utils.py
import platform
import shutil
import os
import signal
import subprocess
from DrissionPage import ChromiumOptions
# import tempfile

def kill_chromium_processes():
    """
    Kills all running Chromium or Chrome processes.
    """
    try:
        # Find all running Chromium or Chrome processes
        result = subprocess.run(['pgrep', '-f', 'chromium'], stdout=subprocess.PIPE)
        pids = result.stdout.decode().splitlines()

        # Also check for Google Chrome processes
        result_chrome = subprocess.run(['pgrep', '-f', 'chrome'], stdout=subprocess.PIPE)
        chrome_pids = result_chrome.stdout.decode().splitlines()

        pids += chrome_pids

        # Kill each process
        for pid in pids:
            os.kill(int(pid), signal.SIGKILL)
        print("Killed all Chromium/Chrome processes.")
    except Exception as e:
        print(f"Error stopping Chromium/Chrome processes: {e}")


def check_chromium_running():
    """
    Checks if any Chromium or Chrome processes are running.
    Returns True if they are running, otherwise False.
    """
    try:
        # Check for running Chromium processes
        result = subprocess.run(['pgrep', '-f', 'chromium'], stdout=subprocess.PIPE)
        pids = result.stdout.decode().splitlines()

        # Check for running Google Chrome processes
        result_chrome = subprocess.run(['pgrep', '-f', 'chrome'], stdout=subprocess.PIPE)
        chrome_pids = result_chrome.stdout.decode().splitlines()

        if pids or chrome_pids:
            print(f"Chromium/Chrome is running with PIDs: {pids + chrome_pids}")
            return True
        return False
    except Exception as e:
        print(f"Error checking Chromium/Chrome processes: {e}")
        return True  # Assume something is running if there's an error


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

    # temp_dir = tempfile.mkdtemp()

    co = ChromiumOptions()
    co.set_browser_path(chromium_path)  # Set the detected path

    if headless:
        co.headless()  # Enable headless mode if specified
    co.new_env()
    co.incognito()  # Set browser to incognito mode
    co.set_argument('--no-first-run')
    co.auto_port(True)  # Automatically assign a free port
    # co.set_argument(f'--user-data-dir={temp_dir}')
    co.set_argument('--disable-cache')  # Disables the cache
    co.set_argument('--disk-cache-size=0')  # Set cache size to zero
    co.set_argument('--media-cache-size=0')  # Disable media cache
    co.set_argument('--no-sandbox')  # Disable sandboxing
    co.set_argument('--disable-application-cache')  # Disable the application cache
    co.set_argument('--aggressive-cache-discard')
    co.set_argument('--disable-site-isolation-trials')  # Disable site isolation for cache clearing
    # co.set_argument('--disable-web-security')  # Disable web security (for testing purposes)
    co.set_argument('--start-maximized')
    co.set_argument('--guest')
    # Clear browser storage (cookies, local storage, etc.)
    co.set_argument('--clear-storage')  # Optional argument to clear storage on every run

    return co
