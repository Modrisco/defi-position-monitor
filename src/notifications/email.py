"""Email notification service."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..config import EmailConfig

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Send notifications via email."""

    def __init__(self, config: EmailConfig) -> None:
        self.alert_email = config.alert_email
        self.smtp_server = config.smtp_server
        self.smtp_port = config.smtp_port
        self.sender_email = config.sender_email
        self.sender_password = config.sender_password

    async def send_alert(self, message: str, subject: str = "") -> bool:
        """Send email alert."""
        if not self.alert_email:
            logger.debug("No alert email configured, skipping email")
            return False

        if not self.sender_email or not self.sender_password:
            logger.warning("Email credentials not configured")
            return False

        msg = MIMEMultipart()
        msg["From"] = self.sender_email
        msg["To"] = self.alert_email
        msg["Subject"] = subject

        msg.attach(MIMEText(message, "plain"))

        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.send_message(msg)
            server.quit()
            logger.info("Alert email sent to %s", self.alert_email)
            return True
        except Exception as e:
            logger.error("Failed to send email: %s", e)
            return False

    async def send_log(self, message: str, silent: bool = True) -> bool:
        """Email notifier does not support log messages — no-op."""
        return False
