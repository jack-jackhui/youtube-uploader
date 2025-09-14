#!/usr/bin/env python3
"""
XHS Cookie Expiry Checker

This script checks if XHS cookies are expired and sends email notifications
if they need renewal before the scheduled 9 PM upload run.

Run this script daily at noon (12 PM) to get advance warning about cookie expiry.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Determine which .env file to load
env = os.getenv('ENV', 'development')
dotenv_path = f'.env.{env}'

# Load the environment variables from the chosen file
load_dotenv(dotenv_path=dotenv_path)

# Add parent directory to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

from utils.cookie_manager import XhsCookieManager
import logging

def setup_logging():
    """Setup basic logging for the cookie checker"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('cookie_check.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def main():
    """Main function to check cookie expiry and send notifications"""
    logger = setup_logging()
    logger.info("🕐 Starting XHS cookie expiry check...")
    
    # Get notification email from environment variable
    notification_email = os.getenv('NOTIFICATION_EMAIL', 'info@jackhui.com.au')
    
    try:
        # Initialize cookie manager
        cookie_manager = XhsCookieManager(logger=logger)
        
        # Check if cookies exist
        cookies = cookie_manager.load_cookies()
        if not cookies:
            logger.warning("❌ No cookies found - first time setup required")
            cookie_manager.send_cookie_expiry_notification(float('inf'))
            return
        
        # Check cookie age and notify if expired (48 hours threshold)
        max_age_hours = 48  # Consider cookies expired after 48 hours
        cookie_expired = cookie_manager.check_and_notify_cookie_expiry(max_age_hours)
        
        if cookie_expired:
            logger.warning(f"⚠️ XHS cookies have expired - notification email sent")
        else:
            cookie_age = cookie_manager.get_cookie_age()
            logger.info(f"✅ XHS cookies are valid (age: {cookie_age:.1f} hours)")
            
            # Send warning if cookies are getting old (>36 hours)
            if cookie_age > 36:
                logger.info(f"📧 Sending early warning - cookies are {cookie_age:.1f} hours old")
                subject = "⚠️ XHS Cookies Getting Old - Consider Renewal"
                body = f"""
The XHS (小红书) authentication cookies are getting old and may expire soon.

Cookie Details:
- Current age: {cookie_age:.1f} hours
- Recommended renewal threshold: 48 hours
- Next scheduled run: Tonight at 9 PM

Recommendation:
Consider renewing the cookies proactively to avoid upload interruptions.

Best regards,
YouTube Uploader System
                """
                from email_notifier import send_email
                send_email(subject, body, [notification_email])
                logger.info("📧 Early warning notification sent")
        
        logger.info("✅ Cookie expiry check completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Error during cookie expiry check: {e}")
        
        # Send error notification
        try:
            from email_notifier import send_email
            subject = "❌ XHS Cookie Check Failed"
            body = f"""
The XHS cookie expiry check script encountered an error:

Error: {str(e)}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please check the system and run the upload script manually tonight.

Best regards,
YouTube Uploader System
            """
            send_email(subject, body, [notification_email])
        except:
            pass  # Don't let email errors break the main error handling

if __name__ == "__main__":
    main()