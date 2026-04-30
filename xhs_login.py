#!/usr/bin/env python3
"""
XHS Login Tool - Persistent Session Login

This tool performs a one-time login to Xiaohongshu (小红书) and saves
cookies that last for months (not the typical 48 hours).

Usage:
    python xhs_login.py           # Perform login
    python xhs_login.py --check   # Check if already logged in
    python xhs_login.py --info    # Show cookie details

How it works:
    1. Opens a browser window
    2. Shows XHS login page with QR code
    3. You scan the QR code with XHS mobile app
    4. Extracts ALL cookies via Chrome DevTools Protocol
    5. Saves cookies for future uploads

The key difference from regular cookie extraction:
    - Uses CDP Network.getAllCookies (like xiaohongshu-mcp does)
    - Captures HttpOnly cookies with actual session tokens
    - Results in sessions lasting months instead of hours
"""

import argparse
import json
import sys
import os
import logging

# Add project root to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from dotenv import load_dotenv

# Load environment
env = os.getenv('ENV', 'production')
dotenv_path = os.path.join(script_dir, f'.env.{env}')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv()

from utils.persistent_login import XhsPersistentLogin


def setup_logging(verbose=False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="XHS Persistent Login Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python xhs_login.py              # Login with QR code scan
  python xhs_login.py --check      # Check if session is valid
  python xhs_login.py --info       # Show cookie details
  python xhs_login.py --timeout 15 # Extend QR scan timeout to 15 mins
        """
    )
    
    parser.add_argument(
        '--check', 
        action='store_true', 
        help="Check login status only (don't open browser)"
    )
    
    parser.add_argument(
        '--info', 
        action='store_true', 
        help="Show detailed cookie information"
    )
    
    parser.add_argument(
        '--timeout', 
        type=int, 
        default=10, 
        help="Login timeout in minutes (default: 10)"
    )
    
    parser.add_argument(
        '--verbose', '-v', 
        action='store_true', 
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        '--force', '-f', 
        action='store_true', 
        help="Force login even if already logged in"
    )
    
    args = parser.parse_args()
    logger = setup_logging(args.verbose)
    
    try:
        login = XhsPersistentLogin(logger=logger)
        
        # Info mode: show cookie details
        if args.info:
            print("\n📊 XHS Cookie Information")
            print("=" * 40)
            info = login.get_cookie_info()
            
            if not info.get('exists'):
                print("❌ No cookies found")
                if 'error' in info:
                    print(f"   Error: {info['error']}")
                return 1
            
            print(f"✅ Cookies exist")
            print(f"   Count: {info.get('count', 'unknown')}")
            print(f"   Saved: {info.get('timestamp', 'unknown')}")
            print(f"   Method: {info.get('extraction_method', 'unknown')}")
            print(f"   HttpOnly: {info.get('http_only_count', 'unknown')}")
            print(f"   Secure: {info.get('secure_count', 'unknown')}")
            return 0
        
        # Check mode: verify login status
        if args.check:
            print("\n🔍 Checking XHS login status...")
            is_valid = login.check_login_status(headless=True)
            
            if is_valid:
                print("✅ Session is VALID - ready for uploads!")
                return 0
            else:
                print("❌ Session is INVALID or EXPIRED")
                print("   Run 'python xhs_login.py' to login")
                return 1
        
        # Login mode
        print("\n🔐 XHS Persistent Login")
        print("=" * 40)
        
        # Check if already logged in (unless forced)
        if not args.force:
            print("Checking existing session...")
            if login.check_login_status(headless=True):
                print("✅ Already logged in! Session is valid.")
                print("   Use --force to login again anyway")
                return 0
        
        # Perform login
        print(f"\n📱 Opening browser for QR code login...")
        print(f"   Timeout: {args.timeout} minutes")
        print(f"   Scan the QR code with your XHS mobile app\n")
        
        success = login.do_login(timeout_minutes=args.timeout)
        
        if success:
            print("\n" + "=" * 40)
            print("✅ LOGIN SUCCESSFUL!")
            print("   Cookies saved with CDP extraction")
            print("   Session should last for months")
            print("=" * 40)
            return 0
        else:
            print("\n" + "=" * 40)
            print("❌ LOGIN FAILED")
            print("   - QR code not scanned in time, or")
            print("   - Browser closed unexpectedly")
            print("=" * 40)
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ Login cancelled by user")
        return 130
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
