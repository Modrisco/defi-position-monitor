"""Email notification service"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from ..config import (
    ALERT_EMAIL,
    SMTP_SERVER,
    SMTP_PORT,
    SENDER_EMAIL,
    SENDER_PASSWORD,
)


class EmailNotifier:
    """Send notifications via email"""

    def __init__(self):
        self.alert_email = ALERT_EMAIL
        self.smtp_server = SMTP_SERVER
        self.smtp_port = SMTP_PORT
        self.sender_email = SENDER_EMAIL
        self.sender_password = SENDER_PASSWORD

    async def send_alert(self, subject: str, body: str) -> bool:
        """Send email alert"""
        if not self.alert_email:
            print("No alert email configured, skipping email")
            return False

        if not self.sender_email or not self.sender_password:
            print("Email credentials not configured")
            return False

        msg = MIMEMultipart()
        msg['From'] = self.sender_email
        msg['To'] = self.alert_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.send_message(msg)
            server.quit()
            print(f"Alert email sent to {self.alert_email}")
            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False
