import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv

# Determine which .env file to load
env = os.getenv('ENV', 'development')
dotenv_path = f'.env.{env}'

# Load the environment variables from the chosen file
load_dotenv(dotenv_path=dotenv_path)
def test_send_email():
    # Set the subject and body of the email
    subject = "Test Email from YouTube Uploader"
    body = "This is a test email to verify the functionality of the SMTP setup with SSL."

    # Set the recipient email address
    recipient = ["jack_hui@msn.com"]  # Change to a valid email address for testing

    # Call the send_email function
    print("Sending test email...")
    send_email(subject, body, recipient)

def send_email(subject, body, to_emails):
    # Environment variables for email credentials and SMTP settings
    email_user = os.getenv('EMAIL_USER')
    email_password = os.getenv('EMAIL_PASSWORD')
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = 465

    # Set up the email message
    msg = MIMEMultipart()
    msg['From'] = email_user
    msg['To'] = ', '.join(to_emails)
    msg['Subject'] = subject

    # Attach the body of the email to the message
    msg.attach(MIMEText(body, 'plain'))

    # Set up the SMTP server and send the email
    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        #server.set_debuglevel(1)
        server.login(email_user, email_password)  # Log in to the SMTP server
        text = msg.as_string()
        server.sendmail(email_user, to_emails, text)
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    test_send_email()