"""Unit tests for notification services."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import EmailConfig, TelegramConfig
from src.notifications.email import EmailNotifier
from src.notifications.telegram import TelegramNotifier


# ---------------------------------------------------------------------------
# TelegramNotifier
# ---------------------------------------------------------------------------


@pytest.fixture()
def telegram_notifier() -> TelegramNotifier:
    return TelegramNotifier(
        TelegramConfig(
            enabled=True,
            alert_bot_token="alert-tok",
            log_bot_token="log-tok",
            chat_id="12345",
        )
    )


@pytest.fixture()
def telegram_notifier_unconfigured() -> TelegramNotifier:
    return TelegramNotifier(
        TelegramConfig(enabled=True, alert_bot_token="", log_bot_token="", chat_id="")
    )


class TestTelegramNotifier:
    @pytest.mark.asyncio
    async def test_send_alert_success(self, telegram_notifier: TelegramNotifier) -> None:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.notifications.telegram.aiohttp.ClientSession", return_value=mock_session):
            with patch("src.notifications.telegram.aiohttp.TCPConnector"):
                result = await telegram_notifier.send_alert("test alert")

        assert result is True

    @pytest.mark.asyncio
    async def test_send_alert_failure(self, telegram_notifier: TelegramNotifier) -> None:
        mock_response = AsyncMock()
        mock_response.status = 403
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.notifications.telegram.aiohttp.ClientSession", return_value=mock_session):
            with patch("src.notifications.telegram.aiohttp.TCPConnector"):
                result = await telegram_notifier.send_alert("test alert")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_log_success(self, telegram_notifier: TelegramNotifier) -> None:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.notifications.telegram.aiohttp.ClientSession", return_value=mock_session):
            with patch("src.notifications.telegram.aiohttp.TCPConnector"):
                result = await telegram_notifier.send_log("test log")

        assert result is True

    @pytest.mark.asyncio
    async def test_unconfigured_returns_false(
        self, telegram_notifier_unconfigured: TelegramNotifier
    ) -> None:
        result = await telegram_notifier_unconfigured.send_alert("test")
        assert result is False

        result = await telegram_notifier_unconfigured.send_log("test")
        assert result is False


# ---------------------------------------------------------------------------
# EmailNotifier
# ---------------------------------------------------------------------------


@pytest.fixture()
def email_notifier() -> EmailNotifier:
    return EmailNotifier(
        EmailConfig(
            enabled=True,
            alert_email="test@example.com",
            smtp_server="smtp.example.com",
            smtp_port=587,
            sender_email="sender@example.com",
            sender_password="password123",
        )
    )


@pytest.fixture()
def email_notifier_unconfigured() -> EmailNotifier:
    return EmailNotifier(EmailConfig(enabled=True))


class TestEmailNotifier:
    @pytest.mark.asyncio
    async def test_send_alert_success(self, email_notifier: EmailNotifier) -> None:
        mock_smtp = MagicMock()
        with patch("src.notifications.email.smtplib.SMTP", return_value=mock_smtp):
            result = await email_notifier.send_alert("test body", subject="Test")
        assert result is True
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once()
        mock_smtp.send_message.assert_called_once()
        mock_smtp.quit.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_smtp_error(self, email_notifier: EmailNotifier) -> None:
        with patch(
            "src.notifications.email.smtplib.SMTP",
            side_effect=ConnectionError("SMTP down"),
        ):
            result = await email_notifier.send_alert("test body", subject="Test")
        assert result is False

    @pytest.mark.asyncio
    async def test_no_alert_email_returns_false(
        self, email_notifier_unconfigured: EmailNotifier
    ) -> None:
        result = await email_notifier_unconfigured.send_alert("test")
        assert result is False

    @pytest.mark.asyncio
    async def test_no_credentials_returns_false(self) -> None:
        notifier = EmailNotifier(
            EmailConfig(enabled=True, alert_email="test@example.com")
        )
        result = await notifier.send_alert("test")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_log_is_noop(self, email_notifier: EmailNotifier) -> None:
        result = await email_notifier.send_log("test")
        assert result is False
